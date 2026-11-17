"""Final method, schema, lifetime and native client acceptance."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import re

import pytest
from expose_api import TestClient as AsyncClient
from starlette.testclient import TestClient
from tortoise import Tortoise

from main import create_app
from web_reference import CONTRACT


def test_recorded_method_contract(client):
    recorded = json.loads(Path(__file__).with_name('fixtures').joinpath('http-methods.json').read_text())
    for path, methods in recorded.items():
        for method, expected in methods.items():
            response = client.request(method, path, follow_redirects=False)
            assert response.status_code == expected['status'], (method, path, response.text)
            assert set((response.headers.get('allow') or '').split(', ')) == set((expected['allow'] or '').split(', ')), (method, path)
            assert response.text == expected['body'], (method, path)
            assert response.headers.get('location') == expected['location']


def test_openapi_operation_inventory_and_prefix(web_storage):
    app = create_app(db_url='sqlite://:memory:', root_path='/notes')
    registered = {(re.sub(r'\{(\w+):path\}', r'{\1}', path), method.lower())
                  for path, methods, _ in app.http_app.http_routes for method in methods}
    described = {(path, method) for path, methods in CONTRACT['paths'].items() for method in methods}
    assert described <= registered
    assert {item for item in registered if item[0].startswith('/api') and item[0] not in {'/api/', '/api/{unknown}', '/api/publishment/', '/api/publishing/publication/'}} == described
    with TestClient(app) as client:
        document = client.get('/notes/openapi.json').json()
        expected = deepcopy(CONTRACT)
        expected['servers'] = [{'url': '/notes'}]
        assert document == expected
        assert document['components']['securitySchemes']['OAuth2PasswordBearer']['flows']['password']['tokenUrl'] == '/api/token'
        for path in ('/docs', '/redoc', '/docs/oauth2-redirect'):
            response = client.get('/notes' + path)
            assert response.status_code == 200 and 'href="/notes/openapi.json"' in response.text
            assert '<script' not in response.text


def test_application_models_match_the_public_schema():
    from api import auth_api, layout_api, notebooks, permissions, publish_api, publishing_api
    def annotations(schema):
        # The previous generator omitted null defaults; validation constraints
        # and required/nullable fields still compare without that annotation.
        if isinstance(schema, dict):
            return {key: annotations(value) for key, value in schema.items()
                    if key != 'default' or value is not None}
        if isinstance(schema, list):
            return [annotations(value) for value in schema]
        return schema
    for model in (auth_api.PasswordInput, auth_api.UserInput, layout_api.PNBPWebLayout,
                  notebooks.NotebookInput, permissions.RoleInput, permissions.GrantInput,
                  permissions.CredentialInput, publish_api.PublicationInput,
                  publish_api.RouteClaim, publishing_api.CheckedPublication):
        assert annotations(model.model_json_schema()) == annotations(CONTRACT['components']['schemas'][model.__name__]), model.__name__


def test_native_lifetime_closes_orm_once(web_storage, monkeypatch):
    original = Tortoise.close_connections
    calls = []
    async def close():
        calls.append('close')
        await original()
    monkeypatch.setattr(Tortoise, 'close_connections', close)
    app = create_app(db_url='sqlite://:memory:')
    async def exercise():
        async with AsyncClient(app) as client:
            assert (await client.get('/')).status == 200
            assert (await client.get('/n/search?q=missing')).status == 200
            assert hasattr(app.state, '_tortoise_context')
        assert calls == ['close'] and not hasattr(app.state, '_tortoise_context')
    asyncio.run(exercise())


def test_startup_failure_closes_orm_and_preserves_local_diagnostic(web_storage, monkeypatch):
    from api import schema
    async def failed():
        raise RuntimeError('synthetic migration diagnostic')
    monkeypatch.setattr(schema, 'migrate', failed)
    app = create_app(db_url='sqlite://:memory:')
    with pytest.raises(RuntimeError, match='synthetic migration diagnostic'):
        with TestClient(app):
            pass
    assert not hasattr(app.state, '_tortoise_context')


def test_empty_publication_paths_keep_authentication_and_precondition_order(client, auth_headers):
    for path in ('/api/publishment/', '/api/publishing/publication/'):
        assert client.delete(path).status_code == 401
    legacy = client.delete('/api/publishment/', headers=auth_headers)
    assert legacy.status_code == 400 and legacy.json() == {'detail': 'Invalid publication filename.'}
    assert client.delete('/api/publishing/publication/', headers=auth_headers).status_code == 428
    checked = client.delete('/api/publishing/publication/', headers={**auth_headers, 'If-Match': '"unused"'})
    assert checked.status_code == 400 and checked.json() == {'detail': 'Invalid publication name.'}
