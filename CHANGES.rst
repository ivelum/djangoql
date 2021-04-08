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
