import json

from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import TestCase


USER_MODEL = get_user_model()


class DjangoQLAdminTest(TestCase):
    def setUp(self):
        self.credentials = {'username': 'test', 'password': 'lol'}
        USER_MODEL.objects.create_superuser(email='herp@derp.rr', **self.credentials)

    def test_introspections(self):
        for item in ('book', 'publisher'):
            url = reverse('admin:core_%s_djangoql_introspect' % item)
            # unauthorized request should be redirected
            response = self.client.get(url)
            self.assertEqual(302, response.status_code)
            self.assertTrue(self.client.login(**self.credentials))
            # authorized request should be served
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)
            introspections = json.loads(response.content.decode('utf8'))
            self.assertEqual('core.%s' % item, introspections['current_model'])

            for model in ('core.book', 'core.publisher', 'auth.user', 'auth.group'):
                self.assertIn(model, introspections['models'])

            self.client.logout()
