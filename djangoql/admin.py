from collections import OrderedDict
import json

from django.apps import apps
from django.conf.urls import url
from django.contrib import messages
from django.core.exceptions import FieldError, ValidationError
from django.db.models import AutoField, BooleanField, CharField, DateField, \
    DateTimeField, DecimalField, FloatField, IntegerField, NullBooleanField, \
    TextField
from django.http import HttpResponse

from .exceptions import DjangoQLSyntaxError
from .queryset import apply_search


class DjangoQLSearchMixin(object):
    search_fields = ('_djangoql',)  # just a stub to have search input displayed
    djangoql_completion = True

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

    @property
    def media(self):
        media = super(DjangoQLSearchMixin, self).media
        if self.djangoql_completion:
            media.add_js((
                'js/lib/lexer.js',
                'js/djangoql_completion.js',
                'js/djangoql_completion_admin.js',
            ))
            media.add_css({'': (
                'css/djangoql_completion.css',
                'css/djangoql_completion_admin.css',
            )})
        return media

    def get_urls(self):
        custom_urls = []
        if self.djangoql_completion:
            custom_urls += [
                url(
                    r'^introspect/$',
                    self.admin_site.admin_view(self.introspect),
                    name='%s_%s_djangoql_introspect' % (
                        self.model._meta.app_label,
                        self.model._meta.model_name,
                    ),
                ),
            ]
        return custom_urls + super(DjangoQLSearchMixin, self).get_urls()

    def introspect(self, request):
        models = {}
        for app_label in apps.app_configs:
            for model in apps.get_app_config(app_label).get_models():
                fields = {}
                for field in model._meta.get_fields():
                    if field.is_relation:
                        if not field.related_model:
                            # GenericForeignKey
                            continue
                        field_type = 'relation'
                        relation = str(field.related_model._meta)
                    else:
                        field_type = self.get_field_type(field)
                        relation = None
                    fields[field.name] = {
                        'type': field_type,
                        'relation': relation,
                    }
                models[str(model._meta)] = OrderedDict(sorted(fields.items()))
        response = {
            'current_model': str(self.model._meta),
            'models': models,
        }
        return HttpResponse(
            content=json.dumps(response, indent=2),
            content_type='application/json; charset=utf-8',
        )

    def get_field_type(self, field):
        if isinstance(field, (AutoField, IntegerField)):
            return 'int'
        elif isinstance(field, (CharField, TextField)):
            return 'str'
        elif isinstance(field, (BooleanField, NullBooleanField)):
            return 'bool'
        elif isinstance(field, (DecimalField, FloatField)):
            return 'float'
        elif isinstance(field, DateTimeField):
            return 'datetime'
        elif isinstance(field, DateField):
            return 'date'
        return 'unknown'
