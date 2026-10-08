import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.library.store import get_library, DocumentLibrary, LibraryError, parse_orders
from app.agents.loop import execute_tool, run_loop
from test_library_parsing import pdf_file
from test_agent_loop import ScriptedModel, call, text


def test_exact_csv_persistence_conflicts_and_scope():
    lib = get_library()
    doc = lib.ingest('orders.csv', b'order_id,status,amount\n00123,delivered,12.50 EUR\n00123,returned,12.50 EUR\n')
    assert doc['record_count'] == 2 and doc['warnings']
    reopened = DocumentLibrary(lib.directory)
    result = reopened.lookup('00123')
    assert result['total_matches'] == 2
    assert result['matches'][0]['fields']['amount'] == '12.50 EUR'
    assert not reopened.lookup('123')['found']
    assert not execute_tool('get_order', {'order_id': 'BH-1003'})['found']
    assert not reopened.lookup('00123', [])['has_documents']
    assert lib.ingest('orders.csv', b'order_id,status,amount\n00123,delivered,12.50 EUR\n00123,returned,12.50 EUR\n')['duplicate']
    lib.set_active(doc['document_id'], False)
    with pytest.raises(LibraryError):
        lib.scope([doc['document_id']])
    lib.set_active(doc['document_id'], True)
    assert lib.lookup('00123')['found']


def test_pdf_pages_selection_and_no_builtin_fallback(tmp_path):
    lib = get_library()
    doc = lib.ingest('returns.pdf', pdf_file(tmp_path, ['', 'Returns: 45 days. Unused goods only.']).read_bytes())
    hit = lib.search('returns')['matches'][0]
    assert hit['page'] == 2 and '45 days' in hit['text']
    assert hit['url'].endswith('#page=2') and doc['warnings']
    assert execute_tool('get_order', {'order_id': 'BH-1003'})['error'] == 'no_csv_selected'
    assert not lib.search('returns', [])['matches']
    assert not lib.search('unrelatedxyz')['matches']


@pytest.mark.parametrize('content', [b'order_id,status\n', b'order_id,status\n1,x,extra\n', b'order_id,order_id\n1,2\n', b'order_id,status\n,x\n'])
def test_invalid_csv_is_atomic(content):
    lib = get_library()
    with pytest.raises(LibraryError):
        lib.ingest('bad.csv', content)
    assert lib.list_documents() == []


def test_custom_column_delimiter_and_case():
    _, key, records, _ = parse_orders(b'Reference;State\nAb-01;shipped\n', 'Reference')
    assert key == 'Reference' and records[0][1] == 'Ab-01'
    lib = get_library()
    lib.ingest('custom.csv', b'Reference;State\nAb-01;shipped\n', 'Reference')
    assert not lib.lookup('ab-01')['found']
    with pytest.raises(LibraryError):
        parse_orders(b'Reference,State\nAb-01,shipped\n')


def test_api_upload_sources_archive_and_invalid_pdf():
    with TestClient(app) as client:
        response = client.post('/api/v1/documents', files={'file': ('orders.csv', b'order_id,note\n0001,<script>alert(1)</script>\n', 'text/csv')})
        assert response.status_code == 201, response.text
        doc = response.json()['document_id']
        assert len(client.get('/api/v1/documents').json()['documents']) == 1
        assert b'0001' in client.get(f'/api/v1/documents/{doc}/file').content
        preview = client.get(f'/api/v1/documents/{doc}/records/1')
        assert '<script>' not in preview.text and '&lt;script&gt;' in preview.text
        assert client.post('/api/v1/documents', files={'file': ('bad.pdf', b'not-pdf')}).status_code == 422
        assert client.patch(f'/api/v1/documents/{doc}', json={'active': False}).status_code == 200
        assert client.get(f'/api/v1/documents/{doc}/file').status_code == 404
        assert client.patch(f'/api/v1/documents/{doc}', json={'active': True}).status_code == 200


def test_loop_returns_uploaded_source_citations():
    doc = get_library().ingest('orders.csv', b'order_id,status\nUP-2001,delivered\n')
    model = ScriptedModel([call('get_order', {'order_id': 'UP-2001'}), text('Delivered [orders.csv, record 1].'),
                           call('submit_review', {'decision': 'approve', 'feedback': 'Verified record.'})])
    async def collect():
        return [e async for e in run_loop('Check UP-2001', [], model, document_ids=[doc['document_id']])]
    result = asyncio.run(collect())[-1]
    assert result['review_approved']
    assert result['citations'][0]['url'].endswith('/records/1')
    assert result['sources'] == ['orders.csv · record 1']
