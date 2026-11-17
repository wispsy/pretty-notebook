"""Exercise notebook publication policy against the real installed transport."""

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import pytest

from pretty_notebook import Notebook
from pretty_notebook._internal import http


@pytest.fixture
def endpoint():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_call(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            calls.append((self.command, self.path, len(body)))
            if self.path == '/redirect':
                self.send_response(307)
                self.send_header('Location', '/echo')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            value = {'size': len(body), 'body': body.decode() if len(body) < 1024 else '',
                     'content_type': self.headers.get('Content-Type'),
                     'authorization': self.headers.get('Authorization')}
            data = json.dumps(value).encode()
            self.send_response(404 if self.path == '/missing' else 200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Receipt', 'checked')
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = handle_call

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_real_json_forms_queries_headers_and_checked_errors(endpoint, tmp_path, monkeypatch):
    base, calls = endpoint
    monkeypatch.setenv('PNBP_SETTINGS', 'off')
    nb = Notebook(tmp_path, {'API_BASE': base})
    response = nb._api_request(http.post, '/echo', json={'aliases': ('café', 'two')},
                               headers={'Authorization': 'Bearer synthetic'})
    assert json.loads(response.json()['body']) == {'aliases': ['café', 'two']}
    assert response.json()['authorization'] == 'Bearer synthetic'
    form = http.post(base+'/echo', data={'name': 'café', 'tag': ['one','two']}).json()
    assert parse_qs(form['body']) == {'name': ['café'], 'tag': ['one','two']}
    assert form['content_type'] == 'application/x-www-form-urlencoded'
    nb._api_request(http.get, '/echo', params=[('tag','one'),('tag','two')])
    assert calls[-1][1] == '/echo?tag=one&tag=two'
    with pytest.raises(http.HTTPError) as rejected:
        nb._api_request(http.get, '/missing')
    assert rejected.value.response is not None
    assert rejected.value.response.status_code == 404
    assert rejected.value.response.headers['x-receipt'] == 'checked'


def test_supported_ten_mib_image_keeps_file_ownership(endpoint):
    base, calls = endpoint
    image = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'x' * (10*1024*1024 - 8))
    try:
        response = http.put(base+'/echo', files={'file': ('image.png', image, 'image/png')})
        response.raise_for_status()
        assert 10*1024*1024 < response.json()['size'] < http.MAX_REQUEST_BYTES
        assert response.json()['content_type'].startswith('multipart/form-data; boundary=')
        assert not image.closed and len(calls) == 1
    finally:
        image.close()


def test_oversized_image_fails_before_dispatch_without_closing_caller_file(endpoint):
    base, calls = endpoint
    with io.BytesIO(b'x' * http.MAX_REQUEST_BYTES) as image:
        with pytest.raises(http.RequestException, match='selected policy'):
            http.post(base+'/echo', files={'file': ('large.png', image, 'image/png')})
        assert not image.closed and not calls


def test_mutation_redirect_is_not_replayed(endpoint):
    base, calls = endpoint
    response = http.post(base+'/redirect', json={'once': True})
    assert response.status_code == 307
    assert [call[:2] for call in calls] == [('POST', '/redirect')]


def test_timeout_selection_and_transport_cleanup_on_failure(monkeypatch):
    selected, closed = {}, []
    class Session:
        def __init__(self, **kwargs): selected.update(kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): closed.append(True)
        def request(self, *args, **kwargs): raise http.ConnectionError('synthetic failure')
    monkeypatch.setattr(http.requ, 'Session', Session)
    with pytest.raises(http.ConnectionError):
        http.get('https://example.invalid', timeout=(2, 7))
    assert selected == {'timeout': (2, 7), 'max_request_bytes': http.MAX_REQUEST_BYTES,
                        'max_bytes': http.MAX_RESPONSE_BYTES, 'trust_env': False}
    assert closed == [True]
