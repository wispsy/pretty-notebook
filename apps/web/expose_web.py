"""Explicit native handlers over the application's shared services."""

import logging

from expose_api import App, JSONResponse, Response
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.health import health_status
from api.search_api import SearchField, results
from native_requests import ApplicationRequest, json_value
from native_publishing import PublishingAudit, register, selected


class SearchQuery(BaseModel):
    q: str = Field(min_length=1, max_length=512)
    field: SearchField = 'any'
    tag: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class _SecurityHeaders:
    """Apply the existing security/no-store contract to native API responses."""

    def __init__(self, application, *, assets):
        self.application, self.assets = application, assets

    async def __call__(self, scope, receive, send):
        async def secured(event):
            if event['type'] == 'http.response.start':
                headers = list(event.get('headers', ()))
                existing = {name.lower() for name, _ in headers}
                selected = {
                    b'x-content-type-options': 'nosniff',
                    b'x-frame-options': 'DENY',
                    b'referrer-policy': 'strict-origin-when-cross-origin',
                    b'permissions-policy': 'camera=(), geolocation=(), microphone=()',
                    b'content-security-policy': self.assets.security_policy(),
                    b'cache-control': 'no-store',
                }
                headers.extend((name, value.encode('latin-1')) for name, value in selected.items()
                               if name not in existing)
                event = {**event, 'headers': headers}
            await send(event)
        await self.application(scope, receive, secured)


class ExposedApplication:
    """Native pilot and publishing routes with explicit remaining-group delegation.

    One baseline lifespan retains ORM startup, migrations, process locks and
    shutdown while the application handlers are ported in focused groups.
    """

    framework = 'expose-api'
    native_paths = frozenset(('/healthz', '/api/search'))

    def __init__(self, baseline, *, allowed_hosts):
        self.baseline = baseline
        self.state = baseline.state
        self.root_path = baseline.root_path
        self.dependency_overrides = baseline.dependency_overrides
        self.http_app = App(title='Pretty Notebook', max_body_size=16 * 1024 * 1024)
        self.http_app.add_middleware(_SecurityHeaders, assets=self.state.assets)
        self.http_app.add_middleware(PublishingAudit, services=baseline)
        self.http_app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

        @self.http_app.exception_handler(HTTPException)
        async def public_error(request, error):
            return JSONResponse({'detail': json_value(error.detail)}, status=error.status_code,
                                headers=error.headers or ())

        @self.http_app.exception_handler(Exception)
        async def internal_error(request, error):
            status, message = getattr(error, 'status', None), getattr(error, 'message', None)
            if type(status) is int and 400 <= status < 500 and isinstance(message, str):
                return JSONResponse({'detail': message}, status=status, headers=getattr(error, 'headers', ()))
            logging.getLogger(__name__).error('Unhandled web application error (%s).', type(error).__name__)
            return Response(b'Internal Server Error', status=500, media_type='text/plain; charset=utf-8')

        @self.http_app.route('/healthz', public=True)
        async def health(request):
            return JSONResponse(await health_status())

        @self.http_app.route('/api/search', public=True)
        async def search(request):
            query = request.query_params
            values = {name: query[name] for name in ('q', 'field', 'limit', 'offset') if name in query}
            values['tag'] = query.getlist('tag')
            try:
                selected = SearchQuery.model_validate(values)
            except ValidationError as error:
                details = error.errors(include_url=False)
                for detail in details:
                    detail['loc'] = ['query', *detail['loc']]
                    if detail['type'] == 'missing':
                        detail['input'] = None
                return JSONResponse({'detail': details}, status=422)
            service_request = ApplicationRequest(request, self.baseline)
            value = await results(service_request, selected.q, selected.field,
                                  selected.tag, selected.limit, selected.offset)
            return JSONResponse(value)

        register(self.http_app, baseline, self.dependency_overrides)

    async def __call__(self, scope, receive, send):
        root = (self.root_path or scope.get('root_path', '')).rstrip('/')
        path = scope.get('path', '')
        if root and (path == root or path.startswith(root + '/')):
            path = path[len(root):] or '/'
        if scope['type'] == 'http' and ((scope['method'] == 'GET' and path in self.native_paths)
                                      or selected(scope['method'], path)):
            await self.http_app({**scope, 'root_path': root}, receive, send)
        else:
            # Non-GET method behavior and unported groups retain the recorded
            # baseline; lifespan startup and teardown still execute once.
            await self.baseline(scope, receive, send)
