"""Application-owned wire, validation and service adapters for native handlers."""

from collections.abc import Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, time
from email.message import Message
import inspect
import json
from types import SimpleNamespace

from expose_api import JSONResponse, MultipartLimits, Response, UploadFile
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from starlette.responses import Response as BaselineResponse

from api import auth_api

MISSING = object()
BODY_LIMIT = 16 * 1024 * 1024


class Headers(Mapping):
    """Case-insensitive first-value reads over the original ordered headers."""

    def __init__(self, headers):
        self.pairs = headers.multi_items()

    def __getitem__(self, name):
        name = name.lower()
        for key, value in self.pairs:
            if key == name:
                return value
        raise KeyError(name)

    def __iter__(self):
        return iter(dict(self.pairs))

    def __len__(self):
        return len(dict(self.pairs))


class ApplicationRequest:
    """Bind explicit native request metadata to existing application services."""

    def __init__(self, request, application):
        self.http, self.app = request, application
        self.scope, self.method = request.scope, request.method
        self.headers = Headers(request.headers)
        self.url = SimpleNamespace(path=request.path)

    @property
    def query_params(self):
        return self.http.query_params


def json_value(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode='json')
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, bytes):
        return value.decode('utf-8')
    if isinstance(value, Exception):
        return {}
    return value


def response_for(value, *, status=200):
    if isinstance(value, BaselineResponse):
        return Response(value.body, status=value.status_code, headers=value.raw_headers)
    return JSONResponse(json_value(value), status=status)


@dataclass(frozen=True)
class Authentication:
    user: object


async def authentication(request, overrides):
    override = overrides.get(auth_api.get_current_user)
    if override is not None:
        user = override()
        return Authentication(await user if inspect.isawaitable(user) else user)
    value = Headers(request.headers).get('Authorization', '')
    scheme, _, token = value.partition(' ')
    if not value or scheme.casefold() != 'bearer':
        raise auth_api.unauthorized('Not authenticated')
    return Authentication(await auth_api.get_current_user(token))


@dataclass(frozen=True)
class JSONBody:
    value: object


async def json_body(request):
    body = await request.body()
    if not body:
        return JSONBody(MISSING)
    message = Message()
    raw = Headers(request.headers).get('Content-Type')
    if raw:
        message['content-type'] = raw
    is_json = raw is None or (message.get_content_maintype() == 'application' and
                             (message.get_content_subtype() == 'json' or
                              message.get_content_subtype().endswith('+json')))
    if not is_json:
        return JSONBody(body)
    try:
        return JSONBody(json.loads(body))
    except json.JSONDecodeError as error:
        raise HTTPException(422, [{'type': 'json_invalid', 'loc': ['body', error.pos],
            'msg': 'JSON decode error', 'input': {}, 'ctx': {'error': error.msg}}]) from None
    except UnicodeDecodeError:
        raise HTTPException(400, 'There was an error parsing the body') from None


def missing_input(*path):
    raise HTTPException(422, [{'type': 'missing', 'loc': ['body', *path],
                             'msg': 'Field required', 'input': None}])


async def model_input(request, schema):
    body = (await request.resolve(JSONBody)).value
    if body is MISSING or body is None:
        missing_input()
    try:
        return schema.validate_python(body, from_attributes=True)
    except ValidationError as error:
        details = error.errors(include_url=False)
        for detail in details:
            detail['loc'] = ['body', *detail['loc']]
        raise HTTPException(422, json_value(details)) from None


@dataclass(frozen=True)
class UploadBody:
    form: Mapping


@asynccontextmanager
async def upload_body(request):
    message = Message()
    message['content-type'] = Headers(request.headers).get('Content-Type', '')
    media_type = message.get_content_type()
    async with AsyncExitStack() as stack:
        if media_type == 'multipart/form-data' and message.get_param('boundary') is None:
            raise HTTPException(400, 'Missing boundary in multipart.')
        try:
            if media_type == 'multipart/form-data':
                form = await stack.enter_async_context(request.multipart(limits=MultipartLimits(
                    max_total_bytes=BODY_LIMIT, max_part_bytes=BODY_LIMIT,
                    max_field_bytes=1024 * 1024, max_parts=1024,
                    max_files=1000, max_fields=1000)))
            elif media_type == 'application/x-www-form-urlencoded':
                form = await request.form()
            else:
                form = {}
        except Exception as error:
            # Adapt only a decoder's selected HTTP refusal. Disconnects,
            # cancellation, protocol and I/O failures retain their ownership.
            status = getattr(error, 'status', None)
            if status not in (400, 413, 415):
                raise
            detail = 'Image exceeds the 10 MiB limit.' if status == 413 else 'There was an error parsing the body'
            raise HTTPException(413 if status == 413 else 400, detail) from None
        yield UploadBody(form)


async def file_input(request):
    value = (await request.resolve(UploadBody)).form.get('file')
    if value is None or value == '':
        missing_input('file')
    if not isinstance(value, UploadFile):
        message = f"Expected UploadFile, received: {type(value)}"
        raise HTTPException(422, [{'type': 'value_error', 'loc': ['body', 'file'],
            'msg': 'Value error, ' + message, 'input': json_value(value), 'ctx': {'error': {}}}])
    return value
