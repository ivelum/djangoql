# Using DjangoQL outside the admin

Sure. You can add DjangoQL search functionality to any Django model using `DjangoQLQuerySet`:

``` python
from django.db import models

from djangoql.queryset import DjangoQLQuerySet


class Book(models.Model):
    name = models.CharField(max_length=255)
    author = models.ForeignKey('auth.User')

    objects = DjangoQLQuerySet.as_manager()
```

With the example above you can perform a search like this:

``` python
qs = Book.objects.djangoql(
    'name ~ "war" and author.last_name = "Tolstoy"'
)
```

It returns a normal queryset, so you can extend it and reuse if necessary. The following code works fine:

``` python
print(qs.count())
```

Alternatively you can add DjangoQL search to any existing queryset, even if it's not an instance of DjangoQLQuerySet:

``` python
from django.contrib.auth.models import User

from djangoql.queryset import apply_search

qs = User.objects.all()
qs = apply_search(qs, 'groups = None')
print(qs.exists())
```

Schemas can be specified either as a queryset option, or passed to `.djangoql()` queryset method directly:

``` python
class BookQuerySet(DjangoQLQuerySet):
    djangoql_schema = BookSchema


class Book(models.Model):
    ...

    objects = BookQuerySet.as_manager()

# Now, Book.objects.djangoql() will use BookSchema by default:
Book.objects.djangoql('name ~ "Peace"')  # uses BookSchema

# Overriding default queryset schema with AnotherSchema:
Book.objects.djangoql('name ~ "Peace"', schema=AnotherSchema)
```

You can also provide schema as an option for `apply_search()`

``` python
qs = User.objects.all()
qs = apply_search(qs, 'groups = None', schema=CustomSchema)
```
