"""Explicit authenticated publishing routes and operation receipt middleware."""

from typing import Annotated

from expose_api import HTTPRequest, JSONResponse
from fastapi import HTTPException
from pydantic import Field, TypeAdapter

from api import operation_logs, permissions, publish_api, publishing_api
from native_requests import (ApplicationRequest, Authentication, BODY_LIMIT, JSONBody,
    UploadBody, authentication, file_input, json_body, model_input, response_for, upload_body)

STATIC_METHODS = {
    '/api/publishment': {'POST'}, '/api/routes/preview': {'POST'}, '/api/image': {'POST'},
    '/api/publishments': {'GET'}, '/api/images': {'GET'},
    '/api/publishing/capabilities': {'GET'}, '/api/publishing/inventory': {'GET'},
    '/api/publishing/publication': {'PUT'}, '/api/publishing/image': {'PUT'},
}
DELETE_PREFIXES = ('/api/publishment/', '/api/publishing/publication/')


def selected(method, path):
    return (method in STATIC_METHODS.get(path, ()) or method == 'DELETE' and
            any(path.startswith(prefix) and len(path) > len(prefix) for prefix in DELETE_PREFIXES))


class PublishingAudit:
    def __init__(self, application, *, services):
        self.application, self.services = application, services

    async def __call__(self, scope, receive, send):
        request = ApplicationRequest(HTTPRequest(scope, receive, max_body_size=BODY_LIMIT), self.services)
        try:
            receipt = await operation_logs.begin_audit(request)
        except HTTPException as error:
            await JSONResponse({'detail': error.detail}, status=error.status_code)(scope, receive, send)
            return
        if receipt is None:
            await self.application(scope, receive, send)
            return
        event_id, operation_id = receipt
        finished = False
        async def audited(event):
            nonlocal finished
            if event['type'] == 'http.response.start':
                await operation_logs._finish(request, event_id, event['status'])
                finished = True
                event = {**event, 'headers': [*event.get('headers', ()),
                         (b'x-pnbp-operation-id', operation_id.encode('ascii'))]}
            await send(event)
        try:
            await self.application(scope, receive, audited)
        finally:
            if not finished:
                await operation_logs._finish(request, event_id, 500)


def register(app, services, overrides):
    publication = TypeAdapter(publish_api.PublicationInput)
    claims = TypeAdapter(Annotated[list[publish_api.RouteClaim], Field(max_length=200)])
    checked = TypeAdapter(publishing_api.CheckedPublication)
    async def load_authentication(request):
        return await authentication(request, overrides)
    app.provide(Authentication, load_authentication)
    app.provide(JSONBody, json_body)
    app.provide(UploadBody, upload_body)

    def access(wire=None):
        async def authorized(request):
            # Preserve wire-syntax-before-auth and semantic-validation-after-auth
            # ordering. Managed uploads stay owned through response completion.
            if wire is not None:
                await request.resolve(wire)
            user = (await request.resolve(Authentication)).user
            await permissions.authorize(user, 'publish',
                ApplicationRequest(request, services).headers.get('X-PNBP-Notebook', 'default'))
            return True
        return authorized

    def context(request):
        return ApplicationRequest(request, services)

    @app.route('/api/publishment', methods=('POST',), authorize=access(JSONBody))
    async def publish_legacy(request):
        data = await model_input(request, publication)
        return response_for(await publish_api.publishment_post(data, context(request)), status=201)

    @app.route('/api/routes/preview', methods=('POST',), authorize=access(JSONBody))
    async def preview(request):
        data = await model_input(request, claims)
        return response_for(await publish_api.routes_preview(context(request), data))

    @app.route('/api/image', methods=('POST',), authorize=access(UploadBody))
    async def image_legacy(request):
        return response_for(await publish_api.image_post(context(request), await file_input(request)), status=201)

    @app.route('/api/publishments', authorize=access())
    async def inventory_legacy(request):
        return response_for(await publish_api.publishments_get(context(request)))

    @app.route('/api/images', authorize=access())
    async def images_legacy(request):
        return response_for(await publish_api.images_get(context(request)))

    @app.route('/api/publishment/{pub_name:path}', methods=('DELETE',), authorize=access())
    async def delete_legacy(request):
        return response_for(await publish_api.publishment_delete(request.path_params['pub_name'], context(request)))

    @app.route('/api/publishing/capabilities', authorize=access())
    async def capabilities(request):
        return response_for(await publishing_api.capabilities())

    @app.route('/api/publishing/inventory', authorize=access())
    async def inventory(request):
        return response_for(await publishing_api.inventory(context(request)))

    @app.route('/api/publishing/publication', methods=('PUT',), authorize=access(JSONBody))
    async def publish(request):
        data = await model_input(request, checked)
        return response_for(await publishing_api.publish(context(request), data))

    @app.route('/api/publishing/publication/{name:path}', methods=('DELETE',), authorize=access())
    async def delete(request):
        return response_for(await publishing_api.delete(context(request), request.path_params['name']))

    @app.route('/api/publishing/image', methods=('PUT',), authorize=access(UploadBody))
    async def image(request):
        return response_for(await publishing_api.image(context(request), await file_input(request)))
