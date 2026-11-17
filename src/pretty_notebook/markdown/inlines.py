"""Compatibility entry point for shared inline parsing and source spans."""

from parse_md import parse as _parse
from parse_md.inlines import decode, destination, normalize_label, plain_text, reference_definition
from .nodes import _adapt_document


def parse(source, *, options=None, dialect='commonmark'):
    selected = 'extended' if dialect == 'notebook' else dialect
    return _adapt_document(_parse(source, options=options, dialect=selected),
                           'notebook' if dialect == 'notebook' else None)
