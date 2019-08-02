import json
import logging
from functools import wraps

from django.views.generic import View
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Q
from django.forms.models import model_to_dict

from .models import Query
from .forms import QueryForm


logger = logging.getLogger(__name__)


def check_model(fn):
    @wraps(fn)
    def wrapper(self, request, *args, **kwargs):
        model = request.GET.get('model')
        if not model:
            return JsonResponse({'error': 'No model provided'}, status=400)
        model = ContentType.objects.get(model=model)
        return fn(self, request, model, *args, **kwargs)
    return wrapper


class QueryView(View):
    EXPOSED_MODEL_FIELDS = ('id', 'name', 'text', 'private')

    @check_model
    def get(self, request, model, *args, **kwargs):
        if kwargs.get('pk'):
            return self._get_one(request, model, *args, **kwargs)
        return self._get_list(request, model, *args, **kwargs)

    @check_model
    @method_decorator(login_required)
    def post(self, request, model, *args, **kwargs):
        obj = json.loads(request.body.decode())
        pk = obj.get('id')
        # If pk is provided, then we're modifying an existing query
        query = Query.objects.get(pk=pk) if pk else None
        form = QueryForm({
            'name': obj.get('name'),
            'text': obj.get('text'),
            'private': obj.get('private')
        }, instance=query)

        if form.is_valid():
            query = form.save(commit=False)
            query.content_type = model
            query.user = request.user
            query.save()
            return JsonResponse({'id': query.id})
        else:
            return JsonResponse({'errors': form.errors}, status=400)

    @check_model
    @method_decorator(login_required)
    def delete(self, request, model, *args, **kwargs):
        query = Query.objects.filter(
            Q(user=request.user) | Q(private=False), id=self.kwargs['pk'])

        query.delete()
        return JsonResponse({'ok': True})

    def _get_one(self, request, model, *args, **kwargs):
        obj = Query.objects.get(pk=kwargs.get('pk'))
        return JsonResponse(model_to_dict(obj, fields=self.EXPOSED_MODEL_FIELDS))

    def _get_list(self, request, model, *args, **kwargs):
        query = Query.objects.filter(content_type=model)
        query = query.filter(Q(user=request.user) | Q(private=False))

        return JsonResponse(
            list(query.values(*self.EXPOSED_MODEL_FIELDS)), safe=False
        )
