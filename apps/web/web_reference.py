"""Local API reference and the application-owned OpenAPI contract."""

from copy import deepcopy
from html import escape
import json
from pathlib import Path

from expose_api import HTMLResponse, JSONResponse

CONTRACT = json.loads(Path(__file__).with_name('openapi.json').read_text(encoding='utf-8'))


def register(app):
    @app.route('/openapi.json', methods=('GET', 'HEAD'), public=True)
    async def schema(request):
        document = deepcopy(CONTRACT)
        if root := request.scope.get('root_path', ''):
            document['servers'] = [{'url': root}]
        return JSONResponse(document)

    @app.route('/docs', methods=('GET', 'HEAD'), public=True)
    @app.route('/redoc', methods=('GET', 'HEAD'), public=True)
    @app.route('/docs/oauth2-redirect', methods=('GET', 'HEAD'), public=True)
    async def reference(request):
        root = escape(request.scope.get('root_path', ''), quote=True)
        rows = ''.join('<li><code>' + escape(method.upper() + ' ' + path) + '</code> — ' +
                       escape(operation.get('summary', operation.get('operationId', ''))) + '</li>'
                       for path, methods in CONTRACT['paths'].items() for method, operation in methods.items())
        return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<title>Pretty Notebook API</title><h1>Pretty Notebook API</h1>'
            '<p>Use bearer authentication for protected operations. '
            'Obtain a token with a form POST to <code>' + root + '/api/token</code>.</p>'
            '<p><a href="' + root + '/openapi.json">OpenAPI document</a></p><ul>' + rows + '</ul></html>')
