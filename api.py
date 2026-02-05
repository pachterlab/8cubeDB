from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse        
import pandas as pd
import sqlite3
import os
import io
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------
# Path to your SQLite database
DB_FILE = "/data/8cube.db"

# Helper function to establish connection
def get_db_connection():
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database file {DB_FILE} not found in container.")
    return sqlite3.connect(DB_FILE)

# ---------------------------------------------------------------------
# Path to the mean/variance SQLite database
GENE_EXPR_DB_FILE = "/data/mean_var_DB.db"

def get_gene_expr_db_connection():
    if not os.path.exists(GENE_EXPR_DB_FILE):
        raise FileNotFoundError(f"Database file {GENE_EXPR_DB_FILE} not found in container.")
    return sqlite3.connect(GENE_EXPR_DB_FILE)

# ---------------------------------------------------------------------
# Helper: Normalize gene and Ensembl IDs
def normalize_gene_inputs(gene_list: list[str]) -> list[str]:
    """
    Normalize gene and Ensembl ID inputs for case-insensitive matching.
    - Ensembl IDs → uppercase
    - Gene names → Title Case (first letter capitalized)
    """
    normalized = []
    for g in gene_list:
        if g.upper().startswith("ENS"):
            normalized.append(g.upper())
        else:
            normalized.append(g.capitalize())
    return normalized

# ---------------------------------------------------------------------
# Helper: Get unique values from a column
def get_unique_values(column_name: str):
    """Get unique values from table_1 for the given column."""
    try:
        conn = get_db_connection()
        query = f"SELECT DISTINCT {column_name} FROM table_1 WHERE {column_name} IS NOT NULL;"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return sorted(df[column_name].dropna().unique().tolist())
    except Exception as e:
        print(f"Warning: Could not load unique values for {column_name}: {e}")
        return []

# Helper: Get column names from a table
def get_columns_from_table(table_name: str):
    """Fetch column names from a given table in the DB."""
    try:
        conn = get_db_connection()
        cursor = conn.execute(f"PRAGMA table_info('{table_name}')")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        # Exclude non-block columns
        return [c for c in columns if c not in ("gene_name", "ensembl_id")]
    except Exception as e:
        print(f"Warning: Could not fetch columns for {table_name}: {e}")
        return []

# ---------------------------------------------------------------------
# Dynamically build Enums for dropdowns
analysis_levels = get_unique_values("Analysis_level")
analysis_types = get_unique_values("Analysis_type")

AnalysisLevel = Enum("AnalysisLevel", {v: v for v in analysis_levels})
AnalysisType = Enum("AnalysisType", {v: v for v in analysis_types})

# ---------------------------------------------------------------------
# Initialize FastAPI app
app = FastAPI(
    title="8cubeDB API",
    description="API for querying gene specificity from the Rebboah et al. (2025) 8cube founder dataset.",
    version="1.0.0"
)

# ---------------------------------------------------------------------
# Helper to stream CSV from DataFrame
def df_to_csv_stream(df: pd.DataFrame, filename: str = "data.csv"):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# Endpoint 1: Specificity
@app.get("/specificity")
def extract_all_specificity_per_gene(
    gene_list: list[str] = Query(..., description="List of gene names or Ensembl IDs")
):
    """Extract rows where 'gene_name' OR 'ensembl_id' is in gene_list."""
    conn = get_db_connection()

    # Normalize input and build query (case-insensitive)
    gene_list = normalize_gene_inputs(gene_list)
    gene_str = ', '.join(f"'{g}'" for g in gene_list)
    query = f"""
        SELECT *
        FROM table_1
        WHERE gene_name COLLATE NOCASE IN ({gene_str})
           OR ensembl_id COLLATE NOCASE IN ({gene_str})
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if len(gene_list) <= 3:
        safe_names = [g.replace(" ", "_") for g in gene_list]
        filename = "_".join(safe_names) + "_specificity.csv"
    else:
        filename = f"{len(gene_list)}_specificity.csv"

    return df_to_csv_stream(df, filename)

# ---------------------------------------------------------------------
# Endpoint 2: psi_block
@app.get("/psi_block")
def extract_psi_block(
    analysis_level: AnalysisLevel,
    analysis_type: AnalysisType,
    gene_list: Optional[list[str]] = Query(None, description="List of gene names or Ensembl IDs to filter (optional)")
):
    """Reads a psi_block table from the DB based on analysis type and level."""
    conn = get_db_connection()
    table_name = f"{analysis_level.value}_{analysis_type.value}"
    base_query = f"SELECT * FROM '{table_name}'"

    if gene_list:
        gene_list = normalize_gene_inputs(gene_list)
        gene_str = ', '.join(f"'{g}'" for g in gene_list)
        query = f"{base_query} WHERE gene_name COLLATE NOCASE IN ({gene_str}) OR ensembl_id COLLATE NOCASE IN ({gene_str})"
    else:
        query = base_query

    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found. {e}")
    finally:
        conn.close()

    if gene_list:
        if len(gene_list) <= 3:
            safe_names = [g.replace(" ", "_") for g in gene_list]
            filename = "_".join(safe_names) + f"_{table_name}_psi_block.csv"
        else:
            filename = f"{len(gene_list)}_{table_name}_psi_block.csv"
    else:
        filename = f"all_{table_name}_psi_block.csv"

    return df_to_csv_stream(df, filename)

# ---------------------------------------------------------------------
# Endpoint 3: Highly specific genes
@app.get("/highly_specific")
def extract_highly_specific(
    analysis_level: AnalysisLevel,
    analysis_type: AnalysisType,
    psi_cutoff: float = 0.5,
    zeta_cutoff: float = 0.5
):
    """Extracts genes highly specific to the given analysis level/type."""
    conn = get_db_connection()
    query = f"""
        SELECT *
        FROM table_1
        WHERE Analysis_level = '{analysis_level.value}'
          AND Analysis_type = '{analysis_type.value}'
          AND Psi_mean > {psi_cutoff}
          AND Zeta_mean > {zeta_cutoff}
        ORDER BY Psi_mean DESC, Zeta_mean DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df_to_csv_stream(df, "highly_specific.csv")

# ---------------------------------------------------------------------
# Endpoint 4: Non-specific housekeeping genes
@app.get("/non_specific")
def extract_non_specific(
    analysis_level: AnalysisLevel,
    analysis_type: AnalysisType,
    psi_cutoff: float = 0.5,
    zeta_cutoff: float = 0.5
):
    """Extracts non-specific (housekeeping) genes."""
    conn = get_db_connection()
    query = f"""
        SELECT *
        FROM table_1
        WHERE Analysis_level = '{analysis_level.value}'
          AND Analysis_type = '{analysis_type.value}'
          AND Psi_mean > {psi_cutoff}
          AND Zeta_mean < {zeta_cutoff}
        ORDER BY Psi_mean DESC, Zeta_mean ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df_to_csv_stream(df, "non_specific.csv")

# ---------------------------------------------------------------------
# Endpoint 5: Marker genes
@app.get("/marker")
def extract_marker(
    analysis_level: AnalysisLevel,
    analysis_type: AnalysisType,
    block_label: str,
    psi_cutoff: float = 0.5,
    psi_block_cutoff: float = 0.5
):
    conn = get_db_connection()
    main_table_name = '"table_1"' 
    psi_block_table = f'{analysis_level.value}_{analysis_type.value}'
    psi_block_table_quoted = f'"{psi_block_table}"' 

    query = f"""
        SELECT T1.*, T2."{block_label}"
        FROM {main_table_name} AS T1
        INNER JOIN {psi_block_table_quoted} AS T2
            ON T1.gene_name = T2.gene_name
        WHERE T1.Analysis_level = '{analysis_level.value}'
          AND T1.Analysis_type = '{analysis_type.value}'
          AND T1.Psi_mean > {psi_cutoff}
          AND T2."{block_label}" > {psi_block_cutoff}
        ORDER BY T1.Psi_mean DESC, T2."{block_label}" DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Error executing JOIN query: {e}")
    finally:
        conn.close()

    return df_to_csv_stream(df, "marker_genes.csv")


# ---------------------------------------------------------------------
@app.get("/gene_expression")
def extract_gene_expression(
    analysis_level: AnalysisLevel,
    analysis_type: AnalysisType,
    gene_list: Optional[list[str]] = Query(
        None, description="List of gene names or Ensembl IDs"
    ),
):
    """Extracts gene expression mean and variance values."""
    conn = get_gene_expr_db_connection()
    table_name = f"{analysis_level.value}_{analysis_type.value}"
    base_query = f'SELECT * FROM "{table_name}"'   # <-- quoting is correct

    if gene_list:
        gene_list = normalize_gene_inputs(gene_list)
        gene_str = ", ".join(f"'{g}'" for g in gene_list)

        # FIX: search both gene_name and ensembl_id
        query = f"""
            {base_query}
            WHERE gene_name COLLATE NOCASE IN ({gene_str})
               OR ensembl_id COLLATE NOCASE IN ({gene_str})
        """
    else:
        query = base_query

    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found. {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading '{table_name}': {e}")
    finally:
        conn.close()

    # filenames remain unchanged
    if gene_list:
        if len(gene_list) <= 3:
            safe_names = [g.replace(" ", "_") for g in gene_list]
            filename = "_".join(safe_names) + f"_{table_name}_gene_expr.csv"
        else:
            filename = f"{len(gene_list)}_{table_name}_gene_expr.csv"
    else:
        filename = f"all_{table_name}_gene_expr.csv"

    return df_to_csv_stream(df, filename)


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
            "/gene_expression": "Download gene expression mean and variance as CSV"
        }
    }

# ============================================================================
# MCP SERVER INTEGRATION (CORRECTED)
# ============================================================================

from mcp.server.fastapi import FastApiSseServerTransport
from mcp_server import server as mcp_logic

# Initialize the SSE transport with the correct path
mcp_sse_transport = FastApiSseServerTransport("/mcp/sse")

# CRITICAL: Use connect() to attach your MCP server logic
@app.on_event("startup")
async def startup_mcp():
    """Initialize MCP server on startup"""
    await mcp_sse_transport.connect(mcp_logic)

# SSE endpoint - this is where MCP clients connect
@app.get("/mcp/sse")
async def handle_mcp_sse(request: Request):
    """Handle MCP Server-Sent Events connection"""
    return await mcp_sse_transport.handle_sse(
        request.scope,
        request.receive, 
        request._send
    )

# Messages endpoint - this is where MCP clients send requests
@app.post("/mcp/messages")  
async def handle_mcp_messages(request: Request):
    """Handle MCP message POST requests"""
    return await mcp_sse_transport.handle_post_message(
        request.scope,
        request.receive,
        request._send
    )

# Health check for MCP server
@app.get("/mcp/health")
async def mcp_health():
    """Check if MCP server is running"""
    return {
        "status": "ok",
        "server": "8cubeDB-Explorer",
        "mcp_version": "1.0.0"
    }