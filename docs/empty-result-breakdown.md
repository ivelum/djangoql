# Empty-result breakdown

When a multi-condition query returns **zero rows**, it's often not obvious *why*.
For a single condition (`doi = "x"`) it's clear — nothing matches. But for
`genre = 1 and rating = 5 and published_date = "1900-01-01"` the user wants to
know **where in the query the data runs out**: which condition (or combination
of conditions) collapses the result to nothing.

The empty-result breakdown answers that question. It walks the validated query
tree, runs one `count()` per sub-expression against the base queryset, and
points at the node where the count drops to zero.

It works for an **arbitrary boolean structure** (`and` / `or` / parentheses),
not just a flat `and` chain.


## In the admin

The breakdown is wired into `DjangoQLSearchMixin` and needs no configuration. When
a valid DjangoQL search returns no rows, the changelist shows a warning that
renders the query as a condition tree with per-node counts and highlights the
node where the data runs out, for example:

```
genre = 1                         2
and rating = 5                    2
and published_date = "1900-01-01" 0   ← no data from here on
```

It is **lazy**: the extra `count()` queries run only when the result set is
actually empty, so a normal (non-empty) search never pays for them.

You can tune or disable it per `ModelAdmin`:

```python
from djangoql.admin import DjangoQLSearchMixin
from django.contrib import admin

from .models import Book


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    # Turn the breakdown off entirely (no extra queries on empty results):
    djangoql_explain_empty = True
    # Cost guard: max AST nodes counted before the breakdown is truncated to
    # the top-level conditions (see "Cost guard" below).
    djangoql_explain_empty_max_nodes = 50
```


## Queryset API

The same logic is available as a standalone helper so you can render the
breakdown yourself (outside the admin, in an API, etc.):

```python
from djangoql.breakdown import explain_empty

tree = explain_empty(
    Book.objects.all(),
    'genre = 1 and rating = 5',
)
```

`explain_empty` returns `None` unless there is an active search **and** the
overall result is empty — the breakdown only applies to the zero-rows case.
Otherwise it returns a tree of plain dicts:

```python
{
    'text': '(genre = 1) and (rating = 5)',
    'count': 0,
    'role': 'killer_and',
    'children': [
        {'text': 'genre = 1', 'count': 2, 'role': 'leaf', 'children': []},
        {'text': 'rating = 5', 'count': 2, 'role': 'leaf', 'children': []},
    ],
}
```

Each node carries:

- `text` — a readable label reconstructed from the query tree.
- `count` — rows matching that sub-expression on its own, against the base
  queryset.
- `role` — what the node represents (see below).
- `children` — child nodes (empty for leaves).

If a derived/aggregate field (e.g. `book__count`) is referenced, its annotations
are applied before counting, so the helper works with `ExtrasSchema` too:

```python
from djangoql.extras import ExtrasSchema

tree = explain_empty(
    User.objects.all(),
    'book__count > 100 and is_staff = True',
    schema=ExtrasSchema,
)
```


## Node roles

| `role`            | Meaning                                                              |
| ----------------- | ------------------------------------------------------------------- |
| `leaf`            | A single comparison (`Name <op> value`).                            |
| `and`             | An `AND` node whose count is non-zero.                              |
| `or`              | An `OR` node whose count is non-zero.                              |
| `killer_and`      | An `AND` whose count is **zero** — this is where the data runs out. |
| `dead_or_branch`  | A branch of an `OR` that matches **zero** rows on its own.           |

A `killer_and` is the key signal: each side may individually match rows, yet
their intersection is empty. A `dead_or_branch` flags the parts of an `OR` that
never contribute, even when the `OR` as a whole still matches something.


## Cost guard

The breakdown costs one `count()` per evaluated node. Typical queries are small,
but a pathological query could be large, so the walk is bounded by a **max node
budget** (`max_nodes`, default 50). If the query exceeds the budget, only the
top-level conditions are counted and the returned tree is marked
`truncated=True` (and the admin warning says so) — there is no silent cap.

```python
tree = explain_empty(qs, very_large_search, max_nodes=20)
if tree and tree.get('truncated'):
    ...  # only the top-level conditions were evaluated
```


## Labels

Node labels are reconstructed from the parsed query tree rather than sliced from
the original search string (the parser does not expose per-node source spans).
The rendering is stable and unambiguous; it may differ cosmetically from what
you typed (e.g. normalized spacing, explicit parentheses around grouped nodes).
