"""Factory selection and explicit lifetime ownership for the migration gate."""

import asyncio

import pytest
from expose_api import App, TestClient as AsyncClient
from starlette.testclient import TestClient

from main import create_app


def test_selected_factory_keeps_shared_state_and_root_prefix(web_storage, web_framework):
    app = create_app(db_url='sqlite://:memory:', root_path='/notes')
    assert app.framework == web_framework
    if web_framework == 'expose-api':
        assert isinstance(app.http_app, App)
        assert not hasattr(app, 'baseline')
    with TestClient(app) as client:
        response = client.get('/notes/healthz')
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}
        assert response.headers['cache-control'] == 'no-store'
        assert client.get('/notes/docs').status_code == 200
        assert client.get('/notes/openapi.json').json()['openapi'] == '3.1.0'


def test_explicit_factory_overrides_environment(web_storage, monkeypatch):
    monkeypatch.setenv('PNBP_WEB_FRAMEWORK', 'invalid')
    app = create_app(db_url='sqlite://:memory:', framework='expose-api')
    assert app.framework == 'expose-api'
    with TestClient(app) as client:
        assert client.get('/healthz').status_code == 200


def test_default_runtime_is_native(web_storage, monkeypatch):
    monkeypatch.delenv('PNBP_WEB_FRAMEWORK', raising=False)
    assert create_app(db_url='sqlite://:memory:').framework == 'expose-api'


@pytest.mark.parametrize('value', ['', 'automatic', 'EXPOSE-API', 'fastapi', 'starlette'])
def test_invalid_factory_refuses_construction(web_storage, value):
    with pytest.raises(RuntimeError, match='PNBP_WEB_FRAMEWORK'):
        create_app(framework=value)


def test_public_async_client_drives_the_selected_lifespan_once(web_storage, web_framework, monkeypatch):
    from api import schema
    original = schema.migrate
    calls = []
    async def migrate():
        calls.append('migrate')
        return await original()
    monkeypatch.setattr(schema, 'migrate', migrate)
    app = create_app(db_url='sqlite://:memory:')
    async def exercise():
        async with AsyncClient(app) as client:
            first = await client.get('/healthz')
            second = await client.get('/healthz')
            assert first.status == second.status == 200
            assert first.json == second.json == {'status': 'ok'}
        assert calls == ['migrate']
    asyncio.run(exercise())
