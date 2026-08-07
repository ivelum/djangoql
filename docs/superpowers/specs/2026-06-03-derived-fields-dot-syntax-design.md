# Derived fields UX: dot-syntax aggregates, hidden derived fields, better errors

Date: 2026-06-03
Status: A approved for implementation. B and C are handoffs (future work).

## Problem

Enabling `ExtrasSchema` explodes the field list. For every to-many relation and
every numeric field on the related model we generate
`<rel>__<numfield>__{sum,avg,min,max}`, plus 8–11 date/time parts per
date/datetime field. Consequences the user reported:

1. **Autocomplete drowns** in derived fields.
2. The **"Unknown field … Possible choices are: …"** error dumps the entire
   masses of derived field names.
3. The flat aggregate naming `autorzy__kolejnosc__sum` is **inconsistent** with
   djangoql's dot navigation. The user expected `autorzy.kolejnosc__sum`.

## Decisions

- **Numeric aggregates move to dot syntax** (relation traversed by `.`, aggregate
  as a suffix on the numeric field): `autorzy.kolejnosc__{sum,avg,min,max}`.
  The flat form `autorzy__kolejnosc__sum` is **removed** (breaking vs 0.21.0).
- **Relation count stays flat**: `autorzy__count` is kept as-is per the user
  ("`autorzy__count` jest spoko"). Only `Sum/Avg/Min/Max` move to dot.
  (Accepted minor inconsistency: count via `__`, numeric via `.`. Adding
  `autorzy.count` as a synonym later is trivial; not done now.)
- **All derived fields are hidden from autocomplete and from the error's choice
  list**: relation count (`__count`) and date/time parts (`written__year`, …)
  get `suggested=False`; numeric aggregates are never schema fields at all
  (synthesized on demand), so they are inherently absent from both.
- **The "Unknown field" error gains a hint** listing the hidden derived syntaxes
  with 2–3 real examples derived from the actual model.
- Tests in `test_project/core/tests/test_extras.py` are rewritten around
  `ExtrasSchema` + dot syntax; hand-built low-level schemas are dropped except
  where they test field mechanics directly.

## Architecture (A)

Numeric aggregates are a property of *the relation on the parent*, not of the
related model — so they are **synthesized at name-resolution time**, where the
traversed relation is known. This avoids placing ambiguous/contextual fields on
the related model.

### 1. `djangoql/extras.py`

- `AggregateSchemaMixin.get_fields`: still adds `CountField(name='<rel>__count')`
  per usable to-many relation, but with `suggested=False`. **Stops** generating
  the flat `<rel>__<numfield>__<agg>` fields.
- `AggregateField.__init__`: default `suggested=False` (count is always hidden;
  numeric are synthesized and never serialized).
- `AggregateField` gains `relation_hop_in_path` (default `False`). When `True`,
  subquery correlation uses `path[:-1]` (the last path element is the relation
  itself, already encoded in `owner_lookup`); the annotation alias keeps the full
  path for uniqueness.
- `AggregateSchemaMixin.resolve_unknown(model_cls, prev_relation, name_part)`:
  when `prev_relation` is a usable to-many relation and
  `name_part == "<numeric_field>__<agg>"` (`agg ∈ {sum,avg,min,max}`, `<numeric_field>`
  a non-pk, non-fk, editable numeric field on the related model), synthesize the
  matching `Sum/Avg/Min/Max` field with `relation_hop_in_path=True`,
  `owner_lookup`/`related_model` taken from `prev_relation`.
- `AggregateSchemaMixin.unknown_field_hint(model_cls)`: append a sentence with
  real examples (`<rel>__count`, `<rel>.<numfield>__sum`) when the model has
  usable to-many relations.
- `DatePartsSchemaMixin`: date-part field classes get class-level
  `suggested = False`. `unknown_field_hint` appends a date/time-parts sentence
  with a real example (`<datefield>__year`).

### 2. `djangoql/schema.py`

- `resolve_name`: track the previously traversed relation (`prev_relation`) and
  the current model class (`model_cls`). When a part is missing, call
  `self.resolve_unknown(model_cls, prev_relation, name_part)` (default `None`)
  before raising. The error message is built by `_unknown_field_message`, which:
  - lists only `suggested` fields under "Possible choices",
  - appends `self.unknown_field_hint(model_cls)` (default `''`) when non-empty.
- New overridable hooks on `DjangoQLSchema`:
  `resolve_unknown(self, model_cls, prev_relation, name_part) -> field | None`
  and `unknown_field_hint(self, model_cls) -> str`.

### Correlation math (verified)

`get_lookup` and `collect_annotations` both pass `path = parts[:-1]`.

| Query (search model) | path | alias | correlation OuterRef | owner_lookup |
|---|---|---|---|---|
| `book__count` (User) | `[]` | `djangoql__book__count` | `pk` | `author` |
| `book.rating__sum` (User) | `['book']` | `djangoql__book__rating__sum` | `pk` | `author` |
| `author.book__count` (Book) | `['author']` | `djangoql__author__book__count` | `author__pk` | `author` |
| `author.book.rating__sum` (Book) | `['author','book']` | `…author__book__rating__sum` | `author__pk` | `author` |

Count rows keep `relation_hop_in_path=False` (correlate via full `path`);
numeric synthesized rows use `relation_hop_in_path=True` (correlate via
`path[:-1]`).

## Files to change

- `djangoql/schema.py` — `resolve_name` refactor + 2 hooks + `_unknown_field_message`.
- `djangoql/extras.py` — stop flat numeric generation, `suggested=False`,
  `relation_hop_in_path`, `resolve_unknown`, `unknown_field_hint`, date-part
  `suggested=False`.
- `test_project/core/tests/test_extras.py` — rewrite to ExtrasSchema + dot.
- `docs/derived-fields.md` — dot syntax for numeric, count stays flat, hidden +
  error-hint behavior.
- `CHANGES.rst` — new (unreleased) breaking entry. Version bump / publish left to
  the maintainer.

## Test plan (TDD)

- Numeric dot resolves and filters: `book.rating__avg > 5`, `book.price__sum >= N`
  (search User).
- Flat numeric removed: `book__rating__sum` now raises `DjangoQLSchemaError`.
- Count unchanged: `book__count`, `groups__count`, nested `author.book__count`.
- Nested numeric: `author.book.rating__sum` (search Book) correlates correctly.
- Hidden from serializer: `book__count` and date parts absent from serialized
  schema; normal fields present.
- Error hint: unknown field on ExtrasSchema → message lists only suggested
  fields and includes the derived-syntax hint with real examples.
- pk/fk numeric excluded: `book.id__sum` / `book.author__sum` do not resolve;
  `book.price__sum` does.
- Backward-compat: stock `DjangoQLSchema` unchanged (no derived fields, no
  annotations).

---

## Future work — handoff

> B and C now have dedicated specs:
> - **B** → `2026-06-03-autocomplete-value-fields-design.md` (**approved**).
> - **C** → `2026-06-03-empty-result-breakdown-design.md` (design).
>
> The summaries below are kept for context; the dedicated specs are canonical.

### B. Pluggable value suggestions / autocomplete

**Already present:** value suggestions for `choices` fields work today via
`DjangoQLField.suggest_options` + `get_options`, and the
`SuggestionsAPISerializer` + `suggestions_api_url` provide the async-lookup
skeleton (`serializers.py`).

**The gap / idea (user):** a *pluggable* value autocomplete for relation/FK
fields, like Django admin's `autocomplete_fields`. After typing a relation field
and an operator — e.g. `autor.autor =` — the widget would pop an async,
debounced lookup against an endpoint, instead of (or in addition to) static
choices. In admin this is usually configured per field
(`autocomplete_fields` / `get_search_results`), so the natural design is to let a
schema/field declare a pluggable "value provider" (sync choices, or an async URL
backed by an admin autocomplete view), and have the completion widget trigger it
contextually after `<field> <op>`.

Open questions for B's own spec: where the provider is declared (schema field vs
admin option), how it reuses admin autocomplete views/permissions, debounce and
result shape, and how it interacts with the existing `suggestions_api_url`.

### C. "Where the query drops to zero" — empty-result breakdown

**Idea (user):** when a multi-condition query returns nothing, show an elegant
breakdown of how each `AND` step narrows the set (e.g. `doi = x` → 500,
`rok in (…)` → 4, next `AND` → 0) and point at the condition that zeroed it.

**Scope correction (user):** not limited to a flat `AND` chain — the feature
should show *where in the query the data runs out* for an arbitrary boolean
structure (AND/OR/NOT/parentheses).

**Feasibility sketch:** walk the validated AST and evaluate `count()` for
sub-expressions to locate where the result set becomes empty. For an `AND` the
interesting signal is which conjunct(s) zero the set; for an `OR` it is which
branches contribute nothing; nesting composes these. Present it as the query
tree annotated with per-node counts (and a highlight on the node that drops the
count to 0), rather than a single linear narrowing. Cost is one `count()` per
evaluated node, so make it **lazy / on-demand** (only when the overall result is
empty, possibly behind a click), rendered in the admin changelist empty state.

Open questions for C's own spec: exactly which AST nodes to evaluate (every node
vs. leaves + immediate combinations) to stay informative without exploding the
query count; how to render the annotated tree; performance guards on large
tables; and whether to surface it outside the admin too.
