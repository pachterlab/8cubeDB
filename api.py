from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
import pandas as pd
import sqlite3
import os
import io

# Path to your SQLite database
DB_FILE = "/data/8cube.db" 

# Helper function to establish connection
def get_db_connection():
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database file {DB_FILE} not found in container.")
    return sqlite3.connect(DB_FILE)

# Initialize the FastAPI app
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
# Option 1: Extract all specificity per gene
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
    return df_to_csv_stream(df, "specificity.csv")

# ---------------------------------------------------------------------
# Option 2: Extract psi_block df
@app.get("/psi_block")
def extract_psi_block(
    Analysis_level: str,
    Analysis_type: str,
    limit: int = 1000
):
    """Reads a psi_block table from the DB based on analysis type and level."""
    conn = get_db_connection()
    table_name = f"{Analysis_level}_{Analysis_type}"
    query = f"SELECT * FROM '{table_name}' LIMIT {limit}"
    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        print(f"Error: Table '{table_name}' not found in the database. {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df_to_csv_stream(df, f"{table_name}.csv")

# ---------------------------------------------------------------------
# Option 3: Extract highly specific genes
@app.get("/highly_specific")
def extract_highly_specific(
    Analysis_level: str,
    Analysis_type: str,
    Psi_cutoff: float = 0.5,
    Zeta_cutoff: float = 0.5
):
    """Extracts genes highly specific to the given analysis level/type."""
    conn = get_db_connection()
    query = f"""
        SELECT *
        FROM table_1
        WHERE Analysis_level = '{Analysis_level}'
          AND Analysis_type = '{Analysis_type}'
          AND Psi_mean > {Psi_cutoff}
          AND Zeta_mean > {Zeta_cutoff}
        ORDER BY Psi_mean DESC, Zeta_mean DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df_to_csv_stream(df, "highly_specific.csv")

# ---------------------------------------------------------------------
# Option 4: Extract non-specific housekeeping genes
@app.get("/non_specific")
def extract_non_specific(
    Analysis_level: str,
    Analysis_type: str,
    Psi_cutoff: float = 0.5,
    Zeta_cutoff: float = 0.5
):
    """Extracts non-specific (housekeeping) genes."""
    conn = get_db_connection()
    query = f"""
        SELECT *
        FROM table_1
        WHERE Analysis_level = '{Analysis_level}'
          AND Analysis_type = '{Analysis_type}'
          AND Psi_mean > {Psi_cutoff}
          AND Zeta_mean < {Zeta_cutoff}
        ORDER BY Psi_mean DESC, Zeta_mean ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df_to_csv_stream(df, "non_specific.csv")

# ---------------------------------------------------------------------
# Option 5: Extract marker genes
@app.get("/marker")
def extract_marker(
    Analysis_level: str,
    Analysis_type: str,
    block_label: str,
    Psi_cutoff: float = 0.5,
    psi_block_cutoff: float = 0.5
):
    """Extracts marker genes by merging the main table with a psi_block table."""
    conn = get_db_connection()
    main_table_name = "table_1"
    psi_block_table_name = f"{Analysis_level}_{Analysis_type}"
    query = f"""
        SELECT T1.*, T2."{block_label}"
        FROM {main_table_name} AS T1
        INNER JOIN {psi_block_table_name} AS T2
            ON T1.gene_name = T2.gene_name
        WHERE T1.Analysis_level = '{Analysis_level}'
          AND T1.Analysis_type = '{Analysis_type}'
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
    return df_to_csv_stream(df, "marker_genes.csv")

# ---------------------------------------------------------------------
# Root endpoint
@app.get("/")
def home():
    return {
        "message": "Welcome to the 8cubeDB API!",
        "note": "All endpoints stream CSV downloads.",
        "endpoints": {
            "/specificity": "Download gene specificity for a list of genes as CSV",
            "/psi_block": "Download psi block table as CSV (with optional limit)",
            "/highly_specific": "Download highly specific genes as CSV",
            "/non_specific": "Download housekeeping genes as CSV",
            "/marker": "Download marker genes as CSV"
        }
    }
