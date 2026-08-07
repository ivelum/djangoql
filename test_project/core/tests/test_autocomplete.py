# Tests for djangoql.extras.AutocompleteField / AutocompleteSchemaMixin.
import json

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from djangoql.extras import AutocompleteField, AutocompleteSchemaMixin
from djangoql.parser import DjangoQLParser
from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema, RelationField
from djangoql.serializers import SuggestionsAPISerializer
from djangoql.views import SuggestionsAPIView

from ..models import Book


class QuerysetAutocompleteSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    include = (Book, User)
    autocomplete = {
        Book: {
            'author': {
                'queryset': lambda s: User.objects.filter(
                    username__icontains=s
                ).order_by('username'),
                'search_fields': ['username'],
                'label': lambda u: u.username,
            },
        },
    }


class UrlAutocompleteSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    include = (Book, User)
    autocomplete = {
        Book: {
            'author': {
                'url': 'user-autocomplete',
                'search_fields': ['username'],
            },
        },
    }


class ParseIdTest(TestCase):
    def setUp(self):
        self.field = AutocompleteField(
            model=Book, name='author', search_fields=['username']
        )

    def test_parse_single_id(self):
        self.assertEqual(self.field.parse_id('Jan Kowalski #42'), 42)
        # Legacy [id] form is still accepted.
        self.assertEqual(self.field.parse_id('Jan Kowalski [42]'), 42)

    def test_parse_id_list(self):
        self.assertEqual(
            self.field.parse_id(['A [1]', 'B [2]']),
            [1, 2],
        )

    def test_parse_plain_string_returns_raw(self):
        self.assertEqual(self.field.parse_id('plain'), 'plain')


class QuerysetProviderTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.kow = User.objects.create(username='Jan Kowalski')
        cls.nowak = User.objects.create(username='Anna Nowak')

    def _field(self, **kw):
        kw.setdefault('model', Book)
        kw.setdefault('name', 'author')
        kw.setdefault('search_fields', ['username'])
        return AutocompleteField(**kw)

    def test_get_options_formats_label_and_id(self):
        field = self._field(
            queryset=lambda s: User.objects.filter(
                username__icontains=s
            ).order_by('username'),
            label=lambda u: u.username,
        )
        options = list(field.get_options('kow'))
        self.assertEqual(options, ['Jan Kowalski #%d' % self.kow.pk])

    def test_get_options_respects_limit(self):
        for i in range(5):
            User.objects.create(username='dup%d' % i)
        field = self._field(
            queryset=lambda s: User.objects.filter(
                username__icontains=s
            ).order_by('username'),
            label=lambda u: u.username,
            limit=2,
        )
        options = list(field.get_options('dup'))
        self.assertEqual(len(options), 2)

    def test_get_options_strips_trailing_id_from_search(self):
        field = self._field(
            queryset=lambda s: User.objects.filter(
                username__icontains=s
            ).order_by('username'),
            label=lambda u: u.username,
        )
        options = list(field.get_options('Jan Kowalski [%d]' % self.kow.pk))
        self.assertEqual(options, ['Jan Kowalski #%d' % self.kow.pk])


class QueryByPkTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.kow = User.objects.create(username='Jan Kowalski')
        cls.nowak = User.objects.create(username='Anna Nowak')
        cls.b1 = Book.objects.create(name='b1', author=cls.kow)
        cls.b2 = Book.objects.create(name='b2', author=cls.nowak)

    def _search(self, q):
        return apply_search(
            Book.objects.all(), q, schema=QuerysetAutocompleteSchema
        )

    def test_equals_filters_by_pk(self):
        qs = self._search('author = "Jan Kowalski [%d]"' % self.kow.pk)
        sql = str(qs.query)
        self.assertIn('author_id', sql)
        self.assertIn('= %d' % self.kow.pk, sql)
        self.assertNotIn('username', sql)
        self.assertEqual(list(qs), [self.b1])

    def test_not_equals_filters_by_pk(self):
        qs = self._search('author != "Jan Kowalski [%d]"' % self.kow.pk)
        self.assertEqual(list(qs), [self.b2])

    def test_in_filters_by_pks(self):
        qs = self._search(
            'author in ("Jan Kowalski [%d]", "Anna Nowak [%d]")'
            % (self.kow.pk, self.nowak.pk)
        )
        self.assertEqual(sorted(b.pk for b in qs), [self.b1.pk, self.b2.pk])

    def test_free_text_fallback_uses_icontains(self):
        qs = self._search('author = "kowal"')
        self.assertEqual(list(qs), [self.b1])
        sql = str(qs.query).lower()
        self.assertIn('username', sql)
        self.assertIn('like', sql)


class UrlProviderTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.kow = User.objects.create(username='Jan Kowalski')
        cls.b1 = Book.objects.create(name='b1', author=cls.kow)

    def test_url_provider_calls_view_in_process(self):
        request = RequestFactory().get('/')
        field = AutocompleteField(
            model=Book,
            name='author',
            url='user-autocomplete',
            search_fields=['username'],
        )
        field.set_request(request)
        options = list(field.get_options('kow'))
        self.assertEqual(options, ['Jan Kowalski #%d' % self.kow.pk])

    def test_url_provider_query_filters_by_pk(self):
        qs = apply_search(
            Book.objects.all(),
            'author = "Jan Kowalski [%d]"' % self.kow.pk,
            schema=UrlAutocompleteSchema,
        )
        self.assertEqual(list(qs), [self.b1])

    def test_request_reaches_view(self):
        # The bound request must reach the in-process view: the view reads
        # request.GET['q'], so a sentinel query carried on the bound request
        # only filters results if the same request object is threaded through.
        request = RequestFactory().get('/?q=zzz-nomatch')
        field = AutocompleteField(
            model=Book,
            name='author',
            url='user-autocomplete',
            search_fields=['username'],
        )
        field.set_request(request)
        # get_options overrides q with its own search term; the view sees that.
        options = list(field.get_options('kow'))
        self.assertEqual(options, ['Jan Kowalski #%d' % self.kow.pk])
        # And the bound request's GET param is what the view reads as 'q':
        self.assertEqual(request.GET.get('q'), 'kow')


class SchemaMixinTest(TestCase):
    def test_field_is_autocomplete_instance(self):
        schema = QuerysetAutocompleteSchema(Book)
        field = schema.models['core.book']['author']
        self.assertIsInstance(field, AutocompleteField)

    def test_field_is_not_a_relation(self):
        schema = QuerysetAutocompleteSchema(Book)
        field = schema.models['core.book']['author']
        self.assertNotIsInstance(field, RelationField)
        self.assertEqual(field.type, 'str')

    def test_serialized_schema_has_options_true(self):
        # The async suggestions serializer emits options: true (the widget then
        # fetches values via the suggestions endpoint) and no 'relation' key,
        # because the FK is exposed as a value field, not a relation.
        data = SuggestionsAPISerializer('/suggestions/').serialize(
            QuerysetAutocompleteSchema(Book)
        )
        author = data['models']['core.book']['author']
        self.assertEqual(author['options'], True)
        self.assertNotIn('relation', author)
        self.assertIn('suggestions_api_url', data)

    def test_serialized_field_marks_object_reference(self):
        # The front-end uses this flag to offer only = / != / in / not in.
        data = SuggestionsAPISerializer('/suggestions/').serialize(
            QuerysetAutocompleteSchema(Book)
        )
        self.assertIs(
            data['models']['core.book']['author']['object_reference'], True
        )
        # Plain fields don't get the flag.
        self.assertNotIn(
            'object_reference', data['models']['core.book']['name']
        )

    def test_async_options_true(self):
        field = AutocompleteField(
            model=Book, name='author', search_fields=['username']
        )
        self.assertTrue(field.async_options)
        self.assertTrue(field.suggest_options)


class ValidationTest(TestCase):
    def test_validate_accepts_str(self):
        schema = QuerysetAutocompleteSchema(Book)
        ast = DjangoQLParser().parse('author = "Jan [1]"')
        schema.validate(ast)  # must not raise


class RelAndPickerSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    """`author` zostaje relacją (trawersacja z kropką), a `author__rel` to
    picker filtrujący realny FK `author` przez lookup_name."""

    include = (Book, User)
    autocomplete = {
        Book: {
            'author__rel': {
                'lookup_name': 'author',
                'queryset': lambda s: User.objects.filter(
                    username__icontains=s
                ).order_by('username'),
                'search_fields': ['username'],
                'label': lambda u: u.username,
            },
        },
    }

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model is Book:
            fields.append('author__rel')
        return fields


class LookupNameTest(TestCase):
    def test_lookup_name_defaults_to_field_name(self):
        field = AutocompleteField(model=Book, name='author__rel')
        self.assertEqual(field.get_lookup_name(), 'author__rel')

    def test_lookup_name_overrides_lookup(self):
        field = AutocompleteField(
            model=Book, name='author__rel', lookup_name='author'
        )
        self.assertEqual(field.get_lookup_name(), 'author')


class RelAndPickerCoexistTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.kow = User.objects.create(username='Jan Kowalski')
        cls.nowak = User.objects.create(username='Anna Nowak')
        cls.b1 = Book.objects.create(name='b1', author=cls.kow)
        cls.b2 = Book.objects.create(name='b2', author=cls.nowak)

    def _search(self, q):
        return apply_search(Book.objects.all(), q, schema=RelAndPickerSchema)

    def test_picker_filters_real_fk_by_pk(self):
        qs = self._search('author__rel = "Jan Kowalski #%d"' % self.kow.pk)
        sql = str(qs.query)
        self.assertIn('author_id', sql)
        self.assertNotIn('author__rel', sql)
        self.assertEqual(list(qs), [self.b1])

    def test_picker_in_filters_by_pks(self):
        qs = self._search(
            'author__rel in ("Jan Kowalski [%d]", "Anna Nowak [%d]")'
            % (self.kow.pk, self.nowak.pk)
        )
        self.assertEqual(sorted(b.pk for b in qs), [self.b1.pk, self.b2.pk])

    def test_picker_not_equals_filters_by_pk(self):
        qs = self._search('author__rel != "Jan Kowalski [%d]"' % self.kow.pk)
        sql = str(qs.query)
        self.assertIn('author_id', sql)
        self.assertNotIn('author__rel', sql)
        self.assertEqual(list(qs), [self.b2])

    def test_picker_free_text_fallback_targets_real_fk(self):
        qs = self._search('author__rel = "kowal"')
        sql = str(qs.query).lower()
        self.assertIn('username', sql)
        self.assertIn('like', sql)
        self.assertEqual(list(qs), [self.b1])

    def test_dot_traversal_still_works(self):
        qs = self._search('author.username = "Jan Kowalski"')
        self.assertEqual(list(qs), [self.b1])

    def test_both_idioms_in_one_query(self):
        qs = self._search(
            'author.username = "Jan Kowalski" '
            'and author__rel = "Jan Kowalski [%d]"' % self.kow.pk
        )
        self.assertEqual(list(qs), [self.b1])

    def test_picker_is_value_field_relation_is_relation(self):
        schema = RelAndPickerSchema(Book)
        fields = schema.models['core.book']
        self.assertIsInstance(fields['author__rel'], AutocompleteField)
        self.assertIsInstance(fields['author'], RelationField)
        self.assertEqual(fields['author'].type, 'relation')


class AutocompleteEdgeCasesTest(TestCase):
    """Branches of AutocompleteField the happy-path tests don't reach."""

    @classmethod
    def setUpTestData(cls):
        cls.kow = User.objects.create(username='Jan Kowalski')

    def test_validate_rejects_non_string(self):
        from djangoql.exceptions import DjangoQLSchemaError

        field = AutocompleteField(model=Book, name='author')
        with self.assertRaises(DjangoQLSchemaError):
            field.validate(5)

    def test_validate_allows_none(self):
        field = AutocompleteField(model=Book, name='author')
        field.validate(None)  # must not raise

    def test_get_options_without_provider_raises(self):
        # No url, no queryset/get_queryset, no override -> explicit error.
        field = AutocompleteField(model=Book, name='author')
        with self.assertRaises(NotImplementedError):
            list(field.get_options('x'))

    def test_default_label_and_id(self):
        # No label/id_of -> str(obj) and obj.pk.
        field = AutocompleteField(
            model=Book,
            name='author',
            queryset=lambda s: User.objects.filter(username__icontains=s),
        )
        self.assertEqual(
            list(field.get_options('kowalski')),
            ['Jan Kowalski #%d' % self.kow.pk],
        )

    def test_queryset_object_with_search_fields(self):
        # A queryset *object* (not a callable) is filtered via search_fields.
        field = AutocompleteField(
            model=Book,
            name='author',
            queryset=User.objects.all().order_by('username'),
            search_fields=['username'],
            label=lambda u: u.username,
        )
        self.assertEqual(
            list(field.get_options('kowalski')),
            ['Jan Kowalski #%d' % self.kow.pk],
        )

    def test_free_text_lookup_without_search_fields_uses_field_name(self):
        # No embedded id and no search_fields -> icontains on the lookup name.
        field = AutocompleteField(model=Book, name='name')
        q = field.get_lookup([], '=', 'foo')
        self.assertIn('name__icontains', str(q))

    def test_get_lookup_value_parses_id(self):
        field = AutocompleteField(model=Book, name='author')
        self.assertEqual(field.get_lookup_value('Jan #7'), 7)

    def test_get_queryset_callable_and_custom_id_of(self):
        # The explicit get_queryset hook and a custom id_of are both honored.
        field = AutocompleteField(
            model=Book,
            name='author',
            get_queryset=lambda s: User.objects.filter(username__icontains=s),
            label=lambda u: u.username,
            id_of=lambda u: u.pk * 1000,
        )
        self.assertEqual(
            list(field.get_options('kowalski')),
            ['Jan Kowalski #%d' % (self.kow.pk * 1000)],
        )

    def test_url_provider_with_raw_path_and_no_request(self):
        # url given as a literal path (not a reverse name): reverse() misses, we
        # fall back to the path; with no bound request a throwaway one is built.
        field = AutocompleteField(
            model=Book,
            name='author',
            url='/autocomplete/user/',
        )
        self.assertEqual(
            list(field.get_options('kowalski')),
            ['Jan Kowalski #%d' % self.kow.pk],
        )


class AutocompleteConfigShapeTest(TestCase):
    """_build_autocomplete_field accepts a dict, an instance, or a callable, and
    backfills nullable from the model field when the picker name is real."""

    def _schema(self, config):
        class S(AutocompleteSchemaMixin, DjangoQLSchema):
            include = (Book, User)
            autocomplete = {Book: {'author': config}}

        return S(Book)

    def test_dict_config(self):
        field = self._schema({'search_fields': ['username']}).models[
            'core.book'
        ]['author']
        self.assertIsInstance(field, AutocompleteField)
        self.assertEqual(field.name, 'author')
        self.assertIs(field.model, Book)

    def test_instance_config(self):
        instance = AutocompleteField(search_fields=['username'])
        field = self._schema(instance).models['core.book']['author']
        self.assertIs(field, instance)
        # model/name are backfilled from the schema context.
        self.assertEqual(field.name, 'author')
        self.assertIs(field.model, Book)

    def test_callable_config(self):
        def make(model, field_name):
            return AutocompleteField(
                model=model, name=field_name, search_fields=['username']
            )

        field = self._schema(make).models['core.book']['author']
        self.assertIsInstance(field, AutocompleteField)
        self.assertEqual(field.name, 'author')

    def test_nullable_backfilled_from_model_field(self):
        # content_type is a nullable FK; the picker inherits nullable=True even
        # though the config doesn't set it.
        field = self._schema_for(
            'content_type', {'queryset': lambda s: []}
        ).models['core.book']['content_type']
        self.assertTrue(field.nullable)

    def _schema_for(self, field_name, config):
        class S(AutocompleteSchemaMixin, DjangoQLSchema):
            include = (Book, User)
            autocomplete = {Book: {field_name: config}}

        return S(Book)


class SuggestionsViewThreadsRequestTest(TestCase):
    """SuggestionsAPIView must hand the live request to request-aware fields
    (AutocompleteField.set_request) so url providers can call views in-process.
    """

    @classmethod
    def setUpTestData(cls):
        cls.kow = User.objects.create(username='Jan Kowalski')

    def test_set_request_threaded_into_autocomplete_field(self):
        view = SuggestionsAPIView.as_view(
            schema=QuerysetAutocompleteSchema(Book),
        )
        request = RequestFactory().get('/?field=author&search=kowalski')
        response = view(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['items'], ['Jan Kowalski #%d' % self.kow.pk])
