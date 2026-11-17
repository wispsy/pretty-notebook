"""Owner-managed site identity with durable, content-versioned favicons."""

from expose_api import HTTPException, Response, UploadFile
from native_requests import ApplicationRequest as Request

import asyncio
import hashlib
import re
from pathlib import Path


from .atomic_io import atomic_write_bytes
from .png import MAX_FAVICON_BYTES, validate_png
from .layout_api import get_layout_content

VERSION = re.compile(r"[a-f0-9]{64}\Z")


async def stylesheet_put(request: Request):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 65_536:
            raise HTTPException(413, "Stylesheet exceeds the 64 KiB limit.")
    try:
        content.decode("utf-8")
    except UnicodeError as error:
        raise HTTPException(400, "Stylesheet must be UTF-8.") from error
    try:
        async with request.app.state.storage_lock:
            await atomic_write_bytes(request.app.state.settings_path.parent / "appearance.css", bytes(content))
    except OSError as error:
        raise HTTPException(503, "Stylesheet storage is unavailable.") from error
    return Response(status=204)


async def stylesheet_get(request: Request):
    if not (await get_layout_content())["APPEARANCE"]["custom_css"]:
        raise HTTPException(404, "Stylesheet not enabled.")
    path = request.app.state.settings_path.parent / "appearance.css"
    try:
        if path.is_symlink():
            raise OSError("Stylesheet must be a regular file.")
        content = await asyncio.to_thread(path.read_bytes)
    except FileNotFoundError as error:
        raise HTTPException(404, "Stylesheet not found.") from error
    except OSError as error:
        raise HTTPException(503, "Stylesheet storage is unavailable.") from error
    return Response(content, media_type="text/css; charset=utf-8", headers={"Cache-Control": "no-cache"})


def _read_favicon(path: Path) -> bytes | None:
    if path.is_symlink():
        raise ValueError("Favicon must be a regular file.")
    try:
        with path.open("rb") as source:
            content = source.read(MAX_FAVICON_BYTES + 1)
        validate_png(content)
        return content
    except FileNotFoundError:
        return None


async def read_favicon(request: Request) -> bytes | None:
    try:
        return await asyncio.to_thread(_read_favicon, request.app.state.favicon_path)
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Favicon storage is unavailable.") from error


def favicon_url(request: Request, content: bytes) -> str:
    version = hashlib.sha256(content).hexdigest()
    return request.scope.get("root_path", "") + f"/static/favicon/{version}.png"


async def favicon_post(request: Request, file: UploadFile):
    """Validate and atomically replace the site favicon with a static PNG."""
    try:
        if Path(file.filename or "").suffix.lower() != ".png":
            raise HTTPException(400, "Favicon must use the PNG format.")
        content = await file.read(MAX_FAVICON_BYTES + 1)
        if len(content) > MAX_FAVICON_BYTES:
            raise HTTPException(413, "Favicon exceeds the 1 MiB limit.")
        try:
            width, height = validate_png(content)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        async with request.app.state.favicon_lock:
            await atomic_write_bytes(request.app.state.favicon_path, content)
    finally:
        await file.close()
    return {"url": favicon_url(request, content), "width": width, "height": height}


async def favicon_get(request: Request, version: str):
    if not VERSION.fullmatch(version):
        raise HTTPException(404, "Favicon not found.")
    content = await read_favicon(request)
    if content is None or hashlib.sha256(content).hexdigest() != version:
        raise HTTPException(404, "Favicon not found.")
    return Response(content, media_type="image/png", headers={
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": f'"{version}"',
    })
