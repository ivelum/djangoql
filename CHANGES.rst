0.31.2 (2026-08-07)
-------------------

* **Added support for Django 6.1** (Python 3.12--3.14). Django 6.1 is now part
  of the CI test matrix alongside 5.2 LTS and 6.0, and is advertised in the
  package classifiers. No code changes were required.

* **Fixed the ``tests-postgres`` CI job, which silently ran against SQLite.**
  The fixture swapped ``settings.DATABASES``, but the ``default`` connection had
  already been materialised during ``django.setup()``, so every "PostgreSQL" run
  actually exercised SQLite. The job now asserts hard on
  ``connection.settings_dict['ENGINE']`` and additionally asks the server itself
  via ``SELECT version()``. Four tests that had been overfitted to SQLite's SQL
  rendering (``UPPER(...) LIKE`` and the time-zone offset handling) were
  corrected to match PostgreSQL. Tests and CI only -- no changes to the packaged
  code.

0.31.0 (2026-07-11)
-------------------

* **LLM schema — dictionary value deduplication (breaking JSON shape):** a
  related model that is the target of several relations (a shared dictionary /
  lookup table -- e.g. many ``jezyk`` foreign keys, or a self-relation plus
  reverse relations) previously had its full value list re-emitted inline at
  **every** relation, wasting large amounts of prompt space on pure
  redundancy. Its values are now emitted **once**, in a new top-level
  ``dictionaries`` block keyed by ``(related_model, match_field)``, and each
  relation carries only a lightweight ``match_field`` / ``match_fields``
  reference into it. ``str(obj)`` examples are deduplicated the same way under
  the ``"__str__"`` key.

  **Breaking change to the JSON output shape:** relation field entries no
  longer carry an inline ``related_values`` / ``related_examples`` value;
  instead they carry ``match_field`` (which may be ``"__str__"``) or
  ``match_fields``, and the values live under
  ``dictionaries[relates_to][match_key]``. Consumers that parsed per-field
  ``related_values`` must read from the top-level ``dictionaries`` block
  instead. The compact format changes correspondingly: a relation renders as
  ``-> model  match <field>`` (or ``examples``) with the values listed once in
  a ``dictionaries (...)`` block at the bottom, rather than inline
  ``match <field> in (...)`` at each relation. Semantics are otherwise
  unchanged -- ``fk_options``, ``max_fk_options``, ``no_value_targets``, the
  auto-mode sensitive-target guard, and ``choices`` all behave exactly as
  before. As a side effect, a shared dictionary is now queried once rather than
  once per referencing relation.

0.30.3 (2026-07-10)
-------------------

* **LLM schema privacy — ``no_value_targets``:** new optional schema attribute,
  a *hard denylist* of relation-target models (model classes and/or
  ``"app_label.Model"`` dotted labels) whose row values are **never** embedded
  into the description. It is checked before ``fk_options`` and ignores
  ``max_fk_options``, so it overrides even an explicit ``fk_options`` entry and
  any row-count threshold. Use it to keep institution-specific data
  (e.g. organisational-unit or institution names) out of a committed or shared
  schema description, regardless of how few rows a table has. Unknown labels are
  logged and skipped so a typo can never break schema description. Complements
  the auto-only ``SENSITIVE_TARGET_APP_LABELS`` / ``AUTH_USER_MODEL`` guard.

0.30.2 (2026-07-05)
-------------------

* **LLM schema privacy fix:** auto mode now also excludes the project's
  ``AUTH_USER_MODEL`` from embedded related values, not just models in the
  built-in sensitive app-labels (``auth``, ``admin``, ``contenttypes``,
  ``sessions``). A custom user model living in an otherwise non-sensitive app
  (e.g. ``myapp.User``) previously fell through the guard and had its user
  fields (usernames, etc.) auto-emitted. The exclusion check now also compares
  each relation's target against ``get_user_model()``, guarded so a
  malformed/missing ``AUTH_USER_MODEL`` can never break schema description. An
  explicit ``fk_options`` entry still overrides the exclusion, as before.

0.30.1 (2026-07-05)
-------------------

* **LLM schema fixes:** ``_default_match_field`` now prefers identifier-like
  fields (``nazwa``, ``skrot``, ``username``) over the first alphabetical string
  field when auto-picking a match field, and the swallowed exceptions in
  ``_distinct_values`` / ``_str_examples`` are now logged instead of silently
  producing a value-less schema.

0.30.0 (2026-07-05)
-------------------

* **Declarative per-model field filtering:** new ``include_fields`` and
  ``exclude_fields`` schema attributes (``{model: [field names]}``) let you
  expose ONLY certain fields of a model (allowlist) or all fields EXCEPT certain
  ones (denylist), as an alternative to overriding ``get_fields()``. A model may
  appear in one dict or the other, not both, and unknown field names raise
  ``DjangoQLSchemaError`` at schema creation. Because filtering happens during
  introspection, it also trims the autocomplete suggestions, the query
  validation surface, and the ``describe_schema_for_llm`` output. Filtering out
  a relation field additionally removes that traversal and drops the related
  model when nothing else reaches it.

0.29.0 (2026-07-05)
-------------------

* **Richer LLM schema description:** ``describe_schema_for_llm`` now enriches
  each field with its ``label`` (from ``verbose_name``, omitted when it merely
  duplicates the field name) and ``help_text``, always emits a closed-set
  ``choices`` list for choice fields (the human labels DjangoQL accepts, read
  without a query), and — gated by cardinality — embeds concrete related-model
  values. A ``max_fk_options`` threshold (default 50; ``--max-fk-options``;
  ``0`` disables auto mode) and a per-relation ``fk_options = {Model:
  {relation: spec}}`` schema attribute (``spec`` = a field name / list of field
  names / ``'__str__'`` / ``True`` / ``False``) control what is embedded. Auto
  mode picks the identifying field only from schema-visible, suggested fields
  (so ``password`` and hidden fields are never surfaced) and excludes sensitive
  target app-labels (``auth``, ``admin``, ``contenttypes``, ``sessions``); an
  explicit ``fk_options`` entry overrides the exclusion.

* **Compressed, two-format output:** the per-field verbose shape is replaced by
  a compact one. ``describe_schema_for_llm(schema, format='json')`` (default)
  emits a one-time ``operators_by_type`` legend (types plus the pseudo-types
  ``relation`` and ``object_reference``) instead of repeating operators and
  examples on every field, and renders fields tersely — a field with no extras
  is a bare ``"name": "type"`` string, otherwise an object with only
  informative keys, and a ``?`` suffix on the type marks it nullable.
  ``format='compact'`` emits a terse text block (one line per field) that is
  smallest for large schemas. The management command gains ``--format
  {json,compact}``.

* **Collapsed derived-field lookups:** the date-parts and aggregate schema
  mixins generate many virtual fields (``<date>__year`` … ``__second``,
  ``<date>__date``/``__time``, ``<rel>__count``). These are no longer listed
  per field; instead their capability is described once in the type legend —
  ``date``/``datetime`` gain a ``lookups`` note and ``relation`` gains an
  ``aggregates`` note (``<rel>__count`` plus the dot-syntax numeric aggregates
  ``<rel>.<field>__sum|avg|min|max``). The notes appear only when the schema
  actually uses those mixins, and their worked examples reflect only the
  lookups actually available.

0.28.0 (2026-07-04)
-------------------

* **LLM-ready schema description:** a new ``djangoql.llm.describe_schema_for_llm``
  helper turns any ``DjangoQLSchema`` into a compact, self-contained JSON
  description of the whole search space — every model, field, type, nullability,
  related model (the traversable "dependent" fields), the operators legal for
  each field type, concrete suggested values, plus a grammar cheat-sheet and
  worked examples. Drop it into an LLM prompt to teach a model to generate valid
  DjangoQL. Object-picker fields correctly advertise only ``= / != / in /
  not in`` despite their string type.
* **``djangoql_describe_schema_for_llm`` management command:** prints that
  description as JSON for any model, e.g.
  ``python manage.py djangoql_describe_schema_for_llm library.Book``. Supports
  ``--schema`` (use the exact ``DjangoQLSchema`` subclass your admin/view
  exposes) and ``--indent``. Available in any project with ``djangoql`` in
  ``INSTALLED_APPS``.

0.27.0 (2026-06-05)
-------------------

* **Markdown-based, i18n-aware syntax help:** the admin "DjangoQL search syntax"
  help page is now authored as per-language Markdown instead of a single
  block-structured HTML template. When a Markdown compiler is importable the
  help renders as HTML; otherwise it falls back to the raw Markdown inside a
  ``<pre>`` block. djangoql itself does **not** depend on a Markdown library —
  the renderer guards the import — so a bare install degrades gracefully, while
  installing ``markdown`` (for any reason) upgrades the page to HTML with no
  configuration. The help text ships for all 11 maintained locales (de, es, fr,
  it, ja, nl, pl, pt_BR, ru, uk, zh_Hans) and follows the active language with
  an English fallback. The ``djangoql_syntax_help`` admin URL and the
  ``djangoql_syntax_help_template`` override hook are preserved.
* **example_project:** declares ``markdown`` in a new ``requirements.txt`` and
  adds a standalone (non-admin) ``/syntax-help/`` page — with a ``?lang=``
  switcher and a nav link — demonstrating the HTML-rendered help outside the
  admin.

0.26.0 (2026-06-05)
-------------------

* **Translatable autocomplete labels:** the completion popup's operator hint
  labels (``is not equal to``, ``contains``, ``does not contain``) and the
  search box placeholder (``Advanced search with Query Language``) are now
  localised. These strings are baked into the upstream ``djangoql-completion``
  bundle as plain literals, so the admin mixin now serves a ``djangojs`` gettext
  catalog from a new ``djangoql-i18n/`` endpoint (loaded before
  ``completion.js``) and the widget re-renders the labels through
  ``window.gettext`` — falling back to English where no catalog is present.
  Translations ship for all 11 maintained locales (de, es, fr, it, ja, nl, pl,
  pt_BR, ru, uk, zh_Hans).

0.25.0 (2026-06-04)
-------------------

* **Value autocomplete inside ``in (...)`` lists:** the completion widget now
  offers value suggestions while the caret sits inside an ``<field> in ( … )``
  (or ``not in ( … )``) list, not only right after a binary operator. It
  resolves the field to the left of ``in`` and switches to value scope so the
  existing suggestion/insertion machinery applies unchanged. The enhancement is
  best-effort and never breaks base completion — any failure is logged to
  ``console.debug`` rather than swallowed.
* **example_project test suite:** the showcase project now ships its own tests,
  covering the generic ``<name>__rel`` object pickers (forward FK + M2M, nested
  relations, ``lookup_name`` redirection to the real FK, free-text fallback) and
  the standalone ``format`` / ``explain`` / ``search`` JSON endpoints including
  error-location reporting. Run them with ``manage.py test library``; they are
  wired into CI across the full Python/Django matrix.
* **Coverage:** djangoql test coverage raised to ~99%. New tests exercise
  ``AutocompleteField`` edge cases (non-string validation, provider selection,
  request threading through ``SuggestionsAPIView``, url/queryset/callable
  configs), the admin's empty-result breakdown error handling, and the
  aggregate/date-part "unknown field" hint fall-throughs.
* **Fixes:** ``AutocompleteSchemaMixin`` now catches the specific
  ``FieldDoesNotExist`` (instead of a blanket ``except Exception``) when reading
  a picker's nullability from the model; the example schema docstring reflects
  the current ``"<label> #<id>"`` suggestion rendering.

0.24.0 (2026-06-04)
-------------------

* **Example project:** new runnable ``example_project/`` demonstrating all of
  the above on a richly related dataset (books → authors → countries,
  publishers, genres) with a ``seed_demo`` management command. It includes a
  restyled search demo page (auto-completion, multi-line, highlight overlay,
  Format, Explain counts), standalone ``format``/``explain``/``search``
  endpoints, and an admin with completion + multi-line + the opt-in highlight
  overlay. New docs page "Example project".
* **Syntax highlighting (generic, no imposed style):** new
  ``djangoql/js/highlight.js`` exposes ``DjangoQLHighlight.tokenize(text)`` — a
  pure, lossless, UMD tokenizer mirroring the grammar (feed it to any editor) —
  and ``attachOverlay(textarea)``, a lightweight transparent-text overlay (which
  keeps the caret visible by setting ``caret-color`` to the input's original
  text colour). The overlay handle can flag a **syntax-error location** with a
  red squiggle via ``setError(offset)`` / ``setErrorAt(line, column)`` (DjangoQL
  errors carry ``line``/``column``); ``offsetFromLineColumn`` is exported too.
  ``highlight.css`` ships structural rules plus an overridable default palette
  (CSS custom properties). In the admin it is opt-in via
  ``DjangoQLSearchMixin.djangoql_highlight = True`` (off by default). The
  library imposes no colour scheme or editor — that is the integrator's
  decision. New docs page "Syntax highlighting".
* **Query breakdown (record counts per branch):** new
  ``djangoql.breakdown.explain(queryset, search, …)`` always returns the
  per-node count tree (``{text, count, role, children}``, one ``count()`` per
  node, guarded by ``max_nodes``), for any query — the on-demand sibling of the
  zero-rows ``explain_empty`` (now a thin lazy wrapper sharing the same
  helpers). ``DjangoQLSearchMixin`` exposes an ``…/explain/`` JSON endpoint
  (``q`` → ``{tree}`` / ``{error}``+400). It is caller-triggered by design (not
  run per search); wiring/rendering it is the integrator's decision. New docs
  page "Query breakdown (counts)".
* **Pretty-print / formatting:** new ``djangoql.formatter`` module with
  ``format_query(query, indent=2)`` — parses a query and re-renders it as
  indented, multi-line text (round-trip safe and idempotent) — and
  ``serialize_node(node)`` for the compact one-line canonical form. The
  empty-result breakdown now reuses ``serialize_node`` for its node labels
  (dedup). ``DjangoQLSearchMixin`` exposes a ``…/format/`` JSON endpoint backing
  a "Format" button; wiring the button is the integrator's decision. New docs
  page "Pretty-print / formatting".
* **Multi-line queries:** new ``djangoql/js/multiline.js`` lets users insert a
  newline with **Shift+Enter** while plain **Enter** still submits. Loaded
  automatically by ``DjangoQLSearchMixin`` in the admin; framework-agnostic and
  reusable outside the admin (recognises ``textarea.djangoql`` /
  ``textarea[data-djangoql]`` / ``textarea[name="q"]``, or call
  ``DjangoQLMultiline.enable(el)``). It imposes no styling — the look of a
  multi-line query box is the integrator's decision. New docs page
  "Multi-line queries".

0.23.0 (2026-06-04)
-------------------

* Add an additive, non-breaking ``lookup_name`` kwarg to
  ``djangoql.extras.AutocompleteField``. It overrides ``get_lookup_name()`` so a
  picker can live under a second field name (e.g. ``<fk>__rel``) while still
  filtering the **real** foreign key — letting a FK be exposed *both* as a
  navigable relation (dot traversal) *and* as a value picker. Default ``None``
  preserves current behavior. New docs section "Exposing a FK as both a
  navigable relation and a value picker" documents the ``<fk>__rel`` idiom.

0.22.1 (2026-06-04)
-------------------

* Refine the **"Did you mean" field suggestions** so a clear match is no longer
  diluted by unrelated fields that merely share a ``__suffix`` — e.g.
  ``autorzy__cnt`` now suggests only ``autorzy__count``, not ``utworzono__month``.
  Among candidates above the cutoff, only those within a small similarity margin
  of the best match are kept. New ``suggest_cutoff`` / ``suggest_margin`` /
  ``suggest_limit`` schema attributes tune the behavior.
* **Translations:** complete and correct the catalogs for all eleven locales —
  translate the messages introduced in 0.22.0 (the "Did you mean" hint, the
  empty-result breakdown strings, the hidden derived-field hints) and fix a few
  stale machine-merged strings (e.g. the numeric ``numbers`` type and the time
  ``"HH:MM[:SS]"`` format/validation messages).

0.22.0 (2026-06-04)
-------------------

* The **"Unknown field" error** now suggests close matches for likely typos:
  ``Unknown field: autho. Did you mean: author?``. Suggestions are matched
  case-insensitively against every field name (including hidden derived fields,
  so ``book__coun`` can point at ``book__count``); when nothing is close it
  falls back to the full ``Possible choices`` list as before. The matching is
  backed by a new overridable ``DjangoQLSchema.suggest_field_names()`` hook.
* Add an **empty-result breakdown**: when a valid DjangoQL query returns zero
  rows, explain *where in the query the data runs out*. The new
  ``djangoql.breakdown.explain_empty(queryset, search, schema=None, *,
  max_nodes=50)`` helper walks the validated AST for an arbitrary boolean
  structure (``and`` / ``or`` / parentheses), runs one ``count()`` per
  sub-expression against the base queryset, and returns a tree of
  ``{text, count, role, children}`` nodes flagging the killer ``AND``
  (``killer_and``) and dead ``OR`` branches (``dead_or_branch``). The admin
  surfaces it automatically on empty results (lazy; disable with
  ``djangoql_explain_empty = False``, tune the cost guard with
  ``djangoql_explain_empty_max_nodes``).
* Add pluggable **autocomplete value fields** in ``djangoql.extras``
  (``AutocompleteField`` + ``AutocompleteSchemaMixin``). A field's value
  suggestions can come from an arbitrary source — most usefully an existing
  django-autocomplete-light endpoint — letting a user pick an object and filter
  by its primary key. Suggestions are formatted ``"<label> [<id>]"`` and the
  field filters ``<field> = pk`` (``=``, ``!=`` and ``in`` supported), with an
  ``icontains`` free-text fallback over ``search_fields``. Three providers are
  supported (priority high→low): a ``url`` (a DAL endpoint resolved and called
  **in-process** with the current request), a ``queryset`` / callable, or a
  subclass override. ``SuggestionsAPIView`` threads the current request into the
  field via a non-breaking ``set_request`` hook. ``AutocompleteSchemaMixin`` is
  also included in ``ExtrasSchema``. The change is server-side only (no
  JavaScript changes), additive and non-breaking.
* **Breaking (derived fields):** numeric relation aggregates now use dot
  syntax — ``<rel>.<numfield>__{sum,avg,min,max}`` (e.g. ``book.rating__sum``)
  instead of the flat ``<rel>__<numfield>__sum``. This reads consistently with
  DjangoQL's dot navigation and stops the parent model's field list from
  exploding. Relation **count** keeps its flat name ``<rel>__count``.
* **Derived fields are hidden from autocomplete.** All generated derived fields
  ship with ``suggested=False`` (relation count, date/time parts), and numeric
  aggregates are synthesized on demand so they are never listed at all. They
  remain fully usable in queries.
* The **"Unknown field" error** no longer dumps the hidden derived fields into
  its "Possible choices" list. It lists only the suggested fields and appends a
  short hint describing the derived-field syntax with a couple of real examples
  for the current model. New overridable schema hooks ``resolve_unknown()`` and
  ``unknown_field_hint()`` back this behavior.

0.21.0
------

* Add opt-in **derived search fields** in ``djangoql.extras`` (enable via
  ``ExtrasSchema`` or by composing ``DatePartsSchemaMixin`` /
  ``AggregateSchemaMixin``). These ship on PyPI for the first time in this
  release; the ``extras`` module was not included in the 0.20.0 package:

  * Date/time parts for ``DateField`` / ``DateTimeField`` / ``TimeField``,
    e.g. ``written__year >= 2020``, ``written__month in (6, 7, 8)``,
    ``written__hour < 9``, plus ``__date`` / ``__time`` extraction from
    ``DateTimeField``.
  * Relation aggregates computed as lazy, correlated subqueries:
    ``<rel>__count`` for every to-many relation and
    ``<rel>__<numeric_field>__{sum,avg,min,max}``. Aggregates are applied
    only when referenced in a query and work in both the admin and the
    queryset API.
* Add a ``suggested`` flag to ``DjangoQLField`` (default ``True``) to control
  whether a field appears in autocomplete suggestions, independent of value
  suggestions (``suggest_options``). Also reaches PyPI for the first time in
  this release.
* Add a MkDocs (Material) documentation site, published to GitHub Pages,
  with dedicated pages for installation, the admin integration, the
  completion widget, the queryset API, schema, language and derived fields.
* Trim ``README.md`` to a short overview that links to the hosted docs, add a
  PyPI badge, and fix a few examples for Django 4+.

0.20.0
------

* First release of the ``djangoql-iplweb`` fork (the import name is still
  ``djangoql``).
* **Breaking:** dropped support for Python older than 3.10 and Django older
  than 5.2. This release targets Python 3.10–3.14 and Django 5.2 LTS / 6.0.
  Projects running older Python or Django should use the upstream ``djangoql``
  package (0.19.x) instead.
* Add internationalization (i18n) support for user-facing error messages
  produced by the lexer, parser, schema validator and suggestions API.
  Ships translation catalogs for ``pl``, ``de``, ``fr``, ``es``, ``ru``,
  ``uk``, ``pt_BR``, ``it``, ``nl``, ``ja`` and ``zh_Hans``.
* Modernized packaging and developer tooling: migrated from
  ``setup.py``/``setup.cfg`` to ``pyproject.toml`` + uv, switched linting
  from flake8/isort to ruff, switched the test runner to pytest, and added
  bumpver for version management.
* Test suite can now run against PostgreSQL via testcontainers
  (``DJANGOQL_TEST_DB=postgres``); CI exercises both SQLite and PostgreSQL.

0.19.1
------

* Improve string quoting examples in syntax help

0.19.0
------

* Support single quotes too (#126)

.. _#126: https://github.com/ivelum/djangoql/pull/126

0.18.2
------

* Fix `in` and `not in` operators for date and datetime fields
* Fix djangoql_syntax_help url in error_message.html (`#115`_)

.. _#115: https://github.com/ivelum/djangoql/pull/115

0.18.1
------

* Fixed serialization for `options` element (`#112`_)

.. _#112: https://github.com/ivelum/djangoql/pull/112

0.18.0
------

* Add support for multiple django admin sites (`#110`_)
* Add support for Django 5.0 and Python 3.12

.. _#110: https://github.com/ivelum/djangoql/pull/110

0.17.1
------

* Added the ``completion.js.map`` file into the distribution to fix
  compatibility with Django 4.0 collectstatic (thanks to @magdapoppins);

0.17.0
------

* Django 4.0 compatibility (thanks to @Lotfull);

0.16.0
------

* added support for new string-specific comparison operators: ``startswith``,
  ``not startswith``, ``endswith``, ``not endswith``;

0.15.4
------

* fixed a deprecation warning for Django 3.1 (thanks to @sainAk);

0.15.3
------

* fixed ``django-completion`` bug related to removed chained models from
  suggestions;
* fixed ``django-completion`` bug related to fixed circular dependencies.

Related pull requests:

* `https://github.com/ivelum/djangoql-completion/pull/2 <https://github.com/ivelum/djangoql-completion/pull/2>`_
* `https://github.com/ivelum/djangoql/pull/77 <https://github.com/ivelum/djangoql/pull/77>`_

0.15.2
------

* fixed regression for Django < 2.1 (thanks to @derekenos for reporting the
  issue);

0.15.1
------

* fixed ``url()`` deprecation warnings for Django 3.1+ (thanks to @ecilveks);

0.15.0
------

* the completion JavaScript widget has been moved to
  `its own repo <https://github.com/ivelum/djangoql-completion>`_ and is now
  available as a standalone
  `package on npm <https://www.npmjs.com/package/djangoql-completion>`_. It
  still ships with the Python package, though, so if you don't need to embed
  the completion widget in your custom JavaScript application, no additional
  installation steps are required;
* added support for GenericIPAddressField (thanks to @HannaShalamitskaya for
  reporting the issue);
* the source code is now linted with flake8 and isort;

0.14.5
------

* added a help text to some operators;
* fixed the background color in the dark mode (django 3.2+);

0.14.4
------

* add ``~`` operator for date/datetime fields;

0.14.3
------

* ``write_tables`` argument for PLY parser is now disabled by default. This
  change prevents an error that may arise if DjangoQL is installed into
  un-writeable location (#63, #53. Thanks to @sochotnicky for the PR);
* fixed quotes handling in completion widget (#62, thanks to @nicolazilio for
  reporting this);

0.14.2
------

* add basic support for models.BinaryField (thanks to @Akay7);

0.14.1
------

* fixed inconsistency in search by fields with choices (#58, thanks to
  @pandichef for reporting this);
* Officially compatible with Python 3.9 (no changes in the code, just added it
  to the test matrix);

0.14.0
------

* New feature: field suggestion options are now loaded asynchronously via
  Suggestions API;
* **Breaking**: ``DjangoQLField.get_options()`` now accepts mandatory ``search``
  parameter. If you've implemented custom suggestion options for your schema,
  please add handling of this parameter (you should only return results that
  match ``search`` criteria);
* **Breaking**: when using in the admin together with the standard Django
  search, DjangoQL checkbox is now on by default. If you don't want this
  behavior, you can turn it off with ``djangoql_completion_enabled_by_default``
  option. Thanks to @nicolazilio for the idea;
* Deprecated: if you've used ``DjangoQLSchema.as_dict()`` somewhere in your
  code, please switch to new schema serializers instead (see in
  ``serializers.py``);
* Improved field customization examples in the docs (#55, thanks to
  @joeydebreuk);
* Added support for Django 3.1.x (#57, thanks to @jleclanche)

0.13.1
------

* Fixed compatibility with upcoming Django 3.0 (thanks to @vkrizan for the
  reminder);

0.13.0
------

* Added "DjangoQL syntax help" link to the error messages in Django admin
  (thanks to @AngellusMortis for the idea);

0.12.6
------

* Fixed: DateField and DateTimeField lookups no longer crash on comparison with
  None (thanks to @st8st8);
* Officially compatible with Django 2.2 (no changes in the code, just added it
  to the test matrix);

0.12.5
------

* Added convenience method DjangoQLSearchMixin.djangoql_search_enabled()
  (thanks to @MilovanovM);

0.12.4
------

* DjangoQL syntax help page in admin now requires users to be logged-in (thanks
  to @OndrejIT);

0.12.3
------

* Fixed removal/override of related fields, when the referenced model is
  linked from more parent models on multiple levels  (thanks to @vkrizan);

0.12.2
------

* fixed weird completion widget behavior for unknown field types (thanks to
  @vkrizan);

0.12.0
------

* completion widget now supports passing either CSS selector or HTMLElement
  instance (thanks to @vkrizan);

0.11.0
------

* completion widget converted to a constructable JS object to improve  its
  compatibility with JS frameworks (thanks to @vkrizan);

0.10.3
------

* DjangoQL no longer depends on ContentType. Fixes use cases when the package
  is used without Django admin and ContentType is not used;

0.10.2
------

* Removed .DS_Store from the distribution (thanks to @vkrizan);

0.10.1
------

* Added Python 3.7 and Django 2.1 to the test matrix;
* removed PYTHONDONTWRITEBYTECODE from the setup.py and added test_project to
  the distribution (thanks to @vkrizan);

0.10.0
------

* Introducing Search Modes in the admin: now users can switch between Advanced
  Search mode (DjangoQL) and a standard Django search that you define with
  ``search_fields`` in your ModelAdmin;


0.9.1
-----

* Improved schema auto-generation. Now it avoids adding fields that may cause
  circular references, like ``author.book.author.book...``;


0.9.0
-----

* Fixed compatibility with Django 2.0, added Django 2.0 to the test matrix;
