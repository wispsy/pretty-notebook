"""Notebook spelling for the shared extended document profile."""

from parse_md.dialect import attributes, heading_attributes, prepare_task_item, slugify, special_block
from .inlines import parse


def parse_notebook(source, *, options=None):
    return parse(source, options=options, dialect='notebook')
