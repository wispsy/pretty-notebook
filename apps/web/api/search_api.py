"""Literal anonymous search over current public publication revisions."""

from expose_api import HTTPException
from native_requests import ApplicationRequest as Request

import asyncio
from typing import Literal


from .public_index import IndexCapacityError, search_documents, validate_search

SearchField = Literal["any", "title", "content", "tag"]


async def results(request, q, field, tags, limit, offset):
    if "regex" in request.query_params:
        raise HTTPException(422, "Regular expressions are only supported by local notebook search.")
    try:
        validate_search(q, field, tags, limit, offset)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        documents = await request.app.state.public_index.snapshot()
    except IndexCapacityError as error:
        raise HTTPException(503, str(error)) from error
    return await asyncio.to_thread(search_documents, documents, q, field=field,
                                   tags=tags, limit=limit, offset=offset)


async def search(request: Request, q: str,
                 field: SearchField = "any",
                 tag: list[str] = [],
                 limit: int = 20,
                 offset: int = 0):
    return await results(request, q, field, tag, limit, offset)
