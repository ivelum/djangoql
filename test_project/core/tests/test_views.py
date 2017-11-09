import json

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import TestCase


USER_MODEL = get_user_model()


class DjangoQLViewsTest(TestCase):
    fixtures = ['core.json']

    def setUp(self):
        self.user = USER_MODEL.objects.get(pk=3)

        self.client.login(username='robin', password='hellorobin')

    def test_favorite_queries_retrieve(self):
        response = self.client.get(reverse('admin:core_book_create_list_favorite_queries'))

        expected = {
            'favorite_query_list': [
                {
                    'pk': 3,
                    'text': 'spam',
                    'name': 'Query 3',
                    'scope': 'shared',
                    'is_editable': False,
                }, {
                    'pk': 2,
                    'text': 'bar',
                    'name': 'Query 2',
                    'scope': 'private',
                    'is_editable': True,
                }, {
                    'pk': 1,
                    'text': 'foo',
                    'name': 'Query 1',
                    'scope': 'private',
                    'is_editable': True,
                }
            ]
        }

        self.assertEqual(json.dumps(expected).encode(), response.content)

    def test_favorite_query_create(self):
        response = self.client.post(
            path=reverse('admin:core_book_create_list_favorite_queries'),
            data={
                'text': 'hello',
            }
        )

        expected = {
            'favorite_query': {
                'pk': 4,
                'text': 'hello',
                'name': 'Query 4',
                'scope': 'private',
                'is_editable': True,
            }
        }

        self.assertEqual(json.dumps(expected).encode(), response.content)

    def test_favorite_query_destroy(self):
        response = self.client.delete(
            path=reverse(
                viewname='admin:core_book_destroy_update_favorite_queries',
                kwargs={'pk': 2},
            )
        )

        expected = {
            'favorite_query': None,
        }

        self.assertEqual(json.dumps(expected).encode(), response.content)

    def test_favorite_query_update(self):
        response = self.client.post(
            path=reverse(
                viewname='admin:core_book_destroy_update_favorite_queries',
                kwargs={'pk': 2},
            ),
            data={
                'text': 'helloworld',
                'scope': 'shared',
            }
        )

        expected = {
            'favorite_query': {
                'pk': 2,
                'text': 'helloworld',
                'name': 'Query 2',
                'scope': 'shared',
                'is_editable': True,
            }
        }

        self.assertEqual(json.dumps(expected).encode(), response.content)

    def test_favorite_query_delete_shared_query_object_doesnt_exist(self):
        response = self.client.delete(
            path=reverse(
                viewname='admin:core_book_destroy_update_favorite_queries',
                kwargs={'pk': 3},
            )
        )

        expected = {
            'errors': 'object_doesnt_exists',
        }

        self.assertEqual(json.dumps(expected).encode(), response.content)
