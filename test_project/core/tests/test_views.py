import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from djangoql.models import Query
from djangoql.views import QueryView
from django.contrib.contenttypes.models import ContentType
try:
    from django.core.urlresolvers import reverse
except ImportError:  # Django 2.0
    from django.urls import reverse


USER_MODEL = get_user_model()


class DjangoQLViewsTest(TestCase):
    def setUp(self):
        self.user = USER_MODEL.objects.create_user(username='admin',
                                                   password='admin')
        self.client.login(username='admin', password='admin')

    def test_saved_queries_list(self):
        model = ContentType.objects.get(model='book')

        Query.objects.bulk_create([
            Query(
                name='Only published books',
                text='is_published = True',
                content_type=model,
                user=self.user
            ),
            Query(
                name='Drama books',
                text='genre = "Drama"',
                content_type=model,
                private=True,
                user=self.user
            )
        ])

        expected = list(
            Query.objects.all().values(*QueryView.EXPOSED_MODEL_FIELDS))
        response = self.client.get(reverse('djangoql:query'),
                                   {'model': 'book'})
        self.assertListEqual(expected, json.loads(response.content.decode()))

    def test_saved_queries_create(self):
        response = self.client.post(
            path='{}?model=book'.format(reverse('djangoql:query')),
            data=json.dumps({'text': 'hello', 'name': 'test'}),
            content_type='application/json'
        )
        result_id = json.loads(response.content.decode())['id']
        self.assertEqual(type(result_id), int)

    def test_saved_queries_remove(self):
        obj = Query.objects.create(
            name='test',
            text='test',
            content_type=ContentType.objects.get(model='book'),
            user=self.user
        )
        self.client.delete(
            path='{}?model=book'.format(
                reverse('djangoql:concrete_query', args=[obj.id]))
        )
        self.assertEqual(Query.objects.count(), 0)

    def test_other_user_gets_only_shared(self):
        model = ContentType.objects.get(model='book')
        Query.objects.bulk_create([
            Query(
                name='Only published books',
                text='is_published = True',
                content_type=model,
                user=self.user,
                private=False
            ),
            Query(
                name='Drama books',
                text='genre = "Drama"',
                content_type=model,
                private=True,
                user=self.user
            )
        ])

        self.client.logout()
        self.user = USER_MODEL.objects.create_user(username='djangoql_demo',
                                                   password='demo')
        self.client.login(username='djangoql_demo', password='demo')

        response = self.client.get(reverse('djangoql:query'),
                                   {'model': 'book'})
        self.assertEqual(len(json.loads(response.content.decode())), 2)
