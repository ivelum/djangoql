from django.views.generic import View
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from .models import Query
from .forms import QueryForm


class QueryView(View):
    model = None

    def get(self, *args, **kwargs):
        if self.request.user.is_superuser:
            data = Query.objects.filter(model=self._content_type)
        else:
            data = Query.objects.filter(Q(user=self.request.user) | Q(public=True), model=self._content_type)
        return JsonResponse({'value': list(data.values('id', 'name', 'query', 'public'))})

    def post(self, *args, **kwargs):
        form = QueryForm(data=self.request.POST, instance=self._get_instance())
        if form.is_valid():
            query = form.save(commit=False)
            query.user = self.request.user
            query.model = self._content_type
            query.save()
            return JsonResponse({'ok': True, 'id': query.id})
        else:
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)

    def delete(self, *args, **kwargs):
        ok = False
        filters = {'id': self.kwargs['pk']}
        if not self.request.user.is_superuser:
            filters.update({'user': self.request.user})
        result, _ = Query.objects.filter(**filters).delete()
        if result:
            ok = True
        return JsonResponse({'ok': ok})

    @property
    def _content_type(self):
        return ContentType.objects.get_for_model(self.model)

    def _get_instance(self):
        name = self.request.POST.get('name')
        if self.request.user.is_superuser:
            queryset = Query.objects.filter(model=self._content_type)
        else:
            queryset = Query.objects.filter(Q(user=self.request.user) | Q(public=True))
        try:
            return queryset.get(name=name, model=self._content_type)
        except ObjectDoesNotExist:
            pass
        return None