from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group

from djangoql.admin import DjangoQLSearchMixin
from djangoql.schema import DjangoQLSchema

from .models import Book


admin.site.unregister(User)


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = ('name', 'author', 'written', 'is_published')
    list_filter = ('is_published',)


class UserQLSchema(DjangoQLSchema):
    exclude = (Book,)

    def get_fields(self, model):
        if model == Group:
            return ['name']
        return super(UserQLSchema, self).get_fields(model)


@admin.register(User)
class CustomUserAdmin(DjangoQLSearchMixin, UserAdmin):
    djangoql_schema = UserQLSchema
