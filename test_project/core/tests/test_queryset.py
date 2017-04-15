from django.contrib.auth.models import User
from django.test import TestCase

from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema, IntField

from ..models import Book


class WrittenInYearField(IntField):
    model = Book
    name = 'written_in_year'

    def get_lookup_name(self):
        return 'written__year'


class BookCustomSearchSchema(DjangoQLSchema):
    def get_fields(self, model):
        if model == Book:
            return [
                WrittenInYearField(),
            ]


class DjangoQLQuerySetTest(TestCase):
    def test_simple_query(self):
        qs = Book.objects.djangoql('name = "foo" and author.email = "bar@baz"')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            '("core_book"."name" = foo AND "auth_user"."email" = bar@baz)',
            where_clause,
        )

    def test_apply_search(self):
        qs = User.objects.all()
        try:
            qs = apply_search(qs, 'groups = None')
            qs.count()
        except Exception as e:
            self.fail(e)

    def test_custom_field_query(self):
        qs = Book.objects.djangoql(
            'written_in_year = 2017',
            schema=BookCustomSearchSchema,
        )
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertTrue(
            where_clause.startswith('"core_book"."written" BETWEEN 2017-01-01')
        )
