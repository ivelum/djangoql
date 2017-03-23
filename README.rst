DjangoQL
========

.. image:: https://travis-ci.org/ivelum/djangoql.svg?branch=master
        :target: https://travis-ci.org/ivelum/djangoql

Query mini-language that translates into Django ORM. Supports logical operators,
parenthesis, table joins, works with any Django models. Tested vs. Python 2.7, 3.5 
and 3.6, Django 1.8, 1.9, 1.10.

Installation
------------

.. code:: shell

    $ pip install djangoql
    
Usage
-----

You can add DjangoQL search functionality to any Django model using
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


Django admin integration
------------------------

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

License
-------

MIT
