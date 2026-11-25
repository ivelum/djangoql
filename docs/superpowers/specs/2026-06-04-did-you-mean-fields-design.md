# "Did you mean" suggestions for unknown fields

Date: 2026-06-04
Status: **Approved for implementation.**

## Problem

When a query references a field that does not exist, DjangoQL raises
`Unknown field: <name>. Possible choices are: <every suggested field>`. For a
genuine typo (`author` instead of `authors`) the useful answer is buried in a
long list; the user has to eyeball the whole thing. We want to point at the
*likely intended* field when the mistake looks like a typo, and only fall back
to the full list when the input bears no resemblance to anything (e.g.
`aoijdsofiajs`).

## Approach

Extend the existing seam `DjangoQLSchema._unknown_field_message(model,
model_cls, name_part)` (added in 0.22's derived-fields work). Before composing
the "Possible choices" list, attempt a fuzzy match of `name_part` against the
model's field names:

- **Close match(es) found** → message becomes
  `Unknown field: <name>. Did you mean: <a, b>?` and the full list is **omitted**.
- **No close match** → unchanged behavior: `Unknown field: <name>. Possible
  choices are: <suggested fields>`.

In both branches the `unknown_field_hint(model_cls)` sentence is still appended,
preserving the derived-field hint.

### Matching

New overridable method on `DjangoQLSchema`:

```python
def suggest_field_names(self, name_part, candidates):
    import difflib
    lowered = {c.lower(): c for c in candidates}
    hits = difflib.get_close_matches(
        name_part.lower(), list(lowered), n=3, cutoff=0.6,
    )
    return [lowered[h] for h in hits]
```

- `difflib` is stdlib — **zero new dependencies**.
- `get_close_matches` uses a Ratcliff/Obershelp similarity ratio. Cutoff `0.6`
  separates `author`→`authors` (ratio ≈ 0.92) from gibberish (low ratio, no
  match). Up to `n=3` suggestions, best first.
- Case-insensitive (`Author` matches `author`), returns the real cased names.
- Overridable so projects can tune the cutoff / count or plug in another
  algorithm.

### Candidate pool

All field names of the model (`self.models[model].keys()`), **including hidden
derived fields** (`suggested=False`). This lets `book__cnt` suggest the hidden
`book__count`. The *fallback* "Possible choices" list keeps listing only
`suggested=True` fields (unchanged).

### i18n

Two separate translatable templates. The existing
`Unknown field: {field}. Possible choices are: {choices}` string is kept
**byte-identical** so existing `.po` translations keep working; only the new
`Unknown field: {field}. Did you mean: {suggestions}?` string needs translating.

## Files to change

- `djangoql/schema.py` — add `suggest_field_names()`, rework
  `_unknown_field_message()` to try it first.
- `test_project/core/tests/test_schema.py` — new tests (see below).
- `docs/schema.md` — short note about the suggestions + the overridable hook.
- `CHANGES.rst` — entry under the release section.

## Test plan (TDD)

- close typo → `Did you mean: authors` (e.g. `autho`/`authr` on a Book schema).
- gibberish (`aoijdsofiajs`) → falls back to the full `Possible choices` list,
  no `Did you mean`.
- case-insensitive: `Authr` still suggests `author`.
- all-fields pool: on `ExtrasSchema(User)`, `book__cnt` suggests the hidden
  `book__count`.
- the `unknown_field_hint()` sentence is still appended in the did-you-mean
  branch (where a schema defines one).
- `suggest_field_names` is overridable (subclass changes the result).

## Out of scope

- Suggesting *values* (only field names).
- Correcting operators or whole-expression "did you mean".
- Configurable cutoff via settings — overriding the method covers it.
