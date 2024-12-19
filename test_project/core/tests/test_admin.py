import json

from django.contrib.auth.models import User
from django.test import TestCase


try:
    from django.core.urlresolvers import reverse
except ImportError:  # Django 2.0
    from django.urls import reverse


class DjangoQLAdminTest(TestCase):
    def setUp(self):
        self.credentials = {'username': 'test', 'password': 'lol'}
        User.objects.create_superuser(email='herp@derp.rr', **self.credentials)

    def get_json(self, url, status=200, **kwargs):
        response = self.client.get(url, **kwargs)
        self.assertEqual(status, response.status_code)
        try:
            return json.loads(response.content.decode('utf8'))
        except ValueError:
            self.fail('Not a valid json')

    def test_introspections(self):
        url = reverse('admin:core_book_djangoql_introspect')
        # unauthorized request should be redirected
        response = self.client.get(url)
        self.assertEqual(302, response.status_code)
        self.assertTrue(self.client.login(**self.credentials))
        # authorized request should be served
        introspections = self.get_json(url)
        self.assertEqual('core.book', introspections['current_model'])
        for model in ('core.book', 'auth.user', 'auth.group'):
            self.assertIn(model, introspections['models'])

    def test_introspection_suggestion_api_url(self):
        self.assertTrue(self.client.login(**self.credentials))
        for app in ['admin', 'zaibatsu']:
            url = reverse('%s:auth_user_djangoql_introspect' % app)
            introspections = self.get_json(url)
            self.assertEqual(
                reverse('%s:auth_user_djangoql_suggestions' % app),
                introspections['suggestions_api_url'],
            )

    def test_djangoql_syntax_help(self):
        for app in ['admin', 'zaibatsu']:
            url = reverse(f'{app}:djangoql_syntax_help')
            self.client.logout()
            with self.subTest(app=app):
                response = self.client.get(url)
                # unauthorized request should be redirected
                self.assertEqual(302, response.status_code)
                self.assertTrue(self.client.login(**self.credentials))
                # authorized request should be served
                response = self.client.get(url)
                self.assertEqual(200, response.status_code)

    def test_suggestions(self):
        url = reverse('admin:core_book_djangoql_suggestions')
        # unauthorized request should be redirected
        response = self.client.get(url)
        self.assertEqual(302, response.status_code)
        # authorize for the next checks
        self.assertTrue(self.client.login(**self.credentials))

        # field parameter is mandatory
        r = self.get_json(url, status=400)
        self.assertEqual(r.get('error'), '"field" parameter is required')

        # check for unknown fields
        r = self.get_json(url, status=400, data={'field': 'gav'})
        self.assertEqual(r.get('error'), 'Unknown field: gav')
        r = self.get_json(url, status=400, data={'field': 'x.y'})
        self.assertEqual(r.get('error'), 'Unknown model: core.x')
        r = self.get_json(url, status=400, data={'field': 'auth.user.lol'})
        self.assertEqual(r.get('error'), 'Unknown field: lol')

        # field with choices
        r = self.get_json(url, data={'field': 'genre'})
        self.assertEqual(r, {
            'page': 1,
            'has_next': False,
            'items': ['Drama', 'Comics', 'Other'],
        })

        # test that search is working
        r = self.get_json(url, data={'field': 'genre', 'search': 'o'})
        self.assertEqual(r, {
            'page': 1,
            'has_next': False,
            'items': ['Comics', 'Other'],
        })

        # ensure that page parameter is checked correctly
        r = self.get_json(url, status=400, data={'field': 'genre', 'page': 'x'})
        self.assertEqual(
            r.get('error'),
            "invalid literal for int() with base 10: 'x'",
        )
        r = self.get_json(url, status=400, data={'field': 'genre', 'page': '0'})
        self.assertEqual(
            r.get('error'),
            'page must be an integer starting from 1',
        )

        # check that paging after results end works correctly
        r = self.get_json(url, data={'field': 'genre', 'page': 2})
        self.assertEqual(r, {
            'page': 2,
            'has_next': False,
            'items': [],
        })

    def test_query(self):
        url = reverse('admin:core_book_changelist') + '?q=price=0'
        self.assertTrue(self.client.login(**self.credentials))
        response = self.client.get(url)
        # There should be no error at least
        self.assertEqual(200, response.status_code)
