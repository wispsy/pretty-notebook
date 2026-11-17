# Pretty Notebook 0.12.0

Pretty Notebook 0.12.0 requires **Python 3.14 or newer**. The canonical
`pretty_notebook` imports, compatible `pnbp` imports and `pnbp` executable remain
available. The matching `pnbp==0.12.0` distribution contains metadata only.

```sh
python -m pip uninstall pnbp
python -m pip install pretty-notebook==0.12.0
```

## Changes

- Requ 0.2 replaces Requests for bounded, owned HTTP responses and checked
  publishing. Mutation retries and redirects remain explicit.
- Parse MD 0.1 owns the generic Markdown syntax engine. Notebook graph/wiki,
  publication and compatibility adapters retain their existing responsibilities.
- Escape Colors 0.3 replaces Rich for buffered terminal Markdown. The historical
  `get_rich_note` spelling returns plain text; use `get_terminal_note` for explicit
  width, color and hyperlink settings.
- The existing optional web profile uses Backpack's qualified SQLite snapshot
  facility, retaining migration history and backup receipts.
- Build and web dependency pins include the qualified certificate/build-tool
  updates. See [dependency migration](dependency-migration.md) for details.

Existing notebooks and original Markdown remain authoritative. Upgrading the
renderer or dependencies invalidates earlier publication fingerprints: prepare
and review fresh checked plans. Preserve complete code, lock and data backups
for rollback rather than mixing versions.

## Web application boundary

This release preserves the FastAPI/Starlette, Tortoise and SQLite baseline in
`apps/web`. The web application remains separate from the core wheel. The
Expose API framework replacement follows this immutable release under
[PNB-WEB-01 through PNB-WEB-04](https://github.com/wispsy/expose_api/issues/86).
PostgreSQL work is deferred entirely to a future session. The supported host,
worker, authentication and asset policies in [web deployment](web.md) continue
to apply. This package publication does not deploy a site.

## Qualification

The release workflow verifies core regressions, canonical and compatibility
metadata, installed distributions and the notebook upgrade/publish exercise
before uploading its exact artifacts. Existing main CI also covers web protocol,
worker and container acceptance. Registry file hashes and fresh installation
receipts are recorded in [REL-12](https://github.com/wispsy/pretty-notebook/issues/206).
