
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not all([username, email, password]):
    raise RuntimeError("Set the three DJANGO_SUPERUSER environment variables.")

if User.objects.filter(username=username).exists():
    print("Superuser already exists.")
else:
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
    )
    print("Superuser created successfully.")
