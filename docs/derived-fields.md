# Derived fields

Derived fields are virtual search fields that DjangoQL adds automatically on top of the
fields your model already has. They let you write natural queries like
`written__year >= 2020` or `book__count > 5` without any per-admin boilerplate.

There are two families:

- **Date/time parts** — integer components extracted from a `DateField`, `DateTimeField`,
  or `TimeField` (year, month, day, hour, …), plus `__date` and `__time` extractors for
  `DateTimeField`.
- **Relation aggregates** — `<rel>__count` for every to-many relation, plus
  dot-addressed `<rel>.<numfield>__{sum,avg,min,max}` numeric aggregates.

Both families are **opt-in**. The default `DjangoQLSchema` is unchanged; you enable them
by switching to `ExtrasSchema` or by composing the individual mixins into your own schema.

!!! note "Derived fields are hidden from autocomplete"
    To keep the completion drop-down and the "Unknown field" error readable, all
    derived fields are **hidden from autocomplete** (`suggested=False`) — there can be
    a great many of them. They remain fully usable in queries; you just type them
    yourself. When you reference a field that doesn't exist, the error message lists
    the normal fields and adds a short hint describing the derived-field syntax with
    a couple of real examples for that model.


## Enabling derived fields

The quickest way is to use the pre-built `ExtrasSchema`, which enables both families at
once:

```python
from djangoql.extras import ExtrasSchema
from djangoql.admin import DjangoQLSearchMixin
from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    djangoql_schema = ExtrasSchema
```

`ExtrasSchema` is defined as:

```python
class ExtrasSchema(DatePartsSchemaMixin, AggregateSchemaMixin, DjangoQLSchema):
    ...
```

You can also compose the mixins selectively into your own schema — for example, if you
only want date parts but not aggregates:

```python
from djangoql.extras import DatePartsSchemaMixin
from djangoql.schema import DjangoQLSchema


class MySchema(DatePartsSchemaMixin, DjangoQLSchema):
    pass
```

Or only aggregates:

```python
from djangoql.extras import AggregateSchemaMixin
from djangoql.schema import DjangoQLSchema


class MySchema(AggregateSchemaMixin, DjangoQLSchema):
    pass
```

The schema works identically with the queryset API outside the admin:

```python
from djangoql.extras import ExtrasSchema

books = Book.objects.djangoql("written__year >= 2020", schema=ExtrasSchema)
```


## Date and time parts

`DatePartsSchemaMixin` inspects every `DateField`, `DateTimeField`, and `TimeField` on
the model and generates virtual integer fields for each component that makes sense for
that type.

### Which parts are generated

| Django field type | Generated derived fields |
|---|---|
| `DateField` | `__year` `__month` `__day` `__week_day` `__quarter` `__week` `__iso_year` `__iso_week_day` |
| `DateTimeField` | all date parts above **+** `__hour` `__minute` `__second` **+** `__date` **+** `__time` |
| `TimeField` | `__hour` `__minute` `__second` |

`DateTimeField` is a subclass of `DateField` in Django, so the implementation tests for
`DateTimeField` first and generates the full combined set.

### Integer part examples

All part fields are integers and support `=`, `!=`, `>`, `>=`, `<`, `<=`, `in`, and `not in`:

```
written__year >= 2020
written__month in (6, 7, 8)
written__day = 1
written__quarter = 4
written__week <= 26
written__hour < 9
written__minute = 0
written__second < 30
```

!!! note "`week_day` vs `iso_week_day`"
    Django's `week_day` lookup returns **1 = Sunday … 7 = Saturday** (SQL convention).
    `iso_week_day` returns **1 = Monday … 7 = Sunday** (ISO 8601). Use whichever
    matches your expected numbering:

    ```
    written__iso_week_day in (1, 2, 3, 4, 5)   # Monday–Friday
    written__week_day not in (1, 7)              # not Sunday or Saturday
    ```

### Date and time extract fields (DateTimeField only)

For `DateTimeField` columns, two additional extractor fields are generated:

- `__date` — compare to a date string `"YYYY-MM-DD"`.
- `__time` — compare to a time string `"HH:MM"` or `"HH:MM:SS"`.

```
written__date = "2020-01-01"
written__date >= "2024-06-01"
written__time >= "09:00"
written__time < "17:30:00"
```

These use the same value-type validation as `DateField` and `DateTimeField`; an invalid
string raises a `DjangoQLSchemaError` with a human-readable message.


## Relation aggregates

`AggregateSchemaMixin` adds virtual aggregate fields for every **to-many relation** on
the model: reverse foreign keys (one-to-many) and `ManyToManyField` (both directions).

### Naming

| Aggregate | Field name | Meaning |
|---|---|---|
| Count | `<rel>__count` | number of related rows |
| Sum | `<rel>.<numfield>__sum` | sum of a numeric field across related rows |
| Average | `<rel>.<numfield>__avg` | average |
| Minimum | `<rel>.<numfield>__min` | minimum value |
| Maximum | `<rel>.<numfield>__max` | maximum value |

`<rel>` is the same relation name that DjangoQL already uses for dot-navigation
(e.g. `book`, or the value of `related_name`). `<numfield>` is the name of an
`IntegerField`, `FloatField`, or `DecimalField` on the related model.

!!! note "Count is flat, numeric aggregates use a dot"
    Relation **count** keeps the flat name `<rel>__count`. The **numeric** aggregates
    are addressed through the relation with a dot — `<rel>.<numfield>__sum` — which
    reads consistently with the rest of DjangoQL's dot navigation and keeps the
    field list from exploding. The old flat numeric form
    (`<rel>__<numfield>__sum`) is **no longer accepted**.

### Examples

```
# Count-based (flat)
book__count > 5
book__count = 0

# Numeric aggregates on Book's price and rating fields (dot syntax)
book.price__avg > 30
book.price__sum >= 100
book.rating__min > 3
book.rating__max = 5

# Through a relation hop — author with more than one book
author.book__count > 1

# Numeric aggregate two hops out — sum of ratings of this book's author's books
author.book.rating__sum >= 10
```

### Which relations and fields are included

**Relations:** All to-many — reverse foreign keys (one-to-many) and `ManyToManyField`
in both directions. Forward foreign keys (always 0 or 1 related object) are excluded.
Relations whose reverse accessor is hidden (`related_name='+'`) are also skipped,
because a correlated subquery needs a usable reverse lookup.

**Numeric fields for sum/avg/min/max:** `IntegerField`, `FloatField`, and `DecimalField`
on the related model, excluding primary keys, foreign-key id columns, and
non-editable internal columns. Summing primary keys or FK ids is almost never
meaningful, so they are omitted.

Count does not target a specific field and is generated for every eligible relation.

### How aggregates are computed

Aggregates are implemented as **correlated subqueries** (`Subquery` + `OuterRef`), not
as `JOIN`-based annotations. This means:

- Multiple aggregates in a single query remain independent and produce correct results.
  A JOIN-based approach would multiply rows when several to-many relations are joined
  at once, inflating counts.
- Only the aggregates that actually appear in a query are added as subqueries
  (lazy — no annotation overhead for unused fields).
- Subqueries correlate on indexed foreign-key columns, which Django indexes by default.
- Both the Django admin and the queryset API use the same `apply_search` code path, so
  both surfaces behave identically.

### Empty-set semantics

`<rel>__count` uses `Coalesce(subquery, 0)`, so rows with no related objects compare
correctly:

```
book__count = 0    # matches authors who have written no books
book__count >= 1   # matches authors who have written at least one book
```

`sum`, `avg`, `min`, and `max` return SQL `NULL` for an empty related set (standard
aggregate behavior). `NULL` is excluded from `>` / `<` / `=` comparisons, which is
consistent with how Django handles nullable fields.

!!! note "Numeric aggregate precision"
    All numeric aggregate fields use a float output type in this version. For a
    `DecimalField` source, very large `sum` values may lose sub-unit precision. If
    exact decimal arithmetic is required, consider using a raw queryset annotation
    instead.


## The `suggested` flag

Every `DjangoQLField` has a `suggested` attribute (default `True`) that controls
whether the field appears in the autocomplete / introspection JSON sent to the
completion widget. Setting `suggested=False` hides the field from autocomplete while
keeping it fully usable in queries.

This is different from `suggest_options` (which controls whether the widget suggests
**values** for a field, not whether the field itself is listed).

All derived fields (relation count, date/time parts) ship with `suggested=False`, and
numeric aggregates are never listed at all because they are synthesized on demand. So
by default none of them appear in the completion widget. The example below applies the
same flag to one of your own fields.

### Example: hiding a noisy field from autocomplete

```python
from djangoql.extras import AggregateSchemaMixin
from djangoql.schema import DjangoQLSchema, IntField


class BookSchema(AggregateSchemaMixin, DjangoQLSchema):
    def get_fields(self, model):
        fields = super().get_fields(model)
        # Derived fields are hidden by default; re-show one you use a lot so it
        # appears in autocomplete again.
        for f in fields:
            if getattr(f, 'name', None) == 'review__count':
                f.suggested = True
        return fields
```

You can also pass `suggested=False` when constructing a field instance:

```python
IntField(name='internal_score', suggested=False)
```

The serializer (`DjangoQLSchemaSerializer`) skips any field where `suggested` is
`False`, so it never appears in the widget's drop-down list. Standard model fields
default to `True` and remain visible; generated derived fields default to `False` and
stay hidden (but fully queryable).


## Recipes

**Authors with no published books:**

```
book__count = 0
```

**Books written in summer (June, July, August):**

```
written__month in (6, 7, 8)
```

**Books written on a weekday (ISO: Monday–Friday):**

```
written__iso_week_day in (1, 2, 3, 4, 5)
```

**Books where the average related-book price exceeds a threshold (via author):**

```
author.book.price__avg > 30
```

**Records created in the first quarter:**

```
written__quarter = 1
```

**Books created on a specific date from a `DateTimeField`:**

```
written__date = "2024-01-15"
```
