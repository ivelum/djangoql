from django.apps import apps
from django.contrib.auth.models import Group, User
from django.test import TestCase

from djangoql.exceptions import DjangoQLSchemaError
from djangoql.parser import DjangoQLParser
from djangoql.schema import DjangoQLSchema, IntField

from ..models import Book


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
        return super(BookCustomFieldsSchema, self).get_fields(model)


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


class DjangoQLSchemaTest(TestCase):
    def all_models(self):
        models = []
        for app_label in apps.app_configs:
            models.extend(apps.get_app_config(app_label).get_models())
        return models

    def test_default(self):
        schema_dict = DjangoQLSchema(Book).as_dict()
        self.assertIsInstance(schema_dict, dict)
        self.assertEqual('core.book', schema_dict.get('current_model'))
        models = schema_dict.get('models')
        self.assertIsInstance(models, dict)
        all_model_labels = sorted([str(m._meta) for m in self.all_models()])
        session_model = all_model_labels.pop()
        self.assertEqual('sessions.session', session_model)
        self.assertListEqual(all_model_labels, sorted(models.keys()))

    def test_exclude(self):
        schema_dict = ExcludeUserSchema(Book).as_dict()
        self.assertEqual('core.book', schema_dict['current_model'])
        self.assertListEqual(sorted(schema_dict['models'].keys()), [
            'admin.logentry',
            'auth.group',
            'auth.permission',
            'contenttypes.contenttype',
            'core.book'
        ])

    def test_include(self):
        schema_dict = IncludeUserGroupSchema(User).as_dict()
        self.assertEqual('auth.user', schema_dict['current_model'])
        self.assertListEqual(sorted(schema_dict['models'].keys()), [
            'auth.group',
            'auth.user',
        ])

    def test_get_fields(self):
        default = DjangoQLSchema(Book).as_dict()['models']['core.book']
        custom = BookCustomFieldsSchema(Book).as_dict()['models']['core.book']
        self.assertListEqual(list(default.keys()), [
            'author',
            'content_type',
            'genre',
            'id',
            'is_published',
            'name',
            'object_id',
            'price',
            'rating',
            'similar_books',
            'written',
        ])
        self.assertListEqual(list(custom.keys()), ['name', 'is_published'])

    def test_circular_references(self):
        models = DjangoQLSchema(Book).as_dict()['models']
        # If Book references Author then Author shouldn't reference Book back
        book_author_field = models['core.book'].get('author')
        self.assertIsNotNone(book_author_field)
        self.assertEqual('relation', book_author_field['type'])
        self.assertEqual('auth.user', book_author_field['relation'])
        self.assertNotIn('book', models['auth.user'])

    def test_custom_search(self):
        custom = BookCustomSearchSchema(Book).as_dict()['models']['core.book']
        self.assertListEqual(list(custom.keys()), ['written_in_year'])

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
            'gav = 1',                      # unknown field
            'groups.gav > 1',               # unknown related field
            'groups = "lol"',               # can't compare model to a value
            'groups.name != 1',             # bad value type
            'is_staff = True and gav < 2',  # complex expression with valid part
            'date_joined < "1753-30-01"',   # bad timestamps
            'date_joined < "1753-01-01 12"',
            'date_joined < "1753-01-01 12AM"',
        ]
        for query in samples:
            ast = DjangoQLParser().parse(query)
            try:
                IncludeUserGroupSchema(User).validate(ast)
                self.fail('This query should\'t pass validation: %s' % query)
            except DjangoQLSchemaError as e:
                pass
