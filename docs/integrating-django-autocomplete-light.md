# Integrating django-autocomplete-light

DjangoQL can suggest **values** for `choices` fields and for string columns out of the
box. The **autocomplete value field** lets a field's value suggestions come from an
arbitrary source — most usefully an existing
[django-autocomplete-light (DAL)](https://django-autocomplete-light.readthedocs.io/)
endpoint your project already has — so a user can *pick an object* (e.g. an author) and
filter by it, without writing a new endpoint and without forking the completion widget.

The user picks a row from autocomplete; the resulting query filters **unambiguously by the
object's primary key**, even across tens of thousands of rows with duplicate display
names.

!!! note "Server-side only"
    This feature is entirely server-side. There are **no JavaScript changes**. The
    completion widget is the upstream `djangoql-completion` package and is not modified.
    It inserts the chosen suggestion verbatim as a quoted string and shows exactly what it
    inserts, so the server fully controls the inserted text.

## How it works

Suggestions are formatted as `"<label> [<id>]"`, for example:

```
Jan Kowalski [49990]
```

When the user picks that row, the widget inserts the whole string. The
`AutocompleteField` parses the trailing `[<id>]` back to an integer primary key and filters
`<field> = pk`. The embedded `[id]` is visible in the drop-down and in the query — that is
accepted by design and is what makes the match unambiguous.

If the user types free text **without** a bracketed id (e.g. `author = "kowal"`), the field
falls back to an `icontains` lookup over its `search_fields`, so a partially-typed value
still filters.

Because the field exposes a ForeignKey **as a value picker**, under that field name you
filter by the related object — you do not traverse into `author.username`. If you need
both, expose the relation under a second field name.

## Three providers

Suggestions can come from one of three providers (priority high → low):

1. **`url`** — an existing autocomplete endpoint (a URL name or a local path). It is
   resolved and called **in-process** with the current request.
2. **`queryset` / `get_queryset`** — a queryset or a `search -> queryset` callable.
   DAL-agnostic, full control.
3. **A subclass override** of `get_options()` / `format_label()` / `get_id()`.

### 1. URL provider (reuse a DAL endpoint)

Point the field at a DAL endpoint by its URL name (or local path). DjangoQL resolves the
URL and calls the view **in-process** with the **current authenticated request** — its
`GET` parameter `q` (configurable via `search_param`) is set to the search term. This
reuses the DAL view's queryset, permissions, and per-user filtering for free, with no
network round-trip and no cookie forwarding.

```python
from django.contrib.auth.models import User
from djangoql.extras import AutocompleteField
from djangoql.schema import DjangoQLSchema

from .models import Record


class RecordSchema(DjangoQLSchema):
    def get_field_instance(self, model, field_name):
        if model is Record and field_name == 'author':
            return AutocompleteField(
                model=model,
                name='author',
                url='autocomplete-author',   # a DAL url name (or '/path/')
                search_fields=['last_name'], # used for the free-text fallback
            )
        return super().get_field_instance(model, field_name)
```

The endpoint must return Select2 JSON, exactly like DAL does:

```json
{"results": [{"id": 42, "text": "Jan Kowalski"}], "pagination": {"more": false}}
```

DjangoQL maps `results[]` to `"<text> [<id>]"` (HTML tags in `text` are stripped).

### 2. Queryset provider

For full control without DAL, supply a queryset or a `search -> queryset` callable:

```python
AutocompleteField(
    model=Record,
    name='reviewer',
    queryset=lambda s: User.objects.filter(
        is_active=True, last_name__icontains=s
    ).order_by('last_name')[:50],
    search_fields=['last_name'],
    label=lambda u: f'{u.first_name} {u.last_name}',  # default: str(obj)
    id_of=lambda u: u.pk,                              # default: obj.pk
)
```

### 3. Subclass override

For anything else, subclass and override the small overridable methods —
`get_options(search)`, `get_queryset(search)`, `format_label(obj)`, `get_id(obj)`,
`parse_id(value)`:

```python
class CityAutocompleteField(AutocompleteField):
    def get_queryset(self, search):
        return City.objects.filter(name__istartswith=search)

    def format_label(self, obj):
        return f'{obj.name}, {obj.country}'
```

## The `AutocompleteSchemaMixin` map

Instead of overriding `get_field_instance` by hand, declare an `autocomplete` map of
`{Model: {field_name: config}}`. Each config is a dict of `AutocompleteField` kwargs, an
`AutocompleteField` instance, or a callable `(model, field_name) -> AutocompleteField`:

```python
from djangoql.extras import AutocompleteSchemaMixin
from djangoql.schema import DjangoQLSchema


class RecordSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    autocomplete = {
        Record: {
            'author':   {'url': 'autocomplete-author',
                         'search_fields': ['last_name']},
            'reviewer': {'queryset': lambda s: User.objects.filter(
                            is_active=True, last_name__icontains=s)[:50],
                         'search_fields': ['last_name']},
        },
    }
```

The mixin works standalone, and is also included in the batteries-included
[`ExtrasSchema`](derived-fields.md), so the derived-fields schema picks it up too.

## Request threading

When the widget fetches suggestions asynchronously, `SuggestionsAPIView` threads the
current request into the field via a `set_request(request)` hook before calling
`get_options()`. The URL provider uses that bound request to call the DAL view in-process,
so the view sees the same authenticated user and session. Base fields don't define
`set_request` and are unaffected.

This makes per-user / per-request filtering reachable for free: a DAL view that already
filters by `request.user` keeps doing so when called through the autocomplete field.

## Configuration reference

| kwarg | default | meaning |
| --- | --- | --- |
| `url` | `None` | URL name or local path of a Select2-JSON endpoint |
| `queryset` | `None` | a queryset or a `search -> queryset` callable |
| `get_queryset` | `None` | a `search -> queryset` callable (alternative to `queryset`) |
| `search_fields` | `[]` | fields on the related model for the free-text fallback |
| `label` | `str` | callable `obj -> str` for the display label |
| `id_of` | `obj.pk` | callable `obj -> id` for the embedded id |
| `lookup_name` | `None` | real model field to filter on (default: the field's own name); lets a picker live under a second name like `<fk>__rel` |
| `search_param` | `'q'` | GET parameter set on the bound request for the URL provider |
| `limit` | `50` | maximum number of suggestions returned |

## Exposing a FK as both a navigable relation and a value picker

By default a FK is a **navigable relation** — you traverse into it
(`author.last_name`, `author.country.code`). The picker above instead exposes it
as a **value field** under the *same* name, which removes traversal. To keep
**both**, expose the picker under a *second* name and point it back at the real
FK with `lookup_name`. The recommended convention is `<fk>__rel` (double
underscore, consistent with the derived-field family `__count` / `__sum` / …):

```python
from django.contrib.auth.models import User
from djangoql.extras import AutocompleteSchemaMixin
from djangoql.schema import DjangoQLSchema

from .models import Book


class BookSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    include = (Book, User)
    autocomplete = {
        Book: {
            # picker; `author` itself stays a navigable relation
            'author__rel': {
                'lookup_name': 'author',           # filters the real FK
                'url': 'user-autocomplete',
                'search_fields': ['username'],
            },
        },
    }

    def get_fields(self, model):
        # `author__rel` is synthetic (not a real model field), so it must be
        # added explicitly or it won't be introspected / suggested.
        fields = list(super().get_fields(model))
        if model is Book:
            fields.append('author__rel')
        return fields
```

Now both work side by side:

- `author.username = "kowalski"` — traversal into the related model (unchanged);
- `author__rel = "Jan Kowalski [42]"` — picker, filters `author_id = 42`
  (with the usual `icontains` free-text fallback over `search_fields`).

## Limitations

- The `[id]` is visible in the drop-down and in the query (this is what keeps matches
  unambiguous).
- v1 returns a single top-N page; deep pagination / infinite scroll against DAL is future
  work.
- External (non-local, unresolvable) URLs are not called over HTTP — use the `queryset`
  provider for those.
- Grouped (optgroup) results are not supported; v1 handles a flat `results` list.
