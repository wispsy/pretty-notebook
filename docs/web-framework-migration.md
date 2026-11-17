# Web framework migration

The repository web publisher now uses `expose-api==0.2.0` as its sole HTTP
runtime. FastAPI, Starlette, Python Multipart and their registration metadata
are absent from the production dependency locks and application imports.
Python 3.14+ is required. Tortoise 1.1.7, Pydantic, caller-owned Jinja2 and the
qualified local SQLite topology remain application-owned. PostgreSQL is deferred
entirely to a future session.

The published `pretty-notebook==0.12.0` and metadata alias `pnbp==0.12.0` are
immutable and retain their historical source baseline. The repository web app
is separate from those wheels. Supporting releases `expose-api==0.2.0`,
`enforce-type==0.2.0` and `backpack-store==0.2.0` were published and verified
against their registry artifact hashes before this migration. Expose API has no
base runtime dependencies; this application's model/ORM/template choices do not
change that library contract.

## Runtime and upgrade selection

`create_app()` and `create_app(framework='expose-api')` select the native
application. `PNBP_WEB_FRAMEWORK` can be omitted or set to `expose-api`.
Remove a temporary `fastapi` selection from staged migration checkouts; other
values fail during construction. Use the whole reviewed checkout and its locks
for upgrades and stopped-site rollback. No new package version or live deployment
is implied by this repository migration.

The application owns one Tortoise initialization/close pair per worker lifespan,
using the same UTC and global fallback selection as the previous pinned ORM
integration. Startup retains private directory preparation, process-locked schema
migration, publication reconciliation, public indexes and asset-layout validation.
Shutdown closes database connections, including failed startup after initialization.
Public ASGI startup failures stay sanitized; local process owners retain the
original actionable configuration/storage exception.

## HTTP compatibility

| Group | Retained application contract |
| --- | --- |
| Accounts | Single-use bootstrap, bearer/password/script credentials and revocation |
| Permissions and notebooks | Roles, grants, scoped credentials, ownership and isolated namespaces |
| Publishing | Legacy and checked routes, revision/hash ETags, conflicts, rollback and images |
| Site and inbox | Validated settings, bounded CSS/favicon uploads and stored form submissions |
| Search and navigation | Literal search, repeated tags, bounds, escaped server-rendered views |
| Pages and preferences | Caller-owned escaped Jinja templates, cookies, redirects and mounted prefixes |
| Middleware | Trusted hosts, CSP/security/cache policy, redacted durable operation receipts |
| HTTP methods | Declared methods, API fallthrough, static GET/HEAD and existing 404/405 responses |

Explicit native routes call application services directly. There is no signature
injection, automatic ORM/model translation or remaining baseline HTTP delegation.
Typed providers own authentication, decoded JSON and managed multipart resources.
Wire syntax precedes authentication; semantic validation follows it where the
previous contract did. Application Pydantic errors retain their ordered locations,
missing-input details and exact JSON response bytes. Managed uploads close every
parsed file after success, rejection or cancellation. Receipts finalize at response
start, or as failed if a canceled request never starts a response.

The application-owned `apps/web/openapi.json` preserves API paths, operation IDs,
schemas and bearer security metadata. Tests compare every described operation to
the registered native route inventory and application model schemas. Update this
contract with future API changes. `/openapi.json` supplies the active root prefix.
`/docs`, `/redoc` and `/docs/oauth2-redirect` remain available as a local API
reference linking the schema; the reference uses no remote scripts or interactive
Swagger/Redoc runtime. Template debug context is emitted only when an ASGI test
transport requests that extension.

## Selected finite profiles

Native requests use an 8 KiB / 128-field query budget, a 128-field URL-encoded
form budget and a 16 MiB wire-body budget. Image services retain their 10 MiB application limit; CSS and favicon
limits remain 64 KiB and 1 MiB. Wire refusals retain their selected 4xx status
and public detail. Unexpected handler failures retain the value-free plaintext
500 body and media type, and now also retain configured security/no-store headers
and operation correlation receipts.

Repository assets use the native rooted static profile. Published images use an
application-selected private tree and native owned file responses so previously
accepted POSIX filenames remain downloadable. Symlinks and root escapes are
refused; the tree and its ancestors must remain application-owned. Native files
use weak metadata validators and one byte range; multiple ranges receive 416.
Checked publishing's strong revision/hash ETags are unchanged. Manifest assets
retain immutable caching; pages do not acquire API no-store headers.

## Acceptance and delivery

[PNB-WEB-01 through PNB-WEB-04](https://github.com/wispsy/expose_api/issues/86)
are tracked in both project queues. Four staged PRs established the inventory,
pilot, authenticated publishing and remaining handlers. The full dual-factory
suite passed 805 tests at 97% branch-inclusive coverage before removal. Recorded
validation and method transcripts preserve that evidence without retaining the
previous implementation as a test dependency.

The final native suite covers persistent restart, independent four-worker
visibility, owner races, stale writes, transaction rollback, templates/cookies,
file selection/ranges and cancellation cleanup. The existing Starlette ASGI test
client remains test-only; the public Expose API async client also qualifies
native lifecycle and pages. `scripts/check_web_runtime.py` runs in a fresh
production environment before installing test tools and checks bootstrap, checked
publishing, pages, search, receipts, cookies, docs, host refusal, restart and ORM
shutdown with neither old framework installed or imported. Container acceptance
checks framework absence and exercises startup, publication, backup/restore and
restart. Package publication does not deploy a running site.
