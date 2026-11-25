"""Tests for the showcase ``BookSchema`` — the generic ``<name>__rel`` object
pickers built on :class:`djangoql.extras.AutocompleteField`.
"""

from django.test import TestCase

from djangoql.extras import AutocompleteField
from djangoql.queryset import apply_search
from djangoql.schema import RelationField
from library.models import Author, Book, Country, Genre, Publisher
from library.schema import BookSchema, _relation_names


class RelationNamesTest(TestCase):
    def test_forward_fk_and_m2m_only(self):
        # author/publisher (FK) + genres (M2M); reverse/auto relations skipped.
        self.assertEqual(
            set(_relation_names(Book)),
            {'author', 'publisher', 'genres'},
        )

    def test_model_without_forward_relations(self):
        self.assertEqual(_relation_names(Country), [])


class SchemaShapeTest(TestCase):
    def setUp(self):
        self.schema = BookSchema(Book)
        self.book_fields = self.schema.models['library.book']

    def test_relations_stay_relations(self):
        for name in ('author', 'publisher', 'genres'):
            self.assertIsInstance(self.book_fields[name], RelationField)

    def test_pickers_are_autocomplete_fields(self):
        for name in ('author__rel', 'publisher__rel', 'genres__rel'):
            self.assertIsInstance(self.book_fields[name], AutocompleteField)

    def test_nested_relation_gets_a_picker_too(self):
        author_fields = self.schema.models['library.author']
        self.assertIsInstance(author_fields['country__rel'], AutocompleteField)

    def test_country_picker_searches_name_and_code(self):
        field = BookSchema(Author).get_field_instance(Author, 'country__rel')
        self.assertEqual(field.search_fields, ['name', 'code'])
        self.assertEqual(field.get_lookup_name(), 'country')


class PickerFilterTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pl = Country.objects.create(name='Poland', code='PL')
        cls.us = Country.objects.create(name='United States', code='US')
        cls.lem = Author.objects.create(name='Stanislaw Lem', country=cls.pl)
        cls.dick = Author.objects.create(name='Philip K Dick', country=cls.us)
        cls.pub = Publisher.objects.create(name='Acme Press')
        cls.sf = Genre.objects.create(name='Science Fiction')
        cls.solaris = Book.objects.create(
            title='Solaris',
            author=cls.lem,
            publisher=cls.pub,
            year=1961,
            pages=204,
            rating=4.5,
            price=29,
        )
        cls.solaris.genres.add(cls.sf)
        cls.ubik = Book.objects.create(
            title='Ubik',
            author=cls.dick,
            publisher=cls.pub,
            year=1969,
            pages=256,
            rating=4.2,
            price=25,
        )

    def _titles(self, query):
        qs = apply_search(Book.objects.all(), query, schema=BookSchema)
        return sorted(b.title for b in qs)

    def test_author_picker_filters_real_fk_by_pk(self):
        qs = apply_search(
            Book.objects.all(),
            'author__rel = "Stanislaw Lem #%d"' % self.lem.pk,
            schema=BookSchema,
        )
        self.assertEqual([b.title for b in qs], ['Solaris'])
        sql = str(qs.query)
        self.assertIn('author_id', sql)
        self.assertNotIn('author__rel', sql)

    def test_legacy_bracket_id_form_still_accepted(self):
        self.assertEqual(
            self._titles('author__rel = "Lem [%d]"' % self.lem.pk),
            ['Solaris'],
        )

    def test_picker_in_filters_by_pks(self):
        self.assertEqual(
            self._titles(
                'author__rel in ("Lem #%d", "Dick #%d")'
                % (self.lem.pk, self.dick.pk)
            ),
            ['Solaris', 'Ubik'],
        )

    def test_nested_country_picker_filters_by_pk(self):
        self.assertEqual(
            self._titles('author.country__rel = "Poland #%d"' % self.pl.pk),
            ['Solaris'],
        )

    def test_m2m_genres_picker_filters_by_pk(self):
        self.assertEqual(
            self._titles('genres__rel = "SF #%d"' % self.sf.pk),
            ['Solaris'],
        )

    def test_free_text_fallback_uses_search_fields(self):
        # No embedded id -> icontains over the related model's search_fields.
        self.assertEqual(self._titles('author__rel = "lem"'), ['Solaris'])

    def test_country_picker_options_match_by_code(self):
        field = BookSchema(Author).get_field_instance(Author, 'country__rel')
        options = list(field.get_options('PL'))
        self.assertTrue(any('#%d' % self.pl.pk in opt for opt in options))
