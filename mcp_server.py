#!/usr/bin/env python3
"""8cubeDB MCP Server - Optimized for Render deployment with FastAPI"""

import httpx
from typing import Any
from urllib.parse import quote
from mcp.server import Server
from mcp.types import Tool, TextContent

API_URL = "https://eightcubedb.onrender.com"
# This is the object api.py will import
server = Server("8cubeDB-Explorer")
MAX_DISPLAY_ROWS = 50

# Metric explanations
METRICS_HELP = """
📊 Understanding 8cubeDB Metrics:

**Ψ (Psi)**: Information explained by partitioning [0-1]
  • How much of a gene's expression variation is captured by this partition
  • Based on entropy of gene counts across cells
  • High Ψ = gene expression well-explained by this partition
  • Low Ψ = gene expression not well-explained by this partition

**ζ (Zeta)**: Specificity concentration [0-1]
  • Is specificity concentrated in 1-2 blocks (high ζ) or spread across all blocks (low ζ)?
  • High ζ = gene specific to few blocks within partition
  • Low ζ = gene equally distributed across blocks
  • Note: Perfect specificity/non-specificity may not exist biologically!

**ψ_block (Psi-block)**: Block-specific assignment [0-1]
  • How specific a gene is to a particular block within a partition
  • High ψ_block = highly specific to that block
  • Low ψ_block = non-specific to that block
  • All ψ_block values sum to 1.0 across blocks

**Gene Categories** (based on metric pairs):
  • MARKER genes (specific to one block): HIGH ψ_block + HIGH Ψ
  • PARTITION-SPECIFIC genes: HIGH ζ + HIGH Ψ
  • HOUSEKEEPING genes (non-specific): LOW ζ + HIGH Ψ
"""

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_config",
            description=(
                "Shows available mouse strains, tissues, and partition types. "
                "Call with no args to see overview including all 8 mouse strains. "
                "Specify tissue or partition for details."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_level": {
                        "type": "string",
                        "description": "Optional: specific tissue to see its partitions (e.g., 'Liver')"
                    },
                    "analysis_type": {
                        "type": "string", 
                        "description": "Optional: specific partition to see its blocks (e.g., 'Strain')"
                    },
                    "show_metrics_help": {
                        "type": "boolean",
                        "description": "Set true to see Ψ, ζ, ψ_block explanations",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_gene_specificity",
            description=(
                "Analyzes Ψ (partition fit) and ζ (concentration) for a gene across all partitions. "
                "Identifies which partitions best explain gene expression patterns. "
                "High Ψ + High ζ = gene specific to few blocks in that partition."
            ),
            inputSchema={
                "type": "object",
                "properties": {"gene": {"type": "string", "description": "Gene name or Ensembl ID"}},
                "required": ["gene"]
            }
        ),
        Tool(
            name="get_psi_block",
            description=(
                "Shows ψ_block values: how specific a gene is to each block within a partition. "
                "Values sum to 1.0. High ψ_block = gene highly specific to that block."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "gene": {"type": "string"},
                    "analysis_level": {"type": "string", "description": "Tissue (e.g., 'Liver')"},
                    "analysis_type": {"type": "string", "description": "Partition (e.g., 'Celltype', 'Strain')"}
                },
                "required": ["gene", "analysis_level", "analysis_type"]
            }
        ),
        Tool(
            name="get_gene_expression",
            description="Shows mean/variance expression for a gene across blocks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "gene": {"type": "string"},
                    "analysis_level": {"type": "string"},
                    "analysis_type": {"type": "string"}
                },
                "required": ["gene", "analysis_level", "analysis_type"]
            }
        ),
        Tool(
            name="get_marker_genes",
            description=(
                "Finds MARKER genes for ONE specific block using HIGH ψ_block + HIGH Ψ. "
                "These genes are highly specific to the selected block. "
                "USE THIS for queries like: 'PWK_PhJ strain markers', 'hepatocyte markers', "
                "'female-specific genes'. "
                "IMPORTANT: Call get_config first if unsure of exact block_label spelling. "
                "Available strains: 129S1_SvImJ, AJ, BALB_cJ, C3H_HeJ, C57BL_6J, CAST_EiJ, NOD_ShiLtJ, PWK_PhJ"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_level": {"type": "string", "description": "Usually 'Across_tissues' for strain markers"},
                    "analysis_type": {"type": "string", "description": "'Strain' for strain markers"},
                    "block_label": {"type": "string", "description": "Exact strain/block name - check get_config if unsure"},
                    "psi_cutoff": {"type": "number", "default": 0.7, "description": "Min Ψ (partition fit) [0-1]"},
                    "psi_block_cutoff": {"type": "number", "default": 0.7, "description": "Min ψ_block (block specificity) [0-1]"}
                },
                "required": ["analysis_level", "analysis_type", "block_label"]
            }
        ),
        Tool(
            name="get_housekeeping_genes",
            description=(
                "Finds HOUSEKEEPING genes using HIGH Ψ + LOW ζ. "
                "These genes are well-explained by the partition but not specific to any block - "
                "expressed broadly/uniformly across all blocks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_level": {"type": "string"},
                    "analysis_type": {"type": "string"},
                    "psi_cutoff": {"type": "number", "default": 0.8, "description": "Min Ψ (partition fit) [0-1]"},
                    "zeta_cutoff": {"type": "number", "default": 0.2, "description": "Max ζ (specificity concentration) [0-1]"}
                },
                "required": ["analysis_level", "analysis_type"]
            }
        ),
        Tool(
            name="get_highly_specific_genes",
            description=(
                "Finds PARTITION-SPECIFIC genes using HIGH Ψ + HIGH ζ. "
                "These genes are well-explained by the partition AND concentrated in few blocks. "
                "Use for discovery: 'genes that vary by strain' (not 'PWK_PhJ markers'). "
                "Does NOT tell which specific blocks - use get_psi_block after to see block assignments."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_level": {"type": "string"},
                    "analysis_type": {"type": "string"},
                    "psi_cutoff": {"type": "number", "default": 0.7, "description": "Min Ψ (partition fit) [0-1]"},
                    "zeta_cutoff": {"type": "number", "default": 0.7, "description": "Min ζ (specificity concentration) [0-1]"}
                },
                "required": ["analysis_level", "analysis_type"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    
    if name == "get_config":
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/config")
            response.raise_for_status()
            config = response.json().get("analysis_config", {})
        
        level = arguments.get("analysis_level")
        atype = arguments.get("analysis_type")
        show_help = arguments.get("show_metrics_help", False)
        
        # Show metrics help if requested
        if show_help:
            return [TextContent(type="text", text=METRICS_HELP)]
        
        # Filtered query - just what's needed
        if level and atype:
            # Show blocks for specific tissue/partition
            blocks = config.get(level, {}).get(atype, [])
            if not blocks:
                return [TextContent(type="text", text=f"No data for {level}/{atype}")]
            
            result = f"{level}/{atype} blocks ({len(blocks)}):\n{', '.join(blocks)}"
            
            # Add strain info if this is a Strain partition
            if atype == "Strain":
                result += "\n\nStrains: 129S1_SvImJ, AJ, BALB_cJ, C3H_HeJ, C57BL_6J, CAST_EiJ, NOD_ShiLtJ, PWK_PhJ"
            
            return [TextContent(type="text", text=result)]
        
        elif level:
            # Show partitions for specific tissue
            partitions = config.get(level, {})
            if not partitions:
                return [TextContent(type="text", text=f"No data for {level}")]
            summary = f"{level} partitions: {', '.join(partitions.keys())}"
            return [TextContent(type="text", text=summary)]
        
        else:
            # Overview - show strains prominently
            tissues = list(config.keys())
            all_types = set()
            for tissue_data in config.values():
                all_types.update(tissue_data.keys())
            
            summary = "8cubeDB Overview\n\n"
            summary += "Mouse Strains: 129S1_SvImJ, AJ, BALB_cJ, C3H_HeJ, C57BL_6J, CAST_EiJ, NOD_ShiLtJ, PWK_PhJ\n\n"
            summary += f"Tissues: {', '.join(tissues)}\n"
            summary += f"Partitions: {', '.join(sorted(all_types))}\n\n"
            summary += "Call get_config(analysis_level='Liver') for details\n"
            summary += "Call get_config(show_metrics_help=True) for Ψ, ζ, ψ_block info"
            
            return [TextContent(type="text", text=summary)]
    
    elif name == "get_gene_specificity":
        gene = arguments["gene"]
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{API_URL}/specificity", params=[("gene_list", gene)])
            response.raise_for_status()
            csv_data = response.text
        
        lines = csv_data.strip().split('\n')
        if len(lines) <= 1:
            return [TextContent(type="text", text=f"No data for '{gene}'")]
        
        header = lines[0].split(',')
        rows = [line.split(',') for line in lines[1:]]
        
        # Find top 3 patterns only
        patterns = []
        for row in rows:
            row_dict = dict(zip(header, row))
            try:
                psi = float(row_dict.get('Psi_mean', 0))
                zeta = float(row_dict.get('Zeta_mean', 0))
                if psi > 0.5 or zeta > 0.5:
                    patterns.append({
                        'level': row_dict.get('Analysis_level', ''),
                        'type': row_dict.get('Analysis_type', ''),
                        'psi': psi,
                        'zeta': zeta,
                        'score': psi + zeta
                    })
            except:
                continue
        
        patterns.sort(key=lambda x: x['score'], reverse=True)
        
        analysis = f"{gene} - Top partitions:\n"
        for i, p in enumerate(patterns[:3], 1):
            analysis += f"{i}. {p['level']}/{p['type']}: Ψ={p['psi']:.2f}, ζ={p['zeta']:.2f}\n"
            if p['psi'] >= 0.7 and p['zeta'] >= 0.7:
                analysis += "   → Partition-specific\n"
            elif p['psi'] >= 0.7 and p['zeta'] <= 0.3:
                analysis += "   → Housekeeping-like\n"
        
        analysis += f"\nΨ=partition fit, ζ=concentration\n"
        analysis += f"\n📥 {API_URL}/specificity?gene_list={quote(gene)}\n"
        return [TextContent(type="text", text=analysis)]
    
    elif name == "get_psi_block":
        gene = arguments["gene"]
        level = arguments["analysis_level"]
        atype = arguments["analysis_type"]
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{API_URL}/psi_block", 
                params=[("gene_list", gene), ("analysis_level", level), ("analysis_type", atype)])
            response.raise_for_status()
            csv_data = response.text
        
        lines = csv_data.strip().split('\n')
        if len(lines) <= 1:
            return [TextContent(type="text", text=f"No data")]
        
        header = lines[0].split(',')
        values = lines[1].split(',')
        
        block_values = []
        for i, col in enumerate(header):
            if col not in ['gene_name', 'ensembl_id']:
                try:
                    block_values.append((col, float(values[i])))
                except:
                    continue
        
        block_values.sort(key=lambda x: x[1], reverse=True)
        
        analysis = f"{gene} in {level}/{atype}:\n"
        for block, val in block_values[:10]:
            bar = "█" * int(val * 20)
            analysis += f"  {block:20s} {val:.3f} {bar}\n"
        if len(block_values) > 10:
            analysis += f"  ... {len(block_values)-10} more blocks\n"
        
        analysis += f"\n📥 {API_URL}/psi_block?gene_list={quote(gene)}&analysis_level={quote(level)}&analysis_type={quote(atype)}\n"
        return [TextContent(type="text", text=analysis)]
    
    elif name == "get_gene_expression":
        gene = arguments["gene"]
        level = arguments["analysis_level"]
        atype = arguments["analysis_type"]
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{API_URL}/gene_expression",
                params=[("gene_list", gene), ("analysis_level", level), ("analysis_type", atype)])
            response.raise_for_status()
            csv_data = response.text
        
        lines = csv_data.strip().split('\n')
        if len(lines) <= 1:
            return [TextContent(type="text", text=f"No data")]
        
        header = lines[0].split(',')
        values = lines[1].split(',')
        
        expr_data = []
        mean_cols = [(i, h) for i, h in enumerate(header) if h.startswith('mean_')]
        for idx, col in mean_cols:
            block = col.replace('mean_', '')
            try:
                expr_data.append({'block': block, 'mean': float(values[idx])})
            except:
                continue
        
        expr_data.sort(key=lambda x: x['mean'], reverse=True)
        
        # Top 10 only
        analysis = f"{gene} in {level}/{atype}:\n"
        for d in expr_data[:10]:
            analysis += f"  {d['block']:20s} {d['mean']:>8.1f}\n"
        if len(expr_data) > 10:
            analysis += f"  ... {len(expr_data)-10} more\n"
        
        analysis += f"\n📥 {API_URL}/gene_expression?gene_list={quote(gene)}&analysis_level={quote(level)}&analysis_type={quote(atype)}\n"
        return [TextContent(type="text", text=analysis)]
    
    elif name == "get_marker_genes":
        level = arguments["analysis_level"]
        atype = arguments["analysis_type"]
        block = arguments["block_label"]
        psi_cut = arguments.get("psi_cutoff", 0.7)
        psi_block_cut = arguments.get("psi_block_cutoff", 0.7)
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(f"{API_URL}/marker",
                    params={"analysis_level": level, "analysis_type": atype, 
                           "block_label": block, "psi_cutoff": psi_cut, "psi_block_cutoff": psi_block_cut})
                response.raise_for_status()
                csv_data = response.text
            
            lines = csv_data.strip().split('\n')
            if len(lines) <= 1:
                return [TextContent(type="text", text=f"No markers for {block}. Try lower cutoffs or check block name with get_config.")]
            
            count = len(lines) - 1
            
            analysis = f"{block} markers ({count} genes, Ψ≥{psi_cut}, ψ_block≥{psi_block_cut}):\n"
            
            if count > 0:
                genes_list = [lines[i].split(',')[0] for i in range(1, min(21, len(lines)))]
                analysis += ', '.join(genes_list)
                if count > 20:
                    analysis += f" ... +{count-20} more"
            
            analysis += f"\n\n📥 {API_URL}/marker?analysis_level={quote(level)}&analysis_type={quote(atype)}&block_label={quote(block)}&psi_cutoff={psi_cut}&psi_block_cutoff={psi_block_cut}\n"
            
            return [TextContent(type="text", text=analysis)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}\n\nTip: Check exact block name with get_config")]
    
    elif name == "get_housekeeping_genes":
        level = arguments["analysis_level"]
        atype = arguments["analysis_type"]
        psi_cut = arguments.get("psi_cutoff", 0.8)
        zeta_cut = arguments.get("zeta_cutoff", 0.2)
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(f"{API_URL}/non_specific",
                    params={"analysis_level": level, "analysis_type": atype, 
                           "psi_cutoff": psi_cut, "zeta_cutoff": zeta_cut})
                response.raise_for_status()
                csv_data = response.text
            
            lines = csv_data.strip().split('\n')
            if len(lines) <= 1:
                # Try permissive
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(f"{API_URL}/non_specific",
                        params={"analysis_level": level, "analysis_type": atype, 
                               "psi_cutoff": 0.7, "zeta_cutoff": 0.3})
                    response.raise_for_status()
                    csv_data = response.text
                lines = csv_data.strip().split('\n')
                psi_cut, zeta_cut = 0.7, 0.3
            
            if len(lines) <= 1:
                return [TextContent(type="text", text="No housekeeping genes found even with relaxed cutoffs.")]
            
            count = len(lines) - 1
            
            analysis = f"Housekeeping in {level}/{atype} ({count} genes, Ψ≥{psi_cut}, ζ≤{zeta_cut}):\n"
            
            if count > 0:
                genes_list = [lines[i].split(',')[0] for i in range(1, min(21, len(lines)))]
                analysis += ', '.join(genes_list)
                if count > 20:
                    analysis += f" ... +{count-20} more"
            
            analysis += f"\n\n📥 {API_URL}/non_specific?analysis_level={quote(level)}&analysis_type={quote(atype)}&psi_cutoff={psi_cut}&zeta_cutoff={zeta_cut}\n"
            
            return [TextContent(type="text", text=analysis)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "get_highly_specific_genes":
        level = arguments["analysis_level"]
        atype = arguments["analysis_type"]
        psi_cut = arguments.get("psi_cutoff", 0.7)
        zeta_cut = arguments.get("zeta_cutoff", 0.7)
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(f"{API_URL}/highly_specific",
                    params={"analysis_level": level, "analysis_type": atype,
                           "psi_cutoff": psi_cut, "zeta_cutoff": zeta_cut})
                response.raise_for_status()
                csv_data = response.text
            
            lines = csv_data.strip().split('\n')
            if len(lines) <= 1:
                return [TextContent(type="text", text="No highly specific genes. Try lower cutoffs.")]
            
            count = len(lines) - 1
            
            analysis = f"Partition-specific in {level}/{atype} ({count} genes, Ψ≥{psi_cut}, ζ≥{zeta_cut}):\n"
            
            if count > 0:
                genes_list = [lines[i].split(',')[0] for i in range(1, min(21, len(lines)))]
                analysis += ', '.join(genes_list)
                if count > 20:
                    analysis += f" ... +{count-20} more"
            
            analysis += f"\n\nUse get_psi_block to see which blocks.\n"
            analysis += f"\n📥 {API_URL}/highly_specific?analysis_level={quote(level)}&analysis_type={quote(atype)}&psi_cutoff={psi_cut}&zeta_cutoff={zeta_cut}\n"
            
            return [TextContent(type="text", text=analysis)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    else:
        raise ValueError(f"Unknown tool: {name}")