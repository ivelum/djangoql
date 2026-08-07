from django.contrib import admin

from djangoql.admin import DjangoQLSearchMixin

from .models import Author, Book, Country, Genre, Publisher
from .schema import BookSchema


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    # Turn on the (opt-in) syntax-highlighting overlay in the admin search box.
    djangoql_highlight = True
    # Expose `author` as both a relation and the `author__rel` object-picker.
    djangoql_schema = BookSchema
    list_display = (
        'title',
        'author',
        'publisher',
        'year',
        'rating',
        'price',
        'in_stock',
    )
    list_filter = ('in_stock', 'year')
    list_select_related = ('author', 'publisher')
    autocomplete_fields = ('author', 'publisher', 'genres')


@admin.register(Author)
class AuthorAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    djangoql_highlight = True
    list_display = ('name', 'country', 'born', 'alive')
    list_filter = ('alive',)
    search_fields = ('name',)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'founded')
    search_fields = ('name',)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ('name',)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')
