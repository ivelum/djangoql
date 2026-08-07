# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from django.utils.translation import override

from djangoql.exceptions import DjangoQLLexerError, DjangoQLSchemaError
from djangoql.lexer import DjangoQLLexer
from djangoql.parser import DjangoQLParser
from djangoql.schema import StrField

from ..models import Book


class TestI18n(SimpleTestCase):
    """
    Verifies that user-facing error messages are translatable.

    The Polish locale (pl) ships with hand-written, native-quality
    translations and is used as the canary here. Other locales ship as
    best-effort auto-translations.
    """

    def test_lexer_error_is_translated_to_polish(self):
        lexer = DjangoQLLexer()
        with override('pl'):
            try:
                list(lexer.input('@'))
                self.fail('Expected DjangoQLLexerError')
            except DjangoQLLexerError as e:
                self.assertIn('Niedozwolony znak', str(e))
                self.assertIn('Linia', str(e))

    def test_lexer_error_stays_english_by_default(self):
        lexer = DjangoQLLexer()
        with override('en'):
            try:
                list(lexer.input('@'))
                self.fail('Expected DjangoQLLexerError')
            except DjangoQLLexerError as e:
                self.assertIn('Illegal character', str(e))

    def test_parser_error_is_translated(self):
        parser = DjangoQLParser()
        with override('pl'):
            try:
                parser.parse('name =')
                self.fail('Expected a parse error')
            except Exception as e:
                msg = str(e)
                self.assertTrue(
                    'Nieoczekiwany koniec' in msg or 'Błąd składni' in msg,
                    'Got non-Polish message: %s' % msg,
                )

    def test_schema_error_with_named_placeholders_is_translated(self):
        # Triggers the StrField vs int-value validation error.
        field = StrField(model=Book, name='name')
        with override('pl'):
            try:
                field.validate(123)
                self.fail('Expected DjangoQLSchemaError')
            except DjangoQLSchemaError as e:
                msg = str(e)
                self.assertIn('Pole', msg)
                self.assertIn('name', msg)

    def test_value_types_description_is_translated(self):
        with override('pl'):
            self.assertEqual(
                'łańcuchami znaków',
                str(StrField.value_types_description),
            )
