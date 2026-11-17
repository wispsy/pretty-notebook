"""Explicit staged HTTP dispatch over the unchanged application services."""

from expose_api import App


class _BaselineDispatch:
    """Keep unported HTTP groups on the recorded baseline during migration."""

    def __init__(self, application, *, baseline):
        self.baseline = baseline

    async def __call__(self, scope, receive, send):
        await self.baseline(scope, receive, send)


class ExposedApplication:
    """A selectable Expose API HTTP factory with one explicit baseline lifespan.

    The first compatibility stage delegates all groups to the baseline. Later
    stages select native handlers explicitly; no signature injection is inferred.
    """

    framework = 'expose-api'

    def __init__(self, baseline):
        self.baseline = baseline
        self.state = baseline.state
        self.root_path = baseline.root_path
        self.dependency_overrides = baseline.dependency_overrides
        self.http_app = App(title='Pretty Notebook', max_body_size=16 * 1024 * 1024)
        self.http_app.add_middleware(_BaselineDispatch, baseline=baseline)

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            await self.http_app(scope, receive, send)
        else:
            # The existing factory owns ORM startup, migrations, the process
            # lock and shutdown exactly once, including startup error details.
            await self.baseline(scope, receive, send)
