# -*- coding: utf-8 -*-
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType


class Query(models.Model):
    name = models.CharField(max_length=256, unique=True)
    query = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    public = models.BooleanField(default=True)
    model = models.ForeignKey(ContentType, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

