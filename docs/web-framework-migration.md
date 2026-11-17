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
auditing. The default factory remains the baseline during this inventory stage.

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
