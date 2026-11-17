"""Retain public host-refusal text over the native trusted-host policy."""

from expose_api import Response, TrustedHostMiddleware


class TrustedHosts:
    def __init__(self, application, *, allowed_hosts):
        self.application = application
        self.selected = TrustedHostMiddleware(self.forward, allowed_hosts=allowed_hosts)
        self.marker = 'pnbp.trusted-host'

    async def forward(self, scope, receive, send):
        marker = scope[self.marker]
        marker[0] = True
        selected = dict(scope)
        selected.pop(self.marker)
        await self.application(selected, receive, send)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.application(scope, receive, send)
            return
        marker = [False]
        async def accepted(event):
            if marker[0]:
                await send(event)
            elif event['type'] == 'http.response.start':
                await Response('Invalid host header', status=400,
                               media_type='text/plain; charset=utf-8')(scope, receive, send)
        await self.selected({**scope, self.marker: marker}, receive, accepted)
