"""Caller-owned escaped Jinja templates over native HTML responses."""

from expose_api import HTMLResponse
from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape


class RenderedTemplate(HTMLResponse):
    def __init__(self, template, context, *, status):
        self.template, self.context = template, context
        super().__init__(template.render(context), status=status)

    async def __call__(self, scope, receive, send):
        if 'http.response.debug' in scope.get('extensions', {}):
            await send({'type': 'http.response.debug', 'info': {'template': self.template, 'context': self.context}})
        await super().__call__(scope, receive, send)


class Templates:
    def __init__(self, directory):
        self.env = Environment(loader=FileSystemLoader(directory), autoescape=select_autoescape())
        @pass_context
        def url_for(context, name, **params):
            return context['request'].url_for(name, **params)
        self.env.globals['url_for'] = url_for

    def TemplateResponse(self, request, name, context, *, status=200):
        return RenderedTemplate(self.env.get_template(name), {**context, 'request': request}, status=status)
