"""Explicit application method policy over native route registration."""

import re

from expose_api import App, JSONResponse


def path_pattern(path):
    pieces, position = [], 0
    for parameter in re.finditer(r'\{[^}:]+(?::([^}]+))?\}', path):
        pieces.append(re.escape(path[position:parameter.start()]))
        pieces.append('.*' if parameter[1] == 'path' else '[^/]+')
        position = parameter.end()
    return re.compile('^' + ''.join(pieces) + re.escape(path[position:]) + '$')


class WebApplication(App):
    def __init__(self, **options):
        super().__init__(**options)
        self.http_routes = []

    def route(self, path, *, methods=('GET',), **options):
        register = super().route(path, methods=methods, **options)
        def bound(handler):
            result = register(handler)
            self.http_routes.append((path, tuple(methods), path_pattern(path)))
            return result
        return bound


class MethodPolicy:
    """Preserve declared methods, API fallthrough and static mount behavior.

    Native automatic HEAD/OPTIONS remains available to other applications; this
    application selects its previously published HTTP contract explicitly.
    """

    def __init__(self, application, *, routes):
        self.application, self.routes = application, routes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.application(scope, receive, send)
            return
        path = scope['path'].removeprefix(scope.get('root_path', '')) or '/'
        method = scope['method']
        matches = [(methods, pattern) for _, methods, pattern in self.routes if pattern.fullmatch(path)]
        if path.startswith('/static/') and method not in ('GET', 'HEAD'):
            response = JSONResponse({'detail': 'Method Not Allowed'}, status=405)
        elif any(method in methods for methods, _ in matches):
            await self.application(scope, receive, send)
            return
        else:
            allowed = matches[0][0] if matches else ('GET',)
            response = JSONResponse({'detail': 'Method Not Allowed'}, status=405,
                                    headers={'Allow': ', '.join(allowed)})
        await response(scope, receive, send)
