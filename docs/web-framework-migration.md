# Web framework migration

The immutable Pretty Notebook 0.12.0 release records the FastAPI/Starlette web
baseline. PNB-WEB implementation follows that release and uses published
`expose-api==0.2.0` and `backpack-store==0.2.0` with checked registry hashes.
Tortoise, Pydantic, Jinja2 and the supported SQLite storage topology remain
application-owned. PostgreSQL is deferred entirely to a future session.

## Factory selection

`create_app(framework='fastapi')` selects the baseline. Select `'expose-api'` to
exercise the staged native HTTP factory. The explicit argument overrides
`PNBP_WEB_FRAMEWORK`; its default remains `fastapi` until complete parity passes.
Invalid selections fail during construction. The compatibility stage shares
the existing application state and delegates one baseline lifespan, preserving
startup diagnostics, lock ownership, migrations and ORM shutdown. Unported route
groups explicitly delegate to the baseline; no signature injection or automatic
ORM/model translation is provided.

## Recorded HTTP surface

| Group | Declared handlers | Contract retained by the compatibility fixtures |
| --- | ---: | --- |
| Authentication/accounts | 5 | Bootstrap, bearer tokens, revocation, password changes and account index |
| Roles, grants and credentials | 5 | Notebook scopes, ownership, delegation and concealed denial |
| Notebooks and operation logs | 3 | Shared durable state and redacted receipts |
| Legacy publishing/uploads | 6 | Page routes, previews, images and deletion |
| Checked publishing | 5 | Capabilities, inventory, ETags, hashes, conflicts and checked uploads |
| Layout and form inbox | 2 | Validated settings and bounded stored submissions |
| Search API | 1 | Repeated tags, literal search, bounds and error shapes |
| Appearance and favicon API/assets | 4 | CSS, uploads, immutable versions and dynamic-asset precedence |
| Pages/forms/navigation/search views | 10 | Escaping, cookies, redirects, root paths and fixed/catch-all precedence |
| Main factory | 2 | Health and unknown-API response shape |

The baseline also serves `/openapi.json`, `/docs`, `/docs/oauth2-redirect` and
`/redoc`, plus `/static/imgs` before the general `/static` mount. Middleware
retains trusted hosts, application security/CSP/cache headers and operation
auditing. The default factory remains the baseline during the pilot. The Expose API
selection now serves GET `/healthz` and GET `/api/search` through native explicit
handlers, with shared readiness/search services and application-owned Pydantic
query validation. Validation locations, missing-input details, JSON bytes,
security/cache headers and root prefixes retain the baseline protocol. Other
methods and unported groups explicitly delegate to the recorded baseline;
native automatic HEAD/OPTIONS behavior is not silently selected for these URLs.
Transcript checks compare both factories over one persistent database across
restart and prove native GET requests bypass the baseline HTTP router.

The unchanged web protocol fixtures run against both factories, including
authentication, headers/cookies, invalid input, files, uploads, transaction
rollback, restart and independent worker visibility. Worker identification is
test-only ordinary ASGI middleware. The public Expose API async client also
qualifies single startup/shutdown ownership. New modules enter coverage and the
container file inventory.

## Delivery gates

The owning [PNB-WEB issues](https://github.com/wispsy/expose_api/issues/86) are
linked in both the Expose API and Pretty Notebook Projects. PNB-WEB-01 owns this
inventory/selectable harness; PNB-WEB-02 ports health/search, PNB-WEB-03 ports
authenticated publishing/uploads, and PNB-WEB-04 qualifies remaining groups and
switches the default. Keep each PR focused and collect passing checks before
merging the dependent stack. Package publication does not deploy a running site.


## Authenticated publishing stage

The Expose API selection now owns all legacy publishing/preview/image handlers
and the checked publishing group. Explicit typed request providers retain the
authenticated principal, decoded JSON and managed multipart resources. JWT and
script-credential verification, notebook permissions, revisions, ETags, hash
checks, rollback and publication services are reused directly. Syntax decoding
precedes authentication; semantic model/file validation follows it, matching the
recorded error ordering. Wire bodies have a 16 MiB total bound; image services
retain their existing 10 MiB limit and filename/signature checks.

Both factories use one shared redacted audit-begin service. The native ordinary
ASGI audit middleware completes the same receipt at response-start and preserves
the operation correlation header, retention, failure and recovery rules. Managed
upload providers remain open through handler/response ownership and close every
parsed file on exit. Unsupported methods and unported groups still delegate.

Unexpected handler failures retain the baseline's value-free plaintext 500 body
and media type. The native final boundary also retains configured security and
no-store headers, plus the operation correlation receipt on these errors; the
baseline could omit them when an exception escaped its HTTP middleware.

The native request reader retains its finite 8 KiB / 128-field query profile and
16 MiB body profile. Valid bounded search inputs fit that query budget. Wire
refusals retain their selected 4xx status and public detail rather than entering
the sanitized unexpected-failure boundary.

## Remaining handler stage

PNB-WEB-04A moves accounts, permissions, notebooks, logs, inbox, layout, appearance,
favicons, public pages, forms, navigation and static delivery onto explicit native
bindings. Pydantic remains application-owned, including ordered path/body errors,
form defaults, query lists and syntax-before-authentication behavior. Shared
services retain the same authorization, storage and transaction ownership.
Templates retain autoescaping and debug context; cookies, redirects, asset URLs,
CSP and cache policy preserve mounted root prefixes. Only unsupported methods,
generated reference pages and lifecycle still delegate during this stage.

Static assets use Expose API's rooted static profile. Published images use an
application-selected private tree and native owned file responses so existing
accepted POSIX filenames remain downloadable. Symlinks and root escapes are
refused; the tree and its ancestors must stay application-owned. Native file
responses use weak metadata validators and a single byte-range profile; multiple
ranges receive 416. These static validators are intentionally independent of
checked publishing's existing strong revision/hash ETags. Known manifest assets
retain immutable caching; pages do not gain API no-store headers.
