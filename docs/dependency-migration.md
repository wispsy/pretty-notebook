# Dependency migration toward 0.12

The development checkout prepares Pretty Notebook 0.12.0 and requires Python
3.14 or newer, including the metadata-only pnbp compatibility distribution.
The published 0.11.0 release retains its historical Python 3.11+ contract.

## HTTP publishing

Requ 0.2 supplies the bounded Requests-style frontend for publication, accounts,
tokens and operation logs. Requests is no longer a runtime dependency. Each
operation owns a session and closes it before returning owned response bytes.
Caller-owned upload files remain open. The existing (5 second connect, 30 second
read) timeout selection, conditional headers, checked receipts and explicit
reconciliation remain in place. Mutations have no automatic retry or redirect
replay. TLS verification remains mandatory and environment proxies are not
implicitly trusted.

Requests are limited to 16 MiB, covering existing 10 MiB image uploads plus
multipart framing and 2,000,000-character JSON publications. Responses have a
64 MiB limit. Invalid or oversized inputs and transport failures use Requ's
request exception family; CLI errors omit private values.

The web application retains its current FastAPI/Starlette implementation. Its
dependency lock and deployment Python selection follow the root package's 3.14
minimum; changing the HTTP client does not begin the web framework migration.

## Markdown engine

Parse MD 0.1 owns generic nodes, source spans, bounded parsing and versioned
CommonMark/extended syntax. The former parser modules now forward to that
published dependency. The notebook keeps its public imports and notebook-first
RendererContext constructor, legacy component conversion and optional
Python-Markdown backend. A compatibility Document preserves the default notebook
renderer without copying the syntax engine.

Notebook adapters retain graph/wiki resolution, public-only link selection,
fragments, image routes, hidden commit tags, external-link attributes/icons,
heading IDs and rendering metadata. Original Markdown and pending edits remain
unchanged. Publication fingerprints include the installed engine version,
dialect identity and runtime source digest alongside local adapter/policy code;
old plans must be reviewed again after an implementation change.

Rollback uses the complete previous qualified package revision and lock together,
then prepares fresh publication plans. It does not rewrite stored Markdown or
reuse plans produced by a different renderer implementation.

## Terminal output

Escape Colors 0.3 with its Markdown extra replaces Rich. Parse MD supplies the
same extended syntax and Astree supplies the HTML tree; Escape Colors owns
terminal layout and registered syntax highlighting. Notebook adapters supply
the refresh/edit/new-note menu and resolved local wiki links. Code and inline
literal text are never rewritten by a wiki-link regular expression.

`pnbp pprint` displays current pending content without saving it. Redirected or
NO_COLOR output is plain, including visible destinations. A supported TTY gets
styles and explicitly selected HTTP/mail and notebook pnbp/nano OSC 8 links.
These links do not install/register protocol handlers or launch an editor;
macOS protocol-handler support remains deferred. Images have readable labels.
Raw author HTML is escaped for terminal display and source controls are escaped.
Parsing and layout have finite node, nesting, character, line and output limits;
failures write no partial display.

`get_terminal_note` returns buffered text with explicit width/color/hyperlink
options. The historical `get_rich_note` spelling remains available and returns
plain text in 0.12, without a Rich renderable object.

## Certificate and build-tool pins

The web profile pins certifi 2026.10.18 to remove the affected emSign trust roots
identified by GHSA-6q48-6c7w-9gw2, and setuptools 84.1.0 for
GHSA-xmj3-9gf7-h52w. Canonical and compatibility source builds require the patched
setuptools floor. The Linux/Python 3.14 dependency hashes are regenerated without
changing the web framework or storage profile. The core Requ transport uses its
verified standard-library TLS context, without a certifi dependency.
