from collections import OrderedDict

from .schema import RelationField


class DjangoQLSchemaSerializer:
    def serialize(self, schema):
        models = {}
        for model_label, fields in schema.models.items():
            models[model_label] = OrderedDict(
                [
                    (name, self.serialize_field(f))
                    for name, f in fields.items()
                    if f.suggested
                ],
            )
        return {
            'current_model': schema.model_label(schema.current_model),
            'models': models,
        }

    def serialize_field(self, field):
        result = {
            'type': field.type,
            'nullable': field.nullable,
            'options': self.serialize_field_options(field),
        }
        if isinstance(field, RelationField):
            result['relation'] = field.relation
        if getattr(field, 'object_reference', False):
            # Object-picker fields accept only = / != / in / not in.
            result['object_reference'] = True
        return result

    def serialize_field_options(self, field):
        return list(field.get_options('')) if field.suggest_options else None


class SuggestionsAPISerializer(DjangoQLSchemaSerializer):
    def __init__(self, suggestions_api_url):
        self.suggestions_api_url = suggestions_api_url

    def serialize(self, schema):
        result = super().serialize(schema)
        result['suggestions_api_url'] = self.suggestions_api_url
        return result

    def serialize_field_options(self, field):
        if field.async_options:
            return field.suggest_options
        else:
            return field.get_options('')
