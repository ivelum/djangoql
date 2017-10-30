from django.views.generic import TemplateView
from django.views.generic import View
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from .models import Query
from .forms import QueryForm


class QueryView(View):
    model = None

    @property
    def _content_type(self):
        return ContentType.objects.get(
            app_label=self.model._meta.app_label,
            model=self.model._meta.model_name
        )

    def get(self, *args, **kwargs):
        if self.request.user.is_superuser:
            data = Query.objects.filter(model=self._content_type)
        else:
            data = Query.objects.filter(Q(user=self.request.user) | Q(public=True), model=self._content_type)
        return JsonResponse({'value': map(dict, data.values_list('id', 'name', 'query'))})

    def post(self, *args, **kwargs):
        filters = {'id': self.kwargs['pk']}
        if not self.request.user.is_superuser:
            filters.update({'user': self.request.user})
        try:
            instance = Query.objects.get(**filters)
            form = QueryForm(data=self.request.POST, instance=instance)
            try:
                form.save()
                response = {'ok': True}
            except ValueError:
                response = {'ok': False, 'errors': form.errors}
        except ObjectDoesNotExist:
            response = {'ok': False, 'errors': 'Not found'}
        return JsonResponse(response)

    def put(self, *args, **kwargs):
        form = QueryForm(data=self.request.PUT)
        try:
            form.save(commit=False)
            form.user = self.request.user
            form.model = self._content_type
            form.save()
            response = {'ok': True}
        except ValueError:
            response = {'ok': False, 'errors': form.errors}
        return JsonResponse(response)

    def delete(self, *args, **kwargs):
        ok = False
        filters = {'id': self.kwargs['pk']}
        if not self.request.user.is_superuser:
            filters.update({'user': self.request.user})
        result, _ = Query.objects.filter(**filters).delete()
        if result:
            ok = True
        return JsonResponse({'ok': ok})




