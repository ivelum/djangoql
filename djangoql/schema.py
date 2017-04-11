import inspect
from collections import OrderedDict
from datetime import datetime

from django.db.models import AutoField, BooleanField, CharField, DateField, \
    DateTimeField, DecimalField, FloatField, IntegerField, ManyToOneRel, \
    ManyToManyRel, Model, NullBooleanField, TextField

from .ast import Comparison, Const, List, Logical, Name, Node
from .compat import text_type
from .exceptions import DjangoQLSchemaError


class DjangoQLField(object):
    """
    Represents searchable field.
    """
    def __init__(self, name, type, relation, related_model,
                 nullable, options, search=None):
        self.name = name
        self.type = type
        self.relation = relation
        self.related_model = related_model
        self.nullable = nullable
        self.options = options
        self.search = search

    def as_dict(self):
        return {
            'type': self.type,
            'relation': self.relation,
            'nullable': self.nullable,
            'options': self.options
        }

    def add_search_target(self, queryset):
        return queryset


class DjangoQLSchema(object):
    include = ()  # models to include into introspection
    exclude = ()  # models to exclude from introspection

    def __init__(self, model):
        if not inspect.isclass(model) or not issubclass(model, Model):
            raise DjangoQLSchemaError(
                'Schema must be initialized with a subclass of Django model'
            )
        if self.include and self.exclude:
            raise DjangoQLSchemaError(
                'Either include or exclude can be specified, but not both'
            )
        if self.excluded(model):
            raise DjangoQLSchemaError(
                "%s can't be used with %s because it's excluded from it" % (
                    model,
                    self.__class__,
                )
            )
        self.current_model = model
        self._models = None

    def excluded(self, model):
        return model in self.exclude or \
               (self.include and model not in self.include)

    @property
    def models(self):
        if not self._models:
            self._models = self.introspect(
                model=self.current_model,
                exclude=tuple(self.model_label(m) for m in self.exclude),
            )
        return self._models

    def model_label(self, model):
        return text_type(model._meta)

    def get_field_spec(self, model, field_name):
        field = model._meta.get_field(field_name)
        if field.is_relation:
            if not field.related_model:
                # GenericForeignKey
                return
            if self.excluded(field.related_model):
                return
            field_type = 'relation'
            relation = self.model_label(field.related_model)
        else:
            field_type = self.get_field_type(field)
            relation = None
        if field_type == 'str':
            options = self.get_options(model, field_name) or []
        else:
            options = []
        if isinstance(field, (ManyToOneRel, ManyToManyRel)):
            # Django 1.8 doesn't have .null attribute for these fields
            nullable = True
        else:
            nullable = field.null
        return DjangoQLField(
            name=field.name,
            type=field_type,
            relation=relation,
            related_model=relation and field.related_model,
            nullable=nullable,
            options=list(options),
        )

    def introspect(self, model, exclude=()):
        """
        Start with given model and recursively walk through its relationships.

        Returns a dict with all model labels and their fields found.
        """
        fields = OrderedDict()
        result = {self.model_label(model): fields}
        for field_name_or_spec in self.get_fields(model):
            if isinstance(field_name_or_spec, DjangoQLField):
                spec = field_name_or_spec
            else:
                spec = self.get_field_spec(model, field_name_or_spec)
            if not spec:
                continue
            fields[spec.name] = spec
            if spec.relation and spec.relation not in exclude:
                result.update(self.introspect(
                    model=spec.related_model,
                    exclude=tuple(exclude) + tuple(result.keys()),
                ))
        return result

    def get_fields(self, model):
        """
        By default, returns all field names of a given model. 
        
        Override this method to limit field options. You can either return a 
        plain list of field names from it, like ['id', 'name'], or call
        .super() and exclude unwanted fields from its result. 
        """
        return sorted(
            [f.name for f in model._meta.get_fields() if f.name != 'password']
        )

    def get_field_type(self, field):
        if isinstance(field, (AutoField, IntegerField)):
            return 'int'
        elif isinstance(field, (CharField, TextField)):
            return 'str'
        elif isinstance(field, (BooleanField, NullBooleanField)):
            return 'bool'
        elif isinstance(field, (DecimalField, FloatField)):
            return 'float'
        elif isinstance(field, DateTimeField):
            return 'datetime'
        elif isinstance(field, DateField):
            return 'date'
        return 'unknown'

    def get_options(self, model, field_name):
        """
        Override this method to provide suggestion options for model fields.
         
        It should return a list of string values. Quick example:
        
        if model == Group and field_name == 'name':
            return Group.objects.order_by('name').values_list('name', flat=True)
        
        """

    def as_dict(self):
        def explode(models):
            result = {}
            for key, inner_dict in models.items():
                result[key] = OrderedDict(
                    [(inner_key, inner_value.as_dict())
                     for inner_key, inner_value in inner_dict.items()])
            return result

        return {
            'current_model': self.model_label(self.current_model),
            'models': explode(self.models),
        }

    def path_to_field(self, path):
        model = self.model_label(self.current_model)
        field = None
        for name_part in path:
            field = self.models[model].get(name_part)
            if not field:
                raise DjangoQLSchemaError(
                    'Unknown field: %s. Possible choices are: %s' % (
                        name_part,
                        ', '.join(sorted(self.models[model].keys())),
                    )
                )
            if field.type == 'relation':
                model = field.relation
                field = None
        return field

    def validate(self, node):
        """
        Validate DjangoQL AST tree vs. current schema 
        """
        assert isinstance(node, Node)
        if isinstance(node.operator, Logical):
            self.validate(node.left)
            self.validate(node.right)
            return
        assert isinstance(node.left, Name)
        assert isinstance(node.operator, Comparison)
        assert isinstance(node.right, (Const, List))

        # resolve name
        field = self.path_to_field(node.left.parts)

        # Check that field and value types are compatible
        value = node.right.value
        if field is None:
            if value is not None:
                raise DjangoQLSchemaError(
                    'Related model %s can be compared to None only, but not to '
                    '%s' % (node.left.value, type(value).__name__)
                )
        else:
            if not field.nullable and value is None:
                raise DjangoQLSchemaError(
                    'Field %s is not nullable, '
                    'can\'t compare it to None' % node.left.value
                )
            possible_types = {
                'int': ['int'],
                'float': ['int', 'float', 'Decimal'],
                'str': [text_type.__name__],
                'bool': ['bool'],
                'date': [text_type.__name__],
                'datetime': [text_type.__name__],
            }[field.type]
            possible_values = {
                'int': 'integer numbers',
                'float': 'floating point numbers',
                'str': 'strings',
                'bool': 'True or False',
                'date': 'dates in "YYYY-MM-DD" format',
                'datetime': 'timestamps in "YYYY-MM-DD HH:MM" format',
            }[field.type]
            values = value if isinstance(node.right, List) else [value]
            for v in values:
                if v is not None and type(v).__name__ not in possible_types:
                    if field.nullable:
                        msg = (
                            'Field "{field}" has "nullable {field_type}" type. '
                            'It can be compared to {possible_values} or None, '
                            'but not to {value}'
                        )
                    else:
                        msg = (
                            'Field "{field}" has "{field_type}" type. It can '
                            'be compared to {possible_values}, '
                            'but not to {value}'
                        )
                    raise DjangoQLSchemaError(msg.format(
                        field=node.left.value,
                        field_type=field.type,
                        possible_values=possible_values,
                        value=repr(v),
                    ))
                # validate dates
                if field.type == 'date':
                    try:
                        datetime.strptime(v, '%Y-%m-%d')
                    except ValueError:
                        raise DjangoQLSchemaError(
                            'Field "%s" can be compared to dates in '
                            '"YYYY-MM-DD" format, but not to %s' % (
                                node.left.value,
                                repr(v),
                            )
                        )
                elif field.type == 'datetime':
                    mask = '%Y-%m-%d'
                    if len(v) > 10:
                        mask += ' %H:%M'
                    if len(v) > 16:
                        mask += ':%S'
                    try:
                        datetime.strptime(v, mask)
                    except ValueError:
                        raise DjangoQLSchemaError(
                            'Field "%s" can be compared to timestamps in '
                            '"YYYY-MM-DD HH:MM" format, but not to %s' % (
                                node.left.value,
                                repr(v),
                            )
                        )
