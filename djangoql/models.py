from django.db import models
from django.conf import settings


class Query(models.Model):
    name = models.CharField(max_length=100)
    text = models.TextField()
    private = models.BooleanField(default=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='favorite_query_list',
        on_delete=models.CASCADE,
        blank=True,
        null=True)
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE)

    def __str__(self):
        return self.text
