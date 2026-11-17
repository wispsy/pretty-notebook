"""Pretty Notebook's native HTTP factory and persistent storage layout."""

import assets
import web_config
from api import layout_api, publish_api
from api.atomic_io import create_text_once
from api.process_lock import ProcessLock
from expose_web import ExposedApplication
from pretty_notebook._internal.routes import validate_prefix
from types import SimpleNamespace

DEFAULT_DATABASE_URL = web_config.DATABASE_URL


def prepare_storage() -> None:
    """Create the private persistent-data layout without overwriting state."""
    for directory in {
        publish_api.PUB_PATH,
        publish_api.IMG_PATH,
        layout_api.WEB_SETTINGS_PATH.parent,
    }:
        if not directory.exists():
            directory.mkdir(parents=True, mode=0o700, exist_ok=True)

    if not layout_api.WEB_SETTINGS_PATH.exists():
        defaults = web_config.DEFAULT_SETTINGS_PATH.read_text(encoding="utf-8")
        create_text_once(layout_api.WEB_SETTINGS_PATH, defaults)


def create_app(*, db_url=DEFAULT_DATABASE_URL, allowed_hosts=None, root_path=None, framework=None):
    """Create one native worker sharing a local SQLite data root."""
    web_config.web_framework(framework)
    if not db_url.startswith('sqlite://'):
        raise RuntimeError('The supported web profile requires a SQLite database URL.')
    asset_resolver = assets.AssetResolver(web_config.WEB_ROOT / 'static', mode=web_config.asset_mode())
    prepare_storage()
    lock = ProcessLock(layout_api.WEB_SETTINGS_PATH.parent / 'site.lock')
    state = SimpleNamespace(storage_lock=lock, bootstrap_lock=lock,
        pages_path=publish_api.PUB_PATH, images_path=publish_api.IMG_PATH,
        settings_path=layout_api.WEB_SETTINGS_PATH,
        favicon_path=layout_api.WEB_SETTINGS_PATH.parent / 'favicon.png', favicon_lock=lock,
        assets=asset_resolver, code_highlight=web_config.code_highlight())
    return ExposedApplication(state, db_url=db_url,
        root_path=validate_prefix(root_path if root_path is not None else web_config.url_prefix()),
        allowed_hosts=allowed_hosts or web_config.allowed_hosts())


api = create_app()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(api, port=8000, host='127.0.0.1')
