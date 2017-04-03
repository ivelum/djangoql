import inspect
from collections import OrderedDict

from django.db.models import AutoField, BooleanField, CharField, DateField, \
    DateTimeField, DecimalField, FloatField, IntegerField, Model, \
    NullBooleanField, TextField

from .exceptions import DjangoQLSchemaError


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
        return str(model._meta)

    def introspect(self, model, exclude=()):
        """
        Start with given model and recursively walk through its relationships.
        
        Returns a dict with all model labels and their fields found.   
        """
        fields = OrderedDict()
        result = {self.model_label(model): fields}
        for field_name in self.get_fields(model):
            field = model._meta.get_field(field_name)
            if field.is_relation:
                if not field.related_model:
                    # GenericForeignKey
                    continue
                if self.excluded(field.related_model):
                    continue
                field_type = 'relation'
                relation = self.model_label(field.related_model)
                if relation not in exclude:
                    result.update(self.introspect(
                        model=field.related_model,
                        exclude=tuple(exclude) + tuple(result.keys()),
                    ))
            else:
                field_type = self.get_field_type(field)
                relation = None
            fields[field.name] = {
                'type': field_type,
                'relation': relation,
            }
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

    def as_dict(self):
        return {
            'current_model': self.model_label(self.current_model),
            'models': self.models,
        }
