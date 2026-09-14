from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analyzer', '0004_userprofile')]
    operations = [
        migrations.AddField(model_name='scanimage', name='reviewed_annotations', field=models.JSONField(null=True, blank=True, default=None)),
        migrations.AddField(model_name='scanimage', name='review_revision', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='scanimage', name='photo_warnings', field=models.JSONField(default=list, blank=True)),
    ]
