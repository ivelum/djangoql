DjangoQL
========

.. image:: https://travis-ci.org/ivelum/djangoql.svg?branch=master
        :target: https://travis-ci.org/ivelum/djangoql

Advanced search language for Django, with auto-completion. Supports logical
operators, parenthesis, table joins, works with any Django models. Tested vs.
Python 2.7, 3.5 and 3.6, Django 1.8 - 1.11. Auto-completion feature tested
in Chrome, Firefox, Safari, IE9+.

See a video: `DjangoQL demo <https://youtu.be/oKVff4dHZB8>`_

.. image:: https://raw.githubusercontent.com/ivelum/djangoql/master/djangoql/static/djangoql/img/completion_example_scaled.png

Installation
------------

.. code:: shell

    $ pip install djangoql

Add ``'djangoql'`` to ``INSTALLED_APPS`` in your ``settings.py``:

.. code:: python

    INSTALLED_APPS = [
        ...
        'djangoql',
        ...
    ]


Add it to your Django admin
---------------------------

Add ``DjangoQLSearchMixin`` to your model admin, and it will replace standard
Django search functionality with DjangoQL search. Example:

.. code:: python

    from django.contrib import admin

    from djangoql.admin import DjangoQLSearchMixin

    from .models import Book


    @admin.register(Book)
    class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
        pass


Language reference
------------------

DjangoQL is shipped with comprehensive Syntax Help, which is
available in Django admin (see Syntax Help link in auto-completion
popup). Here's a quick summary:

DjangoQL looks close to Python syntax, however there're some minor
differences. Basically you just reference model fields like you do
it in Python code, apply comparison and logical operators and
parenthesis. DjangoQL is case-sensitive.

- model fields: exactly as they are defined in Python code. Access
  nested properties via ``.``, for example ``author.last_name``;
- strings must be double-quoted. Single quotes are not supported.
  To escape a double quote use ``\"``;
- boolean and null values: ``True``, ``False``, ``None``. Please note
  that they can be combined with equality operators only, so you can
  write ``published = False or date_published = None``, but
  ``published > False`` will cause an error;
- logical operators: ``and``, ``or``;
- comparison operators: ``=``, ``!=``, ``<``, ``<=``, ``>``, ``>=``
  - work as you expect. ``~`` and ``!~`` - test that a string contains
  or not contains a substring (translated into ``__icontains``);
- test a value vs. list: ``in``, ``not in``. Example:
  ``pk in (2, 3)``.


DjangoQL Schema
---------------

Schema defines limitations - what you can do with a DjangoQL query.
If you don't specify any schema, DjangoQL will provide a default
schema for you. It would recursively walk though all model fields and
relations and include everything it could find in the schema, so
users would be able to search through everything. However sometimes
this is not what you want, either due to DB performance or security
concerns. If you'd like to limit search models or fields, you should
define a schema. Here's an example:

.. code:: python

    class UserQLSchema(DjangoQLSchema):
        exclude = (Book,)

        def get_fields(self, model):
            if model == Group:
                return ['name']
            return super(UserQLSchema, self).get_fields(model)


    @admin.register(User)
    class CustomUserAdmin(DjangoQLSearchMixin, UserAdmin):
        djangoql_schema = UserQLSchema

In the example above we created a schema that excludes Book model
from search, and also limits available search fields for Group model
to ``name`` only. Instead of ``exclude`` you may also use ``include``,
it would limit search to listed models only.

Another use case for schemas is values auto-completion. You can
optionally override ``.get_options()`` method to provide value
options for auto-completion widget. In the example below we use this
feature to provide options for Group names:

.. code:: python

    class UserQLSchema(DjangoQLSchema):
        include = (User, Group)

        def get_options(self, model, field_name):
            if model == Group and field_name == 'name':
                return Group.objects.order_by('name').values_list('name', flat=True)


    @admin.register(User)
    class CustomUserAdmin(DjangoQLSearchMixin, UserAdmin):
        djangoql_schema = UserQLSchema

Please note that all value options are loaded synchronously, so you
should avoid large lists there.


Can I use it outside of Django admin?
-------------------------------------

Sure. You can add DjangoQL search functionality to any Django model using
``DjangoQLQuerySet``:

.. code:: python

    from django.db import models

    from djangoql.queryset import DjangoQLQuerySet


    class Book(models.Model):
        name = models.CharField(max_length=255)
        author = models.ForeignKey('auth.User')

        objects = DjangoQLQuerySet.as_manager()

With the example above you can perform search like this:

.. code:: python

    qs = Book.objects.djangoql(
        'name ~ "war" and author.last_name = "Tolstoy"'
    )

It returns a normal queryset, so you can extend it and reuse if
necessary. The following code works fine:

.. code:: python

    print(qs.count())

Alternatively you can add DjangoQL search to any existing queryset,
even if it's not an instance of DjangoQLQuerySet:

.. code:: python

    from django.contrib.auth.models import User

    from djangoql.queryset import apply_search

    qs = User.objects.all()
    qs = apply_search(qs, 'groups = None')
    print(qs.exists())

Schemas can be specified either as a queryset option, or passed
to ``.djangoql()`` queryset method directly:

.. code:: python

    class BookQuerySet(DjangoQLQuerySet):
        djangoql_schema = BookSchema


    class Book(models.Model):
        ...

        objects = BookQuerySet.as_manager()

    # Now, Book.objects.djangoql() will use BookSchema by default:
    Book.objects.djangoql('name ~ "Peace")  # uses BookSchema

    # Overriding default queryset schema with AnotherSchema:
    Book.objects.djangoql('name ~ "Peace", schema=AnotherSchema)

You can also provide schema as an option for ``apply_search()``

.. code:: python

    qs = User.objects.all()
    qs = apply_search(qs, 'groups = None', schema=CustomSchema)


Using completion widget outside of Django admin
-----------------------------------------------

Completion widget is not tightly coupled to Django admin, so you can easily
use it outside of admin if you want. Here is an example:

Template code, ``completion_demo.html``:

.. code:: html

    {% load static %}
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>DjangoQL completion demo</title>
      <link rel="stylesheet" type="text/css" href="{% static 'djangoql/css/completion.css' %}" />
      <script src="{% static 'djangoql/js/lib/lexer.js' %}"></script>
      <script src="{% static 'djangoql/js/completion.js' %}"></script>
    </head>
    <body>

      <form action="" method="get">
        <p style="color: red">{{ error }}</p>
        <textarea name="q" cols="40" rows="1" autofocus>{{ q }}</textarea>
      </form>

      <ul>
      {% for item in search_results %}
        <li>{{ item }}</li>
      {% endfor %}
      </ul>

      <script>
        DjangoQL.DOMReady(function () {
          DjangoQL.init({
            // either JS object with a result of DjangoQLSchema(MyModel).as_dict(),
            // or an URL from which this information could be loaded asynchronously
            introspections: {{ introspections|safe }},

            // css selector for query input. It should be a textarea
            selector: 'textarea[name=q]',

            // optional, you can provide URL for Syntax Help link here.
            // If not specified, Syntax Help link will be hidden.
            syntaxHelp: null,

            // optional, enable textarea auto-resize feature. If enabled,
            // textarea will automatically grow its height when entered text
            // doesn't fit, and shrink back when text is removed. The purpose
            // of this is to see full search query without scrolling, could be
            // helpful for really long queries.
            autoResize: true
          });
        });
      </script>
    </body>
    </html>

And in your ``views.py``:

.. code:: python

    import json

    from django.contrib.auth.models import Group, User
    from django.shortcuts import render_to_response
    from django.views.decorators.http import require_GET

    from djangoql.exceptions import DjangoQLError
    from djangoql.queryset import apply_search
    from djangoql.schema import DjangoQLSchema


    class UserQLSchema(DjangoQLSchema):
        include = (User, Group)


    @require_GET
    def completion_demo(request):
        q = request.GET.get('q', '')
        error = ''
        query = User.objects.all().order_by('username')
        if q:
            try:
                query = apply_search(query, q, schema=UserQLSchema)
            except DjangoQLError as e:
                query = query.none()
                error = str(e)
        return render_to_response('completion_demo.html', {
            'q': q,
            'error': error,
            'search_results': query,
            'introspections': json.dumps(UserQLSchema(query.model).as_dict()),
        })


License
-------

MIT
