# LLM Schema Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress `describe_schema_for_llm` output by deduplicating per-type operators/examples into a one-time legend and reducing fields to a terse form, offered in two selectable modes (`json` default, `compact` text).

**Architecture:** Split fact-gathering from rendering. `_build_schema_ir` produces a neutral intermediate representation (per-field semantic facts only). `_render_json` and `_render_compact` turn the IR into output. `describe_schema_for_llm(schema, format=...)` picks the renderer. Operators/examples live in the renderer's legend, never per field.

**Tech Stack:** Python, Django, DjangoQL; tests via `pytest`+`pytest-django` (SQLite); docs via MkDocs.

## Global Constraints

- Two modes via `format` (`'json'` default returns a dict; `'compact'` returns a `str`). Unknown value → `ValueError`.
- Operators/examples are emitted ONCE in a top-level `operators_by_type` legend keyed by type, plus pseudo-types `relation` and `object_reference`. No field entry repeats operators or examples.
- Terse JSON field: a field with no extras is a bare `"name": "type"` string; a field with extras is an object carrying `type` plus only informative keys (`label`, `help_text`, `choices`, `suggested_values`, `relates_to`, `match_field`/`match_fields`, `related_values`, `related_examples`, `object_reference`). Never emit `operators`, `example`, `nullable: false`, or a generic relation `note`.
- Nullable is a `?` suffix on the type token everywhere (`"date?"`, `{"type": "str?"}`). Consumers strip `?` before the operator lookup.
- Operator-lookup rule documented in `grammar`: use `operators_by_type[type]`; `relates_to` → `relation` entry; `object_reference: true` → `object_reference` entry.
- Old verbose per-field format is removed (no verbose mode).
- Preserve all semantic facts from PR #14 (label/help_text, choices, related values, fk_options behavior, sensitive-model exclusion) — only the shape changes.
- Defensiveness unchanged: no DB error may escape `describe_schema_for_llm`.
- Run whole suite: `uv run pytest`. Single test: `uv run pytest <path>::<Class>::<test> -v`. Docs: `uv run mkdocs build --strict`.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: IR + operator legend + normalized `json` renderer

Refactor `djangoql/llm.py` to build an IR and render the new terse JSON. Replaces `describe_field`/`operators_for`/`_examples` and the per-field operator/example/note logic. Rewrites the shape-dependent tests.

**Files:**
- Modify: `djangoql/llm.py`
- Test: `test_project/core/tests/test_llm.py`

**Interfaces:**
- Produces:
  - `describe_schema_for_llm(schema, format='json', max_fk_options=50)` — returns dict for `'json'`.
  - `_build_schema_ir(schema, max_fk_options) -> {'start_model': str, 'models': {label: {name: facts_dict}}}`
  - `_field_ir(name, field, schema, max_fk_options) -> dict` (facts: `type`, `nullable`, optional extras; NO operators/example/note)
  - `_operator_legend() -> dict`, `_render_json(ir) -> dict`, `_json_field(facts) -> str|dict`
  - Relation helpers lose their `note` and their `relation_name` param: `_match_field_entry(related_model, match_field, limit)`, `_match_fields_entry(related_model, match_fields, limit)`, `_examples_entry(related_model, limit)`.

- [ ] **Step 1: Rewrite the affected tests (RED)**

In `test_project/core/tests/test_llm.py`, replace the body of class `DescribeSchemaForLLMTest` (keep `setUp`, `AuthorPickerSchema`, `ExcludeUserSchema` above it) with these tests:

```python
    def test_top_level_keys(self):
        for key in ('start_model', 'grammar', 'operators_by_type',
                    'models', 'examples'):
            self.assertIn(key, self.bundle)

    def test_start_model_is_the_root(self):
        self.assertEqual('core.book', self.bundle['start_model'])

    def test_models_contains_root_and_related(self):
        models = self.bundle['models']
        self.assertIn('core.book', models)
        self.assertIn('auth.user', models)

    def test_operator_legend_is_emitted_once_by_type(self):
        legend = self.bundle['operators_by_type']
        self.assertIn('>', legend['float']['operators'])
        self.assertIn('~', legend['str']['operators'])
        self.assertIn('startswith', legend['str']['operators'])
        self.assertEqual({'=', '!='}, set(legend['bool']['operators']))
        self.assertIn('relation', legend)
        self.assertIn('object_reference', legend)

    def test_grammar_documents_operator_lookup(self):
        self.assertIn('operators_by_type', self.bundle['grammar']['operators'])

    def test_fields_never_repeat_operators_or_examples(self):
        for field in self.bundle['models']['core.book'].values():
            if isinstance(field, dict):
                self.assertNotIn('operators', field)
                self.assertNotIn('example', field)

    def test_plain_scalar_field_is_a_bare_type_string(self):
        # is_published is a non-null bool with no metadata -> bare "bool"
        self.assertEqual('bool',
                         self.bundle['models']['core.book']['is_published'])

    def test_nullable_field_uses_question_mark_suffix(self):
        # published_date is null=True and has no metadata -> "date?"
        self.assertEqual('date?',
                         self.bundle['models']['core.book']['published_date'])
        # rating is a nullable float with no metadata -> "float?"
        self.assertEqual('float?',
                         self.bundle['models']['core.book']['rating'])

    def test_field_with_metadata_is_an_object_with_type(self):
        # name carries verbose_name/help_text -> object, type is 'str'
        name = self.bundle['models']['core.book']['name']
        self.assertEqual('str', name['type'])
        self.assertEqual('Title', name['label'])
        self.assertEqual('The title of the book', name['help_text'])

    def test_choice_field_object_lists_labels(self):
        genre = self.bundle['models']['core.book']['genre']
        self.assertEqual(['Drama', 'Comics', 'Other'], genre['choices'])

    def test_relation_field_object_points_at_related_model(self):
        author = self.bundle['models']['core.book']['author']
        self.assertEqual('auth.user', author['relates_to'])
        self.assertTrue(author['type'].startswith('relation'))

    def test_object_reference_uses_its_operator_class(self):
        bundle = describe_schema_for_llm(AuthorPickerSchema(Book))
        author = bundle['models']['core.book']['author']
        self.assertTrue(author['object_reference'])
        self.assertEqual(['=', '!=', 'in', 'not in'],
                         bundle['operators_by_type']['object_reference']
                         ['operators'])

    def test_grammar_warns_there_is_no_standalone_not(self):
        self.assertIn('negation', self.bundle['grammar'])

    def test_examples_actually_parse(self):
        parser = DjangoQLParser()
        for query in self.bundle['examples']:
            parser.parse(query)
```

Then in class `RelationValuesTest`, update the assertions that read a relation field so they treat it as an object (it always has `relates_to`). Change:
- `test_auto_emits_related_values_for_small_relation`: keep `similar = bundle['models']['core.book']['similar_books']`; assertions `self.assertEqual('name', similar['match_field'])` and the `related_values` set stay valid (relation is an object).
- In every RelationValuesTest test that asserts `self.assertNotIn('related_values', similar)` / `author`, the field is still an object dict, so `assertNotIn` on the key stays correct — no change needed.
- `test_default_match_field_skips_unsuggested_fields`: unchanged (calls `_default_match_field` directly).

Leave `DjangoqlSchemaCommandTest` unchanged for now (it asserts keys/among-keys and JSON validity, which still hold); Task 3 adds the `--format` test.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest test_project/core/tests/test_llm.py::DescribeSchemaForLLMTest -v`
Expected: FAIL (e.g. `KeyError: 'operators_by_type'`, and bare-string assertions fail against today's dict-per-field output).

- [ ] **Step 3: Add the legend, grammar, examples constants and IR builder**

In `djangoql/llm.py`, ADD these (place after the existing constants block, before the helper functions). Keep `OPERATORS_BY_TYPE`, `_EXAMPLE_VALUE_BY_TYPE`, `MAX_SUGGESTED_VALUES`, `MAX_CHOICE_VALUES`, `SENSITIVE_TARGET_APP_LABELS`, `_AUTO`:

```python
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
            'example': 'x {} {}'.format(op, _EXAMPLE_VALUE_BY_TYPE[ftype]),
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
```

- [ ] **Step 4: Strip the note (and unused param) from the relation-value helpers**

Replace `_match_field_entry`, `_match_fields_entry`, `_examples_entry` with these note-free versions, and update their callers in `_relation_values`:

```python
def _match_field_entry(related_model, match_field, limit):
    """Facts for a single identifying field, or {} if nothing fits."""
    if match_field is None:
        return {}
    values = _distinct_values(related_model, match_field, limit)
    if not values:
        return {}
    return {'match_field': match_field, 'related_values': values}


def _match_fields_entry(related_model, match_fields, limit):
    """Facts for several identifying fields, or {} if none fit."""
    values = {}
    for f in match_fields:
        v = _distinct_values(related_model, f, limit)
        if v:
            values[f] = v
    if not values:
        return {}
    return {
        'match_fields': [f for f in match_fields if f in values],
        'related_values': values,
    }


def _examples_entry(related_model, limit):
    """Facts: str(obj) examples for a relation, or {}."""
    examples = _str_examples(related_model, limit)
    if not examples:
        return {}
    return {'related_examples': examples}
```

In `_relation_values`, update the four call sites to drop the `name` argument:
- `return _examples_entry(related_model, limit=None)`
- `return _match_field_entry(related_model, match_field, limit=None)`
- `return _match_field_entry(related_model, spec, limit=max_fk_options)`
- `return _match_fields_entry(related_model, list(spec), limit=max_fk_options)`
- `return _examples_entry(related_model, limit=max_fk_options)`
- final auto: `return _match_field_entry(related_model, match_field, limit=max_fk_options)`

(The `name` parameter of `_relation_values` is still used for the fk_options lookup via `_fk_spec`, so keep it.)

- [ ] **Step 5: Replace `describe_field`/`operators_for`/`_examples` with the IR builder and JSON renderer**

Delete `operators_for` (lines ~82-94), `describe_field` (lines ~331-365), and the `_examples` function (lines ~432-444). Add:

```python
def _field_ir(name, field, schema, max_fk_options):
    """Semantic facts for one field, independent of output format.

    Carries information only — no operators, examples, or notes (those are
    derivable from the type and belong to the renderer's legend).
    """
    ir = {'type': field.type, 'nullable': bool(field.nullable)}
    ir.update(_field_metadata(field))
    if getattr(field, 'object_reference', False):
        ir['object_reference'] = True
    if isinstance(field, RelationField):
        ir['relates_to'] = field.relation
        if schema is not None:
            ir.update(_relation_values(schema, field, name, max_fk_options))
    else:
        choices = _choice_labels(field)
        if choices:
            ir['choices'] = choices
        else:
            options = _field_options(field)
            if options:
                ir['suggested_values'] = options
    return ir


def _build_schema_ir(schema, max_fk_options):
    """Build the format-independent intermediate representation of a schema."""
    return {
        'start_model': schema.model_label(schema.current_model),
        'models': {
            model_label: {
                name: _field_ir(name, field, schema, max_fk_options)
                for name, field in fields.items()
                if field.suggested
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


def _render_json(ir):
    """Render the IR as the normalized JSON description."""
    return {
        'start_model': ir['start_model'],
        'grammar': _GRAMMAR,
        'operators_by_type': _operator_legend(),
        'models': {
            label: {
                name: _json_field(facts) for name, facts in fields.items()
            }
            for label, fields in ir['models'].items()
        },
        'examples': list(_EXAMPLES),
    }
```

- [ ] **Step 6: Rewire `describe_schema_for_llm`**

Replace the whole `describe_schema_for_llm` function with:

```python
def describe_schema_for_llm(schema, format='json', max_fk_options=50):
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
    raise ValueError(
        "format must be 'json' or 'compact', got {!r}".format(format)
    )
```

(The `'compact'` branch is added in Task 2.)

- [ ] **Step 7: Run the rewritten tests (GREEN)**

Run: `uv run pytest test_project/core/tests/test_llm.py -q`
Expected: PASS (DescribeSchemaForLLMTest + RelationValuesTest + the still-unchanged command tests).

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add djangoql/llm.py test_project/core/tests/test_llm.py
git commit -m "$(printf 'refactor: normalize LLM schema JSON (operator legend + terse fields)\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 2: `compact` text renderer

**Files:**
- Modify: `djangoql/llm.py` (add `_render_compact`, `_compact_field`, `_q`, `_COMPACT_HEADER`; wire `format='compact'`)
- Test: `test_project/core/tests/test_llm.py`

**Interfaces:**
- Consumes: `_build_schema_ir` (Task 1), the IR facts shape.
- Produces: `describe_schema_for_llm(schema, format='compact')` returns a `str`; `_render_compact(ir) -> str`.

- [ ] **Step 1: Write the failing tests**

Add a new class to `test_project/core/tests/test_llm.py`:

```python
class CompactFormatTest(TestCase):
    def _bundle(self):
        return describe_schema_for_llm(DjangoQLSchema(Book), format='compact')

    def test_compact_returns_a_string(self):
        self.assertIsInstance(self._bundle(), str)

    def test_header_lists_operators_once(self):
        text = self._bundle()
        # operator hints live in the header, not on every field line
        self.assertIn('Operators', text)
        self.assertIn('start model: core.book', text)

    def test_scalar_line_has_no_operator_tokens(self):
        text = self._bundle()
        line = next(ln for ln in text.splitlines()
                    if ln.strip().startswith('is_published'))
        self.assertIn('bool', line)
        # a plain bool line must not spell out operators
        self.assertNotIn('!=', line)

    def test_nullable_marked_with_question_mark(self):
        text = self._bundle()
        line = next(ln for ln in text.splitlines()
                    if ln.strip().startswith('published_date'))
        self.assertIn('date?', line)

    def test_relation_rendered_with_arrow(self):
        text = self._bundle()
        line = next(ln for ln in text.splitlines()
                    if ln.strip().startswith('author'))
        self.assertIn('-> auth.user', line)

    def test_choice_field_lists_choices(self):
        text = self._bundle()
        line = next(ln for ln in text.splitlines()
                    if ln.strip().startswith('genre'))
        self.assertIn('choices:', line)
        self.assertIn('Drama', line)

    def test_relation_values_render_inline(self):
        Book.objects.create(
            name='Dune', author=User.objects.create(username='ada'),
        )
        Book.objects.create(
            name='Solaris', author=User.objects.create(username='alan'),
        )
        text = describe_schema_for_llm(DjangoQLSchema(Book), format='compact')
        line = next(ln for ln in text.splitlines()
                    if ln.strip().startswith('similar_books'))
        self.assertIn('match name in (', line)
        self.assertIn('"Dune"', line)

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            describe_schema_for_llm(DjangoQLSchema(Book), format='yaml')
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest test_project/core/tests/test_llm.py::CompactFormatTest -v`
Expected: FAIL (`ValueError` for `'compact'`, since Task 1 only handles `'json'`).

- [ ] **Step 3: Add the compact renderer**

In `djangoql/llm.py`, add:

```python
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
    '#   str:             = != ~ !~ startswith endswith (not ...) in  not in'
    '   e.g. name ~ "text"',
    '#   bool:            = !=                                e.g. is_pub = True',
    '#   -> relation:     = None / != None / dot-traverse',
    '#   # object_reference: = != in not in  (match by pk)',
    '# Suffix ? = nullable.  choices: closed set.',
    '',
]


def _q(value):
    """Double-quote a value for the compact rendering."""
    return '"{}"'.format(value)


def _compact_field(name, facts, width):
    """Render one IR field as a single compact line."""
    padded = name.ljust(width)
    type_token = facts['type'] + ('?' if facts.get('nullable') else '')
    if facts.get('object_reference'):
        return '{}  # {} (object_reference)'.format(padded, type_token)
    if facts['type'] == 'relation':
        parts = ['-> {}'.format(facts.get('relates_to', '?'))]
        if 'match_field' in facts:
            vals = ', '.join(_q(v) for v in facts['related_values'])
            parts.append('match {} in ({})'.format(facts['match_field'], vals))
        elif 'match_fields' in facts:
            segs = [
                '{} in ({})'.format(
                    f, ', '.join(_q(v) for v in facts['related_values'][f])
                )
                for f in facts['match_fields']
            ]
            parts.append('match ' + '; '.join(segs))
        elif 'related_examples' in facts:
            ex = ', '.join(_q(v) for v in facts['related_examples'])
            parts.append('examples: ' + ex)
        return '{}  {}'.format(padded, '  '.join(parts))
    parts = [type_token]
    if 'label' in facts:
        label = _q(facts['label'])
        if 'help_text' in facts:
            label += ' — {}'.format(facts['help_text'])
        parts.append(label)
    if 'choices' in facts:
        parts.append('choices: ' + ' | '.join(facts['choices']))
    if 'suggested_values' in facts:
        vals = ', '.join(_q(v) for v in facts['suggested_values'])
        parts.append('values: ' + vals)
    return '{}  {}'.format(padded, '  '.join(parts))


def _render_compact(ir):
    """Render the IR as a terse text block, one line per field."""
    lines = list(_COMPACT_HEADER)
    lines.append('start model: {}'.format(ir['start_model']))
    lines.append('')
    for label, fields in ir['models'].items():
        lines.append('{}:'.format(label))
        width = max((len(n) for n in fields), default=0)
        for name, facts in fields.items():
            lines.append('  ' + _compact_field(name, facts, width))
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'
```

- [ ] **Step 4: Wire the compact branch into `describe_schema_for_llm`**

In `describe_schema_for_llm`, add the compact branch before the `raise`:

```python
    if format == 'json':
        return _render_json(ir)
    if format == 'compact':
        return _render_compact(ir)
    raise ValueError(
        "format must be 'json' or 'compact', got {!r}".format(format)
    )
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest test_project/core/tests/test_llm.py::CompactFormatTest -v`
Expected: PASS.

- [ ] **Step 6: Full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add djangoql/llm.py test_project/core/tests/test_llm.py
git commit -m "$(printf 'feat: add compact text output mode to LLM schema description\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 3: `--format` CLI flag

**Files:**
- Modify: `djangoql/management/commands/djangoql_describe_schema_for_llm.py`
- Test: `test_project/core/tests/test_llm.py` (`DjangoqlSchemaCommandTest`)

**Interfaces:**
- Consumes: `describe_schema_for_llm(schema, format=..., max_fk_options=...)`.
- Produces: command accepts `--format {json,compact}` (default `json`); compact output printed as text.

- [ ] **Step 1: Write the failing test**

Add to `DjangoqlSchemaCommandTest`:

```python
    def test_compact_format_prints_text(self):
        out = self._run('core.Book', '--format', 'compact')
        self.assertIn('start model: core.book', out)
        self.assertIn('-> auth.user', out)
        # compact output is not JSON
        with self.assertRaises(ValueError):
            json.loads(out)

    def test_json_is_the_default_format(self):
        data = json.loads(self._run('core.Book'))
        self.assertIn('operators_by_type', data)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest test_project/core/tests/test_llm.py::DjangoqlSchemaCommandTest -k format -v`
Expected: FAIL (`unrecognized arguments: --format`).

- [ ] **Step 3: Add the `--format` argument**

In `add_arguments`, after the `--max-fk-options` block, add:

```python
        parser.add_argument(
            '--format',
            dest='format',
            choices=['json', 'compact'],
            default='json',
            help='Output format: json (default, machine-readable) or compact '
            '(terse text, smallest for large schemas).',
        )
```

- [ ] **Step 4: Emit the chosen format in `handle`**

Replace the body of `handle` from `bundle = ...` onward with:

```python
        fmt = options['format']
        bundle = describe_schema_for_llm(
            schema,
            format=fmt,
            max_fk_options=options['max_fk_options'],
        )
        if fmt == 'compact':
            self.stdout.write(bundle)
        else:
            indent = options['indent'] or None
            self.stdout.write(
                json.dumps(
                    bundle, indent=indent, ensure_ascii=False, default=str,
                ),
            )
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest test_project/core/tests/test_llm.py::DjangoqlSchemaCommandTest -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add djangoql/management/commands/djangoql_describe_schema_for_llm.py test_project/core/tests/test_llm.py
git commit -m "$(printf 'feat: add --format json/compact to djangoql_describe_schema_for_llm\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

### Task 4: Documentation

**Files:**
- Modify: `docs/llm-schema.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Read the current doc**

Read `docs/llm-schema.md` in full. It currently documents the verbose per-field shape (from PR #14); the whole output section must be rewritten to the normalized shape.

- [ ] **Step 2: Rewrite the format description**

Update the doc to describe:
- The two modes: `describe_schema_for_llm(schema, format='json')` (default, returns a dict) and `format='compact'` (returns text); the `--format {json,compact}` CLI flag.
- The `operators_by_type` legend and the operator-lookup rule from `grammar` (resolve a field's operators by its `type`; `relates_to` → `relation`; `object_reference: true` → `object_reference`).
- Terse field encoding: a field with no extras is a bare `"name": "type"` string; a field with extras is an object with `type` plus informative keys; `?` suffix on the type means nullable; default/empty keys are omitted.
- Keep the existing sections on `label`/`help_text`, `choices`, related values, and `fk_options` (spec table), but update their examples to the new shape.

- [ ] **Step 3: Update the sample outputs**

Replace the sample JSON with a normalized example (operators_by_type legend + a `models` block showing a bare-string field, a `?`-nullable field, a metadata object, a choices object, and a relation object with `match_field`/`related_values`). Add a short `compact` sample block generated to match `_render_compact` (you may run `uv run python test_project/manage.py djangoql_describe_schema_for_llm core.Book --format compact` to get the real shape; note an empty DB shows no related values, so hand-author the related-values line).

- [ ] **Step 4: Build the docs strictly**

Run: `uv run mkdocs build --strict`
Expected: passes, no orphaned pages or broken links.

- [ ] **Step 5: Commit**

```bash
git add docs/llm-schema.md
git commit -m "$(printf 'docs: document normalized json and compact LLM schema formats\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Final verification

- [ ] `uv run pytest -q` — all green.
- [ ] `uv run mkdocs build --strict` — clean.
- [ ] Eyeball both modes:
  - `uv run python test_project/manage.py djangoql_describe_schema_for_llm core.Book --format json --indent 2` — operator legend once at top; `is_published` is `"bool"`; `published_date` is `"date?"`; `name` is an object with `label`/`help_text`; no `operators`/`example` on any field.
  - `uv run python test_project/manage.py djangoql_describe_schema_for_llm core.Book --format compact` — one line per field; `-> auth.user`; `date?`; `genre` shows `choices:`.
