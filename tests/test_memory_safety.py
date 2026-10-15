"""Synthetic contract/regression tests; no production DB writes."""
import asyncio
import csv
from contextlib import closing
import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
path = str(Path(_tmp.name) / 'fixture.db')
conn = sqlite3.connect(path)
conn.executescript('''
CREATE TABLE table_1(gene_name TEXT, ensembl_id TEXT, Analysis_level TEXT,
 Analysis_type TEXT, Psi_mean REAL, Psi_std REAL, Zeta_mean REAL, Zeta_std REAL);
CREATE TABLE Kidney_Strain(gene_name TEXT, ensembl_id TEXT, PWKJ REAL, B6J REAL);
''')
for i in range(1105):
    # duplicate names and tied values exercise original JOIN multiplicity/order.
    conn.execute('INSERT INTO table_1 VALUES(?,?,?,?,?,?,?,?)',
                 [f'Gene{i//2}', f'ENS{i}', 'Kidney', 'Strain', .8, .01, .6, None])
    conn.execute('INSERT INTO Kidney_Strain VALUES(?,?,?,?)',
                 [f'Gene{i//2}', f'ENS{i}', .75, .25])
conn.commit(); conn.close()
os.environ['DB_FILE'] = path
os.environ['GENE_EXPR_DB_FILE'] = path
import api
from fastapi.testclient import TestClient
from memory_metrics import RequestMetrics


def records(response):
    return list(csv.reader(io.StringIO(response.text)))


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)
        self.params = {'analysis_level': 'Kidney', 'analysis_type': 'Strain'}

    def test_full_filtered_and_case_insensitive(self):
        response = self.client.get('/psi_block', params={**self.params, 'gene_list': 'gEnE1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(records(response)), 3)
        self.assertNotIn('X-Page-Limit', response.headers)

    def test_complete_results_reproduce_original_join(self):
        response = self.client.get('/marker', params={**self.params, 'block_label': 'PWKJ'})
        self.assertEqual(response.status_code, 200)
        with closing(sqlite3.connect(path)) as conn:
            expected = conn.execute('''SELECT T1.*,T2.PWKJ FROM table_1 T1
                JOIN Kidney_Strain T2 ON T1.gene_name=T2.gene_name
                WHERE T1.Analysis_level='Kidney' AND T1.Analysis_type='Strain'
                AND T1.Psi_mean>.5 AND T2.PWKJ>.5
                ORDER BY T1.Psi_mean DESC,T2.PWKJ DESC''').fetchall()
        output = io.StringIO(); csv.writer(output).writerows(expected)
        self.assertEqual(records(response)[1:], list(csv.reader(io.StringIO(output.getvalue()))))
        self.assertGreater(len(expected), 1000)

    def test_unfiltered_requests_remain_complete(self):
        for route in ['/psi_block', '/gene_expression', '/highly_specific']:
            response = self.client.get(route, params=self.params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(records(response))-1, 1105)
            self.assertNotIn('X-Page-Limit', response.headers)

    def test_sql_values_and_identifiers_safe(self):
        response = self.client.get('/psi_block', params={**self.params, 'gene_list': "' OR 1=1 --"})
        self.assertEqual(len(records(response)), 1)
        response = self.client.get('/marker', params={**self.params, 'block_label': 'PWKJ" OR 1=1 --'})
        self.assertEqual(response.status_code, 500)

    def test_mcp_endpoints(self):
        self.assertEqual(self.client.get('/mcp/health').status_code, 200)
        for method in ['initialize','tools/list']:
            response=self.client.post('/mcp/messages',json={'jsonrpc':'2.0','id':1,'method':method})
            self.assertEqual(response.status_code,200)
            self.assertIn('result',response.json())

    def test_metadata_and_empty_csv(self):
        self.assertEqual(self.client.get('/config').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)
        response = self.client.get('/highly_specific', params={**self.params, 'psi_cutoff': 1})
        self.assertEqual(len(records(response)), 1)


class MetricsTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_rate_or_concurrency_limits(self):
        async def app(scope, receive, send):
            await asyncio.sleep(0)
            await send({'type':'http.response.start', 'status':200, 'headers':[]})
        metrics = RequestMetrics(app)
        messages=[]
        async def send(message): messages.append(message)
        scope={'type':'http','path':'/marker','client':('researcher',1)}
        await asyncio.gather(*(metrics(scope,None,send) for _ in range(150)))
        self.assertEqual([m['status'] for m in messages], [200]*150)
        self.assertEqual(metrics.active, 0)

    async def test_disconnect_closes_database_connection(self):
        connection=sqlite3.connect(path,check_same_thread=False)
        response=api.csv_query(lambda:connection,'SELECT * FROM table_1',[],'test.csv')
        async def send(message):
            if message['type']=='http.response.body': raise OSError('client disconnected')
        async def receive(): await asyncio.Event().wait()
        with self.assertRaises(Exception):
            await response({'type':'http','asgi':{'spec_version':'2.4'}},receive,send)
        with self.assertRaises(sqlite3.ProgrammingError): connection.execute('SELECT 1')

    async def test_cancellation_restores_active_count(self):
        started=asyncio.Event()
        async def app(scope,receive,send):
            started.set(); await asyncio.Event().wait()
        metrics=RequestMetrics(app)
        task=asyncio.create_task(metrics({'type':'http','path':'/marker'},None,None))
        await started.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(metrics.active,0)


if __name__ == '__main__': unittest.main()
