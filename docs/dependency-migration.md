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
