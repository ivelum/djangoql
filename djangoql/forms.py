from django import forms
from .models import Query


class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        fields = ['name', 'query', 'public']