# Versions and support

Version 0.12.0 requires Python 3.14+. See the
[dependency migration](dependency-migration.md) for the upstream package changes.

The current release is `pretty-notebook==0.12.0`, supporting the Python library
and CLI on Python 3.14 or newer. `pretty_notebook` is the canonical import;
compatible `pnbp` imports and the CLI remain supported. The final `pnbp==0.12.0`
distribution contains metadata only and installs the canonical package.

The historical `pnbp==0.9.0` release retains its versioned contract in the
[0.9 notes](release-0.9.0.md). See [package migration](package-migration.md),
[0.11 notes](release-0.12.0.md) and [readiness evidence](release-0.12.0-readiness.md).
Optional and later features remain explicitly deferred.

The repository Markdown is the canonical documentation. The documentation
build reads that source and the current package for API signatures and CLI help.
There is one source page per topic; the [tutorial](tutorials.md) links those
contracts together. To inspect a release's historical source, select its tag in
GitHub rather than treating `main` as the installed release's reference.

The FastAPI publisher is a separate repository application with its own pinned
dependencies. Its supported deployment is one Gunicorn instance with up to four workers,
one local SQLite database and explicitly owned public notebooks behind a TLS proxy. Follow [web deployment](web.md)
for the current contract. Browser sessions, private-reader access, share links, remote Markdown history,
bidirectional synchronization, browser editing, installed-wheel web packaging,
and distributed or multi-host storage are deferred. macOS protocol handlers remain unsupported.

Sphinx/MyST build tools remain documentation-only. The development checkout and
CI use Python 3.14; historical release support is recorded above.
See [building the documentation](building.md) for a clean local build.

The Read the Docs configuration is prepared, but hosted activation, a custom
domain and documentation publication require separate authorization. Repository
links remain the published documentation entry points until that work is complete.
