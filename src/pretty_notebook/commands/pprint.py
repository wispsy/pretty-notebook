"""Read-only terminal notebook rendering using shared syntax and layout."""

from html import escape
from pathlib import Path
import re
from urllib.parse import quote

from escape_colors.markdown import markdown_print, render_html
from expose_interface import CommandError
from parse_md import RendererContext, TypedRenderer
from parse_md.nodes import ImageEmbed, WikiLink

from pretty_notebook.helpers import pass_nb
from pretty_notebook.markdown import parse_notebook
from pretty_notebook.markdown.dialect import slugify
from pretty_notebook.models import Note

_SCHEMES = ('http', 'https', 'mailto', 'pnbp', 'nano')


def _local_url(nb, path, scheme, fragment=None):
    root = Path(nb.NOTE_PATH).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Terminal note links must stay inside the notebook.')
    value = scheme + '://' + quote(str(target), safe='/')
    return value + ('#' + quote(slugify(fragment)) if fragment else '')


def _anchor(label, target):
    return '<a href="' + escape(target, quote=True) + '">' + escape(label) + '</a>'


def _menu(note, nb):
    numbers = [int(match[1]) for name in nb.notes if (match := re.fullmatch(r'new(\d{1,3})', name))]
    new_name = f'new{max(numbers)+1}.md' if numbers else 'new.md'
    source_path = note.source_path or note.name + '.md'
    return ('<hr /><p><strong>MENU</strong> :</p><p>---&gt;: ' +
            _anchor('refresh', _local_url(nb, source_path, 'pnbp')) + '</p><p>nano: ' +
            _anchor(note.name, _local_url(nb, source_path, 'nano')) + '</p><p>nano: ' +
            _anchor('new note', _local_url(nb, new_name, 'nano')) + '</p><hr />')


def _terminal_html(source, note, nb):
    graph = None

    def wiki(node, context):
        nonlocal graph
        address, _, label = node.target.partition('|')
        label = label.strip() or address.strip().replace('#', ' > ')
        if graph is None:
            graph = nb.graph_index()
        resolved = graph.resolve(node.target, source=note.source_path)
        if resolved.state != 'resolved':
            return escape(label)
        fragment = address.split('#', 1)[1].strip() if '#' in address else None
        return _anchor(label, _local_url(nb, resolved.path, 'pnbp', fragment))

    def image(node, context):
        return '<span>[' + escape(node.name) + ']</span>'

    document = parse_notebook(source)
    context = RendererContext(source_path=note.source_path, dialect='extended',
                              soft_breaks='br', trust='escape',
                              node_handlers=((WikiLink, wiki), (ImageEmbed, image)))
    html = TypedRenderer().render_document(document, context).html
    frame = _menu(note, nb)
    return frame + html + frame


@pass_nb
def get_terminal_note(note: Note, nb=None, *, width=80, color=False, hyperlinks=False):
    """Return buffered display text; never save notes or launch a URL handler."""
    return render_html(_terminal_html(note.current_md, note, nb), width=width,
                       color=color, hyperlinks=hyperlinks, allowed_schemes=_SCHEMES)


@pass_nb
def get_rich_note(note: Note, nb=None):
    """Compatibility spelling returning plain terminal text since 0.12."""
    return get_terminal_note(note=note, nb=nb)


@pass_nb
def _pprint(note: Note, nb=None):
    """Print the current note with destination-aware terminal Markdown."""
    try:
        markdown_print(note.current_md, parser=lambda source: _terminal_html(source, note, nb),
                       hyperlinks=True, allowed_schemes=_SCHEMES)
    except ValueError:
        raise CommandError('Could not render this note within the terminal limits.') from None
