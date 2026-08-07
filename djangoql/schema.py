import difflib
import inspect
import warnings
from collections import OrderedDict, deque
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import ManyToManyRel, ManyToOneRel
from django.db.models.fields.related import ForeignObjectRel
from django.utils.timezone import get_current_timezone
from django.utils.translation import gettext_lazy as _

from .ast import Comparison, Const, List, Logical, Name, Node
from .exceptions import DjangoQLSchemaError


class DjangoQLField:
    """
    Abstract searchable field
    """

    model = None
    name = None
    nullable = False
    suggest_options = False
    suggested = True
    type = 'unknown'
    value_types = []
    value_types_description = ''

    def __init__(
        self,
        model=None,
        name=None,
        nullable=None,
        suggest_options=None,
        suggested=None,
    ):
        if model is not None:
            self.model = model
        if name is not None:
            self.name = name
        if nullable is not None:
            self.nullable = nullable
        if suggest_options is not None:
            self.suggest_options = suggest_options
        if suggested is not None:
            self.suggested = suggested

    def _field_choices(self):
        if self.model:
            try:
                return self.model._meta.get_field(self.name).choices
            except (AttributeError, FieldDoesNotExist):
                pass
        return []

    @property
    def async_options(self):
        return not self._field_choices()

    def get_options(self, search):
        """
        Override this method to provide custom suggestion options
        """
        result = []
        choices = self._field_choices()
        if choices:
            search = search.lower()
            for c in choices:
                choice = str(c[1])
                if search in choice.lower():
                    result.append(choice)
        return result

    def get_lookup_name(self):
        """
        Override this method to provide custom lookup name
        """
        return self.name

    def get_lookup_value(self, value):
        """
        Override this method to convert displayed values to lookup values
        """
        choices = self._field_choices()
        if choices:
            if isinstance(value, list):
                return [c[0] for c in choices if c[0] in value or c[1] in value]
            else:
                for c in choices:
                    if value in c:
                        return c[0]
        return value

    def get_operator(self, operator):
        """
        Get a comparison suffix to be used in Django ORM & inversion flag for it

        :param operator: string, DjangoQL comparison operator
        :return: (suffix, invert) - a tuple with 2 values:
            suffix - suffix to be used in ORM query, for example '__gt' for '>'
            invert - boolean, True if this comparison needs to be inverted
        """
        op = {
            '=': '',
            '>': '__gt',
            '>=': '__gte',
            '<': '__lt',
            '<=': '__lte',
            '~': '__icontains',
            'in': '__in',
            'startswith': '__istartswith',
            'endswith': '__iendswith',
        }.get(operator)
        if op is not None:
            return op, False
        op = {
            '!=': '',
            '!~': '__icontains',
            'not in': '__in',
            'not startswith': '__istartswith',
            'not endswith': '__iendswith',
        }[operator]
        return op, True

    def get_lookup(self, path, operator, value):
        """
        Performs a lookup for this field with given path, operator and value.

        Override this if you'd like to implement a fully custom lookup. It
        should support all comparison operators compatible with the field type.

        :param path: a list of names preceding current lookup. For example,
            if expression looks like 'author.groups.name = "Foo"' path would
            be ['author', 'groups']. 'name' is not included, because it's the
            current field instance itself.
        :param operator: a string with comparison operator. It could be one of
            the following: '=', '!=', '>', '>=', '<', '<=', '~', '!~', 'in',
            'not in'. Depending on the field type, some operators may be
            excluded. '~' and '!~' can be applied to StrField only and aren't
            allowed for any other fields. BoolField can't be used with less or
            greater operators, '>', '>=', '<' and '<=' are excluded for it.
        :param value: value passed for comparison
        :return: Q-object
        """
        search = '__'.join(path + [self.get_lookup_name()])
        op, invert = self.get_operator(operator)
        q = models.Q(**{f'{search}{op}': self.get_lookup_value(value)})
        return ~q if invert else q

    def get_annotations(self, path):
        """
        Return a dict of {alias: expression} to be applied to the queryset via
        .annotate() before filtering. Default: no annotations.

        Only called for fields actually referenced in a query, so aggregate
        fields produce SQL lazily. `path` is the list of names preceding this
        field (relation hops), e.g. ['author'] for 'author.book__count'.
        """
        return {}

    def validate(self, value):
        if not self.nullable and value is None:
            raise DjangoQLSchemaError(
                _("Field %s is not nullable, can't compare it to None")
                % self.name,
            )
        if value is not None and type(value) not in self.value_types:
            if self.nullable:
                msg = _(
                    'Field "{field}" has "nullable {field_type}" type. '
                    'It can be compared to {possible_values} or None, '
                    'but not to {value}',
                )
            else:
                msg = _(
                    'Field "{field}" has "{field_type}" type. It can '
                    'be compared to {possible_values}, '
                    'but not to {value}',
                )
            raise DjangoQLSchemaError(
                msg.format(
                    field=self.name,
                    field_type=self.type,
                    possible_values=self.value_types_description,
                    value=repr(value),
                ),
                # Carry the offending value so callers can locate it in the
                # query (e.g. to highlight it).
                value=value,
            )


class IntField(DjangoQLField):
    type = 'int'
    value_types = [int]
    value_types_description = _('integer numbers')

    def validate(self, value):
        """
        Support enum-like choices defined on an integer field
        """
        return super().validate(self.get_lookup_value(value))


class FloatField(DjangoQLField):
    type = 'float'
    value_types = [int, float, Decimal]
    value_types_description = _('floating point numbers')


class StrField(DjangoQLField):
    type = 'str'
    value_types = [str]
    value_types_description = _('strings')

    def get_options(self, search):
        choice_options = super().get_options(search)
        if choice_options:
            return choice_options
        lookup = {}
        if search:
            lookup['%s__icontains' % self.name] = search
        return (
            self.model.objects.filter(**lookup)
            .order_by(self.name)
            .values_list(self.name, flat=True)
            .distinct()
        )


class BoolField(DjangoQLField):
    type = 'bool'
    value_types = [bool]
    value_types_description = _('True or False')


class DateField(DjangoQLField):
    type = 'date'
    value_types = [str]
    value_types_description = _('dates in "YYYY-MM-DD" format')

    def validate(self, value):
        super().validate(value)
        try:
            self.get_lookup_value(value)
        except ValueError:
            raise DjangoQLSchemaError(
                _(
                    'Field "{field}" can be compared to dates in '
                    '"YYYY-MM-DD" format, but not to {value}',
                ).format(field=self.name, value=repr(value)),
            )

    def get_lookup_value(self, value):
        return (
            [self.parse_date(v) for v in value]
            if isinstance(value, list)
            else self.parse_date(value)
        )

    @staticmethod
    def parse_date(value):
        if not value:
            return None
        return datetime.strptime(value, '%Y-%m-%d').date()


class DateTimeField(DjangoQLField):
    type = 'datetime'
    value_types = [str]
    value_types_description = _('timestamps in "YYYY-MM-DD HH:MM" format')

    def validate(self, value):
        super().validate(value)
        try:
            self.get_lookup_value(value)
        except ValueError:
            raise DjangoQLSchemaError(
                _(
                    'Field "{field}" can be compared to timestamps in '
                    '"YYYY-MM-DD HH:MM" format, but not to {value}',
                ).format(field=self.name, value=repr(value)),
            )

    def get_lookup_value(self, value):
        return (
            [self.parse_datetime(v) for v in value]
            if isinstance(value, list)
            else self.parse_datetime(value)
        )

    @staticmethod
    def parse_datetime(value):
        if not value:
            return None
        mask = '%Y-%m-%d'
        if len(value) > 10:
            mask += ' %H:%M'
        if len(value) > 16:
            mask += ':%S'
        dt = datetime.strptime(value, mask)
        if settings.USE_TZ:
            dt = dt.replace(tzinfo=get_current_timezone())
        return dt

    def get_lookup(self, path, operator, value):
        search = '__'.join(path + [self.get_lookup_name()])
        op, invert = self.get_operator(operator)

        # Add LIKE operator support for datetime fields. For LIKE comparisons
        # we don't want to convert source value to datetime instance, because
        # it would effectively kill the idea. What we want is expressions like
        #       'created ~ "2017-01-30'
        # to be translated to
        #       'created LIKE %2017-01-30%',
        # but it would work only if we pass a string as a parameter. If we pass
        # a datetime instance, it would add time part in a form of 00:00:00,
        # and resulting comparison would look like
        #       'created LIKE %2017-01-30 00:00:00%'
        # which is not what we want for this case.
        val = value if operator in ('~', '!~') else self.get_lookup_value(value)

        q = models.Q(**{f'{search}{op}': val})
        return ~q if invert else q


class RelationField(DjangoQLField):
    type = 'relation'

    def __init__(
        self, model, name, related_model, nullable=False, suggest_options=False
    ):
        super().__init__(
            model=model,
            name=name,
            nullable=nullable,
            suggest_options=suggest_options,
        )
        self.related_model = related_model

    @property
    def relation(self):
        return DjangoQLSchema.model_label(self.related_model)


class DjangoQLSchema:
    include = ()  # models to include into introspection
    exclude = ()  # models to exclude from introspection
    include_fields = {}  # {model: [field names]} - expose ONLY these fields
    exclude_fields = {}  # {model: [field names]} - expose all EXCEPT these
    suggest_options = None

    def __init__(self, model):
        if not inspect.isclass(model) or not issubclass(model, models.Model):
            raise DjangoQLSchemaError(
                _('Schema must be initialized with a subclass of Django model'),
            )
        if self.include and self.exclude:
            raise DjangoQLSchemaError(
                _('Either include or exclude can be specified, but not both'),
            )
        overlap = set(self.include_fields) & set(self.exclude_fields)
        if overlap:
            raise DjangoQLSchemaError(
                _(
                    'Either include_fields or exclude_fields can be specified '
                    'for {models}, but not both',
                ).format(models=', '.join(str(m) for m in overlap)),
            )
        for rules in (self.include_fields, self.exclude_fields):
            for field_model, field_names in rules.items():
                valid = {f.name for f in field_model._meta.get_fields()}
                unknown = [n for n in field_names if n not in valid]
                if unknown:
                    raise DjangoQLSchemaError(
                        _(
                            'Unknown field(s) {fields} specified for {model}',
                        ).format(
                            fields=', '.join(unknown),
                            model=field_model,
                        ),
                    )
        if self.excluded(model):
            raise DjangoQLSchemaError(
                _(
                    "{model} can't be used with {schema_class} because "
                    "it's excluded from it",
                ).format(model=model, schema_class=self.__class__),
            )
        self.current_model = model
        self._models = None
        if self.suggest_options is None:
            self.suggest_options = {}

    def excluded(self, model):
        return model in self.exclude or (
            self.include and model not in self.include
        )

    @property
    def models(self):
        if not self._models:
            self._models = self.introspect(
                model=self.current_model,
                exclude=tuple(self.model_label(m) for m in self.exclude),
            )
        return self._models

    @classmethod
    def model_label(self, model):
        return str(model._meta)

    def introspect(self, model, exclude=()):
        """
        Start with given model and recursively walk through its relationships.

        Returns a dict with all model labels and their fields found.
        """
        result = {}
        open_set = deque([model])
        closed_set = set(exclude)

        while open_set:
            model = open_set.popleft()
            model_label = self.model_label(model)

            if model_label in closed_set:
                continue

            model_fields = OrderedDict()
            for field in self.get_fields(model):
                if not isinstance(field, DjangoQLField):
                    field = self.get_field_instance(model, field)
                if not field:
                    continue
                if isinstance(field, RelationField):
                    open_set.append(field.related_model)
                model_fields[field.name] = field

            result[model_label] = model_fields
            closed_set.add(model_label)

        return result

    def get_fields(self, model):
        """
        By default, returns all field names of a given model.

        Override this method to limit field options. You can either return a
        plain list of field names from it, like ['id', 'name'], or call
        .super() and exclude unwanted fields from its result.

        For a declarative alternative to overriding this method, set
        ``include_fields`` / ``exclude_fields`` on the schema class.
        """
        names = [
            f.name for f in model._meta.get_fields() if f.name != 'password'
        ]
        return sorted(self.apply_field_rules(model, names))

    def apply_field_rules(self, model, names):
        """
        Trim ``names`` according to ``include_fields`` / ``exclude_fields``.

        If ``model`` is a key in ``include_fields``, only the listed names are
        kept (allowlist). Otherwise, if it is a key in ``exclude_fields``, the
        listed names are dropped (denylist). A model in neither dict is
        returned unchanged.
        """
        only = self.include_fields.get(model)
        if only is not None:
            return [n for n in names if n in only]
        excluded = self.exclude_fields.get(model)
        if excluded is not None:
            return [n for n in names if n not in excluded]
        return names

    def get_field_instance(self, model, field_name):
        field = model._meta.get_field(field_name)
        field_kwargs = {'model': model, 'name': field.name}
        if field.is_relation:
            if not field.related_model:
                # GenericForeignKey
                return
            if self.excluded(field.related_model):
                return
            field_cls = RelationField
            field_kwargs['related_model'] = field.related_model
        else:
            field_cls = self.get_field_cls(field)
        if isinstance(field, (ManyToOneRel, ManyToManyRel, ForeignObjectRel)):
            # Django 1.8 doesn't have .null attribute for these fields
            field_kwargs['nullable'] = True
        else:
            field_kwargs['nullable'] = field.null
        field_kwargs['suggest_options'] = (
            field.name in self.suggest_options.get(model, [])
        )
        return field_cls(**field_kwargs)

    def get_field_cls(self, field):
        str_fields = (
            models.CharField,
            models.TextField,
            models.UUIDField,
            models.BinaryField,
            models.GenericIPAddressField,
        )
        if isinstance(field, str_fields):
            return StrField
        elif isinstance(field, (models.AutoField, models.IntegerField)):
            return IntField
        elif isinstance(field, (models.BooleanField, models.NullBooleanField)):
            return BoolField
        elif isinstance(field, (models.DecimalField, models.FloatField)):
            return FloatField
        elif isinstance(field, models.DateTimeField):
            return DateTimeField
        elif isinstance(field, models.DateField):
            return DateField
        return DjangoQLField

    def as_dict(self):
        from .serializers import DjangoQLSchemaSerializer

        warnings.warn(
            'DjangoQLSchema.as_dict() is deprecated and will be removed in '
            'future releases. Please use DjangoQLSchemaSerializer instead.',
        )
        return DjangoQLSchemaSerializer().serialize(self)

    def resolve_name(self, name):
        assert isinstance(name, Name)
        model = self.model_label(self.current_model)
        model_cls = self.current_model
        field = None
        prev_relation = None
        for name_part in name.parts:
            field = self.models[model].get(name_part)
            if field is None:
                # Give schemas a chance to materialize a virtual field that is
                # not stored in self.models (e.g. relation-bound aggregates
                # addressed via dot syntax). Default implementation returns
                # None, which falls through to the "Unknown field" error.
                field = self.resolve_unknown(
                    model_cls, prev_relation, name_part
                )
            if field is None:
                raise DjangoQLSchemaError(
                    self._unknown_field_message(model, model_cls, name_part),
                    # Carry the offending name so callers can locate it in the
                    # query (schema errors don't carry a line/column).
                    value=name_part,
                )
            if field.type == 'relation':
                prev_relation = field
                model = field.relation
                model_cls = field.related_model
                field = None
            else:
                prev_relation = None
        return field

    def resolve_unknown(self, model_cls, prev_relation, name_part):
        """
        Hook for resolving a name part that is not present in self.models.

        Override to synthesize virtual fields on demand. ``model_cls`` is the
        model the part was looked up on, ``prev_relation`` is the RelationField
        just traversed to reach it (or None at the top level). Return a
        DjangoQLField instance, or None to signal "unknown field".
        """
        return None

    def unknown_field_hint(self, model_cls):
        """
        Hook returning an extra sentence appended to the "Unknown field" error,
        e.g. to point users at hidden derived fields. Default: no hint.
        """
        return ''

    #: Minimum difflib similarity ratio for a field name to be offered as a
    #: "Did you mean ...?" suggestion at all.
    suggest_cutoff = 0.6
    #: Once there is a best match, drop any candidate whose ratio is more than
    #: this far below it. Prevents a clear winner (``autorzy__count``) from
    #: being diluted by noise that merely shares a ``__suffix``
    #: (``utworzono__month``).
    suggest_margin = 0.1
    #: Maximum number of suggestions to offer.
    suggest_limit = 3

    def suggest_field_names(self, name_part, candidates):
        """
        Return the field names from ``candidates`` that look like a typo of
        ``name_part``, best match first. Used to turn the "Unknown field" error
        into a "Did you mean ...?" hint.

        Matching is case-insensitive and uses difflib's similarity ratio.
        Candidates below ``suggest_cutoff`` are ignored (so genuine gibberish
        yields no suggestions); among the rest, only those within
        ``suggest_margin`` of the best match are kept, so a dominant match is
        not diluted by weaker ones that only share a ``__suffix``. Override this
        method (or the ``suggest_*`` attributes) to tune the behavior.
        """
        name = name_part.lower()
        scored = sorted(
            (
                (difflib.SequenceMatcher(None, name, c.lower()).ratio(), c)
                for c in candidates
            ),
            key=lambda rc: rc[0],
            reverse=True,
        )
        if not scored or scored[0][0] < self.suggest_cutoff:
            return []
        best = scored[0][0]
        return [
            c
            for ratio, c in scored
            if ratio >= self.suggest_cutoff
            and best - ratio <= self.suggest_margin
        ][: self.suggest_limit]

    def _unknown_field_message(self, model, model_cls, name_part):
        # If the name looks like a typo of a real field, point at the likely
        # match instead of dumping the whole list. The candidate pool is every
        # field name (including hidden derived fields), so e.g. "book__coun"
        # can suggest the hidden "book__count".
        suggestions = self.suggest_field_names(
            name_part,
            self.models[model].keys(),
        )
        if suggestions:
            message = _(
                'Unknown field: {field}. Did you mean: {suggestions}?'
            ).format(field=name_part, suggestions=', '.join(suggestions))
        else:
            # No close match: fall back to listing the fields actually offered
            # in autocomplete; hidden derived fields (suggested=False) and
            # synthesized aggregates are surfaced via unknown_field_hint()
            # instead of bloating this list.
            choices = ', '.join(
                sorted(n for n, f in self.models[model].items() if f.suggested),
            )
            message = _(
                'Unknown field: {field}. Possible choices are: {choices}'
            ).format(field=name_part, choices=choices)
        hint = self.unknown_field_hint(model_cls)
        if hint:
            # Period separates the message from the hint sentence so they don't
            # run together ("...username. Relation aggregates...").
            message = f'{message}. {hint}'
        return message

    def collect_annotations(self, node):
        """
        Walk a validated AST and merge get_annotations() from every field that
        is actually referenced. Returns {alias: expression}.

        Must be called after validate(ast): it assumes leaf nodes have a Name
        on the left (as guaranteed by validation) and does not re-check.
        """
        annotations = {}
        if isinstance(node.operator, Logical):
            annotations.update(self.collect_annotations(node.left))
            annotations.update(self.collect_annotations(node.right))
            return annotations
        field = self.resolve_name(node.left)
        if field is not None:
            annotations.update(field.get_annotations(node.left.parts[:-1]))
        return annotations

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

        # Check that field and value types are compatible
        field = self.resolve_name(node.left)
        value = node.right.value
        if field is None:
            if value is not None:
                raise DjangoQLSchemaError(
                    _(
                        'Related model {model} can be compared to None only, '
                        'but not to {value_type}'
                    ).format(
                        model=node.left.value,
                        value_type=type(value).__name__,
                    ),
                )
        else:
            values = value if isinstance(node.right, List) else [value]
            for v in values:
                field.validate(v)
