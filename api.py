from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import pandas as pd
import sqlite3
import os

# Path to your SQLite database
DB_FILE = "8cube.db"

# Helper function to establish connection
def get_db_connection():
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database file {DB_FILE} not found in container.")
    return sqlite3.connect(DB_FILE)

# Initialize the FastAPI app
app = FastAPI(
    title="8cubeDB API",
    description="API for querying gene specificity from the Rebboah et al. (2025) 8cube founder dataset.",
    version="1.0.0"
)

# ---------------------------------------------------------------------
# Option 1: Extract all specificity per gene
@app.get("/specificity")
def extract_all_specificity_per_gene(gene_list: list[str] = Query(..., description="List of gene names or Ensembl IDs")):
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
    return JSONResponse(df.to_dict(orient="records"))

# ---------------------------------------------------------------------
# Option 2: Extract psi_block df
@app.get("/psi_block")
def extract_psi_block(Analysis_level: str, Anlysis_type: str):
    """Reads a psi_block table from the DB based on analysis type and level."""
    conn = get_db_connection()
    table_name = f"{Analysis_level}_{Anlysis_type}"
    query = f"SELECT * FROM {table_name}"
    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        print(f"Error: Table '{table_name}' not found in the database. {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return JSONResponse(df.to_dict(orient="records"))

# ---------------------------------------------------------------------
# Option 3: Extract highly specific genes
@app.get("/highly_specific")
def extract_highly_specific(
    Analysis_level: str,
    Anlysis_type: str,
    Psi_cutoff: float = 0.5,
    Zeta_cutoff: float = 0.5
):
    """Extracts genes highly specific to the given analysis level/type."""
    conn = get_db_connection()
    query = f"""
        SELECT *
        FROM table_1
        WHERE Analysis_level = '{Analysis_level}'
          AND Analysis_type = '{Anlysis_type}'
          AND Psi_mean > {Psi_cutoff}
          AND Zeta_mean > {Zeta_cutoff}
        ORDER BY Psi_mean DESC, Zeta_mean DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return JSONResponse(df.to_dict(orient="records"))

# ---------------------------------------------------------------------
# Option 4: Extract non-specific housekeeping genes
@app.get("/non_specific")
def extract_non_specific(
    Analysis_level: str,
    Anlysis_type: str,
    Psi_cutoff: float = 0.5,
    Zeta_cutoff: float = 0.5
):
    """Extracts non-specific (housekeeping) genes."""
    conn = get_db_connection()
    query = f"""
        SELECT *
        FROM table_1
        WHERE Analysis_level = '{Analysis_level}'
          AND Analysis_type = '{Anlysis_type}'
          AND Psi_mean > {Psi_cutoff}
          AND Zeta_mean < {Zeta_cutoff}
        ORDER BY Psi_mean DESC, Zeta_mean ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return JSONResponse(df.to_dict(orient="records"))

# ---------------------------------------------------------------------
# Option 5: Extract marker genes
@app.get("/marker")
def extract_marker(
    Analysis_level: str,
    Anlysis_type: str,
    block_label: str,
    Psi_cutoff: float = 0.5,
    psi_block_cutoff: float = 0.5
):
    """Extracts marker genes by merging the main table with a psi_block table."""
    conn = get_db_connection()
    main_table_name = "table_1"
    psi_block_table_name = f"{Analysis_level}_{Anlysis_type}"
    query = f"""
        SELECT T1.*, T2."{block_label}"
        FROM {main_table_name} AS T1
        INNER JOIN {psi_block_table_name} AS T2
            ON T1.gene_name = T2.gene_name
        WHERE T1.Analysis_level = '{Analysis_level}'
          AND T1.Analysis_type = '{Anlysis_type}'
          AND T1.Psi_mean > {Psi_cutoff}
          AND T2."{block_label}" > {psi_block_cutoff}
        ORDER BY T1.Psi_mean DESC, T2."{block_label}" DESC
    """
    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        print(f"Error executing JOIN query: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return JSONResponse(df.to_dict(orient="records"))

# ---------------------------------------------------------------------
# Root endpoint
@app.get("/")
def home():
    return {
        "message": "Welcome to the 8cubeDB API!",
        "endpoints": {
            "/specificity": "Query gene specificity for a list of genes",
            "/psi_block": "Fetch a psi block table by analysis level and type",
            "/highly_specific": "Get highly specific genes by analysis level and type",
            "/non_specific": "Get non-specific housekeeping genes by analysis level and type",
            "/marker": "Extract marker genes by analysis level and type"
        }
    }
