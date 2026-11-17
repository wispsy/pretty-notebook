"""Shared readiness service for the explicitly selected HTTP factories."""

from fastapi import HTTPException
from tortoise import connections

from . import layout_api


async def health_status():
    try:
        await connections.get('default').execute_query('SELECT 1')
        await layout_api.get_layout_content()
    except Exception as error:
        raise HTTPException(503, 'Persistent storage is unavailable.') from error
    return {'status': 'ok'}
