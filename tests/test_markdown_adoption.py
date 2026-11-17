"""The notebook owns application policy while generic syntax stays shared."""

import importlib.metadata
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import parse_md
import pytest

from pretty_notebook import Notebook
from pretty_notebook._internal import publication_plan, rendering
from pretty_notebook.markdown import Document, Paragraph, RendererContext, SourceSpan, parse_notebook, render_notebook
from pretty_notebook.markdown.nodes import NotebookLink


def test_shared_values_and_compatibility_document_preserve_source_spans():
    source = '# Héading\n\n[[target]] and **bold**.\n'
    document = parse_notebook(source)
    generic = parse_md.parse(source, dialect=parse_md.EXTENDED)
    assert Paragraph is parse_md.Paragraph and SourceSpan is parse_md.SourceSpan
    assert NotebookLink is parse_md.WikiLink
    assert isinstance(document, parse_md.Document) and isinstance(document, Document)
    assert document.to_markdown() == generic.to_markdown() == source
    assert document.span == generic.span
    assert document.children == generic.children
    assert document.dialect == 'notebook'
    assert document.to_html() == render_notebook(source).html


def test_notebook_policy_keeps_images_external_links_and_nested_footnotes():
    source = '[label [^a]](https://example.com) ![[image.png]]\n\n[^a]: detail\n'
    document = parse_notebook(source)
    before = document.to_markdown(), document.children
    result = document.to_html()
    assert 'rel="nofollow" target="_blank"' in result
    assert 'class="footnote-ref"' in result and 'detail' in result
    assert "class=\"img-fluid\" src='/static/imgs/image.png'" in result
    assert 'data-pnbp-external' not in result
    assert before == (document.to_markdown(), document.children)


def test_reused_context_observes_current_routing_and_publication_policy(tmp_path, monkeypatch):
    monkeypatch.setenv('PNBP_SETTINGS', 'off')
    (tmp_path/'Target.md').write_text('#public\n# Heading\n')
    nb = Notebook(tmp_path)
    nb.PUB_LNK_ONLY = True
    context = replace(RendererContext(nb), dialect='notebook')
    source = parse_notebook('[[Target]]')
    assert "href='/target'" in source.to_html(context=context)
    nb.config['URL_PREFIX'] = '/notes'
    assert "href='/notes/target'" in source.to_html(context=context)
    nb.COMMIT_TAG = '#other'
    assert "href='/target'" not in source.to_html(context=context)


def test_parser_version_and_installed_sources_are_in_publication_fingerprints(tmp_path, monkeypatch):
    monkeypatch.setenv('PNBP_SETTINGS', 'off')
    nb = Notebook(tmp_path)
    initial = publication_plan.renderer_fingerprint(nb)
    identity = rendering.backend_identity(nb)['engine']
    assert identity['version'] == '0.1.0'
    assert identity['dialect'] == parse_md.EXTENDED.identity
    assert len(identity['implementation']) == 64
    original = importlib.metadata.version
    monkeypatch.setattr(importlib.metadata, 'version', lambda name: '0.1.1' if name == 'parse-md' else original(name))
    assert publication_plan.renderer_fingerprint(nb) != initial
    monkeypatch.setattr(importlib.metadata, 'version', original)
    module = tmp_path/'engine'
    module.mkdir()
    (module/'__init__.py').write_text('first')
    monkeypatch.setattr(parse_md, '__file__', str(module/'__init__.py'))
    first = publication_plan.renderer_fingerprint(nb)
    (module/'__init__.py').write_text('second')
    assert publication_plan.renderer_fingerprint(nb) != first


@pytest.mark.parametrize('document', [Document(Paragraph('builder')), parse_notebook('parsed **source**')])
def test_compatibility_documents_reject_inherited_and_new_attribute_assignment(document):
    for name, value in [('children', ()), ('extra_state', 'mutable')]:
        with pytest.raises(FrozenInstanceError):
            setattr(document, name, value)
