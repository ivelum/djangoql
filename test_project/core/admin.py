from django.contrib import admin

from djangoql.admin import DjangoQLSearchMixin

from .models import Book


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ('name', 'author', 'written', 'is_published')
    list_filter = ('is_published',)
