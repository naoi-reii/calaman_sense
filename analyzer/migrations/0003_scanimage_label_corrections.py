from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('analyzer', '0002_remove_scan_grade_letter_scan_quality_grade')]
    operations = [migrations.AddField(model_name='scanimage', name='label_corrections', field=models.JSONField(default=dict, blank=True))]
