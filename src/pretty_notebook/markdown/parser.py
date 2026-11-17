"""Compatibility entry point for the independent bounded block parser."""

from parse_md import parse_blocks as _parse_blocks
from parse_md.parser import Diagnostic, ParseLimitError, ParseOptions, SourceMap, SourceSpan
from .nodes import _adapt_document


def parse_blocks(source, *, options=None, dialect='commonmark'):
    selected = 'extended' if dialect == 'notebook' else dialect
    return _adapt_document(_parse_blocks(source, options=options, dialect=selected),
                           'notebook' if dialect == 'notebook' else None)
