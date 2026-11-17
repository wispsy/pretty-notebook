"""Compare actual protocol transcripts across the pilot's two factories."""

from functools import partial

import pytest
from fastapi.testclient import TestClient

from main import create_app


def test_native_get_handlers_do_not_dispatch_the_baseline_router(web_storage, monkeypatch):
    app = create_app(db_url='sqlite://:memory:', framework='expose-api')
    async def refused(scope, receive, send):
        raise AssertionError('The baseline HTTP router handled a native pilot route')
    with TestClient(app) as client:
        monkeypatch.setattr(app.baseline, 'middleware_stack', refused)
        assert client.get('/healthz').json() == {'status': 'ok'}
        assert client.get('/api/search?q=absent').json()['total'] == 0


@pytest.mark.parametrize('root', ['', '/notes'])
def test_health_search_transcripts_and_restart_match(web_storage, tmp_path, root):
    database = f'sqlite://{tmp_path / "pilot.sqlite3"}'
    cases = [
        ('GET', '/healthz'), ('GET', '/api/search?q=Common&tag=public&tag=Python'),
        ('GET', '/api/search'), ('GET', '/api/search?q='),
        ('GET', '/api/search?q=x&limit=oops'), ('GET', '/api/search?q=x&limit=0&offset=-1'),
        ('GET', '/api/search?q=x&field=regex'), ('GET', '/api/search?q=x&regex=true'),
        ('GET', '/api/search?q=%20'), ('GET', '/api/search?q=x&tag=two-words'),
        ('HEAD', '/healthz'), ('OPTIONS', '/api/search'), ('POST', '/api/search'),
        ('GET', '/api/search/'), ('GET', '/api/absent'),
    ]
    transcripts = []
    for framework in ('fastapi', 'expose-api'):
        app = create_app(db_url=database, framework=framework, root_path=root)
        with TestClient(app) as client:
            if framework == 'fastapi':
                client.portal.call(partial(app.state.publications.publish, 'one',
                    '<p>#public #Python Common café text</p>', title='Common title'))
            transcript = []
            for method, path in cases:
                response = client.request(method, root + path, follow_redirects=False)
                transcript.append((response.status_code, response.content, dict(response.headers)))
            transcripts.append(transcript)
    assert transcripts[0] == transcripts[1]


def test_native_pilot_retains_host_refusal_and_storage_failure(web_storage):
    with TestClient(create_app(db_url='sqlite://:memory:', framework='expose-api')) as client:
        denied = client.get('/healthz', headers={'Host': 'untrusted.example'})
        assert denied.status_code == 400 and denied.headers['cache-control'] == 'no-store'
        web_storage.settings.write_text('invalid JSON')
        failed = client.get('/healthz')
        assert failed.status_code == 503
        assert failed.json() == {'detail': 'Persistent storage is unavailable.'}
        assert failed.headers['x-frame-options'] == 'DENY'
