# Object-reference autocomplete in the example project — design

Date: 2026-06-04
Status: approved (revised after discovering the library feature already exists)

## Key discovery

The reusable field this was going to build **already exists and is tested** in
`djangoql/extras.py`:

- `AutocompleteField(StrField)` — value field whose suggestions come from a
  pluggable provider (`url` endpoint, `queryset`/`get_queryset`, or subclass),
  formatted `"<label> [<id>]"`; `get_lookup_value` parses the trailing `[<int>]`
  and filters by pk. Supports `lookup_name` (redirect the filter to a real FK
  column), `search_fields`, `label`, `id_of`, `limit`, and an `icontains`
  free-text fallback when no `[id]` is present.
- `AutocompleteSchemaMixin` — declare `autocomplete = {Model: {name: config}}`;
  it builds the field via `get_field_instance`.

`test_project/core/tests/test_autocomplete.py::RelAndPickerCoexistTest` already
proves the exact requested behaviour: `author__rel` (a picker, `lookup_name=
'author'`) coexisting with the `author` relation, both usable in one query.

So there is **no new library code**. The work is: (1) prerequisite UI bug fixes,
(2) wire the existing feature into `example_project`.

## Goal

In `example_project` (admin + standalone demo), expose, on `Book`:

- `author.name`, `author.country.name`, … — relation traversal (already works).
- `author__rel = "John Smith [4290]"` — NEW here: picker over real `Author`
  rows, filtering `Book.author_id` by pk. Coexists with the relation.

## Prerequisite fixes (must land first — the picker is invisible without them)

1. **Completion → highlight repaint (admin + demo).**
   `DjangoQL.prototype.selectCompletion` assigns `textarea.value` without firing
   an `input` event, so the highlight overlay (`highlight.js`, repaints on
   `input`) never updates — inserted suggestions stay transparent
   ("white-on-white"). Fix at the shared source `completion-widget/index.js`:
   wrap `selectCompletion` to dispatch a bubbling `input` event after it runs.
   Reflect the same change in the committed bundle
   `djangoql/static/djangoql/js/completion.js` (surgical patch; `index.js` stays
   the source of truth so a future `yarn build` regenerates it). Fixes admin and
   demo at once.

2. **Demo popup styling.**
   `example_project` restyled only the highlight overlay, never
   `.djangoql-completion`, so the popup shows light `--ink` text on the default
   white box — unreadable. Add dark-theme `.djangoql-completion` styling
   (background, text, hover/active, border, shadow, z-index, small gap) in
   `demo.css`, loaded so it wins over `completion.css`.

3. **Demo hint** teaches relation **dots** (`author.country.name`) and the new
   `author__rel` picker, so users don't reach for Django's `__` lookups.

## Wiring the existing feature into `example_project`

### `example_project/library/schema.py` (new)

```python
from djangoql.extras import AutocompleteSchemaMixin
from djangoql.schema import DjangoQLSchema
from .models import Author, Book


class BookSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    autocomplete = {
        Book: {
            'author__rel': {
                'lookup_name': 'author',  # filter the real FK column
                'queryset': lambda s: Author.objects.filter(
                    name__icontains=s
                ).order_by('name'),
                'search_fields': ['name'],
                'label': str,
            },
        },
    }

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model is Book:
            fields.append('author__rel')
        return fields
```

The `queryset` provider needs no request, so it works for both the admin
(live search via the suggestions endpoint) and the standalone demo (inline
snapshot via `get_options('')` in the plain serializer).

### `example_project/library/admin.py`

`BookAdmin.djangoql_schema = BookSchema`. The mixin's existing admin URLs
(`introspect/`, `suggestions/`) then serve `author__rel` live.

### `example_project/library/views.py`

Use `BookSchema` for both the embedded introspections
(`DjangoQLSchemaSerializer().serialize(BookSchema(Book))`) and `apply_search(qs,
query, BookSchema)`.

### `example_project/library/templates/library/demo.html`

Update the hint paragraph to mention dot-traversal and the `author__rel` picker.

## Testing

- The library feature is already covered by `test_autocomplete.py`. No new
  library tests.
- `example_project` has no test suite; verification is manual (browser):
  - Admin: type `author`, pick `country`, confirm the inserted text is now
    visible and coloured; pick a value (e.g. `None`) and confirm it is visible.
  - Admin & demo: type `author__rel = ` and confirm the popup lists
    `"<name> [<id>]"`; pick one and confirm the query filters to that author's
    books.
  - Demo: confirm the popup is legible (dark theme) and typing/selection
    highlights.

## Risks / decisions

- Demo suggestions are an inline snapshot (plain serializer); the admin is live.
  Acceptable for a demo over a small Authors table.
- Bundle is hand-patched to avoid a noisy/networked `yarn` rebuild; `index.js`
  remains the source of truth.
