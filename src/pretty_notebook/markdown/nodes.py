"""Shared immutable Markdown values and notebook compatibility adapters."""

from parse_md.nodes import (
    literal, safe_url, Node, Text, Container, BoldText,
    ItalicText, Paragraph, Heading, ListItem, BulletList, OrderedList,
    Link, Image, CodeBlock, WikiLink, BlockQuote, ThematicBreak,
    RawHtml, ReferenceDefinition, Code, SoftBreak, HardBreak, StrikethroughText,
    HighlightedText, TableCell, TableRow, Table, TaskListItem, FootnoteDefinition,
    FootnoteReference, ImageEmbed, TagText, TableOfContents, Mermaid,
)
from parse_md.nodes import Document as _Document

NotebookLink = WikiLink


class Document(_Document):
    """Preserve the notebook renderer default while sharing generic nodes."""

    def to_html(self, *, renderer=None, context=None):
        from .renderers import RendererContext, TypedRenderer
        return (renderer or TypedRenderer()).render(self, context or RendererContext())


MarkdownText = Document


def _adapt_document(document, dialect=None):
    result = Document(*document.children, span=document.span, source=document.source,
                      positions=document.positions, attributes=document.attributes)
    object.__setattr__(result, 'diagnostics', document.diagnostics)
    object.__setattr__(result, 'dialect', dialect or document.dialect)
    return result


def from_component(value) -> Node:
    """Adapt legacy values without changing their constructors or string semantics."""
    from pretty_notebook.models.components import CodeBlock as LegacyCode, Link as WikiLink, Tag, Url
    if isinstance(value, LegacyCode):
        return CodeBlock(value.body, value.lang or '')
    if isinstance(value, WikiLink):
        return NotebookLink(str(value))
    if isinstance(value, Url):
        return Link(str(value))
    if isinstance(value, Tag):
        return Text(str(value))
    raise TypeError('Expected a legacy Link, Tag, Url, or CodeBlock.')
