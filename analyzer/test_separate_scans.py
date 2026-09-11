"""Each uploaded photo keeps its own analysis result."""
import tempfile
from dataclasses import fields
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Scan
from services.analysis.types import ScanAnalysisResult

class SeparateImageScanTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.client.force_login(User.objects.create_user(username='grower'))

    def result(self, count, grade):
        values = {field.name: 0 for field in fields(ScanAnalysisResult)}
        values.update(fruit_count_total=count, fruit_count_good=count,
                      quality_grade=grade, model_version='test', mock_annotations=[],
                      ripeness_unripe_pct=100)
        return ScanAnalysisResult(**values)

    @patch('analyzer.views.get_analysis_provider')
    def test_multiple_images_are_independent(self, provider):
        provider.return_value.analyze.side_effect = [self.result(10, 'Good Quality'), self.result(20, 'Average')]
        response = self.client.post('/upload/', {'images': [SimpleUploadedFile('one.jpg', b'one', content_type='image/jpeg'), SimpleUploadedFile('two.jpg', b'two', content_type='image/jpeg')], 'batch_name': 'Same sample'})
        self.assertRedirects(response, '/reports/')
        scans = list(Scan.objects.order_by('id'))
        self.assertEqual([s.fruit_count_total for s in scans], [10,20])
        self.assertEqual([s.quality_grade for s in scans], ['Good Quality','Average'])
        self.assertTrue(all(s.images.count() == 1 for s in scans))
        self.assertTrue(all(s.batch_name == 'Same sample' for s in scans))

    @patch('analyzer.views.get_analysis_provider')
    def test_single_image_opens_its_result(self, provider):
        provider.return_value.analyze.return_value = self.result(7, 'Best Quality')
        response = self.client.post('/upload/', {'images': SimpleUploadedFile('one.jpg', b'one', content_type='image/jpeg')})
        scan = Scan.objects.get()
        self.assertRedirects(response, f'/reports/{scan.id}/')
        self.assertEqual(scan.fruit_count_total, 7)

    @patch('analyzer.views.get_analysis_provider')
    def test_failed_photo_removed_successful_photo_kept(self, provider):
        from .models import ScanImage
        from pathlib import Path
        provider.return_value.analyze.side_effect = [RuntimeError('analysis failed'), self.result(12, 'Average')]
        response = self.client.post('/upload/', {'images': [SimpleUploadedFile('failed.jpg', b'bad', content_type='image/jpeg'), SimpleUploadedFile('success.jpg', b'ok', content_type='image/jpeg')]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'failed.jpg')
        self.assertContains(response, 'Only retry the failed photos')
        self.assertEqual(Scan.objects.count(), 1)
        self.assertEqual(Scan.objects.get().fruit_count_total, 12)
        self.assertEqual(ScanImage.objects.count(), 1)
        self.assertEqual(len(list(Path(self.media.name).rglob('*.jpg'))), 1)

    @patch('analyzer.views.get_analysis_provider')
    def test_provider_failure_creates_no_scan(self, provider):
        provider.side_effect = RuntimeError('unavailable')
        response = self.client.post('/upload/', {'images': SimpleUploadedFile('one.jpg', b'one')})
        self.assertContains(response, 'temporarily unavailable')
        self.assertFalse(Scan.objects.exists())

    def test_empty_upload_has_helpful_error(self):
        response = self.client.post('/upload/', {})
        self.assertContains(response, 'Please choose at least one image')
