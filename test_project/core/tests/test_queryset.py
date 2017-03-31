from django.contrib.auth.models import User
from django.test import TestCase

from djangoql.queryset import apply_search

from ..models import Book


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
