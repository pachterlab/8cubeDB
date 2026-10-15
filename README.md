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
