# Contributing

Thanks for your interest in improving DjangoQL (iplweb fork)!

## Development setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```shell
uv sync --all-extras      # create the virtualenv and install dev deps
uv run pre-commit install # install the git hook
```

## Running the tests

```shell
uv run pytest
```

The suite runs against SQLite by default.  To run the same suite against a
throwaway PostgreSQL container instead, set `DJANGOQL_TEST_DB=postgres`:

```shell
DJANGOQL_TEST_DB=postgres uv run pytest
```

This requires Docker to be running.  The first run will pull the
`postgres:16-alpine` image from Docker Hub; subsequent runs reuse the local
image.  The `testcontainers[postgres]` and `psycopg[binary]` packages are
included in the `dev` extra and are installed by `uv sync --all-extras`.

`test_project/core/tests/test_db_backend.py` asserts that the live connection
really is the backend you asked for, so a Postgres run that quietly falls back
to SQLite fails instead of passing.  Tests that assert on generated SQL must
therefore stay backend-aware — see the `like_ci()` / `dt()` helpers in
`test_project/core/tests/test_queryset.py`.

The suite runs against the bundled `test_project/`. The compiled `.mo`
catalogs are **not** tracked in git — they are generated from the source
`.po` files at build time. To compile them locally (e.g. before running the
tests), run, from the repo root:

```shell
uv run python -c "from _translations import compile_catalogs; compile_catalogs()"
```

This uses Babel (a pure-Python `dev` dependency) — no system `gettext` /
`msgfmt` is required. It is the same function the build backend
(`_build_meta.py`) runs when building the wheel/sdist.

## Linting and formatting

Linting and formatting are handled by [ruff](https://docs.astral.sh/ruff/),
wired through pre-commit.

**Hooks run on _staged files only_** — which is exactly the default behaviour
of `pre-commit` on commit. When you stage and commit a change, ruff
(`ruff check --fix` + `ruff-format`), `pyupgrade`, and `django-upgrade` run on
just the files you touched, so your diff stays scoped to your actual edits.

**Please do not run `pre-commit run --all-files`.** The existing codebase is
intentionally *not* bulk-reformatted: doing so would rewrite large amounts of
untouched, working code (quote styles, line wrapping, syntax modernization)
and bury real changes under mechanical churn. Formatting is applied
incrementally, file by file, as code is naturally edited.

For the same reason, the CI lint job is **informational only** (it never fails
the build). Correctness is enforced by the test matrix; style is enforced by
the pre-commit hook on the lines you change.

## Submitting changes

1. Branch off `master`.
2. Keep each commit focused; let the pre-commit hook lint your staged changes.
3. Make sure `uv run pytest` is green.
4. Open a pull request describing the change and why.

## Translations

Native-speaker review of the auto-translated locales is very welcome — see the
[Internationalization section of the README](README.md#internationalization-i18n)
for how the catalogs are organised.

## Releasing

For maintainers. Releases are cut by pushing a tag; CI does the rest.

1. Make sure `master` is green and holds everything the release should carry.
   If `completion-widget/` changed, the bundle has to be rebuilt and committed
   (`NODE_OPTIONS=--openssl-legacy-provider yarn build`) — the release ships
   `djangoql/static/djangoql/js/completion.js` exactly as it is in git and
   does not rebuild it.
2. Bump the version (updates `djangoql/__init__.py` and `pyproject.toml`,
   without committing):

    ```shell
    uv run bumpver update --patch --no-commit    # or --minor / --major
    ```

3. In `CHANGES.rst`, turn the topmost heading into `<version> (<YYYY-MM-DD>)`
   and keep its underline the same length. The release notes on GitHub are
   cut from that section.
4. Commit, tag with a leading `v`, push both:

    ```shell
    git commit -am "release: 0.31.3"
    git tag v0.31.3
    git push origin master v0.31.3
    ```

Pushing the tag runs `.github/workflows/release.yaml`. It refuses to publish
when the tag and `djangoql.__version__` disagree, builds the wheel and sdist
(the build backend compiles the `.mo` catalogs), checks both artifacts,
uploads them to PyPI and creates the GitHub release.

There is no PyPI token anywhere: the upload uses
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/). The PyPI
project `djangoql-iplweb` trusts the repository `iplweb/djangoql-iplweb`, the
workflow file `release.yaml` and the GitHub environment `pypi`; renaming any of
the three breaks publishing until PyPI is told about the new name.

`bumpver` is configured with `tag = true`, but its tags have no `v` prefix,
which is why the steps above pass `--no-commit` and tag by hand.
