# DjangoQL Derived Fields & Documentation Site — Design

- **Date:** 2026-06-03
- **Branch:** feature-i18n (work to start from here or a fresh branch)
- **Status:** Approved (brainstorming), pending spec review
- **Author:** Michał Pasternak (+ Claude)

## Summary

Add an opt-in family of **derived (virtual) search fields** to DjangoQL so users can
write natural queries without per-admin boilerplate:

- **Date/time parts** — e.g. `written__year >= 2020`, `written__month in (6, 7, 8)`,
  `written__hour < 9`, `written__date = "2020-01-01"`.
- **Relation aggregates** — e.g. `book__count > 5`, `book__price__avg > 30`,
  computed with **correlated subqueries** (correct under multiple aggregates, no
  JOIN row-multiplication), applied **lazily** (only when the field is actually used).

Add a `suggested` flag to fields (control autocomplete visibility, default visible),
and migrate all documentation into a **MkDocs site under `docs/`** (English, logically
organized), superseding the single-file README as the primary documentation source.

## Guiding Principles

1. **Easy and convenient for the user to write.** Field names mirror Django ORM
   conventions (`written__year`, `book__count`, `book__price__avg`) using double
   underscores, so anyone who knows Django guesses them correctly.
2. **Fast and optimal for the database to run.** Aggregates use correlated subqueries
   over indexed FK columns; only the aggregates actually referenced in a query become
   subqueries (lazy). No `GROUP BY` blow-up across the whole queryset.
3. **Backward compatible & opt-in.** Default `DjangoQLSchema` behavior is unchanged.
   Features are enabled by composing schema mixins (or using the provided `ExtrasSchema`).
4. **Isolation.** New field types and schema mixins live in a dedicated module; core
   changes are minimal, additive, and independently testable.

## Non-Goals (v1)

- Auto-generating aggregates beyond count/sum/avg/min/max (e.g. custom expressions).
- JSONField key access and string `__length` transforms (documented as future).
- Deep aggregate paths of 2+ relation hops (supported by the mechanism, but only
  0–1 hop is guaranteed and tested in v1; deeper is "may work").
- A hybrid JOIN-vs-subquery query planner (subquery is the single v1 strategy).
- GitHub Pages / ReadTheDocs deployment automation for the docs site (future).

## Architecture

### Module layout

New module **`djangoql/extras.py`** (opt-in, isolated):

| Class | Responsibility |
|---|---|
| `DatePartField(IntField)` | virtual date/time part, e.g. `written__year` |
| `DateExtractField` | `__date` extraction from DateTimeField (date-typed) |
| `TimeExtractField` | `__time` extraction from DateTimeField (time-typed) |
| `AggregateField` | base for subquery-backed aggregates (alias, lazy annotation, lookup-by-alias) |
| `CountField(AggregateField)` | `<rel>__count` |
| `SumField/AvgField/MinField/MaxField(AggregateField)` | `<rel>__<numfield>__<agg>` |
| `DatePartsSchemaMixin` | expands every Date/DateTime/Time field into part fields |
| `AggregateSchemaMixin` | adds count + numeric aggregates for every to-many relation |
| `ExtrasSchema` | `class ExtrasSchema(DatePartsSchemaMixin, AggregateSchemaMixin, DjangoQLSchema)` |

### Core changes (minimal, additive, backward compatible)

1. **`djangoql/schema.py`**
   - `DjangoQLField`: new attribute `suggested = True`; new method
     `get_annotations(self, path)` returning `{}` by default.
   - `DjangoQLField.__init__`: accept optional `suggested` argument.
   - `DjangoQLSchema.collect_annotations(self, ast)`: walk the AST (same traversal
     shape as `validate`), resolve each `Name`, merge each field's
     `get_annotations(path)`. Returns a dict `{alias: expression}`.

2. **`djangoql/queryset.py`** — `apply_search`, between `validate` and `filter`:
   ```python
   annotations = schema_instance.collect_annotations(ast)
   if annotations:
       queryset = queryset.annotate(**annotations)
   return queryset.filter(build_filter(ast, schema_instance))
   ```
   Both admin (`DjangoQLSearchMixin.get_search_results`) and the queryset API
   (`DjangoQLQuerySet.djangoql`) route through `apply_search`, so both surfaces get
   aggregates for free with no admin-specific code.

3. **`djangoql/serializers.py`** — `DjangoQLSchemaSerializer.serialize` skips fields
   where `not field.suggested`. Default `suggested=True` → no change for existing fields.

### Data flow (lazy guarantee)

```
search → parse → AST → schema.validate(AST)
                         ↓
              schema.collect_annotations(AST)   ← walks ONLY the query's nodes
                         ↓                         → unused aggregate = no subquery
   queryset.annotate(**used_only).filter(build_filter(AST))
```

## Component 1 — Date/Time Part Fields

### Type → parts mapping

| Django field | Generated derived fields |
|---|---|
| `DateField` | `__year __month __day __week_day __quarter __week __iso_year __iso_week_day` |
| `DateTimeField` | all of the above **+** `__hour __minute __second` **+** `__date` **+** `__time` |
| `TimeField` | `__hour __minute __second` |

`isinstance` checks must test `DateTimeField` before `DateField` (DateTimeField is a
subclass of DateField in Django). `TimeField` is a separate type and must be handled
explicitly.

### Field design

`DatePartField` is a thin `IntField`. The field **name equals the ORM lookup**
(`written__year`), so no `get_lookup_name()` override is needed — `get_lookup` builds
`'__'.join(path + ['written__year'])`, which is a valid ORM transform (works directly
and through relation paths like `author.written__year`). Integer comparison operators
(`=, !=, >, >=, <, <=, in`) come for free.

`__date` and `__time` are **not** integers: `DateExtractField` uses date value types
(compare to `"YYYY-MM-DD"`) and `TimeExtractField` uses time value types
(compare to `"HH:MM[:SS]"`), reusing parsing/validation patterns from the existing
`DateField`/`DateTimeField` classes.

### Notes / edge cases

- **`week_day` semantics:** Django returns `1=Sunday … 7=Saturday`, while
  `iso_week_day` returns `1=Monday … 7=Sunday`. Documented explicitly.
- Nullable parts inherit `null` from the base model field.

## Component 2 — Relation Aggregates (subquery-based)

### Naming

| Aggregate | Field name | Meaning |
|---|---|---|
| count | `<rel>__count` | number of related rows |
| sum | `<rel>__<numfield>__sum` | sum of a numeric field across related rows |
| avg | `<rel>__<numfield>__avg` | average |
| min / max | `<rel>__<numfield>__min` / `__max` | extremes |

`<rel>` is the relation name **DjangoQL already exposes** (the related query name,
e.g. `book`, or a `related_name`), for consistency with navigation (`book.name`).

### Which relations / fields

- **Relations:** all to-many — reverse FK (one-to-many) and ManyToMany (both directions).
  Forward FK (always 0/1) is excluded.
- **Numeric fields for sum/avg/min/max:** `IntegerField`, `FloatField`, `DecimalField`
  on the related model, **excluding** primary keys and FK id fields (summing ids is
  meaningless). Count needs no target field.

### Subquery strategy (correctness + performance)

Aggregates are computed as **correlated subqueries** (`Subquery` + `OuterRef`), not
JOIN-based `.annotate(Count(...))`. Rationale:

- Correct regardless of how many to-many aggregates appear in one query (JOIN-based
  aggregation multiplies rows; e.g. `book__count > 5 and tags__count > 2` would be
  wrong with JOINs). Subqueries are independent.
- No `GROUP BY` over the whole queryset.
- Efficient: correlates on indexed FK columns (Django indexes FKs by default).
- Removes the need for any "direct-only" restriction — aggregates reached through a
  relation hop (`author.book__count`) work by pointing `OuterRef` at the joined column.

**Empty-set semantics:** `count` is wrapped in `Coalesce(Subquery(...), 0)` so records
with no related rows compare correctly (`book__count = 0` matches). `sum/avg/min/max`
return SQL `NULL` for empty sets (standard behavior; `NULL` is excluded from
`>`/`<` comparisons).

**Relation types:**
- Reverse FK: subquery filters the related model by the back FK = `OuterRef(<path-to-pk>)`.
- M2M: subquery via the related query name / through relationship (more involved;
  exact ORM construction is decided in the implementation plan).

### `AggregateField` mechanics

- **Alias** (Django annotation aliases cannot contain `__`): derived from the field
  name + path, e.g. `book__count` → `djangoql_book_count`; nested `author.book__count`
  → `djangoql_author_book_count`. Prefixed (`djangoql_`) to avoid collisions.
- `get_annotations(path)` → `{alias: <subquery expression>}`.
- `get_lookup(path, operator, value)` filters by the **alias** directly (the subquery
  already encodes the full path) — it does **not** prepend `path`.
- Value types: `CountField` is integer; `Sum/Avg/Min/Max` accept `int/float/Decimal`.

### Path scope (v1)

0–1 relation hop is fully supported and tested. Deeper paths use the same mechanism
but are documented as "may work, not guaranteed in v1."

## Component 3 — `suggested` flag

- New `DjangoQLField.suggested = True` (default). Controls whether the field appears in
  the autocomplete/introspection JSON.
- `DjangoQLSchemaSerializer.serialize` skips fields with `suggested=False`.
- **Default behavior: all fields visible** (including all date/time parts and all
  aggregates). The flag is an opt-out tool for developers who want to hide specific
  fields; the library hides nothing by default.
- Distinct from the existing `suggest_options` (which controls suggesting **values**
  for a field, not whether the field itself is listed). Both are documented to avoid
  confusion.

## Component 4 — MkDocs Documentation Site

Replace the single-file README as the primary documentation source with a **MkDocs**
site under `docs/`, in English, logically organized.

### Setup

- `mkdocs.yml` at repo root; Material for MkDocs theme.
- MkDocs added as a docs/dev dependency (uv). Local `mkdocs serve` / `mkdocs build`.
- **`docs/superpowers/` must be excluded** from the built site (it holds process
  artifacts like this spec) — via `exclude` pattern or by keeping site sources in a
  dedicated subtree. (Decided in the implementation plan.)
- GitHub Pages/RTD deployment is out of scope for v1 (future).

### Proposed page structure (migrated + reorganized from current README)

- `index.md` — what DjangoQL is, feature overview, screenshots.
- `installation.md` — install, supported versions, settings.
- `language.md` — query language syntax reference (operators, logic, literals, dot
  navigation), with examples.
- `admin.md` — `DjangoQLSearchMixin`, search-mode toggle, completion widget.
- `queryset.md` — `DjangoQLQuerySet` / `apply_search` outside the admin.
- `schema.md` — schema customization: `get_fields`, include/exclude, custom fields,
  suggestion options, `get_lookup_name`/`get_lookup_value`/`get_lookup`.
- `derived-fields.md` — **new**: date/time parts, aggregates (count + sum/avg/min/max),
  naming conventions, `week_day` gotcha, `suggested` flag, enabling via `ExtrasSchema`.
- `i18n.md` — internationalization of error messages (existing feature on this branch).
- `security.md` / `contributing.md` — as applicable.

README.md is trimmed to an overview + a prominent link to the docs site (keep PyPI
badges and the package-name note).

## Error Handling

- Aggregate value-type mismatches raise the existing `DjangoQLSchemaError` via the
  standard `validate()` path.
- Date/time part parsing errors (`__date`/`__time`) reuse the existing date/datetime
  error messages (translated via gettext, consistent with the i18n work).
- Existing admin error surfacing (`djangoql_error_message`) is unchanged.

## Testing Strategy (pytest, `test_project/core/tests/`)

| Area | Assertions |
|---|---|
| Date parts | `written__year/__month/__day/__quarter/__week_day/__week/__iso_year/__iso_week_day` build correct `Q`/SQL |
| Time parts | `__hour/__minute/__second` on DateTimeField **and** TimeField |
| Date/time extract | `written__date = "2020-01-01"`, `written__time >= "09:00"` |
| Count | `book__count > 5` builds a correlated subquery; `= 0` matches empty via Coalesce |
| Sum/Avg/Min/Max | `book__price__avg > 30` etc.; alias has no `__`; lookup filters by alias, not path |
| **Lazy** | a query without an aggregate adds **no** annotation (assert on `qs.query.annotations`) |
| Multiple aggregates | `book__count > 5 and tags__count > 2` returns correct counts (subquery independence) |
| Nested (1 hop) | `author.book__count` works via `OuterRef` on the joined column |
| `suggested` | `suggested=False` removes a field from serializer JSON; default lists all |
| Admin == queryset | both surfaces produce identical results (shared `apply_search`) |
| Backward compat | default `DjangoQLSchema` + serializer behavior unchanged |
| Numeric selection | PK/FK id fields get no sum/avg/min/max; numeric fields do |

## Documentation Deliverables

- MkDocs site as above (the primary deliverable for docs).
- `CHANGES.rst` entry describing derived fields, the `suggested` flag, and the docs move.

## Backward Compatibility

- All core changes are additive with defaults that preserve current behavior
  (`suggested=True`, `get_annotations → {}`, `collect_annotations → {}` for stock fields).
- No changes to the parser, lexer, or AST.
- Existing schemas, admins, and querysets work unchanged; opting in requires switching
  to `ExtrasSchema` (or composing the mixins).

## Future / Out of Scope

- Aggregates beyond count/sum/avg/min/max; custom-expression aggregates.
- `EXISTS`-based optimization for `<rel>__count > 0`.
- JSONField key access; string `__length`.
- Deep (2+ hop) aggregate paths as a guaranteed, tested feature.
- Docs site deployment (GitHub Pages / ReadTheDocs).

## Implementation Sequencing

Implementation is split into **two separate plans**, executed in order:

1. **Feature code** — date/time part fields, subquery-based aggregates, the `suggested`
   flag, core changes, and tests.
2. **Documentation** — MkDocs site under `docs/`, migrating and reorganizing the README.

## Open Questions

- Exact MkDocs exclusion mechanism for `docs/superpowers/` (plugin vs. layout) —
  resolved during the documentation plan.
