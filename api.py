from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
import sqlite3
import os
import io
import csv
import logging
import time
from contextlib import closing
from enum import Enum
from typing import Optional
import json
import asyncio

if __package__:
    from .memory_metrics import RequestMetrics, rss_mb
else:
    from memory_metrics import RequestMetrics, rss_mb

logger = logging.getLogger("uvicorn.error")
DB_FILE = os.environ.get("DB_FILE", "/data/8cube.db")
GENE_EXPR_DB_FILE = os.environ.get("GENE_EXPR_DB_FILE", "/data/mean_var_DB.db")


def connect(path):
    # Read-only prevents accidental database creation/writes. Bound SQLite caches
    # and spill JOIN/ORDER BY intermediates to disk rather than process RAM.
    conn = sqlite3.connect("file:" + os.path.abspath(path) + "?mode=ro", uri=True,
                           check_same_thread=False, cached_statements=16)
    conn.execute("PRAGMA cache_size=-2048")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute("PRAGMA mmap_size=0")
    return conn


def get_db_connection():
    return connect(DB_FILE)


def get_gene_expr_db_connection():
    return connect(GENE_EXPR_DB_FILE)


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def normalize_gene_inputs(genes):
    return [g.upper() if g.upper().startswith("ENS") else g.capitalize() for g in genes]


def get_analysis_options():
    # One scan for both small dropdown lists, never retain table_1 rows.
    try:
        with closing(get_db_connection()) as conn:
            pairs = conn.execute("SELECT DISTINCT Analysis_level, Analysis_type FROM table_1")
            levels, types = set(), set()
            for level, kind in pairs:
                if level is not None:
                    levels.add(level)
                if kind is not None:
                    types.add(kind)
            return sorted(levels), sorted(types)
    except sqlite3.Error as exc:
        logger.warning("Could not load analysis options: %s", exc)
        return [], []


def get_columns_from_table(table_name):
    with closing(get_db_connection()) as conn:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({quote_identifier(table_name)})")
                if r[1] not in ("gene_name", "ensembl_id")]


analysis_levels, analysis_types = get_analysis_options()
AnalysisLevel = Enum("AnalysisLevel", {v: v for v in analysis_levels})
AnalysisType = Enum("AnalysisType", {v: v for v in analysis_types})
app = FastAPI(
    title="8cubeDB API",
    description="API for querying gene specificity from the Rebboah et al. (2025) 8cube founder dataset.",
    version="1.0.0"
)
app.add_middleware(RequestMetrics)


@app.on_event("startup")
async def log_startup_memory():
    logger.info("memory startup rss_mb=%.1f", rss_mb())


def gene_filename(genes, suffix):
    if not genes:
        return "all_" + suffix + ".csv"
    names = normalize_gene_inputs(genes)
    prefix = "_".join(g.replace(" ", "_") for g in names) if len(names) <= 3 else str(len(names))
    return prefix + "_" + suffix + ".csv"


def gene_filter(genes):
    if not genes:
        return "", []
    genes = normalize_gene_inputs(genes)
    slots = ','.join('?' for _ in genes)
    return (f" WHERE gene_name COLLATE NOCASE IN ({slots}) "
            f"OR ensembl_id COLLATE NOCASE IN ({slots})", genes + genes)


class ClosingCSVResponse(StreamingResponse):
    """Close the cursor connection even if the client disconnects mid-stream."""
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.db_connection.close()


def csv_query(connection_factory, query, params, filename):
    started = time.monotonic()
    conn = connection_factory()
    try:
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        cursor = conn.execute(query, params)
        logger.info("query execute file=%s duration_s=%.3f columns=%d rss_mb=%.1f",
                    filename, time.monotonic()-started, len(cursor.description), rss_mb())
    except sqlite3.Error as exc:
        conn.close()
        logger.warning("query failed duration_s=%.3f rss_mb=%.1f error=%s",
                       time.monotonic()-started, rss_mb(), exc)
        raise HTTPException(404 if "no such table" in str(exc) else 500,
                            "Unable to execute database query.") from exc

    def stream():
        rows = size = 0
        completed = False
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        try:
            writer.writerow([c[0] for c in cursor.description])
            yield buffer.getvalue()
            buffer.seek(0); buffer.truncate(0)
            while True:
                batch = cursor.fetchmany(16)
                if not batch:
                    break
                writer.writerows(batch)
                chunk = buffer.getvalue().encode("utf-8")
                rows += len(batch)
                size += len(chunk)
                yield chunk
                buffer.seek(0); buffer.truncate(0)
            completed = True
        except Exception:
            logger.exception("CSV stream failed file=%s rows=%d", filename, rows)
            raise
        finally:
            conn.close()
            logger.info("query finished file=%s completed=%s duration_s=%.3f rows=%d csv_bytes=%d rss_mb=%.1f",
                        filename, completed, time.monotonic()-started, rows, size, rss_mb())
    response = ClosingCSVResponse(stream(), media_type="text/csv", headers=headers)
    response.db_connection = conn
    return response


@app.get("/config")
def get_analysis_config(
    analysis_level: Optional[AnalysisLevel] = Query(None, description="Select an analysis level"),
    analysis_type: Optional[AnalysisType] = Query(None, description="Select an analysis type")
):
    """
    Returns block label options for a given analysis_level and analysis_type,
    or the full nested configuration if no parameters are provided.
    """
    excluded_cols = {"gene_name", "ensembl_id", "Analysis_level", "Analysis_type"}

    if analysis_level and analysis_type:
        table_name = f"{analysis_level.value}_{analysis_type.value}"
        block_labels = get_columns_from_table(table_name)
        filtered_labels = [c for c in block_labels if c not in excluded_cols]

        if not filtered_labels:
            raise HTTPException(
                status_code=404,
                detail=f"No valid block labels found for {table_name}"
            )

        return {
            "analysis_level": analysis_level.value,
            "analysis_type": analysis_type.value,
            "block_labels": filtered_labels
        }

    config = {}
    for level in analysis_levels:
        config[level] = {}
        for a_type in analysis_types:
            table_name = f"{level}_{a_type}"
            block_labels = get_columns_from_table(table_name)
            filtered_labels = [c for c in block_labels if c not in excluded_cols]
            if filtered_labels:
                config[level][a_type] = filtered_labels

    if not config:
        raise HTTPException(status_code=404, detail="No valid analysis configuration found in database.")

    return {
        "description": "Dictionary of all available analysis levels, types, and block labels.",
        "analysis_config": config
    }

@app.get("/specificity")
def extract_all_specificity_per_gene(gene_list: list[str] = Query(...)):
    where, params = gene_filter(gene_list)
    return csv_query(get_db_connection, "SELECT * FROM table_1" + where,
                     params, gene_filename(gene_list, "specificity"))


def block_query(factory, level, kind, genes, suffix):
    table = quote_identifier(f"{level.value}_{kind.value}")
    where, params = gene_filter(genes)
    return csv_query(factory, f"SELECT * FROM {table}" + where,
                     params, gene_filename(genes, f"{level.value}_{kind.value}_{suffix}"))


@app.get("/psi_block")
def extract_psi_block(analysis_level: AnalysisLevel, analysis_type: AnalysisType,
                      gene_list: Optional[list[str]] = Query(None, description="List of gene names or Ensembl IDs to filter (optional)")):
    return block_query(get_db_connection, analysis_level, analysis_type, gene_list, "psi_block")


@app.get("/gene_expression")
def extract_gene_expression(analysis_level: AnalysisLevel, analysis_type: AnalysisType,
                            gene_list: Optional[list[str]] = Query(None, description="List of gene names or Ensembl IDs")):
    return block_query(get_gene_expr_db_connection, analysis_level, analysis_type,
                       gene_list, "gene_expr")


def specificity_query(level, kind, psi, zeta, high):
    comparison, direction = (">", "DESC") if high else ("<", "ASC")
    query = ("SELECT * FROM table_1 WHERE Analysis_level = ? AND Analysis_type = ? "
             f"AND Psi_mean > ? AND Zeta_mean {comparison} ? "
             f"ORDER BY Psi_mean DESC, Zeta_mean {direction}")
    return csv_query(get_db_connection, query, [level.value, kind.value, psi, zeta],
                     "highly_specific.csv" if high else "non_specific.csv")


@app.get("/highly_specific")
def extract_highly_specific(analysis_level: AnalysisLevel, analysis_type: AnalysisType,
                            psi_cutoff: float = 0.5, zeta_cutoff: float = 0.5):
    return specificity_query(analysis_level, analysis_type, psi_cutoff, zeta_cutoff, True)


@app.get("/non_specific")
def extract_non_specific(analysis_level: AnalysisLevel, analysis_type: AnalysisType,
                         psi_cutoff: float = 0.5, zeta_cutoff: float = 0.5):
    return specificity_query(analysis_level, analysis_type, psi_cutoff, zeta_cutoff, False)


@app.get("/marker")
def extract_marker(analysis_level: AnalysisLevel, analysis_type: AnalysisType,
                   block_label: str, psi_cutoff: float = 0.5, psi_block_cutoff: float = 0.5):
    table_name = f"{analysis_level.value}_{analysis_type.value}"
    block = quote_identifier(block_label)
    # Keep the original gene_name join (including duplicate matches) and cutoffs.
    query = (f"SELECT T1.*, T2.{block} FROM table_1 AS T1 "
             f"INNER JOIN {quote_identifier(table_name)} AS T2 ON T1.gene_name = T2.gene_name "
             f"WHERE T1.Analysis_level = ? AND T1.Analysis_type = ? "
             f"AND T1.Psi_mean > ? AND T2.{block} > ? "
             f"ORDER BY T1.Psi_mean DESC, T2.{block} DESC")
    return csv_query(get_db_connection, query,
                     [analysis_level.value, analysis_type.value, psi_cutoff, psi_block_cutoff],
                     "marker_genes.csv")


# ---------------------------------------------------------------------
# Root endpoint
@app.get("/")
def home():
    return {
        "message": "Welcome to the 8cubeDB API!",
        "note": "All endpoints stream CSV downloads.",
        "analysis_levels": analysis_levels,
        "analysis_types": analysis_types,
        "endpoints": {
            "/config": "View all analysis levels, types, and available block labels as json",
            "/specificity": "Download gene specificity for a list of genes as CSV",
            "/psi_block": "Download psi block table as CSV",
            "/highly_specific": "Download highly specific genes as CSV",
            "/non_specific": "Download housekeeping genes as CSV",
            "/marker": "Download marker genes as CSV",
            "/gene_expression": "Download gene expression mean and variance as CSV",
            "/mcp/sse": "MCP Server-Sent Events endpoint",
            "/mcp/messages": "MCP messages endpoint",
            "/mcp/health": "MCP health check"
        }
    }

# ============================================================================
# MCP SERVER INTEGRATION - MANUAL IMPLEMENTATION
# ============================================================================

# Load MCP only when used; REST startup does not need its dependency graph.
def load_mcp_module():
    from importlib import import_module
    return import_module(".mcp_server", __package__) if __package__ else import_module("mcp_server")


def load_mcp_server():
    return load_mcp_module().server

@app.get("/mcp/sse")
async def mcp_sse_endpoint(request: Request):
    """
    SSE endpoint for MCP protocol.
    Keeps connection open and sends events.
    """
    async def event_generator():
        # Send endpoint notification
        yield {
            "event": "endpoint",
            "data": json.dumps("/mcp/messages")
        }
        
        # Keep connection alive with periodic pings
        try:
            while True:
                await asyncio.sleep(15)
                # Send keepalive ping
                yield {"event": "ping", "data": ""}
        except asyncio.CancelledError:
            # Client disconnected
            pass
    
    from sse_starlette.sse import EventSourceResponse
    return EventSourceResponse(event_generator())


@app.post("/mcp/messages")
async def mcp_messages_endpoint(request: Request):
    """
    Handle MCP JSON-RPC messages.
    Supports tools/list and tools/call methods.
    """
    try:
        body = await request.json()
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        }
    
    mcp_server = load_mcp_server()
    method = body.get("method")
    msg_id = body.get("id")
    
    # Handle initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "8cubeDB-Explorer",
                    "version": "1.0.0"
                }
            }
        }
    
    # Handle tools/list
    if method == "tools/list":
        try:
            # The server has a _list_tools_handler attribute that's the decorated function
            # We need to call it directly (it's async)
            if hasattr(mcp_server, '_list_tools_handler'):
                tools_list = await mcp_server._list_tools_handler()
            else:
                # Fallback: manually import the list_tools function from mcp_server module
                tools_list = await load_mcp_module().list_tools()
            
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools_list
                    ]
                }
            }
        except Exception as e:
            import traceback
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error listing tools: {str(e)}\n{traceback.format_exc()}"
                }
            }
    
    # Handle tools/call
    if method == "tools/call":
        try:
            params = body.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32602,
                        "message": "Missing tool name in params"
                    }
                }
            
            # Call the tool handler
            if hasattr(mcp_server, '_call_tool_handler'):
                result = await mcp_server._call_tool_handler(tool_name, arguments)
            else:
                # Fallback: manually import the call_tool function
                result = await load_mcp_module().call_tool(tool_name, arguments)
            
            # Convert TextContent to response format
            content_list = []
            for item in result:
                content_list.append({
                    "type": "text",
                    "text": item.text
                })
            
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": content_list
                }
            }
            
        except ValueError as e:
            # Tool not found
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": str(e)
                }
            }
        except Exception as e:
            # Other error
            import traceback
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": f"Error calling tool: {str(e)}\n{traceback.format_exc()}"
                }
            }
    
    # Handle notifications (no response needed)
    if "id" not in body:
        return {"status": "ok"}
    
    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        }
    }


@app.get("/mcp/health")
async def mcp_health():
    """Health check for MCP server"""
    return {
        "status": "ok",
        "server": "8cubeDB-Explorer",
        "version": "1.0.0",
        "endpoints": {
            "sse": "/mcp/sse",
            "messages": "/mcp/messages"
        }
    }