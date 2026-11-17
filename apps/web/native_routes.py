"""Explicit native bindings for accounts, site administration and public pages."""

from types import SimpleNamespace
from typing import Literal

from expose_api import JSONResponse, Response
from fastapi import HTTPException
from pydantic import BaseModel, Field, TypeAdapter

from api import auth_api, forms as inbox, layout_api, notebooks, operation_logs, permissions, site_api
from api.search_api import SearchField
from native_requests import (ApplicationRequest, Authentication, Headers, JSONBody, MISSING, UploadBody,
    file_input, form_input, model_input, query_input, raise_inputs, response_for, validated)
from native_assets import register as register_assets, StaticResponse
from views import forms, home, navigation, search


class TokenForm(BaseModel):
    grant_type: str | None = Field(default=None, pattern='^password$')
    username: str
    password: str
    scope: str = ''
    client_id: str | None = None
    client_secret: str | None = None


class ThemeForm(BaseModel):
    darkmode: Literal['darkmode', 'lightmode']
    return_to: str = '/'


class AppearanceForm(BaseModel):
    font: Literal['sans', 'serif', 'mono']
    mode: Literal['light', 'dark', 'system'] | None = None
    theme: Literal['forest', 'paper', 'dark', 'midnight'] | None = None
    density: Literal['comfortable', 'compact'] | None = None
    accent: str | None = None
    radius: int | None = None
    return_to: str = '/'


class InboxQuery(BaseModel):
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class LogQuery(BaseModel):
    limit: int = Field(default=100, ge=1, le=100)
    before: int = Field(default=0, ge=0)


class NavigationQuery(BaseModel):
    directory: str = Field(default='', max_length=499)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class PageSearchQuery(BaseModel):
    q: str = Field(default='', max_length=512)
    field: SearchField = 'any'
    tag: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class ContentQuery(BaseModel):
    related: bool = True


POST_PATHS = {'/api/users', '/api/token', '/api/users/me', '/api/credentials', '/api/notebooks',
              '/api/layout', '/api/favicon', '/theme', '/appearance'}


def selected(method, path):
    if method == 'GET':
        return path not in {'/docs', '/redoc', '/docs/oauth2-redirect', '/openapi.json'}
    return (method == 'POST' and (path in POST_PATHS or path.startswith('/forms/')) or
            method == 'PUT' and (path == '/api/appearance/stylesheet' or
                path.startswith('/api/users/') and path.endswith(('/role', '/grants'))) or
            method == 'DELETE' and path.startswith('/api/credentials/'))


def register(app, services):
    adapters = {schema: TypeAdapter(schema) for schema in (auth_api.UserInput, auth_api.PasswordInput,
        permissions.RoleInput, permissions.GrantInput, permissions.CredentialInput,
        notebooks.NotebookInput, layout_api.PNBPWebLayout)}
    integer = TypeAdapter(int)

    def context(request):
        return ApplicationRequest(request, services)

    async def user(request):
        return (await request.resolve(Authentication)).user

    def access(permission=None, wire=None):
        async def allowed(request):
            if wire is not None:
                await request.resolve(wire)
            identity = await user(request)
            if permission is not None:
                await permissions.authorize(identity, permission, context(request).headers.get('X-PNBP-Notebook', 'default'))
            return True
        return allowed

    async def path_body(request, name, schema):
        errors = []
        identifier = validated(integer, request.path_params[name], ('path', name), errors)
        value = validated(adapters[schema], (await request.resolve(JSONBody)).value, ('body',), errors)
        raise_inputs(errors)
        return identifier, value

    @app.route('/api/users', methods=('POST',), public=True)
    async def create_user(request):
        await request.resolve(JSONBody)
        scheme, _, token = context(request).headers.get('Authorization', '').partition(' ')
        identity = await auth_api.get_optional_user(token if scheme.casefold() == 'bearer' else None)
        data = await model_input(request, adapters[auth_api.UserInput])
        return response_for(await auth_api.create_user(data, context(request), identity))

    @app.route('/api/token', methods=('POST',), public=True)
    async def token(request):
        data = await form_input(request, TokenForm)
        metadata = SimpleNamespace(headers={})
        result = await auth_api.generate_token(metadata, data)
        return JSONResponse(result, headers=metadata.headers)

    @app.route('/api/users/me', authorize=access())
    async def current(request):
        return response_for(await auth_api.get_user(await user(request)))

    @app.route('/api/users/me', methods=('POST',), authorize=access(wire=JSONBody))
    async def password(request):
        return response_for(await auth_api.reset_password(await model_input(request, adapters[auth_api.PasswordInput]), await user(request)))

    @app.route('/api', authorize=access())
    async def index(request):
        return response_for(await auth_api.api_index(await user(request)))

    @app.route('/api/users/{user_id}/role', methods=('PUT',), authorize=access('admin', JSONBody))
    async def role(request):
        identifier, value = await path_body(request, 'user_id', permissions.RoleInput)
        return response_for(await permissions.set_role(identifier, value, context(request)))

    @app.route('/api/users/{user_id}/grants', methods=('PUT',), authorize=access('admin', JSONBody))
    async def grants(request):
        identifier, value = await path_body(request, 'user_id', permissions.GrantInput)
        return response_for(await permissions.set_grants(identifier, value, context(request)))

    @app.route('/api/credentials', methods=('POST',), authorize=access('account', JSONBody))
    async def create_credential(request):
        data = await model_input(request, adapters[permissions.CredentialInput])
        return response_for(await permissions.create_credential(data, await user(request)), status=201)

    @app.route('/api/credentials', authorize=access('account'))
    async def credentials(request):
        return response_for(await permissions.list_credentials(await user(request)))

    @app.route('/api/credentials/{credential_id}', methods=('DELETE',), authorize=access('account'))
    async def revoke(request):
        errors = []
        identifier = validated(integer, request.path_params['credential_id'], ('path', 'credential_id'), errors)
        raise_inputs(errors)
        await permissions.revoke_credential(identifier, await user(request))
        return Response(status=204)

    @app.route('/api/notebooks', methods=('POST',), authorize=access('admin', JSONBody))
    async def create_notebook(request):
        data = await model_input(request, adapters[notebooks.NotebookInput])
        return response_for(await notebooks.create_notebook(data, context(request)), status=201)

    @app.route('/api/notebooks', authorize=access('account'))
    async def list_notebooks(request):
        return response_for(await notebooks.list_notebooks(await user(request)))

    @app.route('/api/forms/{form_name}/submissions', authorize=access('inbox'))
    async def submissions(request):
        query = await query_input(request, InboxQuery)
        return response_for(await inbox.list_submissions(request.path_params['form_name'], query.limit, query.offset))

    @app.route('/api/logs', authorize=access('logs'))
    async def logs(request):
        query = await query_input(request, LogQuery)
        return response_for(await operation_logs.list_logs(context(request), query.limit, query.before, await user(request)))

    @app.route('/api/layout', methods=('POST',), authorize=access('site', JSONBody))
    async def layout(request):
        data = await model_input(request, adapters[layout_api.PNBPWebLayout])
        return response_for(await layout_api.layout_post(data, context(request)), status=201)

    @app.route('/api/appearance/stylesheet', methods=('PUT',), authorize=access('site'))
    async def css_upload(request):
        return response_for(await site_api.stylesheet_put(context(request)))

    @app.route('/api/favicon', methods=('POST',), authorize=access('site', UploadBody))
    async def favicon_upload(request):
        return response_for(await site_api.favicon_post(context(request), await file_input(request)), status=201)

    @app.route('/static/custom/appearance.css', public=True)
    async def css(request):
        return response_for(await site_api.stylesheet_get(context(request)))

    @app.route('/static/favicon/{asset}', public=True)
    async def favicon_asset(request):
        asset = request.path_params['asset']
        if asset.endswith('.png'):
            return response_for(await site_api.favicon_get(context(request), asset[:-4]))
        from expose_api import StaticFiles
        return StaticResponse(StaticFiles(services.state.assets.root), '/static')

    register_assets(app, services)

    @app.route('/api/', public=True)
    @app.route('/api/{unknown:path}', public=True)
    async def unknown_api(request):
        raise HTTPException(404, 'Not Found')

    @app.route('/forms/{form_name}', methods=('POST',), public=True)
    async def submit(request):
        return response_for(await forms.submit_form(context(request), request.path_params['form_name']))

    @app.route('/n/search', public=True)
    async def search_page(request):
        query = await query_input(request, PageSearchQuery)
        return response_for(await search.search(context(request), **query.model_dump()))

    @app.route('/n', public=True)
    async def navigation_page(request):
        query = await query_input(request, NavigationQuery)
        return response_for(await navigation.notebook_index(context(request), **query.model_dump()))

    @app.route('/contact', public=True)
    async def contact(request):
        return response_for(await home.contact(context(request)))

    @app.route('/', public=True)
    async def homepage(request):
        return response_for(await home.home(context(request)))

    @app.route('/theme', methods=('POST',), public=True)
    async def theme(request):
        data = await form_input(request, ThemeForm)
        return response_for(await home.set_theme(context(request), **data.model_dump()))

    @app.route('/appearance', methods=('POST',), public=True)
    async def appearance(request):
        data = await form_input(request, AppearanceForm)
        return response_for(await home.set_appearance(context(request), **data.model_dump()))

    @app.route('/appearance', public=True)
    async def preferences(request):
        return response_for(await home.appearance_preferences(context(request)))

    @app.route('/favicon.ico', public=True)
    async def favicon(request):
        return response_for(await home.favicon(context(request)))

    @app.route('/{content:path}', public=True)
    async def content(request):
        query = await query_input(request, ContentQuery)
        return response_for(await home.content(context(request), request.path_params['content'], query.related))
