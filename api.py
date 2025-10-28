from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
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
    version="1.1.0"
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
# NEW ENDPOINT: Configuration Dictionary
@app.get("/config")
def get_analysis_config():
    """
    Returns a nested dictionary of all available analysis levels,
    analysis types, and block labels for each combination.
    Useful for populating dropdowns in a UI.
    """
    config = {}
    for level in analysis_levels:
        config[level] = {}
        for a_type in analysis_types:
            table_name = f"{level}_{a_type}"
            block_labels = get_columns_from_table(table_name)
            if block_labels:
                config[level][a_type] = block_labels

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
    gene_str = ', '.join(f"'{g}'" for g in gene_list)
    query = f"""
        SELECT *
        FROM table_1
        WHERE gene_name IN ({gene_str}) OR ensembl_id IN ({gene_str})
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Construct dynamic file name
    if len(gene_list) <= 3:
        safe_names = [g.replace(" ", "_") for g in gene_list]  # sanitize names
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
    """Reads a psi_block table from the DB based on analysis type and level.
       Optionally filters by gene(s) and generates a dynamic CSV filename."""
    
    conn = get_db_connection()
    table_name = f"{analysis_level.value}_{analysis_type.value}"
    base_query = f"SELECT * FROM '{table_name}'"

    # Build query based on whether genes were passed
    if gene_list:
        gene_str = ', '.join(f"'{g}'" for g in gene_list)
        query = f"{base_query} WHERE gene_name IN ({gene_str}) OR ensembl_id IN ({gene_str})"
    else:
        query = base_query

    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found. {e}")
    finally:
        conn.close()

    # --- Dynamic filename logic ---
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
    """Extracts marker genes by merging the main table with a psi_block table."""
    conn = get_db_connection()
    main_table_name = "table_1"
    psi_block_table_name = f"{analysis_level.value}_{analysis_type.value}"
    query = f"""
        SELECT T1.*, T2."{block_label}"
        FROM {main_table_name} AS T1
        INNER JOIN {psi_block_table_name} AS T2
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
# Root endpoint
@app.get("/")
def home():
    return {
        "message": "Welcome to the 8cubeDB API!",
        "note": "All endpoints stream CSV downloads.",
        "analysis_levels": analysis_levels,
        "analysis_types": analysis_types,
        "endpoints": {
            "/config": "View all analysis levels, types, and available block labels",
            "/specificity": "Download gene specificity for a list of genes as CSV",
            "/psi_block": "Download psi block table as CSV",
            "/highly_specific": "Download highly specific genes as CSV",
            "/non_specific": "Download housekeeping genes as CSV",
            "/marker": "Download marker genes as CSV"
        }
    }
