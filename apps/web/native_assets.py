"""Application-selected public file trees over native owned file responses."""

import asyncio
from pathlib import Path

from expose_api import FileResponse, HTTPException, JSONResponse, Response, StaticFiles


def file_headers(headers):
    values = []
    for name, value in headers:
        if name == b'cache-control':
            continue
        if name == b'content-type' and value.startswith(b'text/') and b'charset=' not in value:
            value += b'; charset=utf-8'
        values.append((name, value))
    return values


class StaticResponse(Response):
    def __init__(self, application, root):
        super().__init__()
        self.application, self.root = application, root

    async def __call__(self, scope, receive, send):
        async def adapted(event):
            if event['type'] == 'http.response.start':
                if event['status'] in (404, 405):
                    # The public API envelope belongs to this application.
                    await JSONResponse({'detail': 'Not Found' if event['status'] == 404 else 'Method Not Allowed'},
                                       status=event['status'])(scope, receive, send)
                    return
                event = {**event, 'headers': file_headers(event.get('headers', ()))}
            elif refused[0]:
                return
            await send(event)
        refused = [False]
        async def select(event):
            if event['type'] == 'http.response.start' and event['status'] in (404, 405):
                refused[0] = True
            await adapted(event)
        await self.application({**scope, 'root_path': scope.get('root_path', '').rstrip('/') + self.root}, receive, select)


class ImageResponse(Response):
    """The private, application-owned tree retains accepted POSIX filenames.

    Reject symlinks and escapes before handing the selected regular file to
    FileResponse, which owns descriptor validation, reads and cleanup. Writers
    use atomic regular-file replacement; untrusted users cannot alter the tree.
    """

    def __init__(self, directory, path):
        super().__init__()
        self.directory, self.path = Path(directory), path

    async def prepare(self, scope):
        def selected():
            parts = self.path.split('/')
            if len(self.path) > 4096 or any(part in ('', '.', '..') for part in parts):
                raise FileNotFoundError
            target = self.directory
            for part in parts:
                if target.is_symlink():
                    raise FileNotFoundError
                target = target / part
            if target.is_symlink() or not target.is_file():
                raise FileNotFoundError
            target.resolve(strict=True).relative_to(self.directory.resolve(strict=True))
            return target
        try:
            target = await asyncio.to_thread(selected)
            response = await FileResponse(target).prepare(scope)
            response.headers = file_headers(response.headers)
            return response
        except (OSError, ValueError, HTTPException):
            return JSONResponse({'detail': 'Not Found'}, status=404)


def register(app, services):
    static = StaticFiles(services.state.assets.root, allow_hidden=True)

    @app.route('/static', public=True)
    async def static_root(request):
        return JSONResponse({'detail': 'Not Found'}, status=404)

    @app.route('/static/imgs/{path:path}', methods=('GET', 'HEAD'), public=True, name='published-images')
    async def image(request):
        return ImageResponse(services.state.images_path, request.path_params['path'])

    @app.route('/static/', methods=('GET', 'HEAD'), public=True)
    async def empty(request):
        return JSONResponse({'detail': 'Not Found'}, status=404)

    @app.route('/static/{path:path}', methods=('GET', 'HEAD'), public=True, name='static')
    async def asset(request):
        return StaticResponse(static, '/static')
