import json

from django.contrib import messages
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import FieldError, ValidationError
from django.db import DataError
from django.forms import Media
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.generic import TemplateView

from .compat import text_type
from .exceptions import DjangoQLError
from .queryset import apply_search
from .schema import DjangoQLSchema
from .serializers import SuggestionsAPISerializer
from .views import SuggestionsAPIView


try:
    from django.core.urlresolvers import reverse
except ImportError:  # Django 2.0
    from django.urls import reverse

try:
    from django.conf.urls import re_path
except ImportError:  # Django <2.0
    from django.conf.urls import url as re_path

DJANGOQL_SEARCH_MARKER = 'q-l'


class DjangoQLChangeList(ChangeList):
    def get_filters_params(self, *args, **kwargs):
        params = super(DjangoQLChangeList, self).get_filters_params(
            *args,
            **kwargs
        )
        if DJANGOQL_SEARCH_MARKER in params:
            del params[DJANGOQL_SEARCH_MARKER]
        return params


class DjangoQLSearchMixin(object):
    search_fields = ('_djangoql',)  # just a stub to have search input displayed
    djangoql_completion = True
    djangoql_completion_enabled_by_default = True
    djangoql_schema = DjangoQLSchema
    djangoql_syntax_help_template = 'djangoql/syntax_help.html'

    def search_mode_toggle_enabled(self):
        # If search fields were defined on a child ModelAdmin instance,
        # we suppose that the developer wants two search modes and therefore
        # enable search mode toggle
        return self.search_fields != DjangoQLSearchMixin.search_fields

    def djangoql_search_enabled(self, request):
        return request.GET.get(DJANGOQL_SEARCH_MARKER, '').lower() == 'on'

    def get_changelist(self, *args, **kwargs):
        return DjangoQLChangeList

    def get_search_results(self, request, queryset, search_term):
        if (
            self.search_mode_toggle_enabled() and
            not self.djangoql_search_enabled(request)
        ):
            return super(DjangoQLSearchMixin, self).get_search_results(
                request=request,
                queryset=queryset,
                search_term=search_term,
            )
        use_distinct = False
        if not search_term:
            return queryset, use_distinct

        try:
            qs = apply_search(queryset, search_term, self.djangoql_schema)
        except (DjangoQLError, ValueError, FieldError, ValidationError) as e:
            msg = self.djangoql_error_message(e)
            messages.add_message(request, messages.WARNING, msg)
            qs = queryset.none()
        else:
            # Hack to handle 'inet' comparison errors in Postgres. If you
            # know a better way to check for such an error, please submit a PR.
            try:
                qs.explain()
            except DataError as e:
                if '::inet' not in str(e):
                    raise
                msg = self.djangoql_error_message(e)
                messages.add_message(request, messages.WARNING, msg)
                qs = queryset.none()

        return qs, use_distinct

    def djangoql_error_message(self, exception):
        if isinstance(exception, ValidationError):
            msg = exception.messages[0]
        else:
            msg = text_type(exception)
        return render_to_string('djangoql/error_message.html', context={
            'error_message': msg,
        })

    @property
    def media(self):
        media = super(DjangoQLSearchMixin, self).media
        if self.djangoql_completion:
            js = [
                'djangoql/js/completion.js',
            ]
            if self.search_mode_toggle_enabled():
                js.append('djangoql/js/completion_admin_toggle.js')
                if not self.djangoql_completion_enabled_by_default:
                    js.append('djangoql/js/completion_admin_toggle_off.js')
            js.append('djangoql/js/completion_admin.js')
            media += Media(
                css={'': (
                    'djangoql/css/completion.css',
                    'djangoql/css/completion_admin.css',
                )},
                js=js,
            )
        return media

    def get_urls(self):
        custom_urls = []
        if self.djangoql_completion:
            custom_urls += [
                re_path(
                    r'^introspect/$',
                    self.admin_site.admin_view(self.introspect),
                    name='%s_%s_djangoql_introspect' % (
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
                re_path(
                    r'^suggestions/$',
                    self.admin_site.admin_view(self.suggestions),
                    name='%s_%s_djangoql_suggestions' % (
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
                re_path(
                    r'^djangoql-syntax/$',
                    self.admin_site.admin_view(TemplateView.as_view(
                        template_name=self.djangoql_syntax_help_template,
                    )),
                    name='djangoql_syntax_help',
                ),
            ]
        return custom_urls + super(DjangoQLSearchMixin, self).get_urls()

    def introspect(self, request):
        suggestions_url = reverse('admin:%s_%s_djangoql_suggestions' % (
            self.model._meta.app_label,
            self.model._meta.model_name,
        ))
        serializer = SuggestionsAPISerializer(suggestions_url)
        response = serializer.serialize(self.djangoql_schema(self.model))
        return HttpResponse(
            content=json.dumps(response, indent=2),
            content_type='application/json; charset=utf-8',
        )

    def suggestions(self, request):
        view = SuggestionsAPIView.as_view(
            schema=self.djangoql_schema(self.model),
        )
        return view(request)
