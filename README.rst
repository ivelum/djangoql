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


License
-------

MIT
