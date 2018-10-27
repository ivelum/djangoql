from django.db import models
from django.contrib.auth.models import User

class history(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    query = models.CharField(max_length=2000)
