"""Remaining handler parity and application-selected native file behavior."""

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.mark.parametrize('web_framework', ['expose-api'], indirect=True)
def test_remaining_groups_bypass_baseline(web_storage, root_credentials, bootstrap_headers, monkeypatch):
    app = create_app(db_url='sqlite://:memory:', framework='expose-api', root_path='/notes')
    async def refused(scope, receive, send):
        raise AssertionError('A ported request reached the baseline HTTP router')
    with TestClient(app) as client:
        monkeypatch.setattr(app.baseline, 'middleware_stack', refused)
        assert client.post('/notes/api/users', json=root_credentials, headers=bootstrap_headers).status_code == 200
        token = client.post('/notes/api/token', data={'username': root_credentials['username'],
            'password': root_credentials['password_hash']}).json()['access_token']
        headers = {'Authorization': 'Bearer ' + token}
        for path in ('/api', '/api/users/me', '/api/credentials', '/api/notebooks', '/api/logs',
                     '/api/forms/contact/submissions', '/', '/contact', '/appearance', '/n', '/n/search'):
            response = client.get('/notes' + path, headers=headers)
            assert response.status_code == 200, (path, response.text)
        assert client.post('/notes/forms/contact', data={'email_address': 'a@example.com',
            'email_message': 'Native inbox'}, follow_redirects=False).status_code == 303
        assert client.get('/notes/api/forms/contact/submissions', headers=headers).json()[0]['payload']['email_message'] == 'Native inbox'
        response = client.post('/notes/theme', data={'darkmode': 'darkmode'}, follow_redirects=False)
        assert response.status_code == 303 and response.headers['location'] == '/notes/'
        assert all('Path=/notes/' in value and 'HttpOnly' in value for value in response.headers.get_list('set-cookie'))
        assert client.get('/notes/static/css/appearance.css').status_code == 404
        assert client.get('/notes/api/unknown').json() == {'detail': 'Not Found'}


@pytest.mark.parametrize('web_framework', ['fastapi'], indirect=True)
def test_remaining_validation_transcripts_match(web_storage, tmp_path, root_credentials, bootstrap_headers):
    database = f'sqlite://{tmp_path / "remaining.sqlite3"}'
    cases = [
        ('POST', '/api/token', {}), ('POST', '/api/token', {'data': {'username': '', 'password': '', 'grant_type': 'other'}}),
        ('POST', '/theme', {}), ('POST', '/theme', {'data': {'darkmode': 'other'}}),
        ('POST', '/appearance', {'data': {'font': 'other', 'radius': 'x'}}),
        ('GET', '/n?limit=0&offset=bad', {}), ('GET', '/n/search?field=other&limit=101', {}),
        ('GET', '/missing?related=other', {}), ('GET', '/api/forms/contact/submissions?limit=0&offset=bad', {}),
        ('GET', '/api/logs?limit=0&before=-1', {}),
        ('PUT', '/api/users/bad/role', {'json': {}}), ('PUT', '/api/users/-2/grants', {'json': {'permissions': []}}),
        ('POST', '/api/notebooks', {'json': {}}), ('POST', '/api/credentials', {'json': {}}),
        ('DELETE', '/api/credentials/bad', {}),
    ]
    transcripts, headers = [], {}
    for framework in ('fastapi', 'expose-api'):
        with TestClient(create_app(db_url=database, framework=framework)) as client:
            if framework == 'fastapi':
                assert client.post('/api/users', json=root_credentials, headers=bootstrap_headers).status_code == 200
                token = client.post('/api/token', data={'username': root_credentials['username'],
                    'password': root_credentials['password_hash']}).json()['access_token']
                headers = {'Authorization': 'Bearer ' + token}
            transcript = []
            for method, path, values in cases:
                response = client.request(method, path, headers=headers, **values)
                transcript.append((method, path, response.status_code, response.content, dict(response.headers)))
            transcripts.append(transcript)
    assert transcripts[0] == transcripts[1]


@pytest.mark.parametrize('filename', ['.hidden.png', 'CON.png', 'colon:name.png', 'pipe|name.png', 'back\\slash.png'])
def test_accepted_image_names_remain_public(client, auth_headers, filename):
    content = b'\x89PNG\r\n\x1a\nimage'
    response = client.post('/api/image', headers=auth_headers, files={'file': (filename, content, 'image/png')})
    assert response.status_code == 201
    response = client.get('/static/imgs/' + quote(filename, safe=''))
    assert response.status_code == 200 and response.content == content


@pytest.mark.parametrize('web_framework', ['expose-api'], indirect=True)
def test_native_file_validators_range_and_rooted_selection(client, web_storage):
    content = b'0123456789'
    (web_storage.images / 'range.png').write_bytes(content)
    first = client.get('/static/imgs/range.png')
    assert first.status_code == 200 and first.headers['etag'].startswith('W/')
    assert client.get('/static/imgs/range.png', headers={'If-None-Match': first.headers['etag']}).status_code == 304
    selected = client.get('/static/imgs/range.png', headers={'Range': 'bytes=2-5'})
    assert selected.status_code == 206 and selected.content == b'2345'
    assert selected.headers['content-range'] == 'bytes 2-5/10'
    assert client.head('/static/imgs/range.png').content == b''
    assert client.get('/static/imgs/range.png', headers={'Range': 'bytes=0-1,4-5'}).status_code == 416
    outside = web_storage.images.parent / 'outside.png'
    outside.write_bytes(b'private')
    (web_storage.images / 'escape.png').symlink_to(outside)
    for path in ('/static', '/static/', '/static/imgs', '/static/imgs/'):
        assert client.get(path, follow_redirects=False).status_code == 404
    assert client.get('/static/imgs/escape.png').status_code == 404
    assert client.get('/static/imgs/%2e%2e/outside.png').status_code == 404
