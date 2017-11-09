from django import forms

from djangoql.models import FavoriteQuery


class FavoriteQueryCreateForm(forms.Form):
    text = forms.CharField()


class FavoriteQueryUpdateForm(forms.Form):
    text = forms.CharField(
        required=False,
    )
    name = forms.CharField(
        required=False,
    )
    scope = forms.ChoiceField(
        choices=FavoriteQuery.SCOPE_CHOICES,
        required=False,
    )
