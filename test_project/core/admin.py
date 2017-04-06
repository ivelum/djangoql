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

    def get_options(self, model, field_name):
        if model == Group and field_name == 'name':
            return Group.objects.order_by('name').values_list('name', flat=True)


@admin.register(User)
class CustomUserAdmin(DjangoQLSearchMixin, UserAdmin):
    djangoql_schema = UserQLSchema

    list_display = ('username', 'first_name', 'last_name', 'is_staff', 'group')

    def group(self, obj):
        return ', '.join([g.name for g in obj.groups.all()])
    group.short_description = 'Groups'
