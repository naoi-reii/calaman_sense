from django.db import migrations


def restore_summaries(apps, schema_editor):
    Scan = apps.get_model('analyzer', 'Scan')
    ScanImage = apps.get_model('analyzer', 'ScanImage')
    for scan in Scan.objects.all().iterator():
        photo = ScanImage.objects.filter(scan_id=scan.pk).order_by('-id').first()
        if photo and photo.review_revision:
            boxes = photo.mock_annotations
            scan.fruit_count_total = len(boxes)
            for key in ('unripe', 'ripe', 'overripe'):
                count = sum(b.get('css_class') == key for b in boxes)
                setattr(scan, f'ripeness_{key}_pct', round(100*count/len(boxes), 2) if boxes else 0)
        if scan.model_version.startswith('yolov8') and not scan.quality_grade:
            ratio = scan.ripeness_unripe_pct / 100
            scan.quality_grade = 'Best Quality' if ratio >= .75 else 'Good Quality' if ratio >= .5 else 'Average'
            scan.size_small_pct, scan.size_medium_pct, scan.size_large_pct, scan.size_xl_pct = 25, 50, 20, 5
        scan.save()
    ScanImage.objects.filter(reviewed_annotations__isnull=False).update(label_corrections={})


class Migration(migrations.Migration):
    dependencies = [('analyzer', '0005_scanimage_review')]
    operations = [
        migrations.RunPython(restore_summaries, migrations.RunPython.noop),
        migrations.RemoveField(model_name='scanimage', name='reviewed_annotations'),
        migrations.RemoveField(model_name='scanimage', name='review_revision'),
        migrations.RemoveField(model_name='scanimage', name='photo_warnings'),
    ]
