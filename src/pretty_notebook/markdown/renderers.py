"""Notebook URL, publication and legacy-backend policy around Parse MD."""

from copy import copy
from dataclasses import dataclass, field, fields, replace
from html import escape
import re
from urllib.parse import quote

from parse_md.renderers import (
    DiagramInfo, HeadingInfo, RenderedMarkdown, Renderer,
    RendererContext as _Context, TypedRenderer as _TypedRenderer,
)
from .nodes import ImageEmbed, Link, Node, NotebookLink, Text, safe_url


def _dialect(value):
    if value not in (None, 'commonmark', 'notebook', 'extended'):
        raise ValueError('Unknown renderer dialect.')
    return 'extended' if value == 'notebook' else value


def _resolve(notebook, target, source_path, dialect, *, graph=None, notes_by_path=None):
    from .dialect import slugify
    address = target.split('|', 1)[0].strip()
    if address.startswith('#'):
        return '#' + quote(slugify(address[1:].strip()))
    if notebook is None:
        return None
    from pretty_notebook._internal import routes
    graph = graph if graph is not None else notebook.graph_index()
    result = graph.resolve(target, source=source_path)
    if result.state != 'resolved':
        return None
    notes = notes_by_path if notes_by_path is not None else {note.source_path: note for note in notebook.notes.values()}
    note = notes.get(result.path)
    if note is None or (dialect == 'extended' and notebook.PUB_LNK_ONLY and not notebook.is_publishable(note)):
        return None
    url = routes.public_url(notebook.config.get('URL_PREFIX', ''), routes.route_for(note, notebook.config).route)
    if '#' in address:
        url += '#' + quote(slugify(address.split('#', 1)[1].strip()))
    return safe_url(url)


def _context(notebook=None, source_path=None, trust='escape', dialect=None, soft_breaks=None):
    selected = _dialect(dialect)
    graph, notes = None, None

    def resolve(target, path):
        nonlocal graph, notes
        if notebook is not None and not target.split('|', 1)[0].strip().startswith('#') and graph is None:
            graph = notebook.graph_index()
            notes = {note.source_path: note for note in notebook.notes.values()}
        return _resolve(notebook, target, path, selected, graph=graph, notes_by_path=notes)

    def image(node, context):
        from pretty_notebook._internal.routes import public_image_url
        value = public_image_url(notebook.config if notebook else {}, node.name)
        try:
            safe_url(value)
        except ValueError:
            value = ''
        value = escape(quote(value, safe="/:?#@!$&'()*+,;=%-._~"), quote=True)
        return '<img class="img-fluid" src=\'' + value + "'>"

    def keep_tag(tag, path):
        return not (notebook is not None and notebook.config.get('HIDE_COMMIT_TAG') and tag == notebook.COMMIT_TAG)

    def decorate(destination, path):
        from pretty_notebook._internal.icons import render_icon
        return ' ' + render_icon('external', size='sm')

    return _Context(source_path=source_path, trust=trust, dialect=selected,
                    soft_breaks=soft_breaks, resolver=resolve, tag_filter=keep_tag,
                    decorate_link=decorate if selected == 'extended' else None,
                    node_handlers=((ImageEmbed, image),))


@dataclass(frozen=True, init=False)
class RendererContext(_Context):
    """Keep the notebook-first constructor and explicit HTML trust selection."""

    notebook: object | None = None
    resolver: object | None = field(default=None, init=False, compare=False)
    image_resolver: object | None = field(default=None, init=False, compare=False)
    tag_filter: object | None = field(default=None, init=False, compare=False)
    decorate_link: object | None = field(default=None, init=False, compare=False)
    node_handlers: tuple = field(default=(), init=False, compare=False)

    def __init__(self, notebook=None, source_path=None, trust='escape', dialect=None, soft_breaks=None):
        context = _context(notebook, source_path, trust, dialect, soft_breaks)
        for field in fields(_Context):
            object.__setattr__(self, field.name, getattr(context, field.name))
        object.__setattr__(self, 'notebook', notebook)

    def resolve(self, target, *, graph=None, notes_by_path=None):
        return _resolve(self.notebook, target, self.source_path, self.dialect,
                        graph=graph, notes_by_path=notes_by_path)


class PythonMarkdownRenderer:
    """Render constructed values through the production Markdown dependency.

    Builders contain no raw HTML node. Literal text is encoded before Markdown
    processing, independent of the context's HTML policy.
    """

    def render(self, document: Node, context: RendererContext) -> str:
        try:
            import markdown
        except ModuleNotFoundError as error:
            raise RuntimeError('PythonMarkdownRenderer requires pretty-notebook[legacy-markdown].') from error
        if document.source is not None and context.trust != 'trusted':
            raise ValueError('Parsed source requires a typed renderer or an explicit trusted context.')
        from .nodes import Container, Link, RawHtml

        def source(node):
            if isinstance(node, RawHtml) and context.trust != 'trusted':
                return Text(node.value).to_markdown()
            if isinstance(node, NotebookLink):
                address, _, label = node.target.partition('|')
                label = label.strip() or address.strip()
                url = context.resolve(node.target)
                return Link(url, label).to_markdown() if url is not None else Text(label).to_markdown()
            if isinstance(node, Container):
                # Adapt descendants before serializing; original values stay immutable.
                from copy import copy
                adapted = copy(node)
                object.__setattr__(adapted, 'children', tuple(Source(source(child)) for child in node.children))
                return adapted.to_markdown()
            return node.to_markdown()

        return markdown.markdown(source(document), extensions=['fenced_code', 'tables', 'attr_list', 'footnotes', 'toc', 'nl2br'])


@dataclass(frozen=True)
class Source(Node):
    """Internal already-serialized child used only by the backend adapter."""

    value: str

    def _markdown(self):
        return self.value



_LINK_MARKER = 'data-pnbp-external'


def _publication_links(node):
    """Mark only typed links on copied values; keep caller source/state intact."""
    children = getattr(node, 'children', ())
    adapted = tuple(_publication_links(child) for child in children)
    if not isinstance(node, Link) and all(a is b for a, b in zip(children, adapted)):
        return node
    result = copy(node)
    if children:
        object.__setattr__(result, 'children', adapted)
    if isinstance(node, Link):
        values = tuple((key, value) for key, value in node.attributes if key != _LINK_MARKER)
        object.__setattr__(result, 'attributes', (*values, (_LINK_MARKER, '1')))
    return result


def _external_attributes(match):
    tag = match[0]
    marker = ' ' + _LINK_MARKER + '="1"'
    if marker not in tag:
        return tag
    return tag.replace(marker, '').replace('<a ', '<a rel="nofollow" target="_blank" ', 1)


class TypedRenderer(_TypedRenderer):
    def render_document(self, document, context=None):
        context = context or RendererContext()
        dialect = context.dialect or getattr(document, 'dialect', 'commonmark')
        if isinstance(context, RendererContext):
            context = _context(context.notebook, context.source_path, context.trust, dialect, context.soft_breaks)
        elif dialect == 'notebook':
            context = replace(context, dialect='extended')
        extended = context.dialect == 'extended'
        result = super().render_document(_publication_links(document) if extended else document, context)
        if extended:
            # The typed marker distinguishes ordinary links from wiki/TOC/footnote links.
            result = replace(result, html=re.sub(r'<a\s[^>]*>', _external_attributes, result.html))
        return result


class NotebookRenderer(TypedRenderer):
    def render_document(self, document, context=None):
        context = context or RendererContext()
        if isinstance(context, RendererContext):
            context = RendererContext(context.notebook, context.source_path, context.trust, 'notebook', context.soft_breaks)
        else:
            context = replace(context, dialect='extended')
        return super().render_document(document, context)


def render_notebook(source, *, context=None, options=None):
    from .dialect import parse_notebook
    return NotebookRenderer().render_document(parse_notebook(source, options=options), context)
