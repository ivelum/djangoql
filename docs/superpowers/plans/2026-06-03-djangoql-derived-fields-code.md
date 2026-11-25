# DjangoQL Derived Fields (Code) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in derived search fields to DjangoQL — date/time parts (`written__year`, `written__hour`, `written__date`…) and subquery-based relation aggregates (`book__count`, `book__price__avg`…), plus a `suggested` autocomplete flag — without changing default behavior.

**Architecture:** New field classes and schema mixins live in `djangoql/extras.py`. Three minimal, additive core changes: a `suggested` flag (schema + serializer), a `get_annotations(path)` field hook with `DjangoQLSchema.collect_annotations(ast)`, and an annotation-injection line in `apply_search`. Aggregates are computed as correlated `Subquery`/`OuterRef` expressions, applied lazily (only when referenced in the query). Both admin and queryset surfaces work for free because both route through `apply_search`.

**Tech Stack:** Python 3.10+, Django 4.2+, PLY (existing parser, untouched), pytest + pytest-django.

**Reference spec:** `docs/superpowers/specs/2026-06-03-djangoql-derived-fields-design.md`

**Test command (from repo root):** `uv run pytest` (config in `pyproject.toml` sets `DJANGO_SETTINGS_MODULE=test_project.settings` and `pythonpath=test_project`).

---

## File Structure

- **Create** `djangoql/extras.py` — `DatePartField`, `DateExtractField`, `TimeExtractField`, `AggregateField` + `CountField`/`SumField`/`AvgField`/`MinField`/`MaxField`, `_owner_lookup`, `DatePartsSchemaMixin`, `AggregateSchemaMixin`, `ExtrasSchema`.
- **Modify** `djangoql/schema.py` — `DjangoQLField.suggested` attr + `suggested` ctor arg + `get_annotations`; `DjangoQLSchema.collect_annotations`.
- **Modify** `djangoql/serializers.py` — skip non-`suggested` fields.
- **Modify** `djangoql/queryset.py` — `apply_search` collects + applies annotations.
- **Modify** `test_project/core/models.py` — add a `DateField` and a `TimeField` to `Book` to exercise all three date/time type mappings.
- **Create** migration for the new `Book` fields.
- **Create** `test_project/core/tests/test_extras.py` — all new tests.

---

## Task 1: `suggested` flag (core)

**Files:**
- Modify: `djangoql/schema.py` (`DjangoQLField` class ~lines 19-40)
- Modify: `djangoql/serializers.py` (`DjangoQLSchemaSerializer.serialize` ~lines 7-16)
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the failing test**

Create `test_project/core/tests/test_extras.py`:

```python
from django.contrib.auth.models import User
from django.test import TestCase

from djangoql.schema import DjangoQLSchema, IntField
from djangoql.serializers import DjangoQLSchemaSerializer

from ..models import Book


class HiddenFieldSchema(DjangoQLSchema):
    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model == Book:
            fields.append(IntField(name='secret', suggested=False))
        return fields


class SuggestedFlagTest(TestCase):
    def test_default_field_is_suggested(self):
        self.assertTrue(IntField(name='x').suggested)

    def test_unsuggested_field_hidden_from_serializer(self):
        data = DjangoQLSchemaSerializer().serialize(HiddenFieldSchema(Book))
        book_fields = data['models']['core.book']
        self.assertIn('name', book_fields)
        self.assertNotIn('secret', book_fields)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest test_project/core/tests/test_extras.py -v`
Expected: FAIL — `IntField()` does not accept `suggested` (TypeError), or `secret` present.

- [ ] **Step 3: Add `suggested` to the base field**

In `djangoql/schema.py`, `DjangoQLField`, add the class attribute next to the others (after `suggest_options = False`):

```python
    suggested = True
```

Update `__init__` signature and body:

```python
    def __init__(self, model=None, name=None, nullable=None,
                 suggest_options=None, suggested=None):
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
```

- [ ] **Step 4: Filter unsuggested fields in the serializer**

In `djangoql/serializers.py`, `DjangoQLSchemaSerializer.serialize`, add the `if f.suggested` guard:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest test_project/core/tests/test_extras.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full suite (no regressions)**

Run: `uv run pytest -q`
Expected: all pass (existing fields default `suggested=True`).

- [ ] **Step 7: Commit**

```bash
git add djangoql/schema.py djangoql/serializers.py test_project/core/tests/test_extras.py
git commit -m "feat(schema): add suggested flag to control autocomplete visibility"
```

---

## Task 2: Lazy annotation hook (core)

Adds `get_annotations(path)` (default `{}`), `DjangoQLSchema.collect_annotations(ast)`, and wires `apply_search` to annotate only referenced fields.

**Files:**
- Modify: `djangoql/schema.py` (`DjangoQLField`, `DjangoQLSchema`)
- Modify: `djangoql/queryset.py` (`apply_search` ~lines 32-40)
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the failing test**

Append to `test_project/core/tests/test_extras.py`:

```python
from django.db.models import Count, Value

from djangoql.queryset import apply_search


class _ProbeCountField(IntField):
    """Minimal annotation-backed field for testing the lazy hook."""
    name = 'probe'

    def get_annotations(self, path):
        return {'probe': Count('book')}

    def get_lookup(self, path, operator, value):
        from django.db.models import Q
        op, invert = self.get_operator(operator)
        q = Q(**{'probe%s' % op: value})
        return ~q if invert else q


class ProbeSchema(DjangoQLSchema):
    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model == User:
            fields.append(_ProbeCountField(model=User))
        return fields


class CollectAnnotationsTest(TestCase):
    def test_annotation_applied_only_when_field_used(self):
        used = apply_search(User.objects.all(), 'probe > 1', schema=ProbeSchema)
        self.assertIn('probe', used.query.annotations)

    def test_annotation_absent_when_field_unused(self):
        unused = apply_search(
            User.objects.all(), 'username = "x"', schema=ProbeSchema,
        )
        self.assertNotIn('probe', unused.query.annotations)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest test_project/core/tests/test_extras.py::CollectAnnotationsTest -v`
Expected: FAIL — `probe` never present (no annotation wiring yet).

- [ ] **Step 3: Add `get_annotations` to the base field**

In `djangoql/schema.py`, `DjangoQLField`, add after `get_lookup`:

```python
    def get_annotations(self, path):
        """
        Return a dict of {alias: expression} to be applied to the queryset via
        .annotate() before filtering. Default: no annotations.

        Only called for fields actually referenced in a query, so aggregate
        fields produce SQL lazily. `path` is the list of names preceding this
        field (relation hops), e.g. ['author'] for 'author.book__count'.
        """
        return {}
```

- [ ] **Step 4: Add `collect_annotations` to the schema**

In `djangoql/schema.py`, `DjangoQLSchema`, add (after `validate`):

```python
    def collect_annotations(self, node):
        """
        Walk a validated AST and merge get_annotations() from every field that
        is actually referenced. Returns {alias: expression}.
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
```

- [ ] **Step 5: Wire `apply_search`**

In `djangoql/queryset.py`, replace `apply_search` body:

```python
def apply_search(queryset, search, schema=None):
    """
    Applies search written in DjangoQL mini-language to given queryset
    """
    ast = DjangoQLParser().parse(search)
    schema = schema or DjangoQLSchema
    schema_instance = schema(queryset.model)
    schema_instance.validate(ast)
    annotations = schema_instance.collect_annotations(ast)
    if annotations:
        queryset = queryset.annotate(**annotations)
    return queryset.filter(build_filter(ast, schema_instance))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest test_project/core/tests/test_extras.py::CollectAnnotationsTest -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add djangoql/schema.py djangoql/queryset.py test_project/core/tests/test_extras.py
git commit -m "feat(schema): lazy get_annotations hook wired into apply_search"
```

---

## Task 3: Test model fields (DateField + TimeField)

The only date-ish field on `Book` is `written` (DateTimeField). Add a `DateField` and a `TimeField` so all three type mappings are exercised.

**Files:**
- Modify: `test_project/core/models.py` (`Book`)
- Create: `test_project/core/migrations/0002_book_published_date_time.py` (via makemigrations)

- [ ] **Step 1: Add the fields to `Book`**

In `test_project/core/models.py`, inside `Book`, add after `written = ...`:

```python
    published_date = models.DateField(null=True, blank=True)
    published_time = models.TimeField(null=True, blank=True)
```

- [ ] **Step 2: Make the migration**

Run: `cd test_project && uv run python manage.py makemigrations core && cd ..`
Expected: creates `test_project/core/migrations/0002_*.py` adding two fields.

- [ ] **Step 3: Verify the suite still collects/runs**

Run: `uv run pytest -q`
Expected: all pass (migrations applied to the test DB automatically).

- [ ] **Step 4: Commit**

```bash
git add test_project/core/models.py test_project/core/migrations/
git commit -m "test: add DateField and TimeField to Book for derived-field tests"
```

---

## Task 4: Date/time part fields + DatePartsSchemaMixin

**Files:**
- Create: `djangoql/extras.py`
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_project/core/tests/test_extras.py`:

```python
class DatePartsTest(TestCase):
    def _where(self, search):
        from djangoql.extras import DatePartsSchemaMixin

        class S(DatePartsSchemaMixin, DjangoQLSchema):
            pass

        qs = apply_search(Book.objects.all(), search, schema=S)
        return str(qs.query).split('WHERE')[1].strip()

    def test_datetime_year(self):
        self.assertIn('django_datetime_extract', self._where('written__year = 2020').lower())

    def test_datetime_hour(self):
        where = self._where('written__hour >= 9').lower()
        self.assertIn('hour', where)

    def test_date_field_month(self):
        where = self._where('published_date__month = 6').lower()
        self.assertIn('month', where)

    def test_time_field_minute(self):
        where = self._where('published_time__minute = 30').lower()
        self.assertIn('minute', where)

    def test_datetime_date_extract(self):
        where = self._where('written__date = "2020-01-01"').lower()
        self.assertIn('date', where)
```

> Note: exact SQL function names vary by DB backend (SQLite vs Postgres). The
> assertions check for the transform keyword case-insensitively, which is stable
> across backends for these lookups. If a backend emits a different spelling,
> relax the assertion to check the query runs without error
> (`list(qs[:1])`) and returns the expected rows in a seeded test.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest test_project/core/tests/test_extras.py::DatePartsTest -v`
Expected: FAIL — `djangoql.extras` does not exist.

- [ ] **Step 3: Create `djangoql/extras.py` with date/time parts**

Create `djangoql/extras.py`:

```python
from datetime import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _

from .schema import DateField, DjangoQLField, IntField


class DatePartField(IntField):
    """
    Virtual integer field for a date/time part extracted via a Django ORM
    transform, e.g. ``written__year`` -> ``written__year`` lookup.

    The field name IS the ORM lookup, so no get_lookup_name() override is
    needed: get_lookup joins ``path + [name]`` with ``__``.
    """

    def __init__(self, base_field, part, model=None, nullable=False):
        self.base_field = base_field
        self.part = part
        super().__init__(
            model=model,
            name='%s__%s' % (base_field, part),
            nullable=nullable,
        )


class DateExtractField(DateField):
    """``<datetime>__date`` -> compares to a date in YYYY-MM-DD format."""

    def __init__(self, base_field, model=None, nullable=False):
        self.base_field = base_field
        super().__init__(
            model=model,
            name='%s__date' % base_field,
            nullable=nullable,
        )


class TimeExtractField(DjangoQLField):
    """``<datetime>__time`` -> compares to a time in HH:MM[:SS] format."""

    type = 'time'
    value_types = [str]
    value_types_description = _('times in "HH:MM" format')

    def __init__(self, base_field, model=None, nullable=False):
        self.base_field = base_field
        super().__init__(
            model=model,
            name='%s__time' % base_field,
            nullable=nullable,
        )

    def get_lookup_value(self, value):
        if not value:
            return None
        mask = '%H:%M:%S' if value.count(':') > 1 else '%H:%M'
        return datetime.strptime(value, mask).time()

    def validate(self, value):
        super().validate(value)
        try:
            self.get_lookup_value(value)
        except ValueError:
            raise_value = _(
                'Field "{field}" can be compared to times in "HH:MM" '
                'format, but not to {value}',
            ).format(field=self.name, value=repr(value))
            from .exceptions import DjangoQLSchemaError
            raise DjangoQLSchemaError(raise_value)


class DatePartsSchemaMixin:
    """
    Schema mixin: expands every Date/DateTime/Time model field into virtual
    part fields (year, month, ..., hour, minute, second) plus __date/__time
    extraction for DateTimeField.
    """

    DATE_PARTS = (
        'year', 'month', 'day', 'week_day', 'quarter',
        'week', 'iso_year', 'iso_week_day',
    )
    TIME_PARTS = ('hour', 'minute', 'second')

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        for f in model._meta.get_fields():
            # DateTimeField is a subclass of DateField — test it first.
            if isinstance(f, models.DateTimeField):
                parts = self.DATE_PARTS + self.TIME_PARTS
                fields += [
                    DatePartField(f.name, p, model=model, nullable=f.null)
                    for p in parts
                ]
                fields += [
                    DateExtractField(f.name, model=model, nullable=f.null),
                    TimeExtractField(f.name, model=model, nullable=f.null),
                ]
            elif isinstance(f, models.DateField):
                fields += [
                    DatePartField(f.name, p, model=model, nullable=f.null)
                    for p in self.DATE_PARTS
                ]
            elif isinstance(f, models.TimeField):
                fields += [
                    DatePartField(f.name, p, model=model, nullable=f.null)
                    for p in self.TIME_PARTS
                ]
        return fields
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest test_project/core/tests/test_extras.py::DatePartsTest -v`
Expected: PASS. If a part assertion fails only due to backend SQL spelling, switch that assertion to the seeded-result form described in the Step 1 note.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add djangoql/extras.py test_project/core/tests/test_extras.py
git commit -m "feat(extras): date/time part fields and DatePartsSchemaMixin"
```

---

## Task 5: AggregateField base + CountField (reverse FK)

**Files:**
- Modify: `djangoql/extras.py`
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the failing behavioral test**

Append to `test_project/core/tests/test_extras.py`:

```python
class _CountSchemaFK(DjangoQLSchema):
    """Hand-built schema adding only User.book__count (reverse FK)."""

    def get_fields(self, model):
        from djangoql.extras import CountField, _owner_lookup

        fields = list(super().get_fields(model))
        if model == User:
            rel = User._meta.get_field('book')  # ManyToOneRel
            fields.append(CountField(
                model=User,
                relation_name='book',
                related_model=rel.related_model,
                owner_lookup=_owner_lookup(rel),
                name='book__count',
            ))
        return fields


class CountFKTest(TestCase):
    def setUp(self):
        self.prolific = User.objects.create(username='prolific')
        self.quiet = User.objects.create(username='quiet')
        for i in range(3):
            Book.objects.create(name='b%d' % i, author=self.prolific)

    def _usernames(self, search):
        qs = apply_search(User.objects.all(), search, schema=_CountSchemaFK)
        return set(qs.values_list('username', flat=True))

    def test_count_gt(self):
        self.assertEqual(self._usernames('book__count > 2'), {'prolific'})

    def test_count_zero_matches_empty(self):
        # Coalesce(...,0) makes "= 0" match users with no books.
        self.assertIn('quiet', self._usernames('book__count = 0'))
        self.assertNotIn('prolific', self._usernames('book__count = 0'))

    def test_count_lazy(self):
        qs = apply_search(User.objects.all(), 'username = "x"', schema=_CountSchemaFK)
        self.assertEqual(qs.query.annotations, {})
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest test_project/core/tests/test_extras.py::CountFKTest -v`
Expected: FAIL — `CountField`/`_owner_lookup` not defined.

- [ ] **Step 3: Implement `_owner_lookup`, `AggregateField`, `CountField`**

Append to `djangoql/extras.py`. First add imports at the top (next to the existing ones):

```python
from django.db.models import Count, OuterRef, Subquery
from django.db.models import IntegerField as ORMIntegerField
from django.db.models import Q
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields.related import ForeignObjectRel
from django.db.models.functions import Coalesce
```

Then add the classes:

```python
def _owner_lookup(relation_field):
    """
    Given a to-many relation entry from ``model._meta.get_fields()``, return the
    lookup used to filter the *related* model's rows by the owning instance,
    for building a correlated subquery.

    - Reverse relations (ForeignObjectRel: reverse FK / reverse M2M): the
      forward field lives on the related model -> use its name.
    - Forward M2M (ManyToManyField on the searched model): use the reverse
      query name back to the owner.
    """
    if isinstance(relation_field, ForeignObjectRel):
        return relation_field.field.name
    return relation_field.related_query_name()


class AggregateField(IntField):
    """
    Base class for subquery-backed relation aggregates. Subclasses set
    ``aggregate`` (an aggregate class) and ``aggregate_name``.

    The user-facing field name (e.g. ``book__count``) maps to a collision-safe
    annotation alias (``djangoql_book_count``); the filter is applied to the
    alias, while the path is used to correlate the subquery.
    """

    aggregate = None
    aggregate_name = None

    def __init__(self, model, relation_name, related_model, owner_lookup, name,
                 source_field=None, nullable=True, suggested=True):
        self.relation_name = relation_name
        self.related_model = related_model
        self.owner_lookup = owner_lookup
        self.source_field = source_field
        super().__init__(
            model=model, name=name, nullable=nullable, suggested=suggested,
        )

    def annotation_alias(self, path):
        joined = '_'.join(list(path) + [self.name])
        return 'djangoql_' + joined.replace('__', '_')

    def output_field(self):
        return ORMIntegerField()

    def build_expression(self, path):
        return self._subquery(path)

    def _subquery(self, path):
        outer = LOOKUP_SEP.join(list(path) + ['pk'])
        rel_qs = (
            self.related_model._base_manager
            .order_by()
            .filter(**{self.owner_lookup: OuterRef(outer)})
            .values(self.owner_lookup)
            .annotate(_agg=self.aggregate(self.source_field or 'pk'))
            .values('_agg')
        )
        return Subquery(rel_qs, output_field=self.output_field())

    def get_annotations(self, path):
        return {self.annotation_alias(path): self.build_expression(path)}

    def get_lookup(self, path, operator, value):
        alias = self.annotation_alias(path)
        op, invert = self.get_operator(operator)
        q = Q(**{'%s%s' % (alias, op): self.get_lookup_value(value)})
        return ~q if invert else q


class CountField(AggregateField):
    aggregate = Count
    aggregate_name = 'count'

    def build_expression(self, path):
        # Coalesce to 0 so "<rel>__count = 0" matches rows with no relations.
        return Coalesce(self._subquery(path), 0)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest test_project/core/tests/test_extras.py::CountFKTest -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add djangoql/extras.py test_project/core/tests/test_extras.py
git commit -m "feat(extras): subquery-based AggregateField and CountField (reverse FK)"
```

---

## Task 6: CountField over ManyToMany

Verifies `_owner_lookup` and the subquery work for a forward M2M (`User.groups`).

**Files:**
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the failing test**

Append to `test_project/core/tests/test_extras.py`:

```python
from django.contrib.auth.models import Group


class _CountSchemaM2M(DjangoQLSchema):
    def get_fields(self, model):
        from djangoql.extras import CountField, _owner_lookup

        fields = list(super().get_fields(model))
        if model == User:
            rel = User._meta.get_field('groups')  # ManyToManyField (forward)
            fields.append(CountField(
                model=User,
                relation_name='groups',
                related_model=rel.related_model,
                owner_lookup=_owner_lookup(rel),
                name='groups__count',
            ))
        return fields


class CountM2MTest(TestCase):
    def setUp(self):
        self.g1 = Group.objects.create(name='g1')
        self.g2 = Group.objects.create(name='g2')
        self.member = User.objects.create(username='member')
        self.member.groups.add(self.g1, self.g2)
        self.loner = User.objects.create(username='loner')

    def _usernames(self, search):
        qs = apply_search(User.objects.all(), search, schema=_CountSchemaM2M)
        return set(qs.values_list('username', flat=True))

    def test_m2m_count_gt(self):
        self.assertEqual(self._usernames('groups__count > 1'), {'member'})

    def test_m2m_count_zero(self):
        self.assertIn('loner', self._usernames('groups__count = 0'))
```

- [ ] **Step 2: Run to verify it fails (or passes)**

Run: `uv run pytest test_project/core/tests/test_extras.py::CountM2MTest -v`
Expected: PASS if `_owner_lookup` already handles forward M2M (it should, via `related_query_name()`). If it FAILS with a `FieldError` on the lookup name, fix `_owner_lookup` so the M2M branch returns the correct reverse query name, then re-run until green. Do not change the test.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add djangoql/extras.py test_project/core/tests/test_extras.py
git commit -m "test(extras): CountField over ManyToMany relations"
```

---

## Task 7: Sum / Avg / Min / Max fields

**Files:**
- Modify: `djangoql/extras.py`
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the failing test**

Append to `test_project/core/tests/test_extras.py`:

```python
class _AggSchema(DjangoQLSchema):
    def get_fields(self, model):
        from djangoql.extras import (
            AvgField, MaxField, MinField, SumField, _owner_lookup,
        )

        fields = list(super().get_fields(model))
        if model == User:
            rel = User._meta.get_field('book')
            common = dict(
                model=User,
                relation_name='book',
                related_model=rel.related_model,
                owner_lookup=_owner_lookup(rel),
                source_field='rating',
            )
            fields += [
                SumField(name='book__rating__sum', **common),
                AvgField(name='book__rating__avg', **common),
                MinField(name='book__rating__min', **common),
                MaxField(name='book__rating__max', **common),
            ]
        return fields


class AggregatesTest(TestCase):
    def setUp(self):
        self.u = User.objects.create(username='u')
        Book.objects.create(name='a', author=self.u, rating=2.0)
        Book.objects.create(name='b', author=self.u, rating=4.0)
        self.v = User.objects.create(username='v')
        Book.objects.create(name='c', author=self.v, rating=10.0)

    def _usernames(self, search):
        qs = apply_search(User.objects.all(), search, schema=_AggSchema)
        return set(qs.values_list('username', flat=True))

    def test_avg(self):
        # u avg = 3.0, v avg = 10.0
        self.assertEqual(self._usernames('book__rating__avg > 5'), {'v'})

    def test_sum(self):
        # u sum = 6.0, v sum = 10.0
        self.assertEqual(self._usernames('book__rating__sum < 8'), {'u'})

    def test_min_max(self):
        self.assertEqual(self._usernames('book__rating__min >= 10'), {'v'})
        self.assertEqual(self._usernames('book__rating__max <= 4'), {'u'})
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest test_project/core/tests/test_extras.py::AggregatesTest -v`
Expected: FAIL — `SumField`/`AvgField`/`MinField`/`MaxField` not defined.

- [ ] **Step 3: Implement the numeric aggregate fields**

In `djangoql/extras.py`, extend the aggregate imports:

```python
from django.db.models import Avg, Max, Min, Sum
from django.db.models import FloatField as ORMFloatField
```

Make `AggregateField` accept float/decimal values (override value typing) by adding to the `AggregateField` class body:

```python
    value_types = [int, float]
    value_types_description = _('numbers')
```

Add the subclasses after `CountField`:

```python
class SumField(AggregateField):
    aggregate = Sum
    aggregate_name = 'sum'

    def output_field(self):
        return ORMFloatField()


class AvgField(AggregateField):
    aggregate = Avg
    aggregate_name = 'avg'

    def output_field(self):
        return ORMFloatField()


class MinField(AggregateField):
    aggregate = Min
    aggregate_name = 'min'

    def output_field(self):
        return ORMFloatField()


class MaxField(AggregateField):
    aggregate = Max
    aggregate_name = 'max'

    def output_field(self):
        return ORMFloatField()
```

> Note: `CountField` overrides nothing here, so it keeps integer semantics
> (it does not use `value_types` for choices, and its expression is an integer
> `Coalesce`). The `value_types = [int, float]` on the base only affects the
> numeric aggregate subclasses' validation, allowing `> 5` and `> 5.0`.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest test_project/core/tests/test_extras.py::AggregatesTest -v`
Expected: PASS (4 assertions across 3 tests).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add djangoql/extras.py test_project/core/tests/test_extras.py
git commit -m "feat(extras): Sum/Avg/Min/Max subquery aggregate fields"
```

---

## Task 8: AggregateSchemaMixin + ExtrasSchema (auto-generation, nested, multi-aggregate)

**Files:**
- Modify: `djangoql/extras.py`
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_project/core/tests/test_extras.py`:

```python
class AutoAggregateTest(TestCase):
    def setUp(self):
        self.u = User.objects.create(username='u')
        Book.objects.create(name='a', author=self.u, rating=2.0, price=5)
        Book.objects.create(name='b', author=self.u, rating=4.0, price=7)
        self.v = User.objects.create(username='v')

    def _schema(self):
        from djangoql.extras import ExtrasSchema
        return ExtrasSchema

    def _usernames(self, search):
        qs = apply_search(User.objects.all(), search, schema=self._schema())
        return set(qs.values_list('username', flat=True))

    def test_auto_count(self):
        self.assertEqual(self._usernames('book__count = 2'), {'u'})

    def test_auto_numeric_aggregate(self):
        self.assertEqual(self._usernames('book__price__sum >= 12'), {'u'})

    def test_pk_and_fk_excluded(self):
        # No <rel>__id__sum / <rel>__author__sum auto-generated.
        from djangoql.extras import ExtrasSchema
        names = set(ExtrasSchema(User).models['auth.user'].keys())
        self.assertIn('book__count', names)
        self.assertNotIn('book__id__sum', names)
        self.assertNotIn('book__author__sum', names)

    def test_multiple_aggregates_are_independent(self):
        # Two to-many aggregates in one query must not multiply each other.
        # u: book__count = 2, groups__count = 0
        self.u.groups.clear()
        result = self._usernames('book__count = 2 and groups__count = 0')
        self.assertEqual(result, {'u'})

    def test_nested_one_hop(self):
        # Search Book; filter by the author's book count.
        from djangoql.extras import ExtrasSchema
        qs = apply_search(
            Book.objects.all(), 'author.book__count > 1', schema=ExtrasSchema,
        )
        names = set(qs.values_list('name', flat=True))
        self.assertEqual(names, {'a', 'b'})

    def test_date_and_count_compose(self):
        # DatePartsSchemaMixin and AggregateSchemaMixin coexist in ExtrasSchema.
        from djangoql.extras import ExtrasSchema
        user_fields = set(ExtrasSchema(User).models['auth.user'].keys())
        self.assertIn('date_joined__year', user_fields)
        self.assertIn('book__count', user_fields)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest test_project/core/tests/test_extras.py::AutoAggregateTest -v`
Expected: FAIL — `ExtrasSchema`/`AggregateSchemaMixin` not defined.

- [ ] **Step 3: Implement the aggregate mixin and ExtrasSchema**

Append to `djangoql/extras.py`:

```python
class AggregateSchemaMixin:
    """
    Schema mixin: for every to-many relation (reverse FK + M2M, both
    directions) of a model, add a ``<rel>__count`` field and
    ``<rel>__<numfield>__{sum,avg,min,max}`` for each numeric field on the
    related model (excluding primary keys and FK ids).
    """

    NUMERIC_FIELDS = (
        models.IntegerField, models.FloatField, models.DecimalField,
    )
    AGGREGATE_FIELDS = (
        ('sum', SumField), ('avg', AvgField),
        ('min', MinField), ('max', MaxField),
    )

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        for f in model._meta.get_fields():
            if not (f.is_relation and (f.one_to_many or f.many_to_many)):
                continue
            related = f.related_model
            if related is None:
                continue
            owner = _owner_lookup(f)
            rel = f.name
            fields.append(CountField(
                model=model, relation_name=rel, related_model=related,
                owner_lookup=owner, name='%s__count' % rel,
            ))
            for nf in related._meta.get_fields():
                if (
                    isinstance(nf, self.NUMERIC_FIELDS)
                    and not nf.is_relation
                    and not getattr(nf, 'primary_key', False)
                ):
                    for agg_name, agg_cls in self.AGGREGATE_FIELDS:
                        fields.append(agg_cls(
                            model=model, relation_name=rel,
                            related_model=related, owner_lookup=owner,
                            source_field=nf.name,
                            name='%s__%s__%s' % (rel, nf.name, agg_name),
                        ))
        return fields


class ExtrasSchema(DatePartsSchemaMixin, AggregateSchemaMixin, DjangoQLSchema):
    """Opt-in schema with date/time parts and relation aggregates enabled."""
```

Add the missing import at the top of `extras.py` (the schema base used by `ExtrasSchema`):

```python
from .schema import DjangoQLSchema
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest test_project/core/tests/test_extras.py::AutoAggregateTest -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add djangoql/extras.py test_project/core/tests/test_extras.py
git commit -m "feat(extras): AggregateSchemaMixin auto-generation and ExtrasSchema"
```

---

## Task 9: Backward-compatibility guard + lint + final verification

**Files:**
- Test: `test_project/core/tests/test_extras.py`

- [ ] **Step 1: Write the backward-compat test**

Append to `test_project/core/tests/test_extras.py`:

```python
class BackwardCompatTest(TestCase):
    def test_default_schema_unchanged(self):
        # Stock schema adds no annotations and exposes no derived fields.
        qs = apply_search(Book.objects.all(), 'name = "x"')
        self.assertEqual(qs.query.annotations, {})
        names = set(DjangoQLSchema(Book).models['core.book'].keys())
        self.assertNotIn('written__year', names)
        self.assertNotIn('author__count', names)

    def test_stock_field_get_annotations_empty(self):
        self.assertEqual(IntField(name='x').get_annotations([]), {})
```

- [ ] **Step 2: Run to verify it passes**

Run: `uv run pytest test_project/core/tests/test_extras.py::BackwardCompatTest -v`
Expected: PASS (2 tests).

- [ ] **Step 3: Run the entire test suite**

Run: `uv run pytest -q`
Expected: all pass (existing 50 + new tests).

- [ ] **Step 4: Lint the new/changed files**

Run: `uv run ruff check djangoql/extras.py djangoql/schema.py djangoql/serializers.py djangoql/queryset.py test_project/core/tests/test_extras.py`
Expected: no errors. Fix any reported issues (line length 80, import order) and re-run.

- [ ] **Step 5: Format check**

Run: `uv run ruff format --check djangoql/ test_project/core/tests/test_extras.py`
Expected: no changes needed. If it reports reformatting, run without `--check` and re-run the suite.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test(extras): backward-compatibility guards; lint clean"
```

---

## Self-Review Notes (author)

- **Spec coverage:** date parts (Task 4), time parts + `__date`/`__time` (Task 4), TimeField (Task 4), count (Tasks 5–6), sum/avg/min/max (Task 7), numeric-field selection incl. PK/FK exclusion (Task 8), `suggested` flag (Task 1), lazy annotation (Tasks 2, 5, 8), multiple-aggregate independence (Task 8), nested 1-hop (Task 8), admin+queryset shared path (via `apply_search`, exercised by queryset tests; admin uses the same function), backward compatibility (Task 9). MkDocs is intentionally deferred to the second plan.
- **Known risk:** exact SQL spellings for date transforms differ by backend; Task 4 tests assert keywords case-insensitively with a documented fallback to seeded-result assertions.
- **Known risk:** `_owner_lookup` for forward M2M relies on `related_query_name()`; Task 6 validates it behaviorally and instructs fixing the helper (not the test) if a backend/relation shape differs.
- **Decimal output:** numeric aggregates use a Float output field for v1 simplicity (comparisons coerce); documented in the spec's future section if exact decimal typing is later required.
```
