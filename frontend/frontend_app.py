import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import math
import base64
import os
import streamlit as st


API_URL = "https://eightcubedb.onrender.com"

st.set_page_config(page_title="8cubeDB Dashboard", layout="wide")

import streamlit as st
import base64
import os

# --- Helper to load logos ---
def image_to_base64(path):
    if not os.path.exists(path):
        st.warning(f"⚠️ Logo not found: {path}")
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# --- Load logos ---
base_dir = os.path.dirname(__file__)
caltech_logo = image_to_base64(os.path.join(base_dir, "caltech_logo.png"))
uci_logo = image_to_base64(os.path.join(base_dir, "uci_logo.png"))
igvf_logo = image_to_base64(os.path.join(base_dir, "igvf_logo.png"))

# --- Header styling ---
st.markdown(
    """
    <style>
        .top-banner {
            display: flex;
            justify-content: flex-end;
            align-items: flex-start;
            padding: 10px 20px 0px 20px;
        }
        .logos-right {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 15px;
        }
        .logos-right img {
            height: 42px;
            object-fit: contain;
        }
        .logos-right img:nth-child(2) {
            height: 42px; /* UCI slightly smaller */
        }
        .logos-right img:last-child {
            height: 60px; /* IGVF slightly bigger */
        }
        .title-center {
            text-align: center;
            margin-top: -25px;
            margin-bottom: 5px;
        }
        .title-center h1 {
            font-family: "Helvetica Neue", Arial, sans-serif;
            font-weight: 750;
            color: #1e293b;
            font-size: 44px; /* MUCH larger title */
            margin-bottom: 8px;
        }
        .title-center p {
            color: #6b7280;
            font-size: 17px;
            margin-top: 0;
        }
        hr {
            border: 0.7px solid #dcdcdc;
            margin-top: 10px;
            margin-bottom: 20px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Header content ---
st.markdown(
    f"""
    <div class="top-banner">
        <div class="logos-right">
            {f'<img src="data:image/png;base64,{caltech_logo}" alt="Caltech">' if caltech_logo else ''}
            {f'<img src="data:image/png;base64,{uci_logo}" alt="UCI">' if uci_logo else ''}
            {f'<img src="data:image/png;base64,{igvf_logo}" alt="IGVF">' if igvf_logo else ''}
        </div>
    </div>

    <div class="title-center">
        <h1>Mouse Specificity Explorer 🐭</h1>
        <p>Exploring gene specificity in 8 tissues across 8 founder mouse strains</p>
    </div>
    <hr/>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------
# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔬 Gene Viewer",
    "🗺️ Specificity Explorer",
    "⭐ Highly Specific Genes",
    "🏠 Housekeeping Genes",
    "🎯 Marker Genes"
])
# ------------------------------------------------------

# ======================================================
# TAB 1 – PSI-BLOCK AND GENE-EXPRESSION VIEWER
# ======================================================
with tab1:
    st.title("🔬 Gene Viewer")

    try:
        config_res = requests.get(f"{API_URL}/config")
        config_data = config_res.json().get("analysis_config", {})
    except Exception as e:
        config_data = {}
        st.error(f"Could not fetch /config: {e}")

    col1, col2, col3 = st.columns(3)
    with col1:
        gene_input2 = st.text_input("Gene name or Ensembl ID", "", key="gene_viewer_input")
    with col2:
        analysis_level = st.selectbox(
            "Analysis Level",
            list(config_data.keys()) if config_data else [],
            index=0 if config_data else None,
            key="level_gene_viewer"
        )
    with col3:
        analysis_types = list(config_data.get(analysis_level, {}).keys()) if config_data else []
        analysis_type = st.selectbox(
            "Analysis Type",
            analysis_types,
            index=0 if analysis_types else None,
            key="type_gene_viewer"
        )

    if st.button("Fetch Psi-Block & Gene-Expression Data", key="fetch_gene_viewer"):
        if not (gene_input2 and analysis_level and analysis_type):
            st.warning("Please fill in all fields.")
        else:
            genes = [g.strip() for g in gene_input2.split(",") if g.strip()]
            params = {
                "analysis_level": analysis_level,
                "analysis_type": analysis_type,
            }
            psi_params = list(params.items()) + [("gene_list", g) for g in genes]
            expr_params = psi_params.copy()

            try:
                psi_res = requests.get(f"{API_URL}/psi_block", params=psi_params)
                psi_df = pd.read_csv(psi_res.url) if psi_res.status_code == 200 else pd.DataFrame()

                expr_res = requests.get(f"{API_URL}/gene_expression", params=expr_params)
                expr_df = pd.read_csv(expr_res.url) if expr_res.status_code == 200 else pd.DataFrame()

                c1, c2 = st.columns(2, gap="medium")

                if not psi_df.empty:
                    numeric_cols = psi_df.select_dtypes("number").columns
                    if len(numeric_cols) > 0:
                        row = psi_df.iloc[0]
                        values = [row[c] for c in numeric_cols]
                        fig_psi = go.Figure()
                        fig_psi.add_trace(go.Bar(x=numeric_cols, y=values, marker_color="gray"))
                        fig_psi.update_layout(
                            title=f"{gene_input2}: Psi-block Values ({analysis_level}/{analysis_type})",
                            yaxis=dict(range=[0, 1]), height=600, xaxis_tickangle=-30
                        )
                        c1.plotly_chart(fig_psi, use_container_width=True)

                if not expr_df.empty:
                    mean_cols = [c for c in expr_df.columns if c.startswith("mean_")]
                    var_cols = [c for c in expr_df.columns if c.startswith("variance_")]
                    common_labels = [
                        c.replace("mean_", "")
                        for c in mean_cols if "variance_" + c.replace("mean_", "") in var_cols
                    ]
                    if common_labels:
                        mean_vals = [expr_df[f"mean_{c}"].mean() for c in common_labels]
                        var_vals = [expr_df[f"variance_{c}"].mean() for c in common_labels]

                        mean_df = pd.DataFrame({"Block": common_labels, "Mean": mean_vals})
                        var_df = pd.DataFrame({"Block": common_labels, "Variance": var_vals})

                        c2a, c2b = c2.columns(2)
                        fig_mean = go.Figure()
                        fig_mean.add_trace(go.Bar(x=mean_df["Block"], y=mean_df["Mean"], marker_color="lightgray"))
                        fig_mean.update_layout(title="Expression Mean", height=600, xaxis_tickangle=-30)
                        c2a.plotly_chart(fig_mean, use_container_width=True)

                        fig_var = go.Figure()
                        fig_var.add_trace(go.Bar(x=var_df["Block"], y=var_df["Variance"], marker_color="lightgray"))
                        fig_var.update_layout(title="Expression Variance", height=600, xaxis_tickangle=-30)
                        c2b.plotly_chart(fig_var, use_container_width=True)

                if not psi_df.empty:
                    st.subheader("📋 Psi-block Table")
                    st.dataframe(psi_df, use_container_width=True, height=250)
                if not expr_df.empty:
                    st.subheader("📋 Gene Expression Table")
                    st.dataframe(expr_df, use_container_width=True, height=250)

            except Exception as e:
                st.error(f"Error fetching data: {e}")

# ======================================================
# TAB 2 – SPECIFICITY VIEWER
# ======================================================
with tab2:
    st.title("🗺️ Specificity Explorer")

    # Gene input
    gene_input = st.text_input("Gene name or Ensembl ID:", key="gene_specificity")

    if st.button("Fetch Specificity Data", key="fetch_specificity"):
        genes = [g.strip() for g in gene_input.split(",") if g.strip()]
        if not genes:
            st.warning("Please enter at least one gene.")
        else:
            try:
                params = [("gene_list", g) for g in genes]
                response = requests.get(f"{API_URL}/specificity", params=params)

                if response.status_code != 200:
                    st.error(f"API returned {response.status_code}")
                else:
                    df = pd.read_csv(response.url)
                    if df.empty:
                        st.warning("No results found.")
                    else:
                        st.success(f"Loaded {len(df)} rows for {', '.join(genes)}")

                        # --- Display table ---
                        st.dataframe(df, use_container_width=True, height=400)

                        # --- Plot if columns available ---
                        expected_cols = {
                            "Analysis_level",
                            "Analysis_type",
                            "Psi_mean",
                            "Psi_std",
                            "Zeta_mean",
                            "Zeta_std",
                        }

                        if expected_cols.issubset(df.columns):
                            grouped = (
                                df.groupby(["Analysis_level", "Analysis_type"])
                                .agg(
                                    Psi_mean=("Psi_mean", "mean"),
                                    Psi_std=("Psi_std", "mean"),
                                    Zeta_mean=("Zeta_mean", "mean"),
                                    Zeta_std=("Zeta_std", "mean"),
                                )
                                .reset_index()
                            )

                            st.subheader("📊 Ψ (Psi) and ζ (Zeta) Mean ± SD per Analysis Level")

                            levels = grouped["Analysis_level"].unique()
                            ncols = 2
                            nrows = math.ceil(len(levels) / ncols)

                            for i in range(nrows):
                                cols = st.columns(ncols, gap="small")
                                for j in range(ncols):
                                    idx = i * ncols + j
                                    if idx >= len(levels):
                                        break

                                    level = levels[idx]
                                    subset = grouped[grouped["Analysis_level"] == level]

                                    fig = go.Figure()

                                    # Ψ mean ± SD
                                    fig.add_trace(
                                        go.Bar(
                                            x=subset["Analysis_type"],
                                            y=subset["Psi_mean"],
                                            name="Ψ mean",
                                            error_y=dict(
                                                type="data",
                                                array=subset["Psi_std"],
                                                visible=True,
                                            ),
                                            marker_color="gray",
                                            opacity=0.85,
                                        )
                                    )

                                    # ζ mean ± SD
                                    fig.add_trace(
                                        go.Bar(
                                            x=subset["Analysis_type"],
                                            y=subset["Zeta_mean"],
                                            name="ζ mean",
                                            error_y=dict(
                                                type="data",
                                                array=subset["Zeta_std"],
                                                visible=True,
                                            ),
                                            marker_color="lightgray",
                                            opacity=0.85,
                                        )
                                    )

                                    fig.update_layout(
                                        barmode="group",
                                        title=f"{level}",
                                        yaxis=dict(range=[0, 1], title="Specificity (0–1)"),
                                        xaxis_title="Analysis Type",
                                        margin=dict(t=40, b=60, l=40, r=20),
                                        height=400,
                                        legend=dict(
                                            orientation="h",
                                            yanchor="bottom",
                                            y=1.02,
                                            xanchor="right",
                                            x=1
                                        ),
                                    )

                                    cols[j].plotly_chart(fig, use_container_width=True)

                        else:
                            st.warning("Expected columns missing from data (need Psi/Zeta means and stds).")

            except Exception as e:
                st.error(f"Error fetching data: {e}")


# ======================================================
# TAB 3 – HIGHLY SPECIFIC GENES
# ======================================================
with tab3:
    st.title("⭐ Highly Specific Genes")

    try:
        config_res = requests.get(f"{API_URL}/config")
        config_data = config_res.json().get("analysis_config", {})
    except Exception as e:
        config_data = {}
        st.error(f"Could not fetch /config: {e}")

    col1, col2 = st.columns(2)
    with col1:
        level = st.selectbox("Analysis Level", list(config_data.keys()), key="level_highly_specific")
    with col2:
        types = list(config_data.get(level, {}).keys())
        a_type = st.selectbox("Analysis Type", types, key="type_highly_specific")

    psi_cutoff = st.slider("Ψ cutoff", 0.0, 1.0, 0.5, 0.05, key="psi_cutoff_highly")
    zeta_cutoff = st.slider("ζ cutoff", 0.0, 1.0, 0.5, 0.05, key="zeta_cutoff_highly")

    if st.button("Fetch Highly Specific Genes", key="fetch_highly_specific"):
        params = {
            "analysis_level": level,
            "analysis_type": a_type,
            "psi_cutoff": psi_cutoff,
            "zeta_cutoff": zeta_cutoff,
        }
        res = requests.get(f"{API_URL}/highly_specific", params=params)
        if res.status_code == 200:
            df = pd.read_csv(res.url)
            st.success(f"Loaded {len(df)} highly specific genes.")
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.error(f"Error {res.status_code} fetching data.")

# ======================================================
# TAB 4 – HOUSEKEEPING GENES
# ======================================================
with tab4:
    st.title("🏠 Non-specific (Housekeeping) Genes")

    try:
        config_res = requests.get(f"{API_URL}/config")
        config_data = config_res.json().get("analysis_config", {})
    except Exception as e:
        config_data = {}
        st.error(f"Could not fetch /config: {e}")

    col1, col2 = st.columns(2)
    with col1:
        level = st.selectbox("Analysis Level", list(config_data.keys()), key="level_housekeeping")
    with col2:
        types = list(config_data.get(level, {}).keys())
        a_type = st.selectbox("Analysis Type", types, key="type_housekeeping")

    psi_cutoff = st.slider("Ψ cutoff", 0.0, 1.0, 0.5, 0.05, key="psi_cutoff_house")
    zeta_cutoff = st.slider("ζ cutoff", 0.0, 1.0, 0.5, 0.05, key="zeta_cutoff_house")

    if st.button("Fetch Housekeeping Genes", key="fetch_housekeeping"):
        params = {
            "analysis_level": level,
            "analysis_type": a_type,
            "psi_cutoff": psi_cutoff,
            "zeta_cutoff": zeta_cutoff,
        }
        res = requests.get(f"{API_URL}/non_specific", params=params)
        if res.status_code == 200:
            df = pd.read_csv(res.url)
            st.success(f"Loaded {len(df)} housekeeping genes.")
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.error(f"Error {res.status_code} fetching data.")

# ======================================================
# TAB 5 – MARKER GENES
# ======================================================
with tab5:
    st.title("🎯 Marker Genes")

    try:
        config_res = requests.get(f"{API_URL}/config")
        config_data = config_res.json().get("analysis_config", {})
    except Exception as e:
        config_data = {}
        st.error(f"Could not fetch /config: {e}")

    col1, col2, col3 = st.columns(3)
    with col1:
        level = st.selectbox("Analysis Level", list(config_data.keys()), key="level_marker")
    with col2:
        types = list(config_data.get(level, {}).keys())
        a_type = st.selectbox("Analysis Type", types, key="type_marker")
    with col3:
        blocks = config_data.get(level, {}).get(a_type, [])
        block = st.selectbox("Block Label", blocks, key="block_marker")

    psi_cutoff = st.slider("Ψ cutoff", 0.0, 1.0, 0.5, 0.05, key="psi_cutoff_marker")
    psi_block_cutoff = st.slider("Ψ-block cutoff", 0.0, 1.0, 0.5, 0.05, key="psi_block_cutoff_marker")

    if st.button("Fetch Marker Genes", key="fetch_marker"):
        params = {
            "analysis_level": level,
            "analysis_type": a_type,
            "block_label": block,
            "psi_cutoff": psi_cutoff,
            "psi_block_cutoff": psi_block_cutoff,
        }
        res = requests.get(f"{API_URL}/marker", params=params)
        if res.status_code == 200:
            df = pd.read_csv(res.url)
            st.success(f"Loaded {len(df)} marker genes.")
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.error(f"Error {res.status_code} fetching data.")

            
            # --- Footer styling and content ---
st.markdown(
    """
    <style>
        .footer {
            position: relative;
            bottom: 0;
            width: 100%;
            padding: 20px 10px 10px 10px;
            text-align: center;
            color: #6b7280;
            font-size: 14px;
            border-top: 1px solid #e5e7eb;
            margin-top: 60px;
        }
        .footer a {
            color: #4f46e5;
            text-decoration: none;
            font-weight: 500;
        }
        .footer a:hover {
            text-decoration: underline;
        }
    </style>

    <div class="footer">
        <p><strong>Developed by:</strong> Nikhila P. Swarna, Pachter Lab, Caltech</p>
        <p>© 2025 Pachter Lab · Licensed under <a href="https://opensource.org/licenses/BSD-2-Clause" target="_blank">BSD-2</a> · 
           Part of the <a href="https://www.igvf.org" target="_blank">IGVF Consortium</a></p>

        <p>Data from this website can be programmatically accessed using 8cubeDB API 
           <a href="https://eightcubedb.onrender.com/docs" target="_blank">🔗 API Docs</a></p>

        <p><a href="https://github.com/pachterlab/8cubeDB" target="_blank">🔗 View API GitHub</a></p>

        <p>Specificity analyses done using ember. 
           <a href="https://github.com/pachterlab/ember" target="_blank">🔗 ember GitHub</a></p>

        <p><strong>If you use this website, please cite the following papers:</strong></p>
        <p>
            • Rebboah E, et al. <em>Systematic cell-type resolved transcriptomes of 8 tissues in 8 lab and wild-derived mouse strains captures global and local expression variation.</em> (2025)<br>
            • Swarna NP, et al. <em>Determining gene specificity from multivariate single-cell RNA sequencing data.</em> (2025)
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
