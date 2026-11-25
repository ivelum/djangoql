import json
from unittest import mock

from django.contrib import admin as django_admin
from django.contrib.auth.models import User
from django.contrib.messages import WARNING
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import DataError, NotSupportedError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import translation

from core.admin import BookAdmin, CustomUserAdmin
from djangoql.exceptions import DjangoQLError

from ..models import Book


class FakeQuerySet(list):
    """Minimal stand-in for a QuerySet so we can drive the Postgres-specific
    'inet' error handling in get_search_results without a real Postgres DB."""

    def __init__(self, items=(), explain_exc=None):
        super().__init__(items)
        self.explain_exc = explain_exc

    def explain(self):
        if self.explain_exc is not None:
            raise self.explain_exc


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

    def test_i18n_catalog_endpoint(self):
        url = reverse('admin:core_book_djangoql_i18n')
        # unauthorized request should be redirected
        self.assertEqual(302, self.client.get(url).status_code)
        self.assertTrue(self.client.login(**self.credentials))
        # Served as a JavaScript gettext catalog. Under Polish, it must carry
        # the translated operator hint and search placeholder so the front-end
        # widget can localise them.
        with translation.override('pl'):
            response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        body = response.content.decode('utf8')
        self.assertIn('nie zawiera', body)  # 'does not contain'
        self.assertIn('Zaawansowane wyszukiwanie', body)  # placeholder
        # JavaScriptCatalog \u-escapes non-ASCII, so match the ASCII prefix of
        # the translation ("Pomoc dotycząca składni") to prove the "Syntax Help"
        # link label is localised.
        self.assertIn('"Syntax Help": "Pomoc', body)

    def test_changelist_loads_i18n_catalog_before_completion(self):
        # End-to-end: the rendered admin changelist must emit the gettext
        # catalog <script> and load it before completion.js, so window.gettext
        # is defined by the time the widget localises its labels.
        self.assertTrue(self.client.login(**self.credentials))
        html = self.client.get(
            reverse('admin:core_book_changelist'),
        ).content.decode('utf8')
        catalog_url = reverse('admin:core_book_djangoql_i18n')
        self.assertIn(catalog_url, html)
        self.assertLess(
            html.index(catalog_url),
            html.index('djangoql/js/completion.js'),
        )

    def test_format_endpoint(self):
        url = reverse('admin:core_book_djangoql_format')
        # unauthorized request should be redirected
        self.assertEqual(302, self.client.get(url).status_code)
        self.assertTrue(self.client.login(**self.credentials))
        data = self.get_json(url, data={'q': 'genre = 1 and rating = 2'})
        self.assertEqual('genre = 1\n  and rating = 2', data['formatted'])

    def test_format_endpoint_empty_query(self):
        self.assertTrue(self.client.login(**self.credentials))
        url = reverse('admin:core_book_djangoql_format')
        data = self.get_json(url, data={'q': '   '})
        self.assertEqual('', data['formatted'])

    def test_format_endpoint_syntax_error(self):
        self.assertTrue(self.client.login(**self.credentials))
        url = reverse('admin:core_book_djangoql_format')
        response = self.client.get(url, {'q': 'genre = = ='})
        self.assertEqual(400, response.status_code)
        self.assertIn('error', json.loads(response.content.decode('utf8')))

    def test_explain_endpoint(self):
        url = reverse('admin:core_book_djangoql_explain')
        # unauthorized request should be redirected
        self.assertEqual(302, self.client.get(url).status_code)
        self.assertTrue(self.client.login(**self.credentials))
        data = self.get_json(url, data={'q': 'genre = 1'})
        self.assertIn('tree', data)
        self.assertEqual('leaf', data['tree']['role'])
        self.assertIn('count', data['tree'])

    def test_explain_endpoint_empty_query(self):
        self.assertTrue(self.client.login(**self.credentials))
        url = reverse('admin:core_book_djangoql_explain')
        data = self.get_json(url, data={'q': ''})
        self.assertIsNone(data['tree'])

    def test_explain_endpoint_invalid_query(self):
        self.assertTrue(self.client.login(**self.credentials))
        url = reverse('admin:core_book_djangoql_explain')
        response = self.client.get(url, {'q': 'nonexistent_field = 1'})
        self.assertEqual(400, response.status_code)
        self.assertIn('error', json.loads(response.content.decode('utf8')))

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
            url = reverse('%s:djangoql_syntax_help' % app)
            # unauthorized request should be redirected
            response = self.client.get(url)
            self.assertEqual(302, response.status_code)
            self.assertTrue(self.client.login(**self.credentials))
            # authorized request should be served
            response = self.client.get(url)
            self.assertEqual(200, response.status_code)
            self.client.logout()

    def test_djangoql_syntax_help_renders_markdown_content(self):
        url = reverse('admin:djangoql_syntax_help')
        self.assertTrue(self.client.login(**self.credentials))
        response = self.client.get(url)
        body = response.content.decode('utf-8')
        # Content sourced from the Markdown help is present, and the image
        # token has been substituted with a real static URL.
        self.assertIn('Comparison operators', body)
        self.assertNotIn('COMPLETION_EXAMPLE_IMG', body)
        self.assertIn('completion_example.png', body)

    def test_djangoql_syntax_help_follows_active_language(self):
        url = reverse('admin:djangoql_syntax_help')
        self.assertTrue(self.client.login(**self.credentials))
        with translation.override('pl'):
            response = self.client.get(url)
        body = response.content.decode('utf-8')
        # The Polish help uses a translated heading.
        self.assertIn('Składnia', body)
        self.assertEqual(
            'Składnia zapytań DjangoQL',
            response.context['title'],
        )

    def test_djangoql_syntax_help_accepts_language_query_string(self):
        url = reverse('admin:djangoql_syntax_help')
        self.assertTrue(self.client.login(**self.credentials))
        response = self.client.get(url, {'lang': 'pl'})
        body = response.content.decode('utf-8')
        self.assertIn('Składnia zapytań DjangoQL', body)
        self.assertEqual('pl', response.context['language'])

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
        self.assertEqual(
            r,
            {
                'page': 1,
                'has_next': False,
                'items': ['Drama', 'Comics', 'Other'],
            },
        )

        # test that search is working
        r = self.get_json(url, data={'field': 'genre', 'search': 'o'})
        self.assertEqual(
            r,
            {
                'page': 1,
                'has_next': False,
                'items': ['Comics', 'Other'],
            },
        )

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
        self.assertEqual(
            r,
            {
                'page': 2,
                'has_next': False,
                'items': [],
            },
        )

    def test_query(self):
        url = reverse('admin:core_book_changelist') + '?q=price=0'
        self.assertTrue(self.client.login(**self.credentials))
        response = self.client.get(url)
        # There should be no error at least
        self.assertEqual(200, response.status_code)

    def test_changelist_strips_search_marker(self):
        # DjangoQLChangeList.get_filters_params must drop the q-l marker so it
        # isn't treated as a model field filter (which would 500).
        self.assertTrue(self.client.login(**self.credentials))
        url = reverse('admin:core_book_changelist') + '?q-l=on&q=name="x"'
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)

    def test_suggestions_unsupported_field(self):
        # A field without suggest_options should produce a clear 400 error
        # instead of an empty/crashing response.
        self.assertTrue(self.client.login(**self.credentials))
        url = reverse('admin:core_book_djangoql_suggestions')
        r = self.get_json(url, status=400, data={'field': 'name'})
        self.assertEqual(
            r.get('error'),
            "Book.name doesn't support suggestions",
        )


class DjangoQLSearchFlowTest(TestCase):
    """Exercise DjangoQLSearchMixin.get_search_results and friends directly.

    The endpoint tests above only cover the JSON introspection/suggestions
    views; the actual search path (toggle handling, error -> warning, media)
    needs the admin methods invoked against a request.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username='boss',
            email='boss@derp.rr',
            password='lol',
        )
        Book.objects.create(name='alpha', author=cls.user)

    def setUp(self):
        self.factory = RequestFactory()
        # The mixin is applied to the registered ModelAdmin instances.
        self.book_admin = django_admin.site._registry[Book]
        self.user_admin = django_admin.site._registry[User]

    def _request(self, path='/'):
        request = self.factory.get(path)
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_search_mode_toggle_enabled(self):
        # BookAdmin keeps the stub search_fields -> single (DjangoQL) mode.
        self.assertFalse(self.book_admin.search_mode_toggle_enabled())
        # CustomUserAdmin defines its own search_fields -> toggle offered.
        self.assertTrue(self.user_admin.search_mode_toggle_enabled())

    def test_djangoql_search_enabled(self):
        self.assertTrue(
            self.user_admin.djangoql_search_enabled(self._request('/?q-l=on')),
        )
        self.assertFalse(
            self.user_admin.djangoql_search_enabled(self._request('/?q-l=off')),
        )
        self.assertFalse(
            self.user_admin.djangoql_search_enabled(self._request('/')),
        )

    def test_empty_search_returns_queryset_unchanged(self):
        qs = Book.objects.all()
        result, use_distinct = self.book_admin.get_search_results(
            self._request(),
            qs,
            '',
        )
        self.assertFalse(use_distinct)
        self.assertEqual(list(result), list(qs))

    def test_toggle_falls_back_to_default_search(self):
        # Toggle enabled + no q-l marker -> plain Django search_fields lookup.
        request = self._request('/')
        result, _ = self.user_admin.get_search_results(
            request,
            User.objects.all(),
            'boss',
        )
        self.assertIn(self.user, result)

    def test_valid_djangoql_search(self):
        request = self._request()
        result, _ = self.book_admin.get_search_results(
            request,
            Book.objects.all(),
            'name = "alpha"',
        )
        self.assertEqual([b.name for b in result], ['alpha'])
        self.assertEqual(len(request._messages._queued_messages), 0)

    def test_invalid_djangoql_search_adds_warning(self):
        request = self._request()
        result, _ = self.book_admin.get_search_results(
            request,
            Book.objects.all(),
            'no_such_field = 1',
        )
        # Bad queries yield an empty result set, not a 500.
        self.assertEqual(list(result), [])
        queued = request._messages._queued_messages
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].level, WARNING)

    def test_error_message_from_validation_error(self):
        # ValidationError carries .messages; the mixin must use the first one.
        html = self.book_admin.djangoql_error_message(ValidationError('boom'))
        self.assertIn('boom', html)

    def test_explain_not_supported_falls_back_to_slice(self):
        # If .explain() isn't supported by the backend, the mixin probes the
        # queryset with a 1-row slice instead and returns it unchanged.
        fake = FakeQuerySet(['x'], explain_exc=NotSupportedError())
        request = self._request()
        with mock.patch(
            'djangoql.admin.apply_search',
            return_value=fake,
        ):
            result, _ = self.book_admin.get_search_results(
                request,
                Book.objects.all(),
                'name = "alpha"',
            )
        self.assertIs(result, fake)
        self.assertEqual(len(request._messages._queued_messages), 0)

    def test_search_without_explain_method(self):
        # A queryset lacking a callable .explain() is probed with a slice.
        fake = ['only-item']  # plain list: no .explain attribute
        request = self._request()
        with mock.patch(
            'djangoql.admin.apply_search',
            return_value=fake,
        ):
            result, _ = self.book_admin.get_search_results(
                request,
                Book.objects.all(),
                'name = "alpha"',
            )
        self.assertIs(result, fake)
        self.assertEqual(len(request._messages._queued_messages), 0)

    def test_inet_data_error_is_swallowed_as_warning(self):
        fake = FakeQuerySet(explain_exc=DataError('bad inet value'))
        request = self._request()
        with mock.patch(
            'djangoql.admin.apply_search',
            return_value=fake,
        ):
            result, _ = self.book_admin.get_search_results(
                request,
                Book.objects.all(),
                'name = "alpha"',
            )
        # 'inet' errors become a user warning + empty result set.
        self.assertEqual(list(result), [])
        queued = request._messages._queued_messages
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].level, WARNING)

    def test_non_inet_data_error_propagates(self):
        fake = FakeQuerySet(explain_exc=DataError('some other failure'))
        request = self._request()
        with mock.patch(
            'djangoql.admin.apply_search',
            return_value=fake,
        ):
            with self.assertRaises(DataError):
                self.book_admin.get_search_results(
                    request,
                    Book.objects.all(),
                    'name = "alpha"',
                )

    def test_media_includes_multiline_script(self):
        # Shift+Enter newline support ships as a small framework-agnostic JS
        # file that the admin loads alongside the completion widget.
        rendered = str(self.book_admin.media)
        self.assertIn('djangoql/js/multiline.js', rendered)

    def test_media_includes_i18n_catalog(self):
        # The djangojs gettext catalog is emitted as a <script> on the
        # changelist so completion.js can translate the operator hint labels
        # and the search placeholder. It is referenced by its (root-relative)
        # view URL, not a static path, and must load before completion.js.
        catalog_url = reverse('admin:core_book_djangoql_i18n')
        rendered = str(self.book_admin.media)
        self.assertIn(catalog_url, rendered)
        self.assertLess(
            rendered.index(catalog_url),
            rendered.index('djangoql/js/completion.js'),
        )

    def test_highlight_opt_in_media(self):
        # Highlighting is opt-in: off by default, no overlay assets loaded.
        rendered = str(self.book_admin.media)
        self.assertNotIn('djangoql/js/highlight.js', rendered)
        self.assertNotIn('djangoql/css/highlight.css', rendered)

        # Turning djangoql_highlight on adds the overlay JS + CSS.
        admin_obj = BookAdmin(Book, django_admin.site)
        admin_obj.djangoql_highlight = True
        rendered_on = str(admin_obj.media)
        self.assertIn('djangoql/js/highlight.js', rendered_on)
        self.assertIn('djangoql/css/highlight.css', rendered_on)

    def test_media_includes_toggle_scripts(self):
        rendered = str(self.user_admin.media)
        self.assertIn('djangoql/js/completion_admin_toggle.js', rendered)

        # When completion is on but not by default, an extra script is added.
        admin_obj = CustomUserAdmin(User, django_admin.site)
        admin_obj.djangoql_completion_enabled_by_default = False
        rendered_off = str(admin_obj.media)
        self.assertIn(
            'djangoql/js/completion_admin_toggle_off.js',
            rendered_off,
        )


class EmptyBreakdownTest(TestCase):
    """djangoql_add_empty_breakdown: a valid search returning zero rows gets a
    warning explaining *where* the query runs out of data; failures in that
    diagnostic must never break the changelist."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username='boss-breakdown',
            email='bd@derp.rr',
            password='lol',
        )
        Book.objects.create(name='alpha', author=cls.user)

    def setUp(self):
        self.factory = RequestFactory()
        self.book_admin = django_admin.site._registry[Book]

    def _request(self):
        request = self.factory.get('/')
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def _search(self, admin_obj, term):
        request = self._request()
        result, _ = admin_obj.get_search_results(
            request,
            Book.objects.all(),
            term,
        )
        return request, result

    def test_empty_result_adds_breakdown_warning(self):
        # A valid query that matches nothing -> exactly one WARNING carrying the
        # rendered breakdown.
        request, result = self._search(self.book_admin, 'name = "nope"')
        self.assertEqual(list(result), [])
        queued = request._messages._queued_messages
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].level, WARNING)

    def test_non_empty_result_has_no_breakdown(self):
        request, result = self._search(self.book_admin, 'name = "alpha"')
        self.assertEqual([b.name for b in result], ['alpha'])
        self.assertEqual(len(request._messages._queued_messages), 0)

    def test_breakdown_disabled_skips(self):
        admin_obj = BookAdmin(Book, django_admin.site)
        admin_obj.djangoql_explain_empty = False
        request, result = self._search(admin_obj, 'name = "nope"')
        self.assertEqual(list(result), [])
        self.assertEqual(len(request._messages._queued_messages), 0)

    def test_breakdown_failure_is_swallowed(self):
        # If explain_empty blows up, the changelist still renders the (empty)
        # result with no warning rather than 500-ing.
        with mock.patch(
            'djangoql.admin.explain_empty',
            side_effect=DjangoQLError('boom'),
        ):
            request, result = self._search(self.book_admin, 'name = "nope"')
        self.assertEqual(list(result), [])
        self.assertEqual(len(request._messages._queued_messages), 0)

    def test_breakdown_none_adds_no_warning(self):
        # explain_empty returning None (e.g. not actually empty) adds nothing.
        with mock.patch(
            'djangoql.admin.explain_empty',
            return_value=None,
        ):
            request, _ = self._search(self.book_admin, 'name = "nope"')
        self.assertEqual(len(request._messages._queued_messages), 0)
