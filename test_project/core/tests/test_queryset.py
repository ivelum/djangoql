from django.contrib.auth.models import User
from django.test import TestCase

from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLField, DjangoQLSchema

from ..models import Book


class WrittenInYearSearch(DjangoQLField):
    def __init__(self):
        super(WrittenInYearSearch, self).__init__(
            name='written_in_year',
            type='int',
            relation=None,
            related_model=None,
            nullable=False,
            options=[]
        )

    def add_search_target(self, queryset):
        from django.db.models.expressions import RawSQL
        return queryset.annotate(
            written_in_year=RawSQL('EXTRACT(YEAR FROM written)', [])
        )


class BookCustomSearchSchema(DjangoQLSchema):
    def get_fields(self, model):
        if model == Book:
            return [
                WrittenInYearSearch()
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
            schema=BookCustomSearchSchema)
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(where_clause, "(EXTRACT(YEAR FROM written)) = 2017")
