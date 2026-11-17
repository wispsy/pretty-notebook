"""Escaped public notebook and directory indexes under a fixed route."""

from expose_api import HTTPException
from native_requests import ApplicationRequest as Request



from api.public_navigation import snapshot_navigation, validate_directory
from . import home


async def notebook_index(request: Request, directory: str = "",
                         limit: int = 50,
                         offset: int = 0):
    try:
        validate_directory(directory)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    navigation = await snapshot_navigation(request)
    report = navigation.directory(directory, limit=limit, offset=offset)
    content = await home.get_template_content(request, page_title=directory.rsplit("/", 1)[-1] if directory else "Notebook")
    content["notebook_index"] = report
    return home.templates.TemplateResponse(request, "home/notebook.html", content)
