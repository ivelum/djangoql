# Per-Model Field Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add declarative `include_fields` / `exclude_fields` per-model allowlist / denylist to `DjangoQLSchema`, so a schema author can expose ONLY certain fields of a model, or all fields EXCEPT certain ones, without overriding `get_fields`.

**Architecture:** Two new class-level dict attributes (model class → list of field names), validated at `__init__`, applied inside the default `get_fields()` via a new `apply_field_rules()` helper. Because every downstream consumer (autocomplete serializer, `describe_schema_for_llm`, query validation) reads from the single `schema.models` dict produced by `introspect()` → `get_fields()`, the filter takes effect everywhere from one integration point.

**Tech Stack:** Python, Django, Django's test runner (`manage.py test`).

## Global Constraints

- Backward compatible: a model absent from both dicts exposes all fields (unchanged).
- Fail loud at `__init__`: same model in both dicts, or an unknown field name, raises `DjangoQLSchemaError` (copy the library's existing `include`/`exclude` strictness).
- Model-level `include`/`exclude` and field-level `include_fields`/`exclude_fields` may coexist; only *within* the field pair is a given model restricted to one side.
- Keys are model **classes** (same convention as the existing `suggest_options` dict).
- Run tests with: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema -v 2`
- Spec: `docs/superpowers/specs/2026-07-05-per-model-field-filtering-design.md`

## File Structure

- `djangoql/schema.py` — MODIFY: `DjangoQLSchema` class. Add `include_fields` / `exclude_fields` class attrs (near existing `include`/`exclude`, line 351-353); add validation block in `__init__` (after the existing include/exclude check, ~line 364); refactor `get_fields` (line 427-437); add `apply_field_rules`.
- `test_project/core/tests/test_schema.py` — MODIFY: add schema fixtures and a `FieldFilteringTest` test case.
- `docs/schema.md`, `README.md`, `docs/llm-schema.md`, `CHANGES.rst` — MODIFY: document the feature.

---

### Task 1: Core allowlist / denylist behavior

**Files:**
- Modify: `djangoql/schema.py` (class attrs at ~line 351-353; `get_fields` at 427-437; new `apply_field_rules`)
- Test: `test_project/core/tests/test_schema.py`

**Interfaces:**
- Consumes: existing `DjangoQLSchema.get_fields(model)`, `serializer.serialize(schema)['models']['core.book']` (dict keyed by field name).
- Produces:
  - `DjangoQLSchema.include_fields: dict[type[Model], list[str]]` (class attr, default `{}`)
  - `DjangoQLSchema.exclude_fields: dict[type[Model], list[str]]` (class attr, default `{}`)
  - `DjangoQLSchema.apply_field_rules(self, model, names) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Add to `test_project/core/tests/test_schema.py` (the fixtures go near the other schema classes at the top, the test case anywhere after them):

```python
class OnlyBookNameSchema(DjangoQLSchema):
    include_fields = {Book: ['name', 'is_published']}


class BookWithoutGenreSchema(DjangoQLSchema):
    exclude_fields = {Book: ['genre', 'price']}


class FieldFilteringTest(TestCase):
    def _book_fields(self, schema):
        return set(serializer.serialize(schema)['models']['core.book'].keys())

    def test_include_fields_is_allowlist(self):
        fields = self._book_fields(OnlyBookNameSchema(Book))
        self.assertEqual(fields, {'name', 'is_published'})

    def test_exclude_fields_is_denylist(self):
        fields = self._book_fields(BookWithoutGenreSchema(Book))
        self.assertNotIn('genre', fields)
        self.assertNotIn('price', fields)
        self.assertIn('name', fields)
        self.assertIn('rating', fields)

    def test_unfiltered_model_keeps_all_fields(self):
        default = self._book_fields(DjangoQLSchema(Book))
        filtered = self._book_fields(BookWithoutGenreSchema(Book))
        self.assertEqual(default - filtered, {'genre', 'price'})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema.FieldFilteringTest -v 2`
Expected: FAIL — `test_include_fields_is_allowlist` gets all Book fields, not just two (`include_fields` attribute is ignored / doesn't exist yet).

- [ ] **Step 3: Add the class attributes**

In `djangoql/schema.py`, in class `DjangoQLSchema`, extend the existing block:

```python
class DjangoQLSchema:
    include = ()  # models to include into introspection
    exclude = ()  # models to exclude from introspection
    include_fields = {}  # {model: [field names]} - expose ONLY these fields
    exclude_fields = {}  # {model: [field names]} - expose all EXCEPT these
    suggest_options = None
```

- [ ] **Step 4: Add `apply_field_rules` and refactor `get_fields`**

Replace the existing `get_fields` method (currently line 427-437) with:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema.FieldFilteringTest -v 2`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full schema suite to check for regressions**

Run: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema -v 2`
Expected: PASS (all existing tests still green)

- [ ] **Step 7: Commit**

```bash
git add djangoql/schema.py test_project/core/tests/test_schema.py
git commit -m "feat: declarative per-model field allowlist/denylist

Add include_fields / exclude_fields to DjangoQLSchema, applied in
get_fields via apply_field_rules()."
```

---

### Task 2: Fail-loud validation at initialization

**Files:**
- Modify: `djangoql/schema.py` (`__init__`, after the existing include/exclude mutual-exclusion check, ~line 361-364)
- Test: `test_project/core/tests/test_schema.py`

**Interfaces:**
- Consumes: `DjangoQLSchemaError` (already imported in schema.py), `include_fields`/`exclude_fields` from Task 1.
- Produces: no new public names; `__init__` now raises `DjangoQLSchemaError` for (a) a model listed in both dicts, (b) an unknown field name in either dict.

- [ ] **Step 1: Write the failing tests**

Add these fixtures and tests to `test_project/core/tests/test_schema.py`:

```python
class ConflictingFieldRulesSchema(DjangoQLSchema):
    include_fields = {Book: ['name']}
    exclude_fields = {Book: ['genre']}


class TypoFieldSchema(DjangoQLSchema):
    include_fields = {Book: ['naem']}


class FieldFilteringValidationTest(TestCase):
    def test_same_model_in_both_dicts_raises(self):
        with self.assertRaises(DjangoQLSchemaError):
            ConflictingFieldRulesSchema(Book)

    def test_unknown_field_name_raises_and_is_named(self):
        with self.assertRaises(DjangoQLSchemaError) as ctx:
            TypoFieldSchema(Book)
        self.assertIn('naem', str(ctx.exception))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema.FieldFilteringValidationTest -v 2`
Expected: FAIL — no error raised (both schemas initialize fine because validation doesn't exist yet).

- [ ] **Step 3: Add the validation block**

In `djangoql/schema.py`, in `__init__`, immediately after the existing block:

```python
        if self.include and self.exclude:
            raise DjangoQLSchemaError(
                _('Either include or exclude can be specified, but not both'),
            )
```

insert:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema.FieldFilteringValidationTest -v 2`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full schema suite**

Run: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add djangoql/schema.py test_project/core/tests/test_schema.py
git commit -m "feat: validate include_fields/exclude_fields at schema init

Raise DjangoQLSchemaError when a model appears in both dicts or when a
listed field name does not exist on the model."
```

---

### Task 3: Relation-traversal blocking and LLM-description consistency

Proves the single-source-of-truth claim end to end: filtering a relation name both blocks the `.` traversal and drops the unreachable related model, and the same filter trims the `describe_schema_for_llm` output.

**Files:**
- Test only: `test_project/core/tests/test_schema.py` (no production changes — this behavior emerges from Task 1; these are regression guards for the two most important consequences).

**Interfaces:**
- Consumes: `OnlyBookNameSchema` / `BookWithoutGenreSchema` from Task 1; `DjangoQLParser` (already imported in test_schema.py); `describe_schema_for_llm` (new import).

- [ ] **Step 1: Add the import**

At the top of `test_project/core/tests/test_schema.py`, add:

```python
from djangoql.llm import describe_schema_for_llm
```

- [ ] **Step 2: Write the failing/guard tests**

Add to `test_project/core/tests/test_schema.py`:

```python
class FieldFilteringConsequencesTest(TestCase):
    def test_filtered_relation_drops_related_model(self):
        # OnlyBookNameSchema keeps only Book.name, dropping the `author` FK,
        # so User must never be introspected.
        models = serializer.serialize(OnlyBookNameSchema(Book))['models']
        self.assertEqual(set(models), {'core.book'})
        self.assertNotIn('auth.user', models)

    def test_filtered_relation_blocks_traversal(self):
        schema = OnlyBookNameSchema(Book)
        ast = DjangoQLParser().parse('author.username = "x"')
        with self.assertRaises(DjangoQLSchemaError):
            schema.validate(ast)

    def test_llm_description_respects_field_filter(self):
        description = describe_schema_for_llm(BookWithoutGenreSchema(Book))
        book_fields = description['models']['core.book']
        self.assertNotIn('genre', book_fields)
        self.assertNotIn('price', book_fields)
        self.assertIn('name', book_fields)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd test_project && ../.venv/bin/python manage.py test core.tests.test_schema.FieldFilteringConsequencesTest -v 2`
Expected: PASS (3 tests) — behavior already exists from Task 1; these lock it in.

Note: if `test_filtered_relation_drops_related_model` unexpectedly fails because another retained relation reaches User, re-check that `OnlyBookNameSchema` keeps only `name`. It should not, so all relations are dropped.

- [ ] **Step 4: Run the full test suite (all apps) to confirm no wider regressions**

Run: `cd test_project && ../.venv/bin/python manage.py test -v 1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add test_project/core/tests/test_schema.py
git commit -m "test: lock in relation-block and LLM-description filtering

Filtering a relation name drops the related model and blocks traversal;
the same filter trims describe_schema_for_llm output (one source of truth)."
```

---

### Task 4: Documentation

**Files:**
- Modify: `docs/schema.md` (the "DjangoQL Schema" section, ~line 3-31)
- Modify: `README.md` (schema-limiting description)
- Modify: `docs/llm-schema.md`
- Modify: `CHANGES.rst`

**Interfaces:**
- Consumes: the finished feature. No code.

- [ ] **Step 1: Document `include_fields` / `exclude_fields` in `docs/schema.md`**

In `docs/schema.md`, after the existing schema example and its bullet list (the block ending around line 31 that explains `exclude`/`include` and the `get_fields` override), add:

````markdown
### Declarative per-model field filtering

Instead of overriding `get_fields()` and branching on the model, you can limit
fields declaratively with `include_fields` (an allowlist) or `exclude_fields`
(a denylist), keyed by model class:

```python
from djangoql.schema import DjangoQLSchema


class UserQLSchema(DjangoQLSchema):
    include_fields = {
        Group: ['name'],          # expose ONLY these fields of Group
    }
    exclude_fields = {
        User: ['password_hash'],  # expose all fields of User EXCEPT these
    }
```

Rules:

- A model listed in `include_fields` exposes **only** the named fields.
- A model listed in `exclude_fields` exposes **all fields except** the named ones.
- A model in neither dict exposes all fields (the default).
- A model may appear in `include_fields` **or** `exclude_fields`, not both.
- Unknown field names raise `DjangoQLSchemaError` when the schema is created,
  so typos surface immediately.

Filtering a relation field (for example dropping `author` from a `Book` schema)
also removes that traversal — you can no longer query `author.username`, and
the related model is not introspected unless another retained relation reaches
it. Model-level `include`/`exclude` and field-level
`include_fields`/`exclude_fields` can be combined in the same schema.
````

- [ ] **Step 2: Mention the new options in `README.md`**

Find the schema-limiting paragraph in `README.md` (search for `get_fields` or `exclude`) and add a sentence after it:

```markdown
You can also limit fields declaratively per model with the `include_fields`
(allowlist) and `exclude_fields` (denylist) schema attributes, instead of
overriding `get_fields()`. See the [schema docs](docs/schema.md) for details.
```

- [ ] **Step 3: Note the LLM-description effect in `docs/llm-schema.md`**

At the end of `docs/llm-schema.md`, add:

```markdown
## Field filtering also trims the description

`describe_schema_for_llm` reads the same introspected schema as autocomplete
and query validation. Any field removed via `include_fields` / `exclude_fields`
(see [schema docs](schema.md)) is therefore absent from the LLM description as
well — there is no separate "visible to the LLM but not to autocomplete" state.
```

- [ ] **Step 4: Add a changelog entry to `CHANGES.rst`**

Add a new entry at the top of the unreleased/next-version section of `CHANGES.rst`:

```rst
- Added ``include_fields`` and ``exclude_fields`` schema attributes for
  declarative per-model field allowlists / denylists, as an alternative to
  overriding ``get_fields()``. Field filtering also trims the autocomplete
  suggestions, the query validation surface, and the ``describe_schema_for_llm``
  output.
```

- [ ] **Step 5: Verify docs build / render (if mkdocs is configured)**

Run: `../.venv/bin/python -m mkdocs build 2>/dev/null && echo "mkdocs OK" || echo "mkdocs not available - skipping (manual review of markdown)"`
Expected: either `mkdocs OK` or the skip message. If skipped, eyeball the edited markdown for correct formatting.

- [ ] **Step 6: Commit**

```bash
git add docs/schema.md README.md docs/llm-schema.md CHANGES.rst
git commit -m "docs: document include_fields / exclude_fields field filtering"
```

---

## Self-Review

**Spec coverage:**
- API surface (`include_fields`/`exclude_fields`, model-class keys, empty default) → Task 1 ✓
- Resolution rules (allowlist / denylist / passthrough) → Task 1 ✓
- Relation semantics (traversal block + related model dropped) → Task 3 ✓
- Integration point in `get_fields` covering autocomplete + LLM + validation → Task 1 (get_fields) + Task 3 (LLM/validation guard tests) ✓
- Validation: same model both dicts → Task 2 ✓
- Validation: unknown field name → Task 2 ✓
- Coexistence with `include`/`exclude` → covered by leaving those untouched; documented in Task 4 ✓
- Backward compatibility (unfiltered model whole) → Task 1 `test_unfiltered_model_keeps_all_fields` ✓
- Docs (schema.md, README.md, llm-schema.md, CHANGES.rst) → Task 4 ✓
- Testing list from spec → mapped across Tasks 1-3 ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; every test step shows full test; commands have expected output. ✓

**Type consistency:** `include_fields`/`exclude_fields` are dicts keyed by model class throughout; `apply_field_rules(model, names)` signature matches its one call site in `get_fields`; `describe_schema_for_llm(schema)['models']['core.book']` returns a dict keyed by field name (verified against the actual output); `serializer.serialize(schema)['models']['core.book']` likewise. ✓
