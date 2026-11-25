from datetime import date

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.db import models
from django.test import TestCase

from djangoql.exceptions import DjangoQLSchemaError
from djangoql.llm import describe_schema_for_llm
from djangoql.parser import DjangoQLParser
from djangoql.schema import (
    DateField,
    DjangoQLField,
    DjangoQLSchema,
    IntField,
    StrField,
)
from djangoql.serializers import SuggestionsAPISerializer

from ..models import Book


serializer = SuggestionsAPISerializer('/suggestions/')


class ExcludeUserSchema(DjangoQLSchema):
    exclude = (User,)


class IncludeUserGroupSchema(DjangoQLSchema):
    include = (Group, User)


class IncludeExcludeSchema(DjangoQLSchema):
    include = (Group,)
    exclude = (Book,)


class BookCustomFieldsSchema(DjangoQLSchema):
    def get_fields(self, model):
        if model == Book:
            return ['name', 'is_published']
        return super().get_fields(model)


class WrittenInYearField(IntField):
    model = Book
    name = 'written_in_year'

    def get_lookup_name(self):
        return 'written__year'


class BookCustomSearchSchema(DjangoQLSchema):
    def get_fields(self, model):
        if model == Book:
            return [
                WrittenInYearField(),
            ]


class OnlyBookNameSchema(DjangoQLSchema):
    include_fields = {Book: ['name', 'is_published']}


class BookWithoutGenreSchema(DjangoQLSchema):
    exclude_fields = {Book: ['genre', 'price']}


class FieldFilteringTest(TestCase):
    def _book_fields(self, schema):
        return set(serializer.serialize(schema)['models']['core.book'].keys())

    def test_include_fields_is_allowlist(self):
        fields = self._book_fields(OnlyBookNameSchema(Book))
        self.assertEqual(fields, {'name', 'is_published'})

    def test_exclude_fields_is_denylist(self):
        fields = self._book_fields(BookWithoutGenreSchema(Book))
        self.assertNotIn('genre', fields)
        self.assertNotIn('price', fields)
        self.assertIn('name', fields)
        self.assertIn('rating', fields)

    def test_unfiltered_model_keeps_all_fields(self):
        default = self._book_fields(DjangoQLSchema(Book))
        filtered = self._book_fields(BookWithoutGenreSchema(Book))
        self.assertEqual(default - filtered, {'genre', 'price'})


class ConflictingFieldRulesSchema(DjangoQLSchema):
    include_fields = {Book: ['name']}
    exclude_fields = {Book: ['genre']}


class TypoFieldSchema(DjangoQLSchema):
    include_fields = {Book: ['naem']}


class FieldFilteringValidationTest(TestCase):
    def test_same_model_in_both_dicts_raises(self):
        with self.assertRaises(DjangoQLSchemaError):
            ConflictingFieldRulesSchema(Book)

    def test_unknown_field_name_raises_and_is_named(self):
        with self.assertRaises(DjangoQLSchemaError) as ctx:
            TypoFieldSchema(Book)
        self.assertIn('naem', str(ctx.exception))


class FieldFilteringConsequencesTest(TestCase):
    def test_filtered_relation_drops_related_model(self):
        # OnlyBookNameSchema keeps only Book.name, dropping the `author` FK,
        # so User must never be introspected.
        models = serializer.serialize(OnlyBookNameSchema(Book))['models']
        self.assertEqual(set(models), {'core.book'})
        self.assertNotIn('auth.user', models)

    def test_filtered_relation_blocks_traversal(self):
        schema = OnlyBookNameSchema(Book)
        ast = DjangoQLParser().parse('author.username = "x"')
        with self.assertRaises(DjangoQLSchemaError):
            schema.validate(ast)

    def test_llm_description_respects_field_filter(self):
        description = describe_schema_for_llm(BookWithoutGenreSchema(Book))
        book_fields = description['models']['core.book']
        self.assertNotIn('genre', book_fields)
        self.assertNotIn('price', book_fields)
        self.assertIn('name', book_fields)


class DjangoQLSchemaTest(TestCase):
    def all_models(self):
        models = []
        for app_label in apps.app_configs:
            models.extend(apps.get_app_config(app_label).get_models())
        return models

    def test_default(self):
        schema_dict = serializer.serialize(DjangoQLSchema(Book))
        self.assertIsInstance(schema_dict, dict)
        self.assertEqual('core.book', schema_dict.get('current_model'))
        models = schema_dict.get('models')
        self.assertIsInstance(models, dict)
        all_model_labels = sorted([str(m._meta) for m in self.all_models()])
        session_model = all_model_labels.pop()
        self.assertEqual('sessions.session', session_model)
        self.assertListEqual(all_model_labels, sorted(models.keys()))

    def test_exclude(self):
        schema_dict = serializer.serialize(ExcludeUserSchema(Book))
        self.assertEqual('core.book', schema_dict['current_model'])
        self.assertListEqual(
            sorted(schema_dict['models'].keys()),
            [
                'admin.logentry',
                'auth.group',
                'auth.permission',
                'contenttypes.contenttype',
                'core.book',
            ],
        )

    def test_include(self):
        schema_dict = serializer.serialize(IncludeUserGroupSchema(User))
        self.assertEqual('auth.user', schema_dict['current_model'])
        self.assertListEqual(
            sorted(schema_dict['models'].keys()),
            [
                'auth.group',
                'auth.user',
            ],
        )

    def test_get_fields(self):
        default_schema = DjangoQLSchema(Book)
        default = serializer.serialize(default_schema)['models']['core.book']
        custom_schema = BookCustomFieldsSchema(Book)
        custom = serializer.serialize(custom_schema)['models']['core.book']
        self.assertListEqual(
            list(default.keys()),
            [
                'author',
                'content_type',
                'genre',
                'id',
                'is_published',
                'name',
                'object_id',
                'price',
                'published_date',
                'published_time',
                'rating',
                'similar_books',
                'written',
            ],
        )
        self.assertListEqual(list(custom.keys()), ['name', 'is_published'])

    def test_circular_references(self):
        models = serializer.serialize(DjangoQLSchema(Book))['models']
        # If Book references Author then Author should also reference Book back
        book_author_field = models['core.book'].get('author')
        self.assertIsNotNone(book_author_field)
        self.assertEqual('relation', book_author_field['type'])
        self.assertEqual('auth.user', book_author_field['relation'])
        self.assertEqual('relation', models['auth.user']['book']['type'])

    def test_custom_search(self):
        models = serializer.serialize(BookCustomSearchSchema(Book))['models']
        self.assertListEqual(
            list(models['core.book'].keys()),
            ['written_in_year'],
        )

    def test_invalid_config(self):
        try:
            IncludeExcludeSchema(Group)
            self.fail('Invalid schema with include & exclude raises no error')
        except DjangoQLSchemaError:
            pass
        try:
            IncludeUserGroupSchema(Book)
            self.fail('Schema was initialized with a model excluded from it')
        except DjangoQLSchemaError:
            pass
        try:
            IncludeUserGroupSchema(User())
            self.fail('Schema was initialized with an instance of a model')
        except DjangoQLSchemaError:
            pass

    def test_validation_pass(self):
        samples = [
            'first_name = "Lolita"',
            'groups.id < 42',
            'groups = None',  # that's ok to compare a model to None
            'groups != None',
            'groups.name in ("Stoics") and is_staff = False',
            'date_joined > "1753-01-01"',
            'date_joined > "1753-01-01 01:24"',
            'date_joined > "1753-01-01 01:24:42"',
        ]
        for query in samples:
            ast = DjangoQLParser().parse(query)
            try:
                IncludeUserGroupSchema(User).validate(ast)
            except DjangoQLSchemaError as e:
                self.fail(e)

    def test_validation_fail(self):
        samples = [
            'gav = 1',  # unknown field
            'groups.gav > 1',  # unknown related field
            'groups = "lol"',  # can't compare model to a value
            'groups.name != 1',  # bad value type
            'is_staff = True and gav < 2',  # complex expression with valid part
            'date_joined < "1753-30-01"',  # bad timestamps
            'date_joined < "1753-01-01 12"',
            'date_joined < "1753-01-01 12AM"',
        ]
        for query in samples:
            ast = DjangoQLParser().parse(query)
            try:
                IncludeUserGroupSchema(User).validate(ast)
                self.fail("This query should't pass validation: %s" % query)
            except DjangoQLSchemaError:
                pass

    def test_get_field_cls_mapping(self):
        # Model field class -> DjangoQL field class resolution, including the
        # plain DateField branch (the test models only use DateTimeField) and
        # the fallthrough for an unmapped field type.
        schema = DjangoQLSchema(Book)
        self.assertIs(schema.get_field_cls(models.DateField()), DateField)
        self.assertIs(
            schema.get_field_cls(models.DurationField()),
            DjangoQLField,
        )

    def test_as_dict_is_deprecated(self):
        # as_dict() calls warnings.warn() without an explicit category, so the
        # warning is a UserWarning rather than a DeprecationWarning.
        with self.assertWarns(UserWarning) as ctx:
            result = DjangoQLSchema(Book).as_dict()
        self.assertIn('deprecated', str(ctx.warning))
        self.assertEqual('core.book', result['current_model'])


class StrFieldOptionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        author = User.objects.create(username='author')
        for name in ('alpha', 'beta', 'gamma'):
            Book.objects.create(name=name, author=author)

    def test_get_options_returns_choices_when_present(self):
        # When the underlying model field defines choices, get_options returns
        # the matching choice labels instead of querying the column.
        field = StrField(model=Book, name='genre')
        self.assertEqual(list(field.get_options('dra')), ['Drama'])

    def test_get_options_falls_back_to_icontains(self):
        # A StrField with no choices should query the model with an icontains
        # lookup on its own column, ordered and de-duplicated.
        field = StrField(model=Book, name='name')
        self.assertEqual(
            list(field.get_options('a')),
            ['alpha', 'beta', 'gamma'],
        )
        self.assertEqual(list(field.get_options('ph')), ['alpha'])
        # Empty search drops the lookup and returns everything.
        self.assertEqual(
            list(field.get_options('')),
            ['alpha', 'beta', 'gamma'],
        )


class FieldValidateTest(TestCase):
    def test_non_nullable_field_rejects_none(self):
        with self.assertRaises(DjangoQLSchemaError):
            IntField(name='age', nullable=False).validate(None)

    def test_nullable_field_rejects_wrong_type(self):
        # A nullable field reports the "nullable <type>" variant of the error.
        with self.assertRaises(DjangoQLSchemaError) as ctx:
            IntField(name='age', nullable=True).validate('not-an-int')
        self.assertIn('nullable', str(ctx.exception))


class DateFieldTest(TestCase):
    def test_parse_date(self):
        self.assertIsNone(DateField.parse_date(''))
        self.assertEqual(DateField.parse_date('2017-01-30'), date(2017, 1, 30))

    def test_validate_rejects_non_date(self):
        field = DateField(model=Book, name='written')
        # A well-formed string that isn't a real date must raise, not crash.
        with self.assertRaises(DjangoQLSchemaError):
            field.validate('not-a-date')


class UnknownFieldSuggestionTest(TestCase):
    """The "Unknown field" error suggests close matches for likely typos."""

    def _error(self, schema, model, query):
        ast = DjangoQLParser().parse(query)
        with self.assertRaises(DjangoQLSchemaError) as ctx:
            schema(model).validate(ast)
        return str(ctx.exception)

    def test_close_typo_suggests_field_and_omits_full_list(self):
        msg = self._error(DjangoQLSchema, Book, 'autho = 1')
        self.assertIn('Did you mean', msg)
        self.assertIn('author', msg)
        # With a good guess, the long fallback list is dropped.
        self.assertNotIn('Possible choices', msg)

    def test_gibberish_falls_back_to_full_list(self):
        msg = self._error(DjangoQLSchema, Book, 'aoijdsofiajs = 1')
        self.assertIn('Possible choices are', msg)
        self.assertNotIn('Did you mean', msg)

    def test_suggestion_is_case_insensitive(self):
        msg = self._error(DjangoQLSchema, Book, 'Authr = 1')
        self.assertIn('Did you mean', msg)
        self.assertIn('author', msg)

    def test_pool_includes_hidden_derived_fields(self):
        from djangoql.extras import ExtrasSchema

        # book__count is a hidden (suggested=False) reverse-relation aggregate,
        # so it is not in the fallback list but is still matchable.
        msg = self._error(ExtrasSchema, User, 'book__coun = 1')
        self.assertIn('Did you mean', msg)
        self.assertIn('book__count', msg)

    def test_hint_still_appended_in_did_you_mean_branch(self):
        class HintSchema(DjangoQLSchema):
            def unknown_field_hint(self, model_cls):
                return 'See the docs'

        msg = self._error(HintSchema, Book, 'autho = 1')
        self.assertIn('Did you mean', msg)
        self.assertIn('See the docs', msg)

    def test_suggest_field_names_is_overridable(self):
        class NoSuggestSchema(DjangoQLSchema):
            def suggest_field_names(self, name_part, candidates):
                return []

        msg = self._error(NoSuggestSchema, Book, 'autho = 1')
        self.assertNotIn('Did you mean', msg)
        self.assertIn('Possible choices', msg)

    def test_strong_match_suppresses_unrelated_suffix_noise(self):
        # A clear winner must not be diluted by fields that merely share a
        # "__suffix": 'autorzy__cnt' should suggest 'autorzy__count', never the
        # unrelated 'utworzono__month'.
        schema = DjangoQLSchema(Book)
        candidates = [
            'autorzy__count',
            'autorzy',
            'utworzono__month',
            'utworzono__year',
            'utworzono',
            'tytul',
            'isbn',
        ]
        result = schema.suggest_field_names('autorzy__cnt', candidates)
        self.assertIn('autorzy__count', result)
        self.assertNotIn('utworzono__month', result)
        self.assertNotIn('utworzono__year', result)

    def test_no_dominant_match_keeps_comparable_options(self):
        # When several candidates are similarly close, keep them (this is a
        # genuine ambiguity, not noise).
        schema = DjangoQLSchema(Book)
        result = schema.suggest_field_names('naem', ['name', 'names'])
        self.assertIn('name', result)
        self.assertIn('names', result)
