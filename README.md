# 8cubeDB: Mouse Specificity Explorer 🐭

### Exploring gene specificity in 8 tissues from 8 individuals for each of the 8 founder mouse strains

**8cubeDB** provides a unified platform to explore gene specificity, marker genes, and expression variability across founder mouse tissues from the *Rebboah et al. (2025)* dataset.
It includes both a **RESTful API** (built with FastAPI), an **interactive dashboard** (built with Streamlit) and **MCP Server integration** for LLM-powered data analysis.

---

## 🌐 Access the Platform

* **Frontend Dashboard:** [https://mouseexplorer.onrender.com](https://mouseexplorer.onrender.com)
  Explore genes, visualize Psi-blocks, and browse marker and housekeeping genes interactively.

* **Backend API:** [https://eightcubedb.onrender.com/docs](https://eightcubedb.onrender.com/docs)
  Programmatic access to the dataset via REST API. Refer to this [colab notebook](https://colab.research.google.com/drive/1ALSKoH1N-szB761yZ7Y2nQjaoe3b7Gr5?usp=sharing) for a tutorial on how to query the database in python.
  
* **MCP Server (Hosted SSE Endpoint):** [https://eightcubedb.onrender.com/mcp/sse](https://eightcubedb.onrender.com/mcp/sse)
  Enables direct integration with LLM clients that support the Model Context Protocol (MCP).

---

## System Overview

### FastAPI Backend

The backend serves data from two curated SQLite databases:

* `8cube.db` — primary specificity and Psi-block data
* `mean_var_DB.db` — mean and variance of gene expression across conditions

All API routes stream data as **CSV downloads** for seamless integration with downstream tools.

#### **Key Endpoints**

| Endpoint           | Description                                                |
| ------------------ | ---------------------------------------------------------- |
| `/`                | API root — overview of available endpoints                 |
| `/config`          | Returns available analysis levels, types, and block labels |
| `/specificity`     | Extract gene specificity data for given genes              |
| `/psi_block`       | Fetch Psi-block data by analysis level/type                |
| `/highly_specific` | Retrieve genes highly specific to a given variable         |
| `/non_specific`    | Retrieve non-specific (housekeeping) genes                 |
| `/marker`          | Identify marker genes by block label                       |
| `/gene_expression` | Get gene expression mean and variance values               |

---

### Streamlit Frontend

The **Mouse Specificity Explorer** dashboard provides an interactive interface to visualize and query the API.

#### **Main Features**

| Tab                          | Functionality                                                   |
| ---------------------------- | --------------------------------------------------------------- |
| 🔬 **Gene Viewer**           | Visualize Psi-block and gene expression data for specific genes |
| 🗺️ **Specificity Explorer** | Browse gene specificity across the dataset                      |
| ⭐ **Highly Specific Genes**  | Identify genes specific to a tissue or condition                |
| 🏠 **Housekeeping Genes**    | Explore broadly expressed, non-specific genes                   |
| 🎯 **Marker Genes**          | Discover marker genes for selected blocks                       |

Built with **Streamlit**, **Plotly**, and **Pandas**, the app offers clean visualizations and downloadable tables.

---

### 🤖 AI & LLM Integration (MCP)

8cubeDB supports the **Model Context Protocol (MCP)**, allowing AI assistants like Claude to query the database directly to answer questions about mouse gene specificity.

#### 1. Hosted MCP (Remote)

You can connect your MCP-compatible client to our hosted SSE endpoint:

* **Endpoint:** `https://eightcubedb.onrender.com/mcp/sse`

#### 2. Local MCP (For Claude Desktop)

To use 8cubeDB directly within the Claude Desktop app, follow these steps:

1. **Download** the [mcp_server_local_for_claude.py](./mcp_server_local_for_claude.py) file from this repository.
2. **Locate your config file:**
* **macOS:** `~/Library/Application\ Support/Claude/claude_desktop_config.json`
* **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`


3. **Add the following configuration** (ensure you update the paths to your specific Python environment and the location of the downloaded script):

```json
{
  "mcpServers": {
    "8cubedb": {
      "command": "/YOUR/PATH/TO/python",
      "args": [
        "/YOUR/PATH/TO/mcp_server_local_for_claude.py"
      ]
    }
  }
}

```

---



## Data Summary

* **Dataset:** Rebboah _et al_. (2025) — *8cube founder mouse dataset*
* **Metrics:** Ψ (Psi) specificity index and ζ (Zeta) selectivity metric
* **Levels:** Multi-scale analysis (cell type, tissue, organ, etc.)
* **Sources:** Derived from `table_1` (global summary) and `*_psi_block` tables (block-level metrics)

---

## ⚙️ Architecture Overview

```

                        ┌──────────────────────────────┐
                        │        SQLite Databases      │
                        │   - 8cube.db                 │
                        │   - mean_var_DB.db           │
                        └───────────────┬──────────────┘
                                        │ SQLite Queries
                                        ▼
                        ┌──────────────────────────────┐
                        │        FastAPI Backend       │
                        │  (eightcubedb.onrender.com)  │
                        └───────────────┬──────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                        ▼                               ▼
        ┌──────────────────────────────┐   ┌──────────────────────────────┐
        │        Streamlit Frontend    │   │        MCP Server (SSE)      │
        │  mouseexplorer.onrender.com  │   │  /mcp/sse or local Claude    │
        └──────────────────────────────┘   └──────────────────────────────┘

```
---

## Project Attribution

Developed by **Nikhila P. Swarna**
*Pachter Lab, Caltech*

Part of the **[IGVF Consortium](https://www.igvf.org)**
Specificity analyses powered by **[ember](https://github.com/pachterlab/ember)**.

---

## License

Licensed under the **BSD 2-Clause License**.
© 2025 Pachter Lab · All rights reserved.

---

##  Citation

If you use this website, MCP server or the accompanying database, please cite the following papers:

* **Rebboah E, _et al_.**
  *Systematic cell-type resolved transcriptomes of 8 tissues in 8 lab and wild-derived mouse strains captures global and local expression variation.* (2025)
  **DOI:** [https://doi.org/10.1101/2025.04.21.649844](https://doi.org/10.1101/2025.04.21.649844)

* **Swarna NP, _et al_.**
  *Determining gene specificity from multivariate single-cell RNA sequencing data.* (2025)
  **DOI:** [https://doi.org/10.1101/2025.11.21.689845](https://doi.org/10.1101/2025.11.21.689845)

## Memory audit and reviewer compatibility (2026-10-15)

The backend continues to return complete CSV downloads with the existing query
parameters, columns, filenames, cutoffs, normalization and ordering. There is no
new pagination, row cap, rate limit, authentication, admission queue or request
rejection. No database or scientific calculation was changed. Nothing was deployed.

### Root cause and implementation

The previous `StreamingResponse` wrapped an already materialized pandas DataFrame
and a complete `StringIO` CSV. It did not stream database results. A broad
expression table tested contains 41,786 rows and 260 columns, producing a
178.455 MiB CSV. SQLite-to-pandas conversion creates additional Python row objects
and arrays; CSV construction and `StringIO` storage add further large allocations.
Concurrent downloads multiply these allocations. A single complete download
already exceeds Render's 512 MB budget in the original implementation.

The database files are approximately 3.6 GB (`8cube.db`) and 2.3 GB
(`mean_var_DB.db`). The primary summary table contains 2,508,910 rows and has no
indexes. `/highly_specific` and `/non_specific` scan and sort qualifying summary
rows; `/marker` additionally builds an automatic temporary join index. The
original SQL already applied scientific filters in SQLite; those predicates and
the `gene_name` join, including duplicate matches, remain unchanged. All exported
columns are required by the response contract, so columns have not been dropped.

Changes:

- Fetch at most 16 rows at a time from SQLite and serialize only that batch with
  the standard CSV writer. Encode each batch once. No REST DataFrames or complete
  output strings are built. This also covers `/specificity` and `/non_specific`.
- Keep SQL filters, cutoffs and sorts in SQLite. Bind values and safely quote table
  and block identifiers. Preserve the complete matching result set.
- Open databases read-only, use a 2 MiB SQLite page-cache target per connection,
  disable memory mapping, and spill temporary joins/sorts to disk. These are
  connection settings; they do not alter database files or indexes. The cache
  setting is a target rather than a hard process memory cap.
- Close connections on successful completion, query failure and disconnected
  downloads. Log query execution and total stream duration, completion status,
  rows, output bytes, RSS, request duration and active export count. Gene lists
  and numerical result values are not logged.
- Build startup dropdowns with one SQL DISTINCT scan and small sets. Remove
  pandas from REST imports and load MCP/SSE dependencies only when used.
- Have the frontend parse the response it has already downloaded. Previously,
  `pd.read_csv(response.url)` silently downloaded every CSV a second time.
- Repair the pre-existing merge marker in `render.yaml`, explicitly retain one
  worker, and support both direct and package imports. Keep MCP/SSE dependencies
  within their existing major versions for the current integration.

Four simultaneous complete expression downloads peaked at approximately 76 MiB
process RSS, each returning the same 178.455 MiB CSV and matching checksum. The
four-download test took about 206 seconds on the local shared host; this supports
the memory improvement, not a production latency guarantee.

There is no large server-side result cache to evict. Root/config/MCP responses
are JSON metadata or summaries, not full numerical-table JSON serialization;
the four investigated data endpoints return CSV. MCP still buffers the CSV it
uses for summaries, so heavy concurrent MCP traffic remains a separate risk.

### Validation

Read-only comparisons used the existing local databases, not regenerated data.
Cases include Cwc22 and Gjb4 strain specificity and Akap13 from the
[EMBER manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC12667802/), plus
Akr1c21 and Kidney/Across-tissues PWKJ examples from
`../extract_functions.ipynb`.

Every tested CSV matched the former SQL+pandas output byte for byte, with exact
numerical comparisons after round-trip float parsing:

| Request | Rows returned |
| --- | ---: |
| Strain psi-block, four manuscript/notebook genes | 4 |
| Strain expression, same four genes | 4 |
| Kidney sex/cell-type psi-block, Mpped1/Akr1c6/Neurog2/Akap13 | 4 |
| Kidney sex/cell-type expression, same four genes | 4 |
| All specificity levels, Cwc22/Gjb4/Akap13 | 186 |
| Kidney/Strain highly specific, cutoffs 0.4/0.4 | 3,402 |
| Kidney/Strain housekeeping, cutoffs 0.7/0.3 | 15,369 |
| Kidney/Strain PWKJ markers, cutoffs 0.5/0.5 | 663 |
| Across_tissues/Strain PWKJ markers, cutoffs 0.5/0.5 | 722 |
| Kidney/Strain highly specific, zero cutoffs | 39,296 |

The widest expression table, `DiencephalonPituitary_Sex:Strain:Celltype`,
contains 770 columns and 41,299 rows. Its full 354.279 MiB export streamed at
approximately 64 MiB peak process RSS. Its checksum matched a chunked pandas
reference over the same complete SQL result. Full measurements and dependency
versions are saved in [scripts/audit_results.json](scripts/audit_results.json).

The complete unfiltered `Across_tissues` / `Sex:Strain:Tissue` expression CSV
also matches exactly: 41,786 rows, 260 columns, 178.455 MiB. Both implementations
produce SHA-256
`9ac2ec4712f3b7a7865d6f196a326f962e74d26f2dd6eed61bf5c771bed29f74`.

Local sampled RSS was approximately 1,418 MiB for the former full pandas/CSV
path and 62 MiB for the complete streaming response. Startup RSS was approximately
165 MiB before and 48 MiB after. These are local Linux measurements, not Render
telemetry. The benchmark samples current RSS every 5 ms; it deliberately avoids
buffering the streamed response in a test HTTP client or relying on an inherited
process high-water mark.

Reproduce with the API dependencies installed:

```bash
python -m unittest discover -s tests -v
DB_FILE=../8cube.db GENE_EXPR_DB_FILE=../mean_var_DB.db python scripts/audit_queries.py
DB_FILE=../8cube.db GENE_EXPR_DB_FILE=../mean_var_DB.db python scripts/audit_queries.py --memory old
DB_FILE=../8cube.db GENE_EXPR_DB_FILE=../mean_var_DB.db python scripts/audit_queries.py --memory new
DB_FILE=../8cube.db GENE_EXPR_DB_FILE=../mean_var_DB.db python scripts/audit_queries.py --memory new --concurrent 4
DB_FILE=../8cube.db GENE_EXPR_DB_FILE=../mean_var_DB.db python scripts/audit_queries.py --memory new --analysis-level DiencephalonPituitary --analysis-type Sex:Strain:Celltype
DB_FILE=../8cube.db GENE_EXPR_DB_FILE=../mean_var_DB.db python scripts/audit_queries.py --memory reference --analysis-level DiencephalonPituitary --analysis-type Sex:Strain:Celltype
```

The old-path benchmark requires more than 512 MB; run it locally, not on Render.
The contract tests also exercise complete unfiltered responses, duplicate-name
joins, case normalization, safe SQL values/identifiers, MCP initialize/list/health,
150 unrestricted concurrent middleware calls, cancellation and connection cleanup.

### Remaining risks and approval boundary

Full exports intentionally remain large. Unbounded automated traffic can still
exhaust CPU, bandwidth, connections or RAM; streaming substantially reduces each
request's memory but does not impose a global bound. Slow consumers retain an
open SQLite connection. Unindexed scans remain expensive, and disk-backed
sorts/temporary indexes need writable temporary storage. Additional workers would
multiply startup and connection memory. Late database/network failures can still
interrupt a stream after HTTP headers have been sent.

Reviewer notebooks require no edits. Any future rate limiting, pagination,
truncation, authentication, concurrency queue/rejection, query deadline, response
schema change or database index change needs explicit approval before implementation.
Production Render logs and its exact deployed configuration were not available;
verify memory and query logs on Render after a separately approved deployment.
