"""Showcase schema.

Every forward relation (ForeignKey and ManyToMany) on each model is exposed
*twice*:

* under its own name as an ordinary relation, traversed with dots
  (``author.name``, ``author.country.name``);
* under ``<name>__rel`` as an object-picker built on
  :class:`djangoql.extras.AutocompleteField` — suggestions are the real related
  rows rendered ``"<label> #<pk>"`` (the legacy ``"<label> [<pk>]"`` form is
  still accepted on input) and the query filters that relation by primary key.

The double-underscore name can't collide with the relation, so both idioms are
available in the same query, e.g.::

    author.country.name = "Poland" and author__rel = "Ursula Dick #42"

This is generic: any FK/M2M on any introspected model gets a picker, including
nested ones (``author.country__rel`` filters ``author__country`` by pk).
"""

from django.db.models import Q

from djangoql.extras import AutocompleteField, AutocompleteSchemaMixin
from djangoql.schema import DjangoQLSchema


REL_SUFFIX = '__rel'

# Related models here all expose a human-friendly ``name``; Country adds a code.
SEARCH_FIELDS_BY_MODEL = {
    'country': ['name', 'code'],
}
DEFAULT_SEARCH_FIELDS = ['name']


def _relation_names(model):
    """Forward FK + M2M field names on ``model`` (skips reverse/auto)."""
    return [
        f.name
        for f in model._meta.get_fields()
        if (f.many_to_one or f.many_to_many) and not f.auto_created
    ]


def _picker_queryset(related_model, search_fields):
    """A ``search -> queryset`` provider matching any of ``search_fields``."""

    def queryset(search):
        q = Q()
        for field in search_fields:
            q |= Q(**{f'{field}__icontains': search})
        return related_model.objects.filter(q).order_by(*search_fields)

    return queryset


class BookSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    def get_fields(self, model):
        fields = list(super().get_fields(model))
        fields += [name + REL_SUFFIX for name in _relation_names(model)]
        return fields

    def get_field_instance(self, model, field_name):
        if field_name.endswith(REL_SUFFIX):
            base = field_name[: -len(REL_SUFFIX)]
            if base in _relation_names(model):
                related = model._meta.get_field(base).related_model
                search_fields = SEARCH_FIELDS_BY_MODEL.get(
                    related._meta.model_name,
                    DEFAULT_SEARCH_FIELDS,
                )
                return AutocompleteField(
                    model=model,
                    name=field_name,
                    lookup_name=base,
                    queryset=_picker_queryset(related, search_fields),
                    search_fields=search_fields,
                    label=str,
                )
        return super().get_field_instance(model, field_name)
