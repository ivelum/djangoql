# Describing a schema for an LLM

Want a language model to *write* DjangoQL for your users — turn "books rated
over 4.5 that are still in stock" into `rating > 4.5 and in_stock = True`? The
model needs to know three things: **what** it can query (the fields and the
relations between them), **how** each field may be compared (the operators legal
for its type), and the handful of **grammar** rules that aren't obvious.

`describe_schema_for_llm()` produces exactly that, as a single self-contained
document, by reusing DjangoQL's own schema introspection — the same walk
over related models that powers auto-completion. Drop the description into a
system prompt and the model has everything it needs to generate valid queries.

## Library primitive: `describe_schema_for_llm`

```python
from djangoql.llm import describe_schema_for_llm
from djangoql.schema import DjangoQLSchema

from library.models import Book

bundle = describe_schema_for_llm(DjangoQLSchema(Book))  # format='json' by default
```

`describe_schema_for_llm(schema, format='json', max_fk_options=50)` takes a
schema **instance** and renders it in one of two formats:

- **`format='json'`** (the default) returns a plain, JSON-serializable
  `dict` — a one-time operator legend plus terse per-field entries. This is
  what you'd typically embed in a system prompt for a tool-calling model.
- **`format='compact'`** returns a `str`: the same information as a short
  text block — one line per field, with the legend written once as a
  comment header. Use it when every prompt token counts (large schemas, tight
  context budgets).

Any other value raises `ValueError`.

### Operators live in a legend, not on every field

Older versions of this description repeated each field's operator list (and a
worked example) inline. That's redundant: every field of a given type allows
exactly the same operators. The description now says that once, in
`operators_by_type`, and each field just states its `type`:

```json
{
  "start_model": "library.book",
  "grammar": {
    "shape": "<field> <operator> <value>, combined with `and` / `or` and grouped with parentheses",
    "operators": "each field lists its type; look up the allowed operators in operators_by_type by that type. A field with `relates_to` uses the `relation` entry; a field with `object_reference` true uses the `object_reference` entry. A `?` suffix on the type means the field is nullable (comparable to None).",
    "relations": "cross model boundaries with a dot: author.country.name = \"Poland\"",
    "lists": "membership uses a parenthesized list: x in (\"a\", \"b\")",
    "null": "a nullable field (type ends with ?) or a relation can equal None",
    "strings": "string values are double-quoted; ~ means contains",
    "negation": "there is NO standalone `not` operator. Negate with the operator itself: != , !~ , not in , not startswith , not endswith. Example: publisher != None (NOT: not publisher = None)"
  },
  "operators_by_type": {
    "int": { "operators": ["=", "!=", ">", ">=", "<", "<=", "in", "not in"], "example": "x = 42" },
    "float": { "operators": ["=", "!=", ">", ">=", "<", "<=", "in", "not in"], "example": "x = 4.5" },
    "date": { "operators": ["=", "!=", ">", ">=", "<", "<=", "in", "not in"], "example": "x = \"2021-06-01\"" },
    "datetime": { "operators": ["=", "!=", ">", ">=", "<", "<=", "~", "!~", "in", "not in"], "example": "x = \"2021-06-01 14:30\"" },
    "str": { "operators": ["=", "!=", "~", "!~", "startswith", "endswith", "not startswith", "not endswith", "in", "not in"], "example": "x ~ \"text\"" },
    "bool": { "operators": ["=", "!="], "example": "x = True" },
    "relation": { "operators": ["= None", "!= None", "<relation>.<field> (traverse with a dot)"] },
    "object_reference": { "operators": ["=", "!=", "in", "not in"] }
  },
  "dictionaries": {
    "library.author": {
      "name": ["Isaac Asimov", "J.R.R. Tolkien", "Ursula K. Le Guin"]
    }
  },
  "models": {
    "library.book": {
      "id": "int",
      "rating": "float",
      "published_date": "date?",
      "genre": {
        "type": "int?",
        "choices": ["Science Fiction", "Fantasy", "Non-Fiction"]
      },
      "title": {
        "type": "str",
        "label": "Book Title",
        "help_text": "The full title as printed on the cover."
      },
      "author": {
        "type": "relation",
        "relates_to": "library.author",
        "match_field": "name"
      }
    },
    "library.author": { "...": "..." }
  },
  "examples": [
    "id = 1",
    "id > 10 and id < 100",
    "id in (1, 2, 3)",
    "id = 1 or id = 2",
    "(id > 1 and id < 5) or id = 10"
  ]
}
```

That one example shows every field shape:

- **`id` / `rating`** — a field with no extra facts is a **bare string**:
  `"name": "type"`. Nothing to add means nothing to spend tokens on.
- **`published_date`** — a `?` suffix on the type (`"date?"`) means the field
  is **nullable**; it may be compared to `None`.
- **`genre`** — as soon as a field has *any* extra fact (here, `choices`), it
  becomes an **object**: `{"type": ..., ...extras}`. The `?` suffix still
  lives on `type`, so `"type": "int?"` reads the same way whether the field
  is a bare string or an object.
- **`title`** — a metadata object: `label` / `help_text` copied from the
  underlying model field.
- **`author`** — a relation object: `relates_to` names the related model, and
  `match_field` names *which* key in that model's `dictionaries` entry holds
  its real, matchable values. The values themselves are **not** repeated on the
  field; they live once under
  `dictionaries["library.author"]["name"]` — see
  [Related-model values](#related-model-values).

No field, of any shape, ever carries `operators`, `example`,
`"nullable": false`, a generic explanatory `note`, or an inline
`related_values` list — those are exactly the things the legend, the `?`
suffix, and the shared `dictionaries` block now say once, at the top.

### The compact format

`format='compact'` renders the same facts as short text — the legend becomes
a comment block (written once), and every field becomes one line:

```text
# DjangoQL schema
# Query: <field> <op> <value>, combined with and/or, grouped with ().
# Negate with != / !~ / not in / not startswith / not endswith (no standalone `not`).
# Relations: traverse with a dot (author.name = "..."), or compare None.
# Operators by type:
#   int/float/date:  = != > >= < <=  in  not in        e.g. rating = 4.5
#   datetime:        (as above) plus ~ !~
#   str:  = != ~ !~ startswith endswith (not ...) in  not in           e.g. name ~ "text"
#   bool:           = !=                           e.g. is_pub = True
#   -> relation:     = None / != None / dot-traverse
#   # object_reference: = != in not in  (match by pk)
# Suffix ? = nullable.  choices: closed set.

start model: library.book

library.book:
  author          -> library.author  match name
  genre           int?  choices: Science Fiction | Fantasy | Non-Fiction
  id              int
  published_date  date?
  rating          float
  title           str  "Book Title" — The full title as printed on the cover.

library.author:
  ...

dictionaries (shared relation values, referenced above):
  library.author
    name: "Isaac Asimov", "J.R.R. Tolkien", "Ursula K. Le Guin"
```

Conventions worth knowing when reading (or grepping) this format:

- **`->`** marks a relation; the target model follows (`-> library.author`).
  A trailing `?` on the target (`-> library.author?`) means the relation
  itself is nullable.
- **`match <field>`** after a relation names *which* key in the target model's
  `dictionaries` block holds the values to traverse with (`match_fields`
  renders as `match field_a, field_b`; a `'__str__'` spec renders as
  `examples`, pointing at the `examples:` key in the dictionary). The values
  themselves are listed once, at the bottom, under `dictionaries`.
- **`?`** right after the type marks a nullable scalar field (`date?`).
- **`#`** before the type marks an `object_reference` picker field (matched by
  primary key), e.g. `author  # str (object_reference)`.
- **`choices: a | b | c`** lists a closed set of values.
- A quoted string after the type is the field's `label`; an em-dash and more
  text after it is the `help_text` (`"Book Title" — The full title...`).
- **`dictionaries (...)`**, at the very bottom, is the glossary the `match`
  references point into: one block per related model, then one `key: values`
  line per match field (or `examples:` for a `'__str__'` spec). Each set of
  values appears here exactly once, no matter how many relations reference it.

What each part of either format carries:

- **`start_model`** — the root model the query is rooted at.
- **`grammar`** — the non-obvious rules, including the `operators` note that
  tells the model *how* to resolve a field's operators (see below).
- **`operators_by_type`** — emitted once, this is the legend: for every
  scalar type (`int`, `float`, `date`, `datetime`, `str`, `bool`) and the two
  pseudo-types `relation` and `object_reference`, the operators legal for
  that type, plus a worked `example` for scalar types. If the schema uses the
  date-parts / aggregate mixins, the `date`, `datetime` and `relation` entries
  also gain a `lookups` / `aggregates` note — see
  [Derived fields](#derived-fields-date-parts-and-aggregates) below.
- **`models`** — every model reachable from the root, keyed by label. This is
  the field *graph*: a field with `relates_to` names the model it relates
  to, so the LLM can traverse `author.country.name` the same way
  introspection does. Only fields that are actually suggested in
  auto-completion are included, so the description matches what a user sees.
- **`suggested_values`** — for open-ended picker/autocomplete fields without
  `choices`, a sample of real values, so the model can pick valid ones rather
  than guess. Fields with `choices` never also carry `suggested_values` (choices
  take precedence).
- **`label`** / **`help_text`** — human-readable metadata copied from the
  underlying model field, when it adds information beyond the field name.
- **`choices`** — for a field defined with `choices=`, the closed set of labels
  DjangoQL accepts.
- **`dictionaries`** — a top-level map `{ related_model_label: { match_key:
  [values] } }`. Each related model's matchable values live here **once**,
  keyed by the field they came from (or `"__str__"` for `str(obj)` examples),
  no matter how many relations point at that model. This is the single source
  of truth a relation's `match_field` / `match_fields` refers into.
- **`match_field`** (or **`match_fields`**) — on a relation, names which key(s)
  in `dictionaries[relates_to]` hold the values to match on. The values are
  never inlined on the field itself; look them up in `dictionaries`. A
  `match_field` of `"__str__"` means `str(obj)` examples.
- **`examples`** — a few worked, schema-agnostic queries.

#### Resolving a field's operators

Given a field entry, the lookup a model (or your own code) performs is:

1. Take the field's `type` and strip a trailing `?` if present.
2. If the entry has `relates_to`, use the `relation` entry in
   `operators_by_type` instead of the (stripped) `type`.
3. Else if the entry has `object_reference: true`, use the
   `object_reference` entry instead.
4. Otherwise look the (stripped) type straight up in `operators_by_type`.

!!! note "Pass the schema *you* expose"
    `describe_schema_for_llm()` takes a schema **instance**, so pass the exact
    `DjangoQLSchema` subclass your admin or view uses (e.g. one that restricts
    fields via `get_fields()` or adds
    [autocomplete pickers](integrating-django-autocomplete-light.md)). The
    description then covers precisely the search space your users have — no more,
    no less. Object-picker fields keep their original type (e.g. `str`) but
    carry `"object_reference": true`, which routes their operator lookup to
    the `object_reference` legend entry (`= / != / in / not in`) instead of
    the string one.

### Field labels and help text

Model fields often carry human-readable metadata that the field *name* alone
doesn't convey — a `verbose_name` like "Book Title", or a `help_text`
explaining what the field means. `describe_schema_for_llm()` copies both onto
the field entry whenever they add information:

- **`label`** comes from the field's `verbose_name`. It is omitted when it
  would only restate the field name (e.g. a field called `title` whose
  auto-generated verbose name is `"title"`) — no point spending prompt tokens
  on a label that says nothing the field name doesn't already say.
- **`help_text`** is copied verbatim whenever the underlying field defines
  one.

Both are hints, not machine-readable constraints: they help the model guess
what a field is *for* before it ever sees a row of data. A field with either
key becomes an object, e.g. `"title": {"type": "str", "label": "Book Title",
"help_text": "The full title as printed on the cover."}`.

### Choice fields

A field defined with Django's `choices=` is a closed set — there's no
guessing a valid value, only the list. `describe_schema_for_llm()` always
emits that list as `choices` (capped at 100 entries), using the
human-readable label side of each `(value, label)` pair — the same label
DjangoQL's own value matching accepts and translates back to the stored
value: `"genre": {"type": "int?", "choices": ["Science Fiction", "Fantasy",
"Non-Fiction"]}`. Because choices live on the field definition, this costs no
database query and needs no opt-in.

### Derived fields (date parts and aggregates)

Two optional schema mixins (`djangoql.extras.DatePartsSchemaMixin` and
`djangoql.extras.AggregateSchemaMixin`) each generate a whole family of extra
queryable fields per field they attach to:

- **Date parts** — every `date` field gains up to eight virtual lookups:
  `<field>__year`, `__month`, `__day`, `__week_day`, `__quarter`, `__week`,
  `__iso_year`, `__iso_week_day`. Every `datetime` field gains those same
  eight plus `__hour`, `__minute`, `__second`, `__date`, and `__time` — up to
  thirteen virtual fields from one real one.
- **Aggregates** — every to-many relation (reverse FK or M2M) gains a
  `<relation>__count` field. Numeric aggregates
  (`<relation>.<numeric_field>__sum|avg|min|max`) are *not* separate fields at
  all — they're synthesized on the fly from the dot-syntax pattern when the
  parser encounters them, so only `<relation>__count` ever exists as a real
  field object.

Listing all of that per field would dominate the description — one
`datetime` field alone could add thirteen entries. So none of it is listed
individually: every generated field (`DatePartField`, `DateExtractField`,
`TimeExtractField`, `AggregateField` and its subclasses) is created with
`suggested=False`, and `describe_schema_for_llm()` excludes them from
`models` by class as well, so even a schema that forces one back to
`suggested=True` still won't see it listed.

Instead, `describe_schema_for_llm()` scans the *whole* schema once —
including those hidden fields — and, only for the capabilities it actually
finds, adds a `lookups` note to the `date`/`datetime` legend entries and an
`aggregates` note to the `relation` entry. One note each, no matter how many
date/datetime fields or to-many relations the schema has:

```json
"date": {
  "operators": ["=", "!=", ">", ">=", "<", "<=", "in", "not in"],
  "example": "x = \"2021-06-01\"",
  "lookups": "also <field>__<part> (integer): year, month, day, week_day, quarter, week, iso_year, iso_week_day. e.g. utworzono__year = 2021"
},
"datetime": {
  "operators": ["=", "!=", ">", ">=", "<", "<=", "~", "!~", "in", "not in"],
  "example": "x = \"2021-06-01 14:30\"",
  "lookups": "also <field>__<part> (integer): year, month, day, week_day, quarter, week, iso_year, iso_week_day, hour, minute, second; <field>__date (date); <field>__time (time). e.g. utworzono__year = 2021, utworzono__date = \"2021-06-01\""
},
"relation": {
  "operators": ["= None", "!= None", "<relation>.<field> (traverse with a dot)"],
  "aggregates": "to-many relation: <rel>__count (integer), e.g. autorzy__count >= 2. Numeric aggregates via dot: <rel>.<numeric_field>__sum|avg|min|max, e.g. autorzy.rating__avg"
}
```

(`utworzono__year` and `autorzy__count` are fixed, generic worked examples
baked into the note text itself — not references to fields in *your*
schema — the same way the scalar legend entries' `example` is generic.)

From that legend alone, the model can build `published_date__year = 2021`
against any `date` field, `written__date = "2021-06-01"` against any
`datetime` field, or `books__count >= 2` / `books.rating__avg > 4` against
any to-many relation — none of which ever appears under `models` by name.

The compact format adds the same information as up to three extra header
lines, right after the fixed legend block and before `start model:`:

```text
# date fields also: <field>__<part> (int): year, month, day, week_day, quarter, week, iso_year, iso_week_day
# datetime fields also: <field>__<part>: hour, minute, second; <field>__date; <field>__time
# to-many relations: <rel>__count; numeric via dot <rel>.<field>__sum|avg|min|max
```

A schema using only `DatePartsSchemaMixin` gets the `date`/`datetime` `lookups`
notes but no relation `aggregates` note (and no `# to-many relations` line in
compact); a schema using only `AggregateSchemaMixin` gets the reverse. The `date
fields also` and `datetime fields also` compact lines appear together whenever
any date or datetime field is present — a schema with only a bare `TimeField`
is the only case that yields the datetime-only line alone. **A schema that uses neither mixin gets none of this** — no
`lookups` key on `date`/`datetime`, no `aggregates` key on `relation`, and no
extra compact header lines. Confirm it yourself on a plain schema:

```shell
$ python manage.py djangoql_describe_schema_for_llm library.Book --format json --indent 2
```

The `date`/`datetime`/`relation` legend entries come back with only
`operators` (and `example`) — and `models` has no `__year`-, `__date`- or
`__count`-suffixed entries anywhere, because the mixins were never attached
to that schema in the first place.

### Related-model values

Knowing that `author` is a `library.author` isn't enough for a model to write
`author.name = "J.R.R. Tolkien"` — it also has to know what a real `name`
looks like. `describe_schema_for_llm()` embeds real, matchable values for a
relation in the shared top-level `dictionaries` block and points the relation
at them with `match_field`, controlled by `max_fk_options`:

```python
from djangoql.llm import describe_schema_for_llm

bundle = describe_schema_for_llm(schema, max_fk_options=50)  # the default
```

or from the command line:

```shell
$ python manage.py djangoql_describe_schema_for_llm library.Book --max-fk-options 50
```

`max_fk_options` is a cardinality gate, not a sample size: a relation's
values are only embedded when the number of *distinct* values is at or under
the threshold, so the model sees the whole domain rather than an arbitrary
slice. `0` disables auto mode and any `'field_name'`/`['a','b']`/`'__str__'` spec (all are gated by this threshold); only `True` (which ignores the threshold) and `False` (always off) are unaffected by `max_fk_options`. Disabled relations fall back to a bare relation object — `relates_to` with no `match_field`/`match_fields` and no entry in `dictionaries` — traversable with a dot or comparable to `None`.

!!! note "Values are deduplicated across relations"
    A single related model (a dictionary/lookup table) is often the target of
    *many* foreign keys — several `jezyk` FKs, a self-relation plus reverse
    relations, and so on. Rather than repeat that model's value list at every
    such relation, `describe_schema_for_llm()` emits it **once**, in the
    top-level `dictionaries` block keyed by `(related_model, match_field)`, and
    every relation to it carries only a lightweight `match_field` reference.
    Two relations pointing at the same model but matching on *different* fields
    produce two separate `dictionaries` entries (one per field), each still
    emitted once.

#### Choosing what a relation reveals: `fk_options`

Without any configuration (**auto mode**, below), `describe_schema_for_llm()`
guesses one identifying field per relation. To be explicit — reveal several
fields, a computed string, or nothing at all — set `fk_options` on the
schema:

```python
class BookSchema(DjangoQLSchema):
    fk_options = {
        Book: {
            'author': ['name', 'country'],  # several fields
            'publisher': '__str__',         # fall back to str(obj)
            'editor': False,                # never reveal editor values
        },
    }
```

`fk_options` is keyed by the **model that owns the relation** (here `Book`,
which has the `author`, `publisher` and `editor` foreign keys), then by the
**relation's field name** on that model. Each entry's value — the *spec* —
controls what gets embedded for that relation:

| Spec | Meaning |
| --- | --- |
| `'field_name'` | Emit that field's distinct values, gated by `max_fk_options`. Produces `match_field` on the relation; values under `dictionaries[relates_to][field_name]`. |
| `['field_a', 'field_b']` | Emit each field's distinct values, gated by `max_fk_options`. Produces `match_fields` on the relation; each field's values under `dictionaries[relates_to][field]`. |
| `'__str__'` | Emit up to `max_fk_options` rows' `str(obj)`, gated by row count rather than distinct-value count. Produces `match_field: "__str__"`; values under `dictionaries[relates_to]["__str__"]`. |
| `True` | Force the relation's default identifying field (see auto mode), ignoring the `max_fk_options` threshold. Falls back to `'__str__'`-style examples if the related model has no string field. |
| `False` | Never reveal values for this relation, regardless of `max_fk_options`. |
| *(no entry)* | **Auto mode** — see below. |

#### Auto mode

A relation with no `fk_options` entry at all is handled automatically: its
identifying field is picked from the related model's *schema-visible*
fields — so it only ever surfaces a field a user could already search on — a
field literally named `name` if there is one, otherwise the first string
field. If that field's distinct-value count is at or under
`max_fk_options`, its values are embedded exactly as with an explicit
`'field_name'` spec. If the related model exposes no string field, or its
value count exceeds the threshold, auto mode emits nothing for that
relation.

Auto mode also skips any relation whose target model belongs to one of
Django's own sensitive apps — `auth`, `admin`, `contenttypes`, `sessions` —
as well as the project's configured `AUTH_USER_MODEL`, even when a custom
user model lives in an otherwise non-sensitive app (e.g. `myapp.User`). This
way schema description never auto-dumps usernames, permission codenames, or
session data into a prompt. An explicit `fk_options` entry for such a
relation overrides the exclusion; the skip only applies to auto mode.

!!! warning "Privacy: auto mode queries your data"
    Every other value in the schema description is either static (field
    names, types, choices) or opt-in (`suggested_values` requires
    `suggest_options` on the field). Auto-mode related values are the one
    exception: by default, any relation under the `max_fk_options` threshold
    has its distinct values queried and embedded, with no explicit opt-in
    beyond calling `describe_schema_for_llm()` at all. If a relation's
    target holds data you don't want surfaced this way — anything not
    already meant to be user-searchable — disable it explicitly with
    `fk_options = {Model: {relation: False}}`, or disable auto mode globally
    with `max_fk_options=0`.

#### Output shape

The values always live in the top-level `dictionaries` block, keyed by
`(related_model, match_key)`; the relation entry itself carries only a
reference, alongside `type` and `relates_to`:

- **`match_field: "field_name"`** — a single field (`'field_name'` spec, auto
  mode, or `True`). Its distinct values are the list at
  `dictionaries[relates_to]["field_name"]`.
- **`match_fields: ["field_a", "field_b"]`** — several fields (`['a', 'b']`
  spec). Each field's distinct values are the list at
  `dictionaries[relates_to][field]`.
- **`match_field: "__str__"`** — `str(obj)` rows, when there's no single field
  to match on (`'__str__'` spec, or as `True`'s fallback when the related model
  has no string field). The examples are the list at
  `dictionaries[relates_to]["__str__"]`.

To resolve a relation's values, take its `match_field` (or each of its
`match_fields`) and look it up in `dictionaries[relates_to]`. A `match_key` of
`"__str__"` is `str(obj)` examples, not a traversable field.

When no values apply (disabled, over threshold, or a sensitive target in auto
mode), the relation entry has no `match_field`/`match_fields` at all — just
`type` and `relates_to`, and no entry in `dictionaries` — and the model falls
back to the `relation` note in `grammar.operators`: traverse with a dot, or
compare to `None`.

## Management command: `djangoql_describe_schema_for_llm`

The same description is available from the command line for any model — handy
for building prompts, fixtures, or eval sets:

```shell
# Default schema (all introspectable fields), JSON output
$ python manage.py djangoql_describe_schema_for_llm library.Book

# The exact schema your admin/view exposes
$ python manage.py djangoql_describe_schema_for_llm library.Book \
    --schema library.schema.BookSchema

# Compact text output, smallest for large schemas
$ python manage.py djangoql_describe_schema_for_llm library.Book \
    --format compact

# JSON, redirected to a file
$ python manage.py djangoql_describe_schema_for_llm library.Book \
    --indent 0 > book_schema.json

# Lower the related-values threshold, or disable auto mode with 0
$ python manage.py djangoql_describe_schema_for_llm library.Book \
    --max-fk-options 10
```

| Argument | Meaning |
| --- | --- |
| `app_label.ModelName` | The model to describe (required). |
| `--schema` | Dotted path to a `DjangoQLSchema` subclass to use instead of the default. |
| `--format` | Output format: `json` (default, machine-readable dict) or `compact` (terse text). |
| `--indent` | JSON indentation (default `2`; `0` for the most compact multi-line output). Ignored for `--format compact`. |
| `--max-fk-options` | Max distinct related-model values to embed per relation (default `50`). `0` disables auto mode and any `'field_name'`/`['a','b']`/`'__str__'` spec; only `True` (ignores threshold) and `False` (always off) are unaffected. See [Related-model values](#related-model-values). |

The command is available in any project that has `'djangoql'` in
`INSTALLED_APPS`.

## Closing the loop: generate → validate → repair

The description teaches the model *what* to write; DjangoQL's own parser and
schema tell you whether it got it right — **without touching the database**:

```python
from djangoql.parser import DjangoQLParser
from djangoql.exceptions import DjangoQLError
from djangoql.schema import DjangoQLSchema

from library.models import Book


def validate_query(query):
    schema = DjangoQLSchema(Book)
    try:
        schema.validate(DjangoQLParser().parse(query))
        return None            # valid
    except DjangoQLError as e:
        return str(e)          # feed this back to the model and ask it to fix
```

Validation errors are written to be actionable — an unknown field yields
`Unknown field: ratng. Did you mean: rating?` — so they make excellent feedback
for a repair step: generate a query, validate it, and on failure hand the error
back to the model for another attempt. Only once `validate_query()` returns
`None` do you run the query against real data.

## Field filtering also trims the description

`describe_schema_for_llm` reads the same introspected schema as autocomplete and
query validation. Any field removed via `include_fields` / `exclude_fields`
(see [Schema & custom fields](schema.md)) is therefore absent from the LLM
description as well — there is no separate "visible to the LLM but not to
autocomplete" state.
