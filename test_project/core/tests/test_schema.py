from django.apps import apps
from django.contrib.auth.models import Group, User
from django.test import TestCase

from djangoql.exceptions import DjangoQLSchemaError
from djangoql.schema import DjangoQLSchema

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
            'id',
            'is_published',
            'name',
            'object_id',
            'price',
            'rating',
            'written',
        ])
        self.assertListEqual(list(custom.keys()), ['name', 'is_published'])

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
