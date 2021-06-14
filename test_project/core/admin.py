import time

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import Count, Q
from django.utils.timezone import now

from djangoql.admin import DjangoQLSearchMixin
from djangoql.schema import DjangoQLSchema, IntField, StrField

from .models import Book


admin.site.unregister(User)


class AuthorField(StrField):
    name = 'author'
    model = Book
    suggest_options = True

    def get_lookup_name(self):
        return 'author__username'

    def get_options(self, search):
        return Book.objects\
            .filter(author__username__icontains=search)\
            .values_list('author__username', flat=True)\
            .order_by('author__username')\
            .distinct()


class BookQLSchema(DjangoQLSchema):
    suggest_options = {
        Book: ['genre'],
    }

    def get_fields(self, model):
        fields = super(BookQLSchema, self).get_fields(model)
        if model == Book:
            fields += [AuthorField()]
        return fields


@admin.register(Book)
class BookAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    djangoql_schema = BookQLSchema
    list_display = ('name', 'author', 'genre', 'written', 'is_published')
    list_filter = ('is_published',)
    filter_horizontal = ('similar_books',)


class UserAgeField(IntField):
    """
    Search by given number of full years
    """
    model = User
    name = 'age'

    def get_lookup_name(self):
        """
        We'll be doing comparisons vs. this model field
        """
        return 'date_joined'

    def get_lookup(self, path, operator, value):
        if operator == 'in':
            result = None
            for year in value:
                condition = self.get_lookup(path, '=', year)
                result = condition if result is None else result | condition
            return result
        elif operator == 'not in':
            result = None
            for year in value:
                condition = self.get_lookup(path, '!=', year)
                result = condition if result is None else result & condition
            return result

        value = self.get_lookup_value(value)
        search_field = '__'.join(path + [self.get_lookup_name()])
        year_start = self.years_ago(value + 1)
        year_end = self.years_ago(value)
        if operator == '=':
            return (
                Q(**{'%s__gt' % search_field: year_start}) &
                Q(**{'%s__lte' % search_field: year_end})
            )
        elif operator == '!=':
            return (
                Q(**{'%s__lte' % search_field: year_start}) |
                Q(**{'%s__gt' % search_field: year_end})
            )
        elif operator == '>':
            return Q(**{'%s__lt' % search_field: year_start})
        elif operator == '>=':
            return Q(**{'%s__lt' % search_field: year_end})
        elif operator == '<':
            return Q(**{'%s__gt' % search_field: year_end})
        elif operator == '<=':
            return Q(**{'%s__gte' % search_field: year_start})

    def years_ago(self, n):
        timestamp = now()
        try:
            return timestamp.replace(year=timestamp.year - n)
        except ValueError:
            # February 29
            return timestamp.replace(month=2, day=28, year=timestamp.year - n)


class BookGenreField(StrField):
    model = Book
    name = 'name'
    suggest_options = True

    def get_options(self, search):
        time.sleep(1)
        return Book.objects.filter(
            name__icontains=search,
        ).values_list('name', flat=True)


class UserQLSchema(DjangoQLSchema):
    suggest_options = {
        Book: ['genre'],
        Group: ['name'],
    }

    def get_fields(self, model):
        fields = super(UserQLSchema, self).get_fields(model)
        if model == User:
            fields += [UserAgeField(), IntField(name='groups_count')]
        elif model == Book:
            fields += [BookGenreField()]
        return fields


@admin.register(User)
class CustomUserAdmin(DjangoQLSearchMixin, UserAdmin):
    djangoql_schema = UserQLSchema
    search_fields = ('username', 'first_name', 'last_name')

    list_display = ('username', 'first_name', 'last_name', 'is_staff', 'group')

    def group(self, obj):
        return ', '.join([g.name for g in obj.groups.all()])
    group.short_description = 'Groups'

    def get_queryset(self, request):
        qs = super(CustomUserAdmin, self).get_queryset(request)
        return qs.\
            annotate(groups_count=Count('groups')).\
            prefetch_related('groups')
