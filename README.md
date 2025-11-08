# 8cubeDB: Mouse Specificity Explorer 🐭

### Exploring gene specificity in *Rebboah et al. (2025)* founder mouse data

**8cubeDB** provides a unified platform to explore gene specificity, marker genes, and expression variability across founder mouse tissues from the *Rebboah et al. (2025)* dataset.
It includes both a **RESTful API** (built with FastAPI) and an **interactive dashboard** (built with Streamlit).

---

## 🌐 Access the Platform

* **Frontend Dashboard:** [https://mouseexplorer.onrender.com](https://mouseexplorer.onrender.com)
  Explore genes, visualize Psi-blocks, and browse marker and housekeeping genes interactively.

* **Backend API:** [https://eightcubedb.onrender.com/docs](https://eightcubedb.onrender.com/docs)
  Programmatic access to the dataset via REST API.

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

## Data Summary

* **Dataset:** Rebboah et al. (2025) — *8cube founder mouse dataset*
* **Metrics:** Ψ (Psi) specificity index and ζ (Zeta) selectivity metric
* **Levels:** Multi-scale analysis (cell type, tissue, organ, etc.)
* **Sources:** Derived from `table_1` (global summary) and `*_psi_block` tables (block-level metrics)

---

## ⚙️ Architecture Overview

```
                ┌──────────────────────────────┐
                │      Streamlit Frontend       │
                │  (https://mouseexplorer.onrender.com) │
                └───────────────┬──────────────┘
                                │ REST API calls (CSV)
                                ▼
                ┌──────────────────────────────┐
                │        FastAPI Backend        │
                │  (https://eightcubedb.onrender.com) │
                └───────────────┬──────────────┘
                                │ SQLite Queries
                                ▼
                ┌──────────────────────────────┐
                │        SQLite Databases       │
                │   - 8cube.db                  │
                │   - mean_var_DB.db            │
                └──────────────────────────────┘
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

## Citation

If you use 8cubeDB or its analyses, please cite:

> **Swarna et al. (2025)**
> *Determining genes specificty from multimodal single-cell data*.
> [DOI forthcoming]
