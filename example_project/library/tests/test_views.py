"""Tests for the standalone demo views — the error-locating helpers and the
``format`` / ``explain`` / ``search`` JSON endpoints.
"""

import json

from django.test import TestCase
from django.urls import reverse

from djangoql.exceptions import DjangoQLParserError, DjangoQLSchemaError
from djangoql.parser import DjangoQLParser
from djangoql.queryset import apply_search
from library.models import Author, Book, Country, Publisher
from library.schema import BookSchema
from library.views import _error_response, _locate


class LocateTest(TestCase):
    def test_prefers_word_boundary_match(self):
        # 'rating' must not match inside 'ratings'; the standalone one wins.
        line, column = _locate('ratings > 4 and rating < 2', 'rating')
        self.assertEqual(line, 1)
        self.assertEqual(column, 17)

    def test_falls_back_to_substring(self):
        # 'cde' is embedded in a word, so the word-boundary regex misses and we
        # fall back to a plain substring search.
        self.assertEqual(_locate('abcdef', 'cde'), (1, 3))

    def test_multiline_line_and_column(self):
        self.assertEqual(_locate('a = 1\nand bad = 2', 'bad'), (2, 5))

    def test_missing_needle_returns_none(self):
        self.assertEqual(_locate('abc', 'zzz'), (None, None))


class ErrorResponseTest(TestCase):
    def test_parser_error_carries_position_and_marks_to_end(self):
        try:
            DjangoQLParser().parse('year = = 5')
        except DjangoQLParserError as exc:
            response = _error_response(exc, 'year = = 5')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('line', data)
        self.assertIn('column', data)
        self.assertEqual(data['mark'], 'to_end')

    def test_schema_error_locates_offending_token(self):
        try:
            apply_search(Book.objects.all(), 'nope = 1', schema=BookSchema)
        except DjangoQLSchemaError as exc:
            response = _error_response(exc, 'nope = 1')
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(data['mark'], 'token')
        self.assertEqual(data['line'], 1)
        self.assertEqual(data['column'], 1)


class ApiEndpointsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(name='Poland', code='PL')
        cls.author = Author.objects.create(name='Lem', country=cls.country)
        cls.publisher = Publisher.objects.create(name='Acme Press')
        cls.book = Book.objects.create(
            title='Solaris',
            author=cls.author,
            publisher=cls.publisher,
            year=1961,
            pages=204,
            rating=4.5,
            price=29,
        )

    def _json(self, name, status=200, **params):
        response = self.client.get(reverse(name), params)
        self.assertEqual(response.status_code, status)
        return json.loads(response.content)

    def test_index_renders(self):
        response = self.client.get(reverse('demo'))
        self.assertEqual(response.status_code, 200)

    def test_search_returns_all_rows(self):
        data = self._json('demo-api-search')
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['rows'][0]['title'], 'Solaris')
        self.assertEqual(data['rows'][0]['author'], 'Lem')

    def test_search_filters_by_query(self):
        self.assertEqual(
            self._json('demo-api-search', q='rating > 4')['total'], 1
        )
        self.assertEqual(
            self._json('demo-api-search', q='rating < 1')['total'], 0
        )

    def test_search_invalid_query_returns_located_error(self):
        data = self._json('demo-api-search', status=400, q='nope = 1')
        self.assertIn('error', data)
        self.assertEqual(data['mark'], 'token')

    def test_format_pretty_prints(self):
        data = self._json('demo-api-format', q='rating > 4 and pages > 100')
        self.assertIn('\n', data['formatted'])

    def test_format_empty_query(self):
        self.assertEqual(
            self._json('demo-api-format', q='   ')['formatted'], ''
        )

    def test_format_invalid_query(self):
        data = self._json('demo-api-format', status=400, q='a = = b')
        self.assertIn('error', data)

    def test_explain_returns_tree(self):
        data = self._json('demo-api-explain', q='rating > 4')
        self.assertIsNotNone(data['tree'])
        self.assertIn('count', data['tree'])

    def test_explain_empty_query(self):
        self.assertIsNone(self._json('demo-api-explain', q='  ')['tree'])


class SyntaxHelpViewTest(TestCase):
    def test_renders_html_when_markdown_installed(self):
        # The example project declares `markdown`, so the help compiles to HTML.
        response = self.client.get(reverse('demo-syntax-help'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('<table>', body)
        self.assertNotIn('COMPLETION_EXAMPLE_IMG', body)
        self.assertIn('completion_example.png', body)

    def test_lang_param_selects_translation(self):
        response = self.client.get(reverse('demo-syntax-help'), {'lang': 'pl'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Składnia', response.content.decode('utf-8'))

    def test_unknown_lang_falls_back_to_english(self):
        response = self.client.get(reverse('demo-syntax-help'), {'lang': 'xx'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Comparison operators', response.content.decode('utf-8'))
