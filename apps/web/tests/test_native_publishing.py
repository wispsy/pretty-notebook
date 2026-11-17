"""Native publishing routing, wire ordering and owned upload acceptance."""

import asyncio
from functools import partial

from expose_api import TestClient as AsyncClient

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.mark.parametrize('web_framework', ['expose-api'], indirect=True)
def test_native_publishing_bypasses_baseline_routes(web_storage, root_credentials, bootstrap_headers, monkeypatch):
    app = create_app(db_url='sqlite://:memory:', framework='expose-api')
    async def refused(scope, receive, send):
        raise AssertionError('The baseline HTTP router handled a native publication')
    with TestClient(app) as client:
        assert client.post('/api/users', json=root_credentials, headers=bootstrap_headers).status_code == 200
        token = client.post('/api/token', data={'username': root_credentials['username'],
                                             'password': root_credentials['password_hash']}).json()['access_token']
        headers = {'Authorization': 'Bearer ' + token}
        monkeypatch.setattr(app.baseline, 'middleware_stack', refused)
        response = client.post('/api/publishment', json={'name': 'one', 'content': '<p>Native</p>'}, headers=headers)
        assert response.status_code == 201 and response.headers['X-PNBP-Operation-ID']
        assert client.get('/api/publishments', headers=headers).json()[0]['pub_name'] == 'one.html'
        assert client.get('/api/publishing/capabilities', headers=headers).json()['checked_images']
        assert client.get('/api/publishing/inventory', headers=headers).json()['pages'][0]['pub_name'] == 'one.html'
        assert client.post('/api/image', headers=headers,
            files={'file': ('native.png', b'\x89PNG\r\n\x1a\nimage', 'image/png')}).status_code == 201
        assert client.get('/api/images', headers=headers).json()[0]['img_name'] == 'native.png'
        assert client.delete('/api/publishment/one.html', headers=headers).status_code == 200
        assert client.portal.call(partial(app.state.publications.inventory)) == []


@pytest.mark.parametrize('web_framework', ['fastapi'], indirect=True)
@pytest.mark.parametrize('authenticated', [False, True])
def test_wire_and_semantic_validation_transcripts_match(web_storage, tmp_path, root_credentials, bootstrap_headers, authenticated):
    database = f'sqlite://{tmp_path / "wire.sqlite3"}'
    cases = [
        ('/api/publishment', {'content': '{', 'headers': {'Content-Type': 'application/json'}}),
        ('/api/publishment', {}), ('/api/publishment', {'content': 'null', 'headers': {'Content-Type': 'application/json'}}),
        ('/api/publishment', {'json': []}),
        ('/api/publishment', {'json': {}}), ('/api/image', {}),
        ('/api/image', {'data': {'file': 'oops'}}),
        ('/api/image', {'content': b'invalid', 'headers': {'Content-Type': 'multipart/form-data; boundary=missing'}}),
        ('/api/image', {'content': b'invalid', 'headers': {'Content-Type': 'multipart/form-data'}}),
    ]
    transcripts, headers = [], {}
    for framework in ('fastapi', 'expose-api'):
        with TestClient(create_app(db_url=database, framework=framework)) as client:
            if framework == 'fastapi':
                assert client.post('/api/users', json=root_credentials, headers=bootstrap_headers).status_code == 200
                token = client.post('/api/token', data={'username': root_credentials['username'],
                    'password': root_credentials['password_hash']}).json()['access_token']
                headers = {'Authorization': 'Bearer ' + token} if authenticated else {}
            transcript = []
            for path, values in cases:
                values = dict(values)
                values['headers'] = {**values.get('headers', {}), **headers}
                response = client.post(path, **values)
                stable = dict(response.headers)
                stable.pop('x-pnbp-operation-id', None)
                transcript.append((response.status_code, response.content, stable))
            transcripts.append(transcript)
    assert transcripts[0] == transcripts[1]


def test_unexpected_failure_retains_public_body_and_native_security(client, auth_headers, monkeypatch, web_framework):
    from api import publish_api
    async def failed(*args, **kwargs):
        raise RuntimeError('synthetic-private-content')
    monkeypatch.setattr(publish_api, 'add_publishment', failed)
    response = client.post('/api/publishment', headers=auth_headers,
                           json={'name': 'failed', 'content': 'body'})
    assert response.status_code == 500 and response.content == b'Internal Server Error'
    assert response.headers['content-type'] == 'text/plain; charset=utf-8'
    if web_framework == 'expose-api':
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-frame-options'] == 'DENY'
        assert response.headers['x-pnbp-operation-id']


@pytest.mark.parametrize('web_framework', ['expose-api'], indirect=True)
def test_all_multipart_files_close_after_rejected_upload(client, auth_headers, monkeypatch):
    from expose_api import multipart as parser
    original = parser.tempfile.SpooledTemporaryFile
    opened = []
    def tracked(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file
    monkeypatch.setattr(parser.tempfile, 'SpooledTemporaryFile', tracked)
    response = client.post('/api/image', headers=auth_headers, files=[
        ('file', ('invalid.png', b'not a PNG', 'image/png')),
        ('ignored', ('other.bin', b'extra upload', 'application/octet-stream')),
    ])
    assert response.status_code == 400
    assert len(opened) == 2 and all(file.closed for file in opened)


@pytest.mark.parametrize('web_framework', ['expose-api'], indirect=True)
def test_canceled_native_request_closes_uploads_and_finalizes_receipt(web_storage, root_credentials, bootstrap_headers, monkeypatch):
    from expose_api import multipart as parser
    from api import publish_api
    original = parser.tempfile.SpooledTemporaryFile
    opened = []
    def tracked(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file
    monkeypatch.setattr(parser.tempfile, 'SpooledTemporaryFile', tracked)
    async def exercise():
        started = asyncio.Event()
        async def held(request, file):
            started.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(publish_api, 'image_post', held)
        app = create_app(db_url='sqlite://:memory:', framework='expose-api')
        async with AsyncClient(app) as client:
            assert (await client.post('/api/users', json=root_credentials, headers=bootstrap_headers)).status == 200
            token = (await client.post('/api/token', data={'username': root_credentials['username'],
                'password': root_credentials['password_hash']})).json['access_token']
            headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'multipart/form-data; boundary=owned'}
            body = (b'--owned\r\nContent-Disposition: form-data; name="file"; filename="canceled.png"\r\n'
                    b'Content-Type: image/png\r\n\r\nsynthetic bytes\r\n--owned--\r\n')
            pending = asyncio.create_task(client.post('/api/image', content=body, headers=headers))
            await asyncio.wait_for(started.wait(), 3)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert opened and all(file.closed for file in opened)
            assert not (web_storage.images / 'canceled.png').exists()
            events = (await client.get('/api/logs', headers={'Authorization': 'Bearer ' + token})).json
            assert events[0]['outcome'] == 'failed' and events[0]['status_code'] == 500
    asyncio.run(exercise())
