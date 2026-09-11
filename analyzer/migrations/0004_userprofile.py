from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('analyzer', '0003_scanimage_label_corrections'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='UserProfile', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('photo', models.ImageField(blank=True, upload_to='profiles/')),
        ('contact_number', models.CharField(blank=True, max_length=30)),
        ('farm_name', models.CharField(blank=True, max_length=150)),
        ('location', models.CharField(blank=True, max_length=255)),
        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
    ])]
