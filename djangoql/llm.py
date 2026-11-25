"""Describe a DjangoQL schema for a Large Language Model.

:func:`describe_schema_for_llm` turns any
:class:`~djangoql.schema.DjangoQLSchema`
into a compact, self-contained, machine-readable description of the entire
search space -- every model, every field, its type, whether it is nullable,
what it relates to (the "dependent" fields), and which operators are legal for
that field type -- plus a grammar cheat-sheet and a few worked examples.

Two output formats share one intermediate representation: ``'json'`` (the
default) renders a normalized, JSON-serializable dict, and ``'compact'``
renders the same information as a terse text block. In both, operators are
never repeated per field -- they are resolved once, by field type, through a
shared ``operators_by_type`` legend (with a graceful fallback entry for any
custom/unknown field type).

Drop the description straight into an LLM system prompt and the model has
everything it needs to generate valid DjangoQL: the field graph tells it
*what* it can query, the operator legend tells it *how*, and the grammar
notes cover the few non-obvious rules (relations traversed with a dot, no
standalone ``not``).

The introspection itself is reused from the schema (the same BFS over related
models that powers autocomplete); this module only layers the operator matrix,
examples and grammar notes on top.
"""

import logging

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist

from .extras import (
    AggregateField,
    CountField,
    DateExtractField,
    DatePartField,
    TimeExtractField,
)
from .schema import RelationField


logger = logging.getLogger(__name__)


#: Operators that make sense per field ``type``. Derived from
#: :meth:`DjangoQLField.get_operator` combined with the per-type notes in its
#: docstring: ``~`` / ``!~`` (LIKE) apply to strings (and datetimes, which have
#: an explicit LIKE override); BoolField is limited to equality. Negation is not
#: a standalone operator in DjangoQL -- it is baked into ``!=``, ``!~`` and the
#: ``not in`` / ``not startswith`` / ``not endswith`` forms.
OPERATORS_BY_TYPE = {
    'int': ['=', '!=', '>', '>=', '<', '<=', 'in', 'not in'],
    'float': ['=', '!=', '>', '>=', '<', '<=', 'in', 'not in'],
    'date': ['=', '!=', '>', '>=', '<', '<=', 'in', 'not in'],
    'datetime': ['=', '!=', '>', '>=', '<', '<=', '~', '!~', 'in', 'not in'],
    'str': [
        '=',
        '!=',
        '~',
        '!~',
        'startswith',
        'endswith',
        'not startswith',
        'not endswith',
        'in',
        'not in',
    ],
    'bool': ['=', '!='],
}

#: One illustrative right-hand-side value per scalar type, used to render a
#: ready-to-copy example expression for each field.
_EXAMPLE_VALUE_BY_TYPE = {
    'int': '42',
    'float': '4.5',
    'date': '"2021-06-01"',
    'datetime': '"2021-06-01 14:30"',
    'str': '"text"',
    'bool': 'True',
}

#: How many concrete suggestion values (choices / autocomplete options) to embed
#: per field. Enough to teach the LLM the shape of the values without bloating
#: the prompt.
MAX_SUGGESTED_VALUES = 20

#: Cap on emitted choice labels. Larger than MAX_SUGGESTED_VALUES because
#: choices are a closed set -- the LLM should see the whole domain, not a
#: sample -- and they are read from the field definition without a query.
MAX_CHOICE_VALUES = 100

#: Target app-labels whose rows must never be auto-dumped into a prompt.
#: An explicit fk_options entry overrides this exclusion.
SENSITIVE_TARGET_APP_LABELS = frozenset(
    {'auth', 'admin', 'contenttypes', 'sessions'},
)

#: Sentinel: a relation with no fk_options entry falls back to auto mode.
_AUTO = object()


def _is_sensitive_target(model):
    """A relation target whose values must never be auto-emitted.

    True for Django's built-in sensitive apps (see
    ``SENSITIVE_TARGET_APP_LABELS``), plus the project's ``AUTH_USER_MODEL``
    -- which may live in any app, including one not otherwise flagged as
    sensitive (e.g. a custom ``myapp.User``). Only guards the *auto* branch of
    :func:`_relation_plan`; an explicit ``fk_options`` entry still overrides.
    """
    if model._meta.app_label in SENSITIVE_TARGET_APP_LABELS:
        return True
    try:
        return model is get_user_model()
    except Exception:
        # get_user_model() raises ImproperlyConfigured if AUTH_USER_MODEL
        # is malformed/missing; schema description must never break on that.
        return False


def _no_value_targets(schema):
    """Resolve ``schema.no_value_targets`` to a set of model classes.

    ``no_value_targets`` is an optional schema attribute: an iterable of model
    classes and/or ``"app_label.Model"`` dotted labels whose row values must
    **never** be emitted -- a hard denylist that overrides both ``fk_options``
    and ``max_fk_options`` (see :func:`_relation_plan`). Use it to keep
    institution-specific data (unit / institution names, etc.) out of a
    committed or shared schema description, independent of row counts.

    Unknown labels are logged and skipped (schema description must never break
    on a typo). The resolved set is memoised on the schema instance.
    """
    cached = getattr(schema, '_no_value_targets_cache', None)
    if cached is not None:
        return cached
    resolved = set()
    for entry in getattr(schema, 'no_value_targets', None) or ():
        if isinstance(entry, str):
            try:
                resolved.add(apps.get_model(entry))
            except (LookupError, ValueError):
                logger.warning(
                    'describe_schema_for_llm: no_value_targets -- nieznany '
                    'model %r, pomijam',
                    entry,
                )
        else:
            resolved.add(entry)
    try:
        schema._no_value_targets_cache = resolved
    except Exception:
        # A schema forbidding attribute assignment (e.g. __slots__) simply
        # re-resolves per call -- correctness over the memo optimisation.
        pass
    return resolved


#: Canonical ordering for date/time lookup parts, so the legend note is stable.
_CANONICAL_DATE_PARTS = [
    'year',
    'month',
    'day',
    'week_day',
    'quarter',
    'week',
    'iso_year',
    'iso_week_day',
]
_CANONICAL_TIME_PARTS = ['hour', 'minute', 'second']
_TIME_PART_NAMES = frozenset(_CANONICAL_TIME_PARTS)

#: Virtual field classes generated by the date-parts / aggregate schema mixins.
#: They are collapsed into a single type-level lookups/aggregates note instead
#: of being listed as individual fields.
_DERIVED_FIELD_CLASSES = (
    DatePartField,
    DateExtractField,
    TimeExtractField,
    AggregateField,
)


#: Generic, always-valid example queries. Schema-agnostic: they teach shape
#: (and/or, grouping, lists, None), not specific fields.
_EXAMPLES = [
    'id = 1',
    'id > 10 and id < 100',
    'id in (1, 2, 3)',
    'id = 1 or id = 2',
    '(id > 1 and id < 5) or id = 10',
]

#: Grammar cheat-sheet, emitted once. The `operators` note tells the LLM to
#: resolve a field's operators via operators_by_type rather than expecting them
#: inline on every field.
_GRAMMAR = {
    'shape': (
        '<field> <operator> <value>, combined with `and` / `or` '
        'and grouped with parentheses'
    ),
    'operators': (
        'each field lists its type; look up the allowed operators in '
        'operators_by_type by that type. A field with `relates_to` uses the '
        '`relation` entry; a field with `object_reference` true uses the '
        '`object_reference` entry. A `?` suffix on the type means the field '
        'is nullable (comparable to None).'
    ),
    'relations': (
        'cross model boundaries with a dot: author.country.name = "Poland"'
    ),
    'lists': 'membership uses a parenthesized list: x in ("a", "b")',
    'null': 'a nullable field (type ends with ?) or a relation can equal None',
    'strings': 'string values are double-quoted; ~ means contains',
    'negation': (
        'there is NO standalone `not` operator. Negate with the operator '
        'itself: != , !~ , not in , not startswith , not endswith. Example: '
        'publisher != None (NOT: not publisher = None)'
    ),
}


def _operator_legend():
    """Per-type operators + one example, emitted once so field entries need
    not repeat them. Includes the pseudo-types ``relation`` and
    ``object_reference``."""
    legend = {}
    for ftype, ops in OPERATORS_BY_TYPE.items():
        op = '~' if ftype == 'str' else '='
        legend[ftype] = {
            'operators': list(ops),
            'example': f'x {op} {_EXAMPLE_VALUE_BY_TYPE[ftype]}',
        }
    legend['relation'] = {
        'operators': [
            '= None',
            '!= None',
            '<relation>.<field> (traverse with a dot)',
        ],
    }
    legend['object_reference'] = {'operators': ['=', '!=', 'in', 'not in']}
    return legend


def _choice_labels(field):
    """Closed-set choice labels for a field, or None.

    DjangoQL matches choice fields by their human label and translates it back
    to the stored value (``schema.py`` get_lookup_value), so the labels are the
    exact tokens an LLM should put in a query. Choices live on the model field
    and are read without a database query.
    """
    model = getattr(field, 'model', None)
    name = getattr(field, 'name', None)
    if not model or not name:
        return None
    try:
        choices = model._meta.get_field(name).choices
    except (FieldDoesNotExist, AttributeError):
        return None
    if not choices:
        return None
    labels = [str(c[1]) for c in choices]
    return labels[:MAX_CHOICE_VALUES] or None


def _field_metadata(field):
    """`label` (verbose_name) and `help_text` from the underlying model field.

    Skips the auto-generated verbose_name (the field name with underscores
    turned into spaces) so we only emit labels that add information. Returns an
    empty dict for custom fields with no backing model field, and for reverse
    relations whose ``_meta`` entry has no ``verbose_name``.
    """
    model = getattr(field, 'model', None)
    name = getattr(field, 'name', None)
    if not model or not name:
        return {}
    try:
        model_field = model._meta.get_field(name)
    except (FieldDoesNotExist, AttributeError):
        return {}
    meta = {}
    verbose = getattr(model_field, 'verbose_name', None)
    if verbose is not None:
        verbose = str(verbose).strip()
        default = name.replace('_', ' ').strip()
        if verbose and verbose.lower() != default.lower():
            meta['label'] = verbose
    help_text = getattr(model_field, 'help_text', None)
    if help_text and str(help_text).strip():
        meta['help_text'] = str(help_text).strip()
    return meta


#: Preferred names for a relation's identifying field (EN + PL), in priority
#: order. Checked before falling back to "first suggested str field", so
#: auto-mode emits a readable dictionary identifier (nazwa/skrot/username)
#: instead of whatever happens to sort first alphabetically (email, an
#: internal enum column).
_PREFERRED_MATCH_FIELDS = (
    'name',
    'nazwa',
    'title',
    'tytul',
    'label',
    'skrot',
    'symbol',
    'kod',
    'code',
    'slug',
    'username',
    'login',
)


def _default_match_field(schema, related_label):
    """Pick an identifying field among the related model's schema-visible
    fields.

    Restricting to schema fields inherits DjangoQL's own exclusions (e.g. the
    password field is never exposed), so we never surface a sensitive column.
    Also skips fields with ``suggested`` set to False, since those are hidden
    from the emitted schema description too. Prefers, in priority order, a
    field whose name appears in :data:`_PREFERRED_MATCH_FIELDS` (e.g.
    ``name``, ``nazwa``, ``username``); else the first (suggested) string
    field. Returns None when the related model exposes no (suggested) string
    field.
    """
    fields = schema.models.get(related_label, {})

    def _ok(f):
        return (
            f is not None
            and getattr(f, 'suggested', True)
            and getattr(f, 'type', None) == 'str'
        )

    for pref in _PREFERRED_MATCH_FIELDS:
        if _ok(fields.get(pref)):
            return pref
    for fname, f in fields.items():
        if _ok(f):
            return fname
    return None


def _distinct_values(related_model, field_name, limit):
    """Distinct string values of ``field_name``; None when over the limit.

    ``limit=None`` forces emission (no cardinality gate), capped at
    MAX_SUGGESTED_VALUES. Any DB/field error yields None so schema description
    never breaks -- the error is logged (warning, with traceback) so a dead
    DB or a bad field name doesn't silently vanish into a schema with no
    ``related_values``.
    """
    try:
        qs = (
            related_model.objects.order_by(field_name)
            .values_list(field_name, flat=True)
            .distinct()
        )
        if limit is None:
            rows = list(qs[:MAX_SUGGESTED_VALUES])
        else:
            rows = list(qs[: limit + 1])
            if len(rows) > limit:
                return None
        return [str(v) for v in rows if v is not None] or None
    except Exception:
        logger.warning(
            'describe_schema_for_llm: nie udało się pobrać wartości '
            '%s.%s -- pomijam (schemat bez related_values dla tej relacji)',
            related_model._meta.label,
            field_name,
            exc_info=True,
        )
        return None


def _fk_spec(schema, field, name):
    """Resolve the fk_options entry for ``name`` on ``field.model``.

    Returns the sentinel ``_AUTO`` when there is no entry (auto mode).
    """
    fk_options = getattr(schema, 'fk_options', None) or {}
    return fk_options.get(field.model, {}).get(name, _AUTO)


def _str_examples(related_model, limit):
    """Up to ``limit`` ``str(obj)`` rows of the related model, or None.

    ``limit=None`` forces emission capped at MAX_SUGGESTED_VALUES. Gated by
    row count (str() cannot be made distinct in SQL). Any error yields None
    -- logged (warning, with traceback) so a dead DB doesn't silently vanish
    into a schema with no ``related_examples``.
    """
    try:
        if limit is None:
            rows = related_model.objects.all()[:MAX_SUGGESTED_VALUES]
        else:
            if related_model.objects.count() > limit:
                return None
            rows = related_model.objects.all()[:limit]
        return [str(o) for o in rows] or None
    except Exception:
        logger.warning(
            'describe_schema_for_llm: nie udało się pobrać przykładów '
            '%s -- pomijam (schemat bez related_examples dla tej relacji)',
            related_model._meta.label,
            exc_info=True,
        )
        return None


#: Dictionary key under which a relation's ``str(obj)`` examples are stored,
#: mirroring the ``'__str__'`` fk_options spec. Safe as a bucket key because no
#: real Django field can be named ``__str__``.
_STR_KEY = '__str__'


def _relation_plan(schema, field, name, max_fk_options):
    """What values a relation should contribute, resolved but not yet fetched.

    A hard ``no_value_targets`` denylist (see :func:`_no_value_targets`) is
    checked first and, when it matches the relation target, suppresses values
    unconditionally -- overriding every ``fk_options`` spec and any
    ``max_fk_options``.

    Otherwise dispatch on the schema's fk_options entry:
      - False        -> nothing (no query)
      - True         -> force the default field, ignore the threshold
                        (capped at MAX_SUGGESTED_VALUES)
      - int N        -> default field's distinct values with a per-relation
                        limit N -- overrides both the MAX_SUGGESTED_VALUES cap
                        and ``max_fk_options`` (emit all iff cardinality <= N)
      - 'field'      -> that field's distinct values, gated by threshold
      - ['a', 'b']   -> each field's distinct values, gated by threshold
      - '__str__'    -> str(obj) examples, gated by row count
      - no entry     -> auto: default field, skip sensitive models / over-limit

    Returns ``None`` when nothing should be emitted, else one of::

        ('field',  match_field,  limit)
        ('fields', [f1, f2, ...], limit)
        ('str',    None,         limit)

    Fetching (and its memoisation across FKs to the same dictionary) is left to
    :func:`_collect_dictionaries`; this function only decides the plan.
    """
    related_model = field.related_model
    if related_model in _no_value_targets(schema):
        return None
    spec = _fk_spec(schema, field, name)

    if spec is False:
        return None
    if spec is True:
        match_field = _default_match_field(schema, field.relation)
        if match_field is None:
            return ('str', None, None)
        return ('field', match_field, None)
    if isinstance(spec, int) and not isinstance(spec, bool):
        # Per-relation integer limit: bypass both the MAX_SUGGESTED_VALUES cap
        # (the True path) and the global max_fk_options threshold. Emits every
        # value iff the relation's cardinality is <= spec, else nothing.
        match_field = _default_match_field(schema, field.relation)
        if match_field is None:
            return ('str', None, spec)
        return ('field', match_field, spec)
    if isinstance(spec, str) and spec != _STR_KEY:
        return ('field', spec, max_fk_options)
    if isinstance(spec, (list, tuple)):
        return ('fields', list(spec), max_fk_options)
    if spec == _STR_KEY:
        return ('str', None, max_fk_options)

    # spec is _AUTO
    if max_fk_options <= 0:
        return None
    if _is_sensitive_target(related_model):
        return None
    match_field = _default_match_field(schema, field.relation)
    if match_field is None:
        return None
    return ('field', match_field, max_fk_options)


def _collect_dictionaries(schema, max_fk_options):
    """Fetch related-model values once per ``(target model, match key)``.

    The same dictionary (e.g. a ``jezyk`` slownik) is often the target of many
    foreign keys; emitting its values inline at every FK bloats the prompt with
    pure redundancy. Here they are gathered a single time into a shared block,
    and each relation carries only a lightweight reference to it.

    Returns ``(dictionaries, field_refs)``:

    - ``dictionaries``: ``{target_label: {match_key: [values, ...]}}`` -- one
      entry per unique ``(target model, match field)``. ``match_key`` is a
      field name, or ``'__str__'`` for ``str(obj)`` examples.
    - ``field_refs``: ``{(owner_label, field_name): {ref}}`` where ``ref`` is
      ``{'match_field': key}`` or ``{'match_fields': [keys]}`` -- what the
      relation should carry to point back into ``dictionaries``. Absent for a
      relation whose values ended up empty (no rows, over threshold, ...).

    Fetches are memoised on the per-target bucket, so N foreign keys to one
    dictionary trigger a single ``SELECT DISTINCT`` rather than N.
    """
    dictionaries = {}
    field_refs = {}

    def _fetch_field(bucket, related_model, match_field, limit):
        if match_field in bucket:
            return bucket[match_field]
        values = _distinct_values(related_model, match_field, limit)
        if values:
            bucket[match_field] = values
        return values

    for owner_label, fields in schema.models.items():
        for name, field in fields.items():
            if not (
                field.suggested
                and isinstance(field, RelationField)
                and not isinstance(field, _DERIVED_FIELD_CLASSES)
            ):
                continue
            plan = _relation_plan(schema, field, name, max_fk_options)
            if plan is None:
                continue
            related_label = field.relation
            related_model = field.related_model
            bucket = dictionaries.setdefault(related_label, {})
            kind, target, limit = plan
            if kind == 'field':
                if _fetch_field(bucket, related_model, target, limit):
                    field_refs[owner_label, name] = {'match_field': target}
            elif kind == 'fields':
                present = [
                    f
                    for f in target
                    if _fetch_field(bucket, related_model, f, limit)
                ]
                if present:
                    field_refs[owner_label, name] = {'match_fields': present}
            else:  # kind == 'str'
                if _STR_KEY not in bucket:
                    examples = _str_examples(related_model, limit)
                    if examples:
                        bucket[_STR_KEY] = examples
                if _STR_KEY in bucket:
                    field_refs[owner_label, name] = {'match_field': _STR_KEY}
            if not bucket:
                dictionaries.pop(related_label, None)

    return dictionaries, field_refs


def _field_ir(name, field, field_refs, owner_label):
    """Semantic facts for one field, independent of output format.

    Carries information only — no operators, examples, or notes (those are
    derivable from the type and belong to the renderer's legend). A relation's
    concrete values live in the shared ``dictionaries`` block; the field only
    references them via ``match_field`` / ``match_fields`` (see
    :func:`_collect_dictionaries`).
    """
    ir = {'type': field.type, 'nullable': bool(field.nullable)}
    ir.update(_field_metadata(field))
    if getattr(field, 'object_reference', False):
        ir['object_reference'] = True
    if isinstance(field, RelationField):
        ir['relates_to'] = field.relation
        ir.update(field_refs.get((owner_label, name), {}))
    else:
        choices = _choice_labels(field)
        if choices:
            ir['choices'] = choices
        else:
            options = _field_options(field)
            if options:
                ir['suggested_values'] = options
    return ir


def _schema_capabilities(schema):
    """Detect derived-lookup capabilities across ALL fields of the schema.

    Scans schema.models (including suggested=False virtual fields) so the
    legend can advertise <field>__<part> / <rel>__count / numeric aggregates
    once, even though the individual derived fields are never listed.
    """
    date_parts, time_parts = set(), set()
    has_date_extract = has_time_extract = relation_count = False
    for fields in schema.models.values():
        for field in fields.values():
            if isinstance(field, DateExtractField):
                has_date_extract = True
            elif isinstance(field, TimeExtractField):
                has_time_extract = True
            elif isinstance(field, DatePartField):
                if field.part in _TIME_PART_NAMES:
                    time_parts.add(field.part)
                else:
                    date_parts.add(field.part)
            elif isinstance(field, CountField):
                # Only CountField (a <rel>__count field) is ever statically
                # registered; numeric AggregateField subclasses are
                # synthesized on demand and never appear in schema.models.
                relation_count = True
    return {
        'date_parts': [p for p in _CANONICAL_DATE_PARTS if p in date_parts],
        'time_parts': [p for p in _CANONICAL_TIME_PARTS if p in time_parts],
        'has_date_extract': has_date_extract,
        'has_time_extract': has_time_extract,
        'relation_count': relation_count,
    }


def _build_schema_ir(schema, max_fk_options):
    """Build the format-independent intermediate representation of a schema."""
    dictionaries, field_refs = _collect_dictionaries(schema, max_fk_options)
    return {
        'start_model': schema.model_label(schema.current_model),
        'capabilities': _schema_capabilities(schema),
        'dictionaries': dictionaries,
        'models': {
            model_label: {
                name: _field_ir(name, field, field_refs, model_label)
                for name, field in fields.items()
                if field.suggested
                and not isinstance(field, _DERIVED_FIELD_CLASSES)
            }
            for model_label, fields in schema.models.items()
        },
    }


def _json_field(facts):
    """Terse JSON for one field: a bare type string when it has no extras,
    else an object with ``type`` plus only informative keys. A ``?`` suffix
    on the type marks the field nullable."""
    type_token = facts['type'] + ('?' if facts.get('nullable') else '')
    extras = {k: v for k, v in facts.items() if k not in ('type', 'nullable')}
    if not extras:
        return type_token
    return {'type': type_token, **extras}


#: Header comment block for the compact format: grammar + per-type operators,
#: written once at the top so field lines stay terse.
_COMPACT_HEADER = [
    '# DjangoQL schema',
    '# Query: <field> <op> <value>, combined with and/or, grouped with ().',
    '# Negate with != / !~ / not in / not startswith / not endswith '
    '(no standalone `not`).',
    '# Relations: traverse with a dot (author.name = "..."), or compare None.',
    '# Operators by type:',
    '#   int/float/date:  = != > >= < <=  in  not in        e.g. rating = 4.5',
    '#   datetime:        (as above) plus ~ !~',
    '#   str:  = != ~ !~ startswith endswith (not ...) in  not in'
    '           e.g. name ~ "text"',
    '#   bool:           = !=                           e.g. is_pub = True',
    '#   -> relation:     = None / != None / dot-traverse',
    '#   # object_reference: = != in not in  (match by pk)',
    '# Suffix ? = nullable.  choices: closed set.',
    '',
]


def _q(value):
    """Double-quote a value for the compact rendering."""
    return f'"{value}"'


def _dict_key_label(key):
    """Human label for a dictionary match key: ``'__str__'`` reads as
    ``examples`` (there is no single field to match on), any other key is the
    field name verbatim. Shared by the FK reference and the dictionary block so
    the two always line up."""
    return 'examples' if key == _STR_KEY else key


def _append_label(parts, facts):
    """Append the quoted ``label`` (with optional ``help_text``) to ``parts``,
    shared by both the scalar and relation branches of :func:`_compact_field`
    so label/help_text formatting is never duplicated."""
    if 'label' in facts:
        label = _q(facts['label'])
        if 'help_text' in facts:
            label += ' — {}'.format(facts['help_text'])
        parts.append(label)


def _compact_field(name, facts, width):
    """Render one IR field as a single compact line."""
    padded = name.ljust(width)
    type_token = facts['type'] + ('?' if facts.get('nullable') else '')
    if facts['type'] == 'relation':
        rel = facts.get('relates_to', '?')
        # Deliberate divergence from JSON: JSON marks nullability on the type
        # (`relation?`), compact marks it on the relation target (`-> x?`).
        if facts.get('nullable'):
            rel += '?'
        parts = [f'-> {rel}']
        # Values themselves live once in the shared dictionaries block; the FK
        # only names which key to look up there.
        if 'match_field' in facts:
            mf = facts['match_field']
            parts.append('examples' if mf == _STR_KEY else 'match ' + mf)
        elif 'match_fields' in facts:
            parts.append('match ' + ', '.join(facts['match_fields']))
        _append_label(parts, facts)
        return '{}  {}'.format(padded, '  '.join(parts))
    # scalar fields (including object_reference pickers)
    if facts.get('object_reference'):
        parts = [f'# {type_token} (object_reference)']
    else:
        parts = [type_token]
    _append_label(parts, facts)
    if 'choices' in facts:
        parts.append('choices: ' + ' | '.join(facts['choices']))
    if 'suggested_values' in facts:
        vals = ', '.join(_q(v) for v in facts['suggested_values'])
        parts.append('values: ' + vals)
    return '{}  {}'.format(padded, '  '.join(parts))


def _compact_capability_lines(caps):
    """Header comment lines describing derived-lookup capabilities, or []."""
    lines = []
    if caps['date_parts']:
        lines.append(
            '# date fields also: <field>__<part> (int): '
            + ', '.join(caps['date_parts'])
        )
    dt = []
    if caps['time_parts']:
        dt.append('<field>__<part>: ' + ', '.join(caps['time_parts']))
    if caps['has_date_extract']:
        dt.append('<field>__date')
    if caps['has_time_extract']:
        dt.append('<field>__time')
    if dt:
        lines.append('# datetime fields also: ' + '; '.join(dt))
    if caps['relation_count']:
        lines.append(
            '# to-many relations: <rel>__count; numeric via dot '
            '<rel>.<field>__sum|avg|min|max'
        )
    return lines


def _render_compact(ir):
    """Render the IR as a terse text block, one line per field."""
    lines = list(_COMPACT_HEADER)
    cap_lines = _compact_capability_lines(
        ir.get(
            'capabilities',
            {
                'date_parts': [],
                'time_parts': [],
                'has_date_extract': False,
                'has_time_extract': False,
                'relation_count': False,
            },
        )
    )
    if cap_lines:
        blank = lines.pop() if lines and lines[-1] == '' else None
        lines.extend(cap_lines)
        if blank is not None:
            lines.append(blank)
    lines.append('start model: {}'.format(ir['start_model']))
    lines.append('')
    for label, fields in ir['models'].items():
        lines.append(f'{label}:')
        width = max((len(n) for n in fields), default=0)
        for name, facts in fields.items():
            lines.append('  ' + _compact_field(name, facts, width))
        lines.append('')
    lines.extend(_compact_dictionary_lines(ir.get('dictionaries') or {}))
    return '\n'.join(lines).rstrip() + '\n'


def _compact_dictionary_lines(dictionaries):
    """The shared dictionaries block: every relation's concrete values, listed
    once and keyed by ``(target model, match key)``, that the ``-> model
    match <field>`` / ``examples`` references above point back into."""
    if not dictionaries:
        return []
    lines = ['dictionaries (shared relation values, referenced above):']
    for label, entries in dictionaries.items():
        lines.append(f'  {label}')
        for key, values in entries.items():
            vals = ', '.join(_q(v) for v in values)
            lines.append(f'    {_dict_key_label(key)}: {vals}')
    lines.append('')
    return lines


def _apply_capabilities_to_legend(legend, caps):
    """Add type-level `lookups`/`aggregates` notes for detected derived fields.

    Only touches legend entries whose capability was actually detected, so a
    schema without the date-parts / aggregate mixins gains nothing.
    """
    date_parts = caps['date_parts']
    time_parts = caps['time_parts']

    def _temporal_example(parts, has_date_extract):
        ex = []
        if 'year' in parts:
            ex.append('utworzono__year = 2021')
        elif parts:
            ex.append('utworzono__%s = 1' % parts[0])
        if has_date_extract:
            ex.append('utworzono__date = "2021-06-01"')
        return ex

    if date_parts and 'date' in legend:
        note = 'also <field>__<part> (integer): %s' % ', '.join(date_parts)
        ex = _temporal_example(date_parts, False)
        if ex:
            note += '. e.g. ' + ', '.join(ex)
        legend['date']['lookups'] = note

    dt_parts = date_parts + time_parts
    dt_bits = []
    if dt_parts:
        dt_bits.append('<field>__<part> (integer): %s' % ', '.join(dt_parts))
    if caps['has_date_extract']:
        dt_bits.append('<field>__date (date)')
    if caps['has_time_extract']:
        dt_bits.append('<field>__time (time)')
    if dt_bits and 'datetime' in legend:
        note = 'also ' + '; '.join(dt_bits)
        ex = _temporal_example(dt_parts, caps['has_date_extract'])
        if ex:
            note += '. e.g. ' + ', '.join(ex)
        legend['datetime']['lookups'] = note
    if caps['relation_count'] and 'relation' in legend:
        legend['relation']['aggregates'] = (
            'to-many relation: <rel>__count (integer), '
            'e.g. autorzy__count >= 2.'
            ' Numeric aggregates via dot: '
            '<rel>.<numeric_field>__sum|avg|min|max, e.g. autorzy.rating__avg'
        )


def _render_json(ir):
    """Render the IR as the normalized JSON description."""
    legend = _operator_legend()
    # Graceful degradation for custom field types (e.g. a DjangoQLField
    # subclass with a novel `type`): mirrors the pre-refactor
    # OPERATORS_BY_TYPE.get(type, [...]) fallback so every field type in the
    # IR resolves to *some* operator list, even one the legend never named.
    for fields in ir['models'].values():
        for facts in fields.values():
            ftype = facts['type']
            if ftype not in legend:
                legend[ftype] = {'operators': ['=', '!=', 'in', 'not in']}
    if 'capabilities' in ir:
        _apply_capabilities_to_legend(legend, ir['capabilities'])
    return {
        'start_model': ir['start_model'],
        'grammar': dict(_GRAMMAR),
        'operators_by_type': legend,
        'dictionaries': ir.get('dictionaries', {}),
        'models': {
            label: {name: _json_field(facts) for name, facts in fields.items()}
            for label, fields in ir['models'].items()
        },
        'examples': list(_EXAMPLES),
    }


def _field_options(field):
    """Concrete suggestion values for a field, if the schema exposes any.

    Mirrors the autocomplete serializer's guard: only fields flagged with
    ``suggest_options`` are queried, so this never hits the database for an
    ordinary field.
    """
    if not getattr(field, 'suggest_options', False):
        return None
    try:
        options = list(field.get_options(''))
    except Exception:
        # A custom get_options() may need request context we don't have here;
        # a missing value list must never break schema description.
        return None
    return [str(o) for o in options[:MAX_SUGGESTED_VALUES]] or None


def describe_schema_for_llm(schema, format='json', max_fk_options=50):  # noqa: A002
    """Describe ``schema`` for an LLM prompt.

    ``schema`` is an *instance* of a DjangoQLSchema subclass. ``format`` selects
    the output: ``'json'`` (default) returns a normalized, JSON-serializable
    dict (a one-time operator legend plus terse field entries); ``'compact'``
    returns a terse text block. Only fields suggested in autocomplete are
    included, so the description matches what a user sees.
    """
    ir = _build_schema_ir(schema, max_fk_options)
    if format == 'json':
        return _render_json(ir)
    if format == 'compact':
        return _render_compact(ir)
    raise ValueError(f"format must be 'json' or 'compact', got {format!r}")
