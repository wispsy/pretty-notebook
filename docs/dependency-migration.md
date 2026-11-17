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
