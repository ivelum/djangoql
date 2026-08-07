# conftest.py — root-level pytest configuration
#
# By default the test suite runs against SQLite (no extra setup needed).
# To run the same suite against a throwaway PostgreSQL container instead,
# set the environment variable before invoking pytest:
#
#     DJANGOQL_TEST_DB=postgres uv run pytest
#
# Requirements for the Postgres path:
#   - Docker must be running on the host.
#   - The `testcontainers[postgres]` and `psycopg[binary]` packages must be
#     installed (they are in the [dev] extra: `uv sync --extra dev`).
#   - The first run will pull the `postgres:16-alpine` image from Docker Hub.

import os

import pytest


@pytest.fixture(scope='session')
def postgres_container():
    """Start a throwaway Postgres container for the test session.

    Yields the container object when DJANGOQL_TEST_DB=postgres is set,
    otherwise yields None so the rest of the stack can skip Postgres setup.
    """
    if os.environ.get('DJANGOQL_TEST_DB') != 'postgres':
        yield None
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        'postgres:16-alpine',  # pinned to match the CI Postgres version
        driver=None,
    ) as pg:
        yield pg


POSTGRES_ENGINE = 'django.db.backends.postgresql'


@pytest.fixture(scope='session')
def django_db_modify_db_settings(
    postgres_container,
    django_db_modify_db_settings_parallel_suffix,  # preserve xdist/tox suffix
):
    """Override pytest-django's hook to point Django's DATABASES at Postgres.

    This fixture is called by pytest-django right before the test database is
    created, which is the correct point to swap out the connection settings.
    When postgres_container is None (default SQLite run) this is a no-op.

    Swapping ``settings.DATABASES`` is *not* enough on its own.  pytest-django
    calls ``django.setup()`` from ``pytest_load_initial_conftests`` — before
    any fixture runs — and app loading materialises the ``default`` connection
    (``Options.contribute_to_class()`` asks ``connection.ops`` for
    ``max_name_length()`` when truncating table names).  That connection object
    keeps its own copy of the settings dict, so without explicitly discarding
    it the whole suite silently keeps running on SQLite while a Postgres
    container burns CI minutes next to it.
    """
    if postgres_container is None:
        return

    from django.conf import settings
    from django.db import connections

    settings.DATABASES['default'] = {
        'ENGINE': POSTGRES_ENGINE,
        'NAME': postgres_container.dbname,
        'USER': postgres_container.username,
        'PASSWORD': postgres_container.password,
        'HOST': postgres_container.get_container_host_ip(),
        'PORT': postgres_container.get_exposed_port(5432),
    }

    # Close and drop every connection object built from the old (SQLite)
    # settings.  ``del connections[alias]`` is ConnectionHandler's public way
    # of removing a cached connection; the handler rebuilds it lazily on next
    # access, this time from the settings above.
    connections.close_all()
    for alias in list(settings.DATABASES):
        try:
            del connections[alias]
        except AttributeError:
            pass  # never materialised — nothing to discard

    # The ConnectionHandler caches its normalised settings dict via
    # cached_property.  After mutating settings.DATABASES we must bust that
    # cache so Django re-runs configure_settings() (which populates defaults
    # like ATOMIC_REQUESTS, TIME_ZONE, etc.) on next access.
    connections.__dict__.pop('settings', None)

    # Fail loudly and immediately rather than quietly testing the wrong
    # database: if a future change to fixture ordering (or to Django's own
    # start-up) re-materialises the connection before we get here, the whole
    # session must stop.  test_project/core/tests/test_db_backend.py asserts
    # the same invariant from the test side.
    engine = connections['default'].settings_dict['ENGINE']
    if engine != POSTGRES_ENGINE:
        raise RuntimeError(
            'DJANGOQL_TEST_DB=postgres, but the "default" connection is still '
            'using %s instead of %s. The test suite would silently run '
            'against the wrong database.' % (engine, POSTGRES_ENGINE)
        )
