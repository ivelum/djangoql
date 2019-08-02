from django.db import migrations
from django.conf import settings
from django.contrib.auth.hashers import make_password

def create_demo_user(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    User.objects.create(
        username='demo',
        password=make_password('demo')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_book_similar_books_related_name'),
    ]

    operations = [
        migrations.RunPython(create_demo_user)
    ]
