from django.contrib import messages
from django.core.exceptions import FieldError, ValidationError

from .exceptions import DjangoQLSyntaxError
from .queryset import apply_search


class DjangoQLSearchMixin(object):
    search_fields = ('_djangoql',)  # just a stub to have search input displayed

    def get_search_results(self, request, queryset, search_term):
        use_distinct = False
        if not search_term:
            return queryset, use_distinct
        catched = (DjangoQLSyntaxError, ValueError, FieldError, ValidationError)
        try:
            return apply_search(queryset, search_term), use_distinct
        except catched as e:
            messages.add_message(request, messages.WARNING, str(e))
            return queryset, use_distinct
