from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings

from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema, IntField

from ..models import Book


def like_ci(column, pattern):
    """Expected SQL for a case-insensitive LIKE (`~`, startswith, endswith).

    DjangoQL maps those operators onto __icontains / __istartswith /
    __iendswith, and the SQL Django emits for them is backend-specific:
    SQLite's LIKE is already case-insensitive for ASCII, so Django emits a
    plain `LIKE ... ESCAPE`, while PostgreSQL has to fold both sides with
    UPPER().  The lookup is the same either way -- only the rendering differs.
    """
    if connection.vendor == 'postgresql':
        return f'UPPER({column}::text) LIKE UPPER({pattern})'
    return f"{column} LIKE {pattern} ESCAPE '\\'"


def dt(value):
    """Expected rendering of a datetime parameter inside str(queryset.query).

    str(query) interpolates the parameters through the backend's adapter:
    psycopg keeps the UTC offset on aware datetimes, whereas SQLite stores
    them as naive UTC strings.
    """
    if connection.vendor == 'postgresql' and settings.USE_TZ:
        return '%s+00:00' % value
    return value


class WrittenInYearField(IntField):
    model = Book
    name = 'written_in_year'

    def get_lookup_name(self):
        return 'written__year'


class BookCustomSearchSchema(DjangoQLSchema):
    suggest_options = {
        Book: ['genre'],
    }

    def get_fields(self, model):
        if model == Book:
            return [
                'genre',
                WrittenInYearField(),
            ]


class DjangoQLQuerySetTest(TestCase):
    def do_simple_query_test(self):
        qs = Book.objects.djangoql(
            'name = "foo" and author.email = "em@il" '
            'and written > "2017-01-30"',
        )
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            '("core_book"."name" = foo AND "auth_user"."email" = em@il '
            'AND "core_book"."written" > %s)' % dt('2017-01-30 00:00:00'),
            where_clause,
        )

    def test_simple_query(self):
        self.do_simple_query_test()

    @override_settings(USE_TZ=False)
    def test_simple_query_without_tz(self):
        self.do_simple_query_test()

    def test_datetime_like_query(self):
        qs = Book.objects.djangoql('written ~ "2017-01-30"')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            like_ci('"core_book"."written"', '%2017-01-30%'),
            where_clause,
        )

    def test_advanced_string_comparison(self):
        qs = Book.objects.djangoql('name ~ "war"')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(like_ci('"core_book"."name"', '%war%'), where_clause)
        qs = Book.objects.djangoql('name startswith "war"')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(like_ci('"core_book"."name"', 'war%'), where_clause)
        qs = Book.objects.djangoql('name not endswith "peace"')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            'NOT (%s)' % like_ci('"core_book"."name"', '%peace'),
            where_clause,
        )

    def test_apply_search(self):
        qs = User.objects.all()
        try:
            qs = apply_search(qs, 'groups = None')
            qs.count()
        except Exception as e:
            self.fail(e)

    def test_choices(self):
        qs = Book.objects.djangoql(
            'genre = "Drama"',
            schema=BookCustomSearchSchema,
        )
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual('"core_book"."genre" = 1', where_clause)
        qs = Book.objects.djangoql(
            'genre in ("Drama", "Comics")',
            schema=BookCustomSearchSchema,
        )
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual('"core_book"."genre" IN (1, 2)', where_clause)

    def test_custom_field_query(self):
        qs = Book.objects.djangoql(
            'written_in_year = 2017',
            schema=BookCustomSearchSchema,
        )
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertTrue(
            where_clause.startswith('"core_book"."written" BETWEEN 2017-01-01'),
        )

    def test_or_query(self):
        # Exercises the OR branch of build_filter (the rest of the suite only
        # builds AND expressions).
        qs = apply_search(
            User.objects.all(),
            'username = "a" or username = "b"',
        )
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            '("auth_user"."username" = a OR "auth_user"."username" = b)',
            where_clause,
        )

    def test_and_has_higher_precedence_than_or(self):
        User.objects.create(username='a', first_name='match')
        User.objects.create(username='b', first_name='other')

        qs = apply_search(
            User.objects.order_by('username'),
            'username = "a" and first_name = "match" or username = "b"',
        )

        self.assertEqual([u.username for u in qs], ['a', 'b'])

    def test_not_in_query(self):
        # 'not in' is the two-token comparison operator form.
        qs = apply_search(User.objects.all(), 'username not in ("a", "b")')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            'NOT ("auth_user"."username" IN (a, b))',
            where_clause,
        )

    def test_empty_datetime(self):
        qs = apply_search(User.objects.all(), 'last_login = None')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual('"auth_user"."last_login" IS NULL', where_clause)

    def test_datetime_in_query(self):
        qs = apply_search(User.objects.all(), 'last_login in ("2017-01-01")')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            '"auth_user"."last_login" IN (%s)' % dt('2017-01-01 00:00:00'),
            where_clause,
        )
