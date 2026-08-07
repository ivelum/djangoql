# Django admin integration

## Add it to your Django admin

Adding `DjangoQLSearchMixin` to your model admin will replace the standard Django search functionality with DjangoQL search. Example:

``` python
from django.contrib import admin

from djangoql.admin import DjangoQLSearchMixin

from .models import Book


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    pass
```

## Using DjangoQL with the standard Django admin search

DjangoQL will recognize if you have defined `search_fields` in your ModelAdmin class, and doing so will allow you to choose between an advanced search with DjangoQL and a standard Django search (as specified by search fields). Example:

``` python
@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    search_fields = ('title', 'author__name')
```

For the example above, a checkbox that controls search mode will appear near the search input. If the checkbox is on, then DjangoQL search is used. There is also an option that controls if that checkbox is enabled by default - `djangoql_completion_enabled_by_default` (set to `True` by default):

``` python
@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    search_fields = ('title', 'author__name')
    djangoql_completion_enabled_by_default = False
```

If you don't want two search modes, simply remove `search_fields` from your ModelAdmin class.
