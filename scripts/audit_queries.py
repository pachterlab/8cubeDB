"""Read-only real-DB regression/benchmark. Run from the API directory.

DB_FILE=../8cube.db GENE_EXPR_DB_FILE=../mean_var_DB.db python scripts/audit_queries.py
Compares complete CSV to the original SQL+pandas path, with exact float parsing.
Use --memory old|new to isolate peak RSS for the a broad expression request.
"""
import argparse
import asyncio
from contextlib import closing
import io
import json
import hashlib
import os
from pathlib import Path
from urllib.parse import urlencode
import sqlite3
import sys
import time
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
parser = argparse.ArgumentParser()
parser.add_argument('--memory', choices=['old','new','reference'])
parser.add_argument('--concurrent', type=int, default=1)
parser.add_argument('--analysis-level', default='Across_tissues')
parser.add_argument('--analysis-type', default='Sex:Strain:Tissue')
args = parser.parse_args()
started = time.monotonic()
# ru_maxrss may inherit the tool launcher's high-water mark across exec.
# Sample this process's current RSS instead for comparable fresh-process peaks.
peak_rss = [0.0]
def sample_rss():
    while True:
        with open('/proc/self/statm') as handle:
            current = int(handle.read().split()[1])*os.sysconf('SC_PAGE_SIZE')/1048576
        peak_rss[0] = max(peak_rss[0], current)
        time.sleep(.005)
threading.Thread(target=sample_rss, daemon=True).start()

if args.memory == 'reference':
    # Chunk the original SQL+pandas serializer only to validate very wide tables
    # without reproducing their multi-gigabyte original full-table allocation.
    import pandas as pd
    table=(args.analysis_level+'_'+args.analysis_type).replace('"','""')
    digest=hashlib.sha256();rows=size=0;first=True
    with closing(sqlite3.connect('file:'+os.path.abspath(os.environ['GENE_EXPR_DB_FILE'])+'?mode=ro',uri=True)) as conn:
        for frame in pd.read_sql_query(f'SELECT * FROM "{table}"',conn,chunksize=128):
            chunk=frame.to_csv(index=False,header=first).encode('utf-8')
            first=False;rows+=len(frame);size+=len(chunk);digest.update(chunk)
    print(json.dumps({'mode':'reference','rows':rows,'sha256':digest.hexdigest(),
                      'csv_mb':size/1048576,'duration_s':time.monotonic()-started}))
    sys.exit()

if args.memory == 'old':
    import pandas as pd
    with closing(sqlite3.connect('file:'+os.path.abspath(os.environ['GENE_EXPR_DB_FILE'])+'?mode=ro',uri=True)) as conn:
        table = (args.analysis_level + '_' + args.analysis_type).replace('"', '""')
        df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
    frame_mb = df.memory_usage(deep=True).sum()/1048576
    buffer = io.StringIO(); df.to_csv(buffer,index=False)
    digest = hashlib.sha256()
    buffer.seek(0)
    for line in buffer: digest.update(line.encode('utf-8'))
    print(json.dumps({'sha256':digest.hexdigest(), 'mode':'old','rows':len(df),'columns':len(df.columns),
                      'dataframe_mb':frame_mb, 'csv_mb':buffer.tell()/1048576,
                      'peak_rss_mb':peak_rss[0],
                      'duration_s':time.monotonic()-started}))
    sys.exit()

import api
from fastapi.testclient import TestClient
client = TestClient(api.app)
if args.memory == 'new':
    # Consume the actual ASGI response with backpressure, without buffering
    # the 178 MB download in a test HTTP client inside the server process.
    async def consume():
        digest=hashlib.sha256(); stats={'bytes':0,'lines':0}
        async def receive(): await asyncio.Event().wait()
        async def send(message):
            if message['type']=='http.response.start':
                assert message['status']==200, message
            elif message['type']=='http.response.body':
                chunk=message.get('body',b'')
                digest.update(chunk)
                stats['bytes']+=len(chunk);stats['lines']+=chunk.count(b'\n')
                await asyncio.sleep(0)
        scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},
               'http_version':'1.1','method':'GET','scheme':'http','path':'/gene_expression',
               'raw_path':b'/gene_expression','root_path':'','headers':[],
               'query_string':urlencode({'analysis_level':args.analysis_level,
                                         'analysis_type':args.analysis_type}).encode(),
               'server':('test',80),'client':('researcher',1)}
        await api.app(scope,receive,send)
        return {'rows':stats['lines']-1,'sha256':digest.hexdigest(),
                'csv_mb':stats['bytes']/1048576}
    async def run():
        return await asyncio.gather(*(consume() for _ in range(args.concurrent)))
    results=asyncio.run(run())
    print(json.dumps({'mode':'new','responses':results,
                      'startup_and_request_peak_rss_mb':peak_rss[0],
                      'duration_s':time.monotonic()-started}))
    sys.exit()

import pandas as pd
from pandas.testing import assert_frame_equal


def check(route, params, sql, values, expression=False):
    start = time.monotonic()
    path = api.GENE_EXPR_DB_FILE if expression else api.DB_FILE
    with closing(sqlite3.connect("file:"+os.path.abspath(path)+"?mode=ro",uri=True)) as conn:
        original = pd.read_sql_query(sql,conn,params=values)
    # Match the exact former pandas CSV serialization, then parse both paths
    # with round-trip precision before comparing all numbers, columns and order.
    expected = pd.read_csv(io.StringIO(original.to_csv(index=False)),float_precision='round_trip')
    response=client.get(route,params=params)
    response.raise_for_status()
    expected_csv=original.to_csv(index=False)
    assert expected_csv == response.text, f"CSV bytes differ for {route} {params}"
    actual=pd.read_csv(io.StringIO(response.text),float_precision='round_trip')
    assert_frame_equal(expected,actual,check_exact=True,check_dtype=False)
    print(json.dumps({'route':route,'params':params,'rows':len(actual),
                      'exact_numeric_match':True,'identical_csv':True,
                      'duration_s':round(time.monotonic()-start,3)}),flush=True)


# Manuscript Fig. 1 strain genes and cell-type housekeeping gene (PMC12667802),
# plus the repository's extract_functions notebook examples.
for route,expr in [('/psi_block',False),('/gene_expression',True)]:
    genes=['Cwc22','Gjb4','Akr1c21','Akap13']
    slots=','.join('?' for _ in genes)
    check(route,{'analysis_level':'Across_tissues','analysis_type':'Strain','gene_list':genes},
          f'SELECT * FROM "Across_tissues_Strain" WHERE gene_name COLLATE NOCASE IN ({slots}) OR ensembl_id COLLATE NOCASE IN ({slots})',
          genes+genes,expr)
for route,expr in [('/psi_block',False),('/gene_expression',True)]:
    genes=['Mpped1','Akr1c6','Neurog2','Akap13']
    slots=','.join('?' for _ in genes)
    check(route,{'analysis_level':'Kidney','analysis_type':'Sex:Celltype','gene_list':genes},
          f'SELECT * FROM "Kidney_Sex:Celltype" WHERE gene_name COLLATE NOCASE IN ({slots}) OR ensembl_id COLLATE NOCASE IN ({slots})',
          genes+genes,expr)
check('/specificity',{'gene_list':['Cwc22','Gjb4','Akap13']},
      'SELECT * FROM table_1 WHERE gene_name COLLATE NOCASE IN (?,?,?) OR ensembl_id COLLATE NOCASE IN (?,?,?)',
      ['Cwc22','Gjb4','Akap13']*2)
for route,zeta,comparison,direction,psi in [('/highly_specific',.4,'>','DESC',.4),('/non_specific',.3,'<','ASC',.7)]:
    check(route,{'analysis_level':'Kidney','analysis_type':'Strain','psi_cutoff':psi,'zeta_cutoff':zeta},
          f'SELECT * FROM table_1 WHERE Analysis_level=? AND Analysis_type=? AND Psi_mean>? AND Zeta_mean{comparison}? ORDER BY Psi_mean DESC,Zeta_mean {direction}',
          ['Kidney','Strain',psi,zeta])
for level in ['Kidney','Across_tissues']:
    check('/marker',{'analysis_level':level,'analysis_type':'Strain','block_label':'PWKJ'},
          f'SELECT T1.*,T2.PWKJ FROM table_1 T1 JOIN "{level}_Strain" T2 ON T1.gene_name=T2.gene_name WHERE T1.Analysis_level=? AND T1.Analysis_type=? AND T1.Psi_mean>? AND T2.PWKJ>? ORDER BY T1.Psi_mean DESC,T2.PWKJ DESC',
          [level,'Strain',.5,.5])
# Broad zero-cutoff result verifies complete, untruncated ranked results.
check('/highly_specific',{'analysis_level':'Kidney','analysis_type':'Strain','psi_cutoff':0,'zeta_cutoff':0},
      'SELECT * FROM table_1 WHERE Analysis_level=? AND Analysis_type=? AND Psi_mean>? AND Zeta_mean>? ORDER BY Psi_mean DESC,Zeta_mean DESC',
      ['Kidney','Strain',0,0])
