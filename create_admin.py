import os
import django
from django.contrib.auth.models import User

# This will run within the django shell context if we set DJANGO_SETTINGS_MODULE
# But easier to just use `python manage.py shell < create_admin.py`
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'Admin123')
    print("Created admin user")
else:
    print("Admin user already exists")
