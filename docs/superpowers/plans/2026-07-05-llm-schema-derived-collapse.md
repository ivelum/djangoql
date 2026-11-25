# LLM Schema Derived-Field Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop listing per-field derived lookups (date parts, `<rel>__count`) in the LLM schema; instead describe their capability once in the type legend, detected across all schema fields.

**Architecture:** `_build_schema_ir` gains a `capabilities` branch detected by scanning every field in `schema.models` (including `suggested=False` virtual fields), and its emission filter explicitly excludes the derived field classes. `_render_json` and `_render_compact` turn `capabilities` into `lookups`/`aggregates` legend notes (JSON) and header lines (compact), gated on presence.

**Tech Stack:** Python, Django, DjangoQL; tests via `pytest`+`pytest-django` (SQLite); docs via MkDocs.

## Global Constraints

- Derived field classes live in `djangoql/extras.py`: `DatePartField` (has `.part`), `DateExtractField` (`__date`), `TimeExtractField` (`__time`), `AggregateField` (base of `CountField` = `__count`). All default to `suggested=False`.
- `_DERIVED_FIELD_CLASSES = (DatePartField, DateExtractField, TimeExtractField, AggregateField)`.
- Detection scans ALL of `schema.models` (which includes `suggested=False` fields); emission filter is `if field.suggested and not isinstance(field, _DERIVED_FIELD_CLASSES)`.
- Time parts are `hour`, `minute`, `second` (`_TIME_PART_NAMES`); all other `DatePartField.part` values are date parts. Canonical order: date parts `year, month, day, week_day, quarter, week, iso_year, iso_week_day`; time parts `hour, minute, second`.
- Legend keys: `lookups` on `date`/`datetime`; `aggregates` on `relation`. Added ONLY when the corresponding capability is detected (gating).
- Aggregate syntax (verbatim in the note): `<rel>__count` (e.g. `autorzy__count >= 2`) and numeric via dot `<rel>.<numeric_field>__sum|avg|min|max` (e.g. `autorzy.rating__avg`).
- No expand escape hatch; collapsed is the only behavior.
- `import` `_build_schema_ir` from `djangoql.llm`; the IR shape is `{'start_model': str, 'capabilities': dict, 'models': {...}}`.
- Run whole suite: `uv run pytest`. Single test: `uv run pytest <path>::<Class>::<test> -v`. Docs: `uv run mkdocs build --strict`.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: IR — detect capabilities and exclude derived fields

**Files:**
- Modify: `djangoql/llm.py`
- Test: `test_project/core/tests/test_llm.py`

**Interfaces:**
- Produces:
  - `_schema_capabilities(schema) -> {'date_parts': list, 'time_parts': list, 'has_date_extract': bool, 'has_time_extract': bool, 'relation_count': bool}`
  - `_build_schema_ir(schema, max_fk_options)` now returns a dict with an added `'capabilities'` key and an emission filter that excludes `_DERIVED_FIELD_CLASSES`.
  - Constants `_CANONICAL_DATE_PARTS`, `_CANONICAL_TIME_PARTS`, `_TIME_PART_NAMES`, `_DERIVED_FIELD_CLASSES`.

- [ ] **Step 1: Write the failing tests**

Add a test schema and class near the top of `test_project/core/tests/test_llm.py` (after the existing imports; `User` and `Book` are already imported, `DjangoQLSchema` too):

```python
from djangoql.extras import AggregateSchemaMixin, DatePartsSchemaMixin
from djangoql.llm import _build_schema_ir


class DerivedSchema(AggregateSchemaMixin, DatePartsSchemaMixin, DjangoQLSchema):
    include = (Book, User)


class DerivedCapabilitiesTest(TestCase):
    def test_capabilities_detected_from_all_fields(self):
        # Derived fields are suggested=False, but detection scans schema.models
        ir = _build_schema_ir(DerivedSchema(Book), 50)
        caps = ir['capabilities']
        self.assertIn('year', caps['date_parts'])
        self.assertIn('hour', caps['time_parts'])
        self.assertTrue(caps['has_date_extract'])
        self.assertTrue(caps['has_time_extract'])
        # User has a reverse to-many to Book -> book__count (CountField)
        self.assertTrue(caps['relation_count'])

    def test_time_parts_never_land_in_date_parts(self):
        ir = _build_schema_ir(DerivedSchema(Book), 50)
        self.assertNotIn('hour', ir['capabilities']['date_parts'])

    def test_plain_schema_has_empty_capabilities(self):
        ir = _build_schema_ir(DjangoQLSchema(Book), 50)
        caps = ir['capabilities']
        self.assertEqual([], caps['date_parts'])
        self.assertEqual([], caps['time_parts'])
        self.assertFalse(caps['relation_count'])

    def test_derived_fields_absent_but_base_present(self):
        ir = _build_schema_ir(DerivedSchema(Book), 50)
        book = ir['models']['core.book']
        self.assertIn('written', book)          # base datetime field stays
        self.assertNotIn('written__year', book)
        self.assertNotIn('written__date', book)
        user = ir['models']['auth.user']
        self.assertNotIn('book__count', user)

    def test_suggested_true_derived_field_still_excluded(self):
        from djangoql.extras import DatePartField

        class SurfacedSchema(DjangoQLSchema):
            def get_fields(self, model):
                fields = list(super().get_fields(model))
                if model == Book:
                    f = DatePartField('written', 'year', model=model)
                    f.suggested = True  # force it visible
                    fields.append(f)
                return fields

        ir = _build_schema_ir(SurfacedSchema(Book), 50)
        self.assertNotIn('written__year', ir['models']['core.book'])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest test_project/core/tests/test_llm.py::DerivedCapabilitiesTest -v`
Expected: FAIL with `KeyError: 'capabilities'`.

- [ ] **Step 3: Add imports and constants**

In `djangoql/llm.py`, extend the import from `.schema` region with a new import (place after `from .schema import RelationField`):

```python
from .extras import (
    AggregateField,
    DateExtractField,
    DatePartField,
    TimeExtractField,
)
```

Add near the other module constants:

```python
#: Canonical ordering for date/time lookup parts, so the legend note is stable.
_CANONICAL_DATE_PARTS = [
    'year', 'month', 'day', 'week_day', 'quarter', 'week',
    'iso_year', 'iso_week_day',
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
```

- [ ] **Step 4: Add the capability detector**

Add above `_build_schema_ir`:

```python
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
            elif isinstance(field, AggregateField):
                relation_count = True
    return {
        'date_parts': [p for p in _CANONICAL_DATE_PARTS if p in date_parts],
        'time_parts': [p for p in _CANONICAL_TIME_PARTS if p in time_parts],
        'has_date_extract': has_date_extract,
        'has_time_extract': has_time_extract,
        'relation_count': relation_count,
    }
```

- [ ] **Step 5: Wire capabilities and the exclusion into `_build_schema_ir`**

Replace `_build_schema_ir` with:

```python
def _build_schema_ir(schema, max_fk_options):
    """Build the format-independent intermediate representation of a schema."""
    return {
        'start_model': schema.model_label(schema.current_model),
        'capabilities': _schema_capabilities(schema),
        'models': {
            model_label: {
                name: _field_ir(name, field, schema, max_fk_options)
                for name, field in fields.items()
                if field.suggested
                and not isinstance(field, _DERIVED_FIELD_CLASSES)
            }
            for model_label, fields in schema.models.items()
        },
    }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest test_project/core/tests/test_llm.py::DerivedCapabilitiesTest -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (the existing DescribeSchemaForLLMTest / RelationValuesTest / CompactFormatTest still green — the added `capabilities` key doesn't affect their assertions).

- [ ] **Step 8: Commit**

```bash
git add djangoql/llm.py test_project/core/tests/test_llm.py
git commit -m "$(printf 'feat: detect derived-lookup capabilities and exclude derived fields from LLM schema IR\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: Render capabilities into the JSON legend and compact header

**Files:**
- Modify: `djangoql/llm.py`
- Test: `test_project/core/tests/test_llm.py`

**Interfaces:**
- Consumes: `ir['capabilities']` (Task 1).
- Produces: `_apply_capabilities_to_legend(legend, caps)`, `_compact_capability_lines(caps) -> list[str]`; `_render_json` adds `lookups`/`aggregates` legend keys; `_render_compact` adds header capability lines.

- [ ] **Step 1: Write the failing tests**

Add to `DerivedCapabilitiesTest` in `test_project/core/tests/test_llm.py`:

```python
    def test_json_date_legend_advertises_part_lookups(self):
        bundle = describe_schema_for_llm(DerivedSchema(Book))
        lookups = bundle['operators_by_type']['date'].get('lookups', '')
        self.assertIn('year', lookups)
        self.assertIn('<field>__', lookups)

    def test_json_datetime_legend_advertises_time_and_extracts(self):
        bundle = describe_schema_for_llm(DerivedSchema(Book))
        lookups = bundle['operators_by_type']['datetime'].get('lookups', '')
        self.assertIn('hour', lookups)
        self.assertIn('__date', lookups)
        self.assertIn('__time', lookups)

    def test_json_relation_legend_advertises_aggregates(self):
        bundle = describe_schema_for_llm(DerivedSchema(Book))
        agg = bundle['operators_by_type']['relation'].get('aggregates', '')
        self.assertIn('__count', agg)
        self.assertIn('sum', agg)

    def test_json_plain_schema_has_no_capability_notes(self):
        bundle = describe_schema_for_llm(DjangoQLSchema(Book))
        self.assertNotIn('lookups', bundle['operators_by_type']['date'])
        self.assertNotIn('aggregates', bundle['operators_by_type']['relation'])

    def test_compact_header_lists_capabilities_once(self):
        text = describe_schema_for_llm(DerivedSchema(Book), format='compact')
        self.assertIn('__count', text)
        self.assertIn('year', text)
        # the derived fields are not emitted as their own lines
        self.assertNotIn('written__year', text)
        self.assertNotIn('book__count  ', text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest test_project/core/tests/test_llm.py::DerivedCapabilitiesTest -k "json or compact" -v`
Expected: FAIL (no `lookups`/`aggregates` keys; compact header lacks the notes).

- [ ] **Step 3: Add the JSON legend applier**

In `djangoql/llm.py`, add above `_render_json`:

```python
def _apply_capabilities_to_legend(legend, caps):
    """Add type-level `lookups`/`aggregates` notes for detected derived fields.

    Only touches legend entries whose capability was actually detected, so a
    schema without the date-parts / aggregate mixins gains nothing.
    """
    date_parts = caps['date_parts']
    time_parts = caps['time_parts']
    if date_parts and 'date' in legend:
        legend['date']['lookups'] = (
            'also <field>__<part> (integer): %s. e.g. utworzono__year = 2021'
            % ', '.join(date_parts)
        )
    dt_bits = []
    if date_parts or time_parts:
        dt_bits.append(
            '<field>__<part> (integer): %s' % ', '.join(date_parts + time_parts)
        )
    if caps['has_date_extract']:
        dt_bits.append('<field>__date (date)')
    if caps['has_time_extract']:
        dt_bits.append('<field>__time (time)')
    if dt_bits and 'datetime' in legend:
        legend['datetime']['lookups'] = (
            'also ' + '; '.join(dt_bits)
            + '. e.g. utworzono__year = 2021, utworzono__date = "2021-06-01"'
        )
    if caps['relation_count'] and 'relation' in legend:
        legend['relation']['aggregates'] = (
            'to-many relation: <rel>__count (integer), e.g. autorzy__count >= 2.'
            ' Numeric aggregates via dot: '
            '<rel>.<numeric_field>__sum|avg|min|max, e.g. autorzy.rating__avg'
        )
```

- [ ] **Step 4: Call it from `_render_json`**

In `_render_json`, after the custom-type fallback loop and before the `return`, add:

```python
    _apply_capabilities_to_legend(legend, ir['capabilities'])
```

(The line sits between the `for fields in ir['models'].values(): ...` fallback loop and `return { ... }`.)

- [ ] **Step 5: Add the compact capability lines**

Add above `_render_compact`:

```python
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
```

- [ ] **Step 6: Insert the lines into `_render_compact`'s header**

In `_render_compact`, replace the opening `lines = list(_COMPACT_HEADER)` with a version that folds capability lines into the header block before its trailing blank line:

```python
def _render_compact(ir):
    """Render the IR as a terse text block, one line per field."""
    lines = list(_COMPACT_HEADER)
    cap_lines = _compact_capability_lines(ir['capabilities'])
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
    return '\n'.join(lines).rstrip() + '\n'
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest test_project/core/tests/test_llm.py::DerivedCapabilitiesTest -v`
Expected: PASS.

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (existing compact/json tests unaffected — plain schemas add no capability notes).

- [ ] **Step 9: Commit**

```bash
git add djangoql/llm.py test_project/core/tests/test_llm.py
git commit -m "$(printf 'feat: advertise derived-field lookups/aggregates once in the LLM legend\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: Documentation

**Files:**
- Modify: `docs/llm-schema.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Read the current doc**

Read `docs/llm-schema.md` in full to match structure and the existing legend/sample sections.

- [ ] **Step 2: Add a "Derived fields (date parts and aggregates)" section**

Document:
- Why derived lookups are not listed per field: the date-parts and aggregate schema mixins generate many virtual fields (`<date>__year … __second`, `<rel>__count`); listing them per field would dominate the output. They are hidden (`suggested=False`) and described once in the type legend instead.
- What the LLM does with it: from the `date`/`datetime` legend `lookups` note it can build `<field>__year`, `<field>__date`, etc.; from the `relation` `aggregates` note it can build `<rel>__count` and, via dot syntax, `<rel>.<numeric_field>__sum|avg|min|max`.
- These notes appear ONLY when the schema actually uses the mixins (a plain schema gets none).

- [ ] **Step 3: Update the sample outputs**

In the JSON sample, add `lookups` to the `date`/`datetime` legend entries and `aggregates` to the `relation` entry (matching the exact strings produced by `_apply_capabilities_to_legend`). In the compact sample, add the `# date fields also: …`, `# datetime fields also: …`, and `# to-many relations: …` header lines. You may run `uv run python test_project/manage.py djangoql_describe_schema_for_llm core.Book --format json --indent 2` for a plain-schema reference, but note the capability notes appear only for a schema with the mixins — hand-author those lines from the strings in `_apply_capabilities_to_legend`/`_compact_capability_lines`.

- [ ] **Step 4: Build the docs strictly**

Run: `uv run mkdocs build --strict`
Expected: passes, no orphaned pages or broken links.

- [ ] **Step 5: Commit**

```bash
git add docs/llm-schema.md
git commit -m "$(printf 'docs: document collapsed derived-field lookups and aggregates\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Final verification

- [ ] `uv run pytest -q` — all green.
- [ ] `uv run mkdocs build --strict` — clean.
- [ ] Sanity: `uv run python test_project/manage.py djangoql_describe_schema_for_llm core.Book --format json --indent 2` on a plain schema shows NO `lookups`/`aggregates` (mixins not used there) and no `written__year`/`book__count` field entries — confirming the collapse and the gating both hold.
