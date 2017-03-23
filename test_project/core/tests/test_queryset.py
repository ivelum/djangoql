from django.test import TestCase

from ..models import Book


class DjangoQLQuerySetText(TestCase):
    def test_simple_query(self):
        qs = Book.objects.djangoql('name = "foo" and author.email = "bar@baz"')
        where_clause = str(qs.query).split('WHERE')[1].strip()
        self.assertEqual(
            '("core_book"."name" = foo AND "auth_user"."email" = bar@baz)',
            where_clause,
        )
