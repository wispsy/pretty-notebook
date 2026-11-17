"""Qualify the installed production web runtime without test-only frameworks."""

import asyncio
import hashlib
from importlib.metadata import version
from importlib.util import find_spec
import os
from pathlib import Path
import sys
import tempfile


def check():
    assert all(find_spec(name) is None for name in ('fastapi', 'starlette'))
    assert version('expose-api') == '0.2.0'
    assert version('backpack-store') == '0.2.0'
    with tempfile.TemporaryDirectory(prefix='pnbp-native-runtime-') as directory:
        os.environ.update(JWT_SECRET='synthetic-runtime-jwt-secret-32-bytes', JWT_ALGO='HS256',
            PNBP_BOOTSTRAP_TOKEN='synthetic-runtime-bootstrap-32-bytes', PNBP_DATA_DIR=directory,
            PNBP_DATABASE_URL='sqlite://' + str(Path(directory) / 'runtime.sqlite3'),
            PNBP_ALLOWED_HOSTS='testserver,localhost', PNBP_WEB_FRAMEWORK='expose-api', PNBP_ASSET_MODE='local')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/web'))
        from main import create_app
        from expose_api import TestClient
        async def exercise():
            app = create_app(root_path='/notes')
            async with TestClient(app) as client:
                assert (await client.get('/notes/healthz')).json == {'status': 'ok'}
                credentials = {'username': 'runtime-owner', 'password_hash': 'synthetic runtime password'}
                assert (await client.post('/notes/api/users', json=credentials,
                    headers={'X-PNBP-Bootstrap-Token': os.environ['PNBP_BOOTSTRAP_TOKEN']})).status == 200
                token = (await client.post('/notes/api/token', data={'username': credentials['username'],
                    'password': credentials['password_hash']})).json['access_token']
                headers = {'Authorization': 'Bearer ' + token}
                body = '<p>Native runtime</p>'
                digest = hashlib.sha256(body.encode()).hexdigest()
                response = await client.put('/notes/api/publishing/publication',
                    headers={**headers, 'If-None-Match': '*'}, json={'name': 'runtime', 'content': body,
                        'source_hash': digest, 'rendered_hash': digest, 'renderer_fingerprint': 'f' * 64})
                assert response.status == 201 and response.headers['etag']
                assert 'Native runtime' in (await client.get('/notes/runtime')).text
                assert (await client.get('/notes/api/search?q=runtime')).json['total'] == 1
                assert (await client.get('/notes/api/logs', headers=headers)).json[0]['outcome'] == 'succeeded'
                response = await client.post('/notes/theme', data={'darkmode': 'darkmode'})
                assert response.status == 303 and response.headers['location'] == '/notes/'
                assert (await client.get('/notes/openapi.json')).json['servers'] == [{'url': '/notes'}]
                assert (await client.get('/notes/docs')).status == 200
                assert (await client.get('/notes/healthz', headers={'Host': 'untrusted.example'})).status == 400
            assert not hasattr(app.state, '_tortoise_context')
            async with TestClient(create_app(root_path='/notes')) as restarted:
                assert 'Native runtime' in (await restarted.get('/notes/runtime')).text
                assert (await restarted.get('/notes/api/publishing/inventory', headers=headers)).json['pages'][0]['pub_name'] == 'runtime.html'
        asyncio.run(exercise())
    assert not any(name in sys.modules for name in ('fastapi', 'starlette'))
    print('Native production runtime: bootstrap, checked publish, pages, search, receipts, cookies, docs, host refusal, restart and ORM shutdown passed.')


if __name__ == '__main__':
    check()
