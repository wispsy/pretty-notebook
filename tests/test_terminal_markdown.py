"""Notebook terminal adapters preserve state, literal content and output policy."""

import io
from pathlib import Path
from urllib.parse import quote

import pytest
from expose_interface import CommandError

from pretty_notebook import Notebook
from pretty_notebook.commands.pprint import _pprint, get_rich_note, get_terminal_note


@pytest.fixture
def notebook(tmp_path, monkeypatch):
    monkeypatch.setenv('PNBP_SETTINGS', 'off')
    root = tmp_path/'notes with spaces'
    root.mkdir()
    (root/'alpha.md').write_text('Original.\n')
    (root/'beta.md').write_text('# Beta\n')
    (root/'new2.md').write_text('Existing new note.\n')
    return Notebook(root)


def test_pending_markdown_menu_and_literal_code_are_read_only(notebook):
    note = notebook.notes['alpha']
    note.md_out = '# Pending\n\n**bold** [[beta|Target]]\n\n- [x] done\n\n| A | B |\n| --- | --- |\n| one | two |\n\n```python\n[[beta]] #public ~~literal~~ red(value)\n```\n'
    root = Path(notebook.NOTE_PATH)
    before = {path: (path.read_bytes(),path.stat().st_mtime_ns) for path in root.rglob('*') if path.is_file()}
    current = note.md_out
    rendered = get_terminal_note(note=note, nb=notebook, width=300)
    assert 'Pending' in rendered and 'bold' in rendered and 'one' in rendered and '[x] done' in rendered
    assert '[[beta]] #public ~~literal~~ red(value)' in rendered
    assert 'Target' in rendered and 'pnbp://'+quote(str(root/'beta.md'),safe='/') in rendered
    assert 'refresh' in rendered and 'nano://'+quote(str(root/'new3.md'),safe='/') in rendered
    assert '\x1b' not in rendered
    assert current == note.md_out and note.is_unsaved
    assert before == {path: (path.read_bytes(),path.stat().st_mtime_ns) for path in root.rglob('*') if path.is_file()}
    assert isinstance(get_rich_note(note=note, nb=notebook), str)


class Tty(io.StringIO):
    def isatty(self): return True


@pytest.mark.parametrize('no_color', [False, True])
def test_tty_links_and_no_color_follow_destination(notebook, monkeypatch, no_color):
    note = notebook.notes['alpha']
    note.md_out = '**Styled** [[beta]]\n'
    stream = Tty()
    monkeypatch.setenv('TERM', 'xterm-256color')
    if no_color: monkeypatch.setenv('NO_COLOR', '1')
    else: monkeypatch.delenv('NO_COLOR', raising=False)
    monkeypatch.setattr('sys.stdout', stream)
    _pprint(note=note, nb=notebook)
    output = stream.getvalue()
    assert 'Styled' in output
    if no_color:
        assert '\x1b' not in output and 'pnbp://' in output
    else:
        assert '\x1b[' in output and '\x1b]8;;pnbp://' in output


def test_source_controls_cannot_become_terminal_commands(notebook):
    note = notebook.notes['alpha']
    note.md_out = 'literal \x1b[31m red(value) \x9b31m\n'
    output = get_terminal_note(note=note, nb=notebook, width=300)
    assert '\x1b' not in output and '\x9b' not in output
    assert 'red(value)' in output and '\\x1b' in output and '\\x9b' in output


def test_limit_failure_prints_no_partial_note(notebook, capsys):
    note = notebook.notes['alpha']
    note.md_out = 'x' * 2_000_001
    with pytest.raises(CommandError, match='terminal limits'):
        _pprint(note=note, nb=notebook)
    assert capsys.readouterr().out == ''
    assert note.md_out == 'x'*2_000_001
