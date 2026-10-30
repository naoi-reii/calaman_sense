from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analyzer', '0006_remove_recent_features')]
    operations = [migrations.AddField(
        model_name='scan', name='upload_group_id',
        field=models.UUIDField(null=True, blank=True, db_index=True),
    )]
