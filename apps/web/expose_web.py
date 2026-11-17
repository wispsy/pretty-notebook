"""Explicit native handlers over the application's shared services."""

from contextlib import asynccontextmanager
import logging
from tortoise import Tortoise

from api import catalog, layout_api, public_index, schema
from web_errors import InputErrors
from web_routing import MethodPolicy, WebApplication
from web_hosts import TrustedHosts
from web_reference import register as reference_routes

from expose_api import HTTPException, JSONResponse, Response
from pydantic import BaseModel, Field, ValidationError
from tortoise.exceptions import DoesNotExist, IntegrityError

from api.health import health_status
from api.search_api import SearchField, results
from native_requests import ApplicationRequest, json_value
from native_publishing import PublishingAudit, register
import native_routes


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
                }
                path = scope['path'].removeprefix(scope.get('root_path', ''))
                if event['status'] in {200, 206, 304} and self.assets.cacheable(path):
                    selected[b'cache-control'] = 'public, max-age=31536000, immutable'
                if path.startswith('/api') or path == '/healthz':
                    selected[b'cache-control'] = 'no-store'
                headers.extend((name, value.encode('latin-1')) for name, value in selected.items()
                               if name not in existing)
                event = {**event, 'headers': headers}
            await send(event)
        await self.application(scope, receive, secured)


class ExposedApplication:
    """Application state and storage lifetime around explicit native HTTP routes."""

    framework = 'expose-api'

    def __init__(self, state, *, db_url, root_path, allowed_hosts):
        self.state, self.root_path = state, root_path
        self.authentication_overrides = {}
        self._lifespan_error = None

        @asynccontextmanager
        async def lifetime(app):
            self._lifespan_error = None
            initialized = False
            try:
                try:
                    self.state._tortoise_context = await Tortoise.init(db_url=db_url,
                        modules={'models': ['api.auth_api', 'api.forms']}, use_tz=True,
                        timezone='UTC', _enable_global_fallback=True)
                    initialized = True
                    async with self.state.storage_lock:
                        self.state.schema_migration = await schema.migrate()
                    self.state.publications = catalog.PublicationStore(self.state.pages_path, lock=self.state.storage_lock)
                    await self.state.publications.start()
                    self.state.public_index = public_index.PublicIndex(self.state.publications)
                    self.state.assets.validate_layout(await layout_api.get_layout_content())
                    yield
                finally:
                    if initialized:
                        await Tortoise.close_connections()
                        del self.state._tortoise_context
            except BaseException as error:
                self._lifespan_error = error
                raise

        self.http_app = WebApplication(title='Pretty Notebook', max_body_size=16 * 1024 * 1024, lifespan=lifetime)
        self.http_app.add_middleware(_SecurityHeaders, assets=self.state.assets)
        self.http_app.add_middleware(PublishingAudit, services=self)
        self.http_app.add_middleware(TrustedHosts, allowed_hosts=allowed_hosts)
        self.http_app.add_middleware(MethodPolicy, routes=self.http_app.http_routes)
        reference_routes(self.http_app)

        @self.http_app.exception_handler(HTTPException)
        async def public_error(request, error):
            return JSONResponse({'detail': json_value(error.detail)}, status=error.status,
                                headers=error.headers or ())

        @self.http_app.exception_handler(InputErrors)
        async def input_error(request, error):
            return JSONResponse({'detail': json_value(error.details)}, status=422)

        @self.http_app.exception_handler(DoesNotExist)
        async def missing_record(request, error):
            return JSONResponse({'detail': str(error)}, status=404)

        @self.http_app.exception_handler(IntegrityError)
        async def invalid_record(request, error):
            return JSONResponse({'detail': [{'loc': [], 'msg': str(error), 'type': 'IntegrityError'}]}, status=422)

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
            service_request = ApplicationRequest(request, self)
            value = await results(service_request, selected.q, selected.field,
                                  selected.tag, selected.limit, selected.offset)
            return JSONResponse(value)

        register(self.http_app, self, self.authentication_overrides)
        native_routes.register(self.http_app, self)

    async def __call__(self, scope, receive, send):
        root = (self.root_path or scope.get('root_path', '')).rstrip('/')
        await self.http_app({**scope, 'root_path': root}, receive, send)
        if scope['type'] == 'lifespan' and self._lifespan_error is not None:
            # Native public startup events are sanitized; local process owners
            # retain the original actionable storage/configuration diagnostic.
            raise self._lifespan_error
