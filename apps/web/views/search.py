"""Escaped, server-rendered public notebook search."""

from expose_api import HTTPException
from native_requests import ApplicationRequest as Request

from urllib.parse import urlencode


from api.search_api import SearchField, results
from api.public_index import normalize_tags
from . import home


async def search(request: Request, q: str = "",
                 field: SearchField = "any",
                 tag: list[str] = [],
                 limit: int = 20,
                 offset: int = 0):
    content = await home.get_template_content(request)
    try:
        filters = normalize_tags(tag)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    content.update(page_title="Search", query=q, search_field=field, tags=filters, report=None,
                   previous_url=None, next_url=None)
    if q:
        report = await results(request, q, field, tag, limit, offset)
        content["report"] = report
        def page_url(page_offset):
            params = [("q", q), ("field", field), ("limit", str(limit)), ("offset", str(page_offset))]
            params.extend(("tag", value) for value in tag)
            return content["root_path"] + "/n/search?" + urlencode(params)
        if offset:
            content["previous_url"] = page_url(max(0, offset - limit))
        if offset + limit < report["total"]:
            content["next_url"] = page_url(offset + limit)
    return home.templates.TemplateResponse(request, "home/search.html", content)
