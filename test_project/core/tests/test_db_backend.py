"""Guard tests: the suite must actually run on the database it claims to.

The CI job `tests-postgres` sets DJANGOQL_TEST_DB=postgres and spends real
time starting a `postgres:16-alpine` container.  It used to silently run the
whole suite on SQLite anyway, because the `default` connection object had
already been materialised from settings.py by the time the
`django_db_modify_db_settings` fixture swapped `settings.DATABASES`.

These tests fail loudly if that ever happens again.
"""

import os

from django.db import connection

import pytest


EXPECTED_ENGINES = {
    'postgres': 'django.db.backends.postgresql',
    'sqlite': 'django.db.backends.sqlite3',
}

EXPECTED_VENDORS = {
    'postgres': 'postgresql',
    'sqlite': 'sqlite',
}


def _requested_backend():
    return os.environ.get('DJANGOQL_TEST_DB', 'sqlite').strip().lower()


@pytest.mark.django_db
def test_connection_uses_the_requested_backend():
    """The live connection - not just settings - must match the request."""
    requested = _requested_backend()
    assert requested in EXPECTED_ENGINES, (
        'Unknown DJANGOQL_TEST_DB=%r; expected one of %s'
        % (requested, sorted(EXPECTED_ENGINES))
    )

    engine = connection.settings_dict['ENGINE']
    assert engine == EXPECTED_ENGINES[requested], (
        'DJANGOQL_TEST_DB=%s but the test database connection is %s. '
        'The suite is not running against the database it claims to.'
        % (requested, engine)
    )


@pytest.mark.django_db
def test_database_really_answers_as_the_requested_backend():
    """Ask the server itself, so a mislabelled settings dict cannot pass."""
    requested = _requested_backend()

    assert connection.vendor == EXPECTED_VENDORS[requested]

    with connection.cursor() as cursor:
        if requested == 'postgres':
            cursor.execute('SELECT version()')
            assert 'PostgreSQL' in cursor.fetchone()[0]
        else:
            cursor.execute('SELECT sqlite_version()')
            assert cursor.fetchone()[0]
