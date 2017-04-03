from collections import OrderedDict

from django.db.models import AutoField, BooleanField, CharField, DateField, \
    DateTimeField, DecimalField, FloatField, IntegerField, Model, \
    NullBooleanField, TextField


class DjangoQLSchema(object):
    exclude = ()  # models to exclude from introspection

    def __init__(self, model):
        assert issubclass(model, Model), 'Subclass of Django Model is expected'
        self.current_model = model
        self._models = None

    @property
    def models(self):
        if not self._models:
            self._models = self.introspect(self.current_model, self.exclude)
        return self._models

    def introspect(self, model, exclude=()):
        """
        Start with given model and recursively walk through its relationships.
        
        Returns a dict with all model labels and their fields found.   
        """
        fields = OrderedDict()
        result = {str(model._meta): fields}
        for field_name in self.get_fields(model):
            field = model._meta.get_field(field_name)
            if field.is_relation:
                if not field.related_model:
                    # GenericForeignKey
                    continue
                if field.related_model in exclude:
                    continue
                result.update(self.introspect(
                    model=field.related_model,
                    exclude=tuple(exclude) + (model,)
                ))
                field_type = 'relation'
                relation = str(field.related_model._meta)
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
            'current_model': str(self.current_model._meta),
            'models': self.models,
        }
