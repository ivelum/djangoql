from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from djangoql.admin import DjangoQLSearchMixin

from .models import Book


admin.site.unregister(User)


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ('name', 'author', 'written', 'is_published')
    list_filter = ('is_published',)


@admin.register(User)
class CustomUserAdmin(DjangoQLSearchMixin, UserAdmin):
    pass
