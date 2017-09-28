from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema, IntField

from ..models import Book


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
                'genre', WrittenInYearField(),
            ]


class DjangoQLQuerySetTest(TestCase):
    def do_simple_query_test(self):
        qs = Book.objects.djangoql(
            'name = "foo" and author.email = "em@il" and written > "2017-01-30"'
        )
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            '("core_book"."name" = foo AND "auth_user"."email" = em@il '
            'AND "core_book"."written" > 2017-01-30 00:00:00)',
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
            '"core_book"."written" LIKE %2017-01-30% ESCAPE \'\\\'',
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
            where_clause.startswith('"core_book"."written" BETWEEN 2017-01-01')
        )
