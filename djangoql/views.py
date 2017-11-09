from django.http import JsonResponse
from django.views.generic import edit
from django.contrib.contenttypes.models import ContentType

from djangoql import forms
from djangoql.models import FavoriteQuery


class FavoriteQueryCreateListView(edit.BaseFormView):
    form_class = forms.FavoriteQueryCreateForm
    model = None

    def get(self, request, *args, **kwargs):
        content_type = ContentType.objects.get_for_model(self.model)

        private_queryset = request.user.favorite_query_list.filter(content_type=content_type)
        shared_queryset = FavoriteQuery.objects.filter(scope=FavoriteQuery.SHARED, content_type=content_type)

        queryset = private_queryset | shared_queryset

        return JsonResponse({
            'favorite_query_list': [item.as_dict(request.user) for item in queryset],
        })

    def form_invalid(self, form):
        return JsonResponse({
            'errors': form.errors,
        })

    def form_valid(self, form):
        query, _ = self.request.user.favorite_query_list.get_or_create(
            text=form.cleaned_data['text'],
            content_type=ContentType.objects.get_for_model(self.model),
        )

        return JsonResponse({
            'favorite_query': query.as_dict(self.request.user),
        })


class FavoriteQueryDestroyUpdateView(edit.FormMixin, edit.View):
    form_class = forms.FavoriteQueryUpdateForm

    def delete(self, request, *args, **kwargs):
        try:
            self.request.user.favorite_query_list.get(pk=kwargs['pk']).delete()

            return JsonResponse({
                'favorite_query': None,
            })

        except FavoriteQuery.DoesNotExist:
            return JsonResponse({
                'errors': 'object_doesnt_exists',
            })

    # TODO PUT / PATCH
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        return JsonResponse({
            'errors': form.errors,
        })

    def form_valid(self, form):
        try:
            query = self.request.user.favorite_query_list.get(pk=self.kwargs['pk'])

            for key in form.changed_data:
                setattr(query, key, form.cleaned_data.get(key))

            query.save()

            return JsonResponse({
                'favorite_query': query.as_dict(self.request.user),
            })

        except FavoriteQuery.DoesNotExist:
            return JsonResponse({
                'errors': 'object_doesnt_exists',
            })
