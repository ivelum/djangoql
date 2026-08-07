# Design: declarative per-model field filtering

Date: 2026-07-05
Status: approved

## Problem

`DjangoQLSchema` already lets you drop **whole models** from introspection via
the class-level `include` / `exclude` tuples. There is no *declarative* way to
limit which **fields** of a given model are exposed. Today the only lever is to
override `get_fields(model)` and branch imperatively on the model
(`if model is Author: return [...]`), which is verbose and easy to get wrong
once several models need trimming.

Users want, per related (or root) model, either:

- an **allowlist**: expose ONLY these fields (e.g. `name`, `short`, `id`), or
- a **denylist**: expose all fields EXCEPT these.

## Solution overview

Two new class-level attributes on `DjangoQLSchema`, mirroring the existing
`include` / `exclude` pair but operating at the field level and keyed by model
class (the same convention already used by `suggest_options`):

```python
class MySchema(DjangoQLSchema):
    include_fields = {
        Author: ['name', 'id', 'short'],   # ONLY these fields
    }
    exclude_fields = {
        Book: ['internal_notes', 'secret'], # all fields EXCEPT these
    }
```

Both default to empty dicts, so existing schemas are unaffected.

### Resolution rules (per model)

For each model reached during introspection:

1. model is a key in `include_fields` → keep **only** the listed field names
   (allowlist).
2. model is a key in `exclude_fields` → keep **all except** the listed names
   (denylist).
3. model in neither → keep **all fields** (unchanged, backward compatible).

A model that appears in neither dict passes through whole — filtering is opt-in
per model.

### Relation semantics (a consequence, not a separate option)

Relation fields are ordinary fields addressed by name. If a relation name is
filtered out (e.g. `Author` allowlists only `['name', 'id']`, dropping
`country`), then:

- the `author.country...` traversal is no longer possible, and
- the `Country` model is not pulled into introspection at all, unless some other
  retained relation still reaches it.

This is intentional: one list governs both a field's visibility and, for
relations, its traversability. There is deliberately no "visible but not
traversable" or "traversable but hidden" middle state.

## Integration point

Filtering is applied inside the default `get_fields()` via a new helper
`apply_field_rules(model, names)`:

```python
def get_fields(self, model):
    names = [f.name for f in model._meta.get_fields() if f.name != 'password']
    return sorted(self.apply_field_rules(model, names))

def apply_field_rules(self, model, names):
    only = self.include_fields.get(model)
    if only is not None:
        return [n for n in names if n in only]
    excluded = self.exclude_fields.get(model)
    if excluded is not None:
        return [n for n in names if n not in excluded]
    return names
```

**Why `get_fields`, not `introspect` or the serializer:** the filter runs on
field *names* before field instances are built and before a relation's
`related_model` is appended to the BFS open set. A filtered-out relation
therefore never triggers traversal — the traversal block is free, with no extra
code.

**Why this covers the LLM description too:** every downstream consumer reads from
the single `schema.models` dict produced by `introspect()` → `get_fields()`:

- autocomplete serialization (`serializers.py`),
- the LLM schema description `describe_schema_for_llm` (`llm.py` iterates
  `schema.models`; its `_meta.get_field(name)` calls only pull metadata for
  names already present),
- query validation (`resolve_name` → `self.models`).

So a single integration point makes a hidden field hidden *everywhere and
consistently* — it cannot be suggested, described to an LLM, JSON-serialized, or
queried.

**Interaction with a full `get_fields` override:** overriding `get_fields`
entirely bypasses the rules (the author takes control), but the override may call
`self.apply_field_rules(model, names)` itself, so the two mechanisms compose.

## Validation (fail loud, at initialization)

In `__init__`, alongside the existing `include` / `exclude` mutual-exclusion
check:

1. **Same model in both `include_fields` and `exclude_fields`** →
   `DjangoQLSchemaError`: "Either include_fields or exclude_fields can be
   specified for {model}, but not both".
2. **Unknown field name** on any list (typo) → `DjangoQLSchemaError` naming the
   offending names, checked against `{f.name for f in model._meta.get_fields()}`.

Rationale: matches the library's fail-loud style; `include` / `exclude` are
already strict, and catching typos at startup beats silently exposing nothing.

## Coexistence with `include` / `exclude`

Model-level `include` / `exclude` and field-level `include_fields` /
`exclude_fields` operate at different layers and may be used together in the same
schema. (Only *within* the field pair is a given model restricted to one side.)

## Testing

Add to `test_project/core/tests/test_schema.py`:

- allowlist: model in `include_fields` exposes only listed fields; others absent.
- denylist: model in `exclude_fields` exposes all but listed fields.
- unfiltered model still exposes all fields (backward compatibility).
- filtering a relation name blocks traversal and drops the unreachable related
  model from `schema.models`.
- `include_fields` + `exclude_fields` on the SAME model → `DjangoQLSchemaError`.
- unknown field name in either dict → `DjangoQLSchemaError` naming it.
- root model filtering works (rules apply to any model, not just related).
- the filtered field is absent from `describe_schema_for_llm` output (proves the
  single-source-of-truth claim end to end).

## Documentation to update

- `docs/schema.md` — "DjangoQL Schema" section: document `include_fields` /
  `exclude_fields` as the declarative alternative to overriding `get_fields`.
- `README.md` — mention the new options where schema limiting is described.
- `docs/llm-schema.md` — note that field filtering also trims the LLM
  description (same source of truth).
- `CHANGES.rst` — changelog entry for the new feature.

## Out of scope (YAGNI)

- Per-field visibility flags beyond include/exclude (e.g. read-only, LLM-only).
- Wildcards / glob patterns in field lists.
- Filtering by field *type* rather than name.
