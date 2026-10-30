"""Each uploaded photo keeps its own analysis result."""
import tempfile
from dataclasses import fields
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Scan
from services.analysis.types import ScanAnalysisResult
from django.core import signing
from django.urls import reverse

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
        token = signing.dumps(list(Scan.objects.order_by('id').values_list('id', flat=True)), salt='upload-results')
        self.assertEqual(response.status_code, 302)
        overview = self.client.get(response.url)
        self.assertEqual(overview.status_code, 200)
        self.assertContains(overview, 'Combined results from all 2 uploaded images.')
        self.assertEqual(overview.context['overall']['total'], 30)
        self.assertContains(overview, 'class="result-summary"', count=1)
        self.assertContains(overview, 'id="group-image-track"', count=1)
        self.assertContains(overview, 'class="result-figure"', count=2)
        self.assertContains(overview, 'id="group-individual-result"')
        scans = list(Scan.objects.order_by('id'))
        self.assertEqual([s.fruit_count_total for s in scans], [10,20])
        self.assertEqual([s.quality_grade for s in scans], ['Good Quality','Average'])
        self.assertTrue(all(s.images.count() == 1 for s in scans))
        self.assertTrue(all(s.batch_name == 'Same sample' for s in scans))
        self.assertIsNotNone(scans[0].upload_group_id)
        self.assertEqual(scans[0].upload_group_id, scans[1].upload_group_id)
        history = self.client.get('/reports/')
        self.assertNotContains(history, 'id="view-multiple-results"')
        self.assertNotContains(history, 'history-group-link')
        # History can reopen the group without retaining the original upload URL.
        reopened = self.client.get(reverse('report_detail', args=[scans[0].id]))
        self.assertEqual(len(reopened.context['upload_scans']), 2)
        detail = self.client.get(reverse('report_detail', args=[scans[0].id]), {'group': token})
        self.assertContains(detail, 'All 2 images')
        self.assertContains(detail, 'aria-current="page"')

    @patch('analyzer.views.get_analysis_provider')
    def test_five_images_are_accepted(self, provider):
        provider.return_value.analyze.return_value = self.result(3, 'Average')
        images = [SimpleUploadedFile(f'{i}.jpg', b'image', content_type='image/jpeg') for i in range(5)]
        response = self.client.post('/upload/', {'images': images})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Scan.objects.count(), 5)
        self.assertContains(self.client.get(response.url), 'Combined results from all 5 uploaded images.')

    def test_slider_keeps_each_images_ripeness_and_counts(self):
        from .models import ScanImage
        owner = User.objects.get(username='grower')
        scans = []
        for index, key in enumerate(('unripe', 'overripe')):
            scan = Scan.objects.create(created_by=owner, fruit_count_total=index + 1,
                                       ripeness_unripe_pct=100 if index == 0 else 0,
                                       ripeness_overripe_pct=100 if index == 1 else 0)
            ScanImage.objects.create(scan=scan, image=SimpleUploadedFile(f'{index}.jpg', b'image'),
                                     mock_annotations=[{'css_class': key, 'label': f'{key} 99%',
                                                        'x': 10, 'y': 20, 'width': 30, 'height': 40}] * (index + 1))
            scans.append(scan)
        token = signing.dumps([scan.id for scan in scans], salt='upload-results')
        response = self.client.get(reverse('upload_results', args=[token]))
        self.assertEqual(response.status_code, 200)
        cards = response.context['result_cards']
        self.assertEqual([row['count'] for row in cards[0]['rows']], [1, 0, 0])
        self.assertEqual([row['count'] for row in cards[1]['rows']], [0, 0, 2])
        self.assertEqual(cards[0]['rows'][0]['pct'], 100)
        self.assertEqual(cards[1]['rows'][2]['pct'], 100)
        self.assertContains(response, 'unripe 99%')
        self.assertContains(response, 'overripe 99%')
        self.assertContains(response, 'id="toggle-labels"')
        self.assertContains(response, 'data-group-slide="1"')
        overall = response.context['overall']
        self.assertEqual(overall['total'], 3)
        self.assertTrue(overall['counts_available'])
        self.assertEqual([row['count'] for row in overall['rows']], [1, 0, 2])
        self.assertAlmostEqual(overall['rows'][0]['pct'], 100 / 3)
        self.assertAlmostEqual(overall['rows'][2]['pct'], 200 / 3)
        self.assertEqual(overall['dominant'], 'overripe')
        self.assertContains(response, 'id="overall-fruit-count"', count=1)
        html = response.content.decode()
        photo_box = html.split('id="group-image-track"', 1)[1].split('id="group-image-prev"', 1)[0]
        self.assertNotIn('class="result-summary"', photo_box)
        for control in ('Save PDF', 'Batch Grade', 'Notes', 'Fruit Inspector', 'Hide labels', 'Scan Another'):
            self.assertContains(response, control)
        photo = scans[1].images.get()
        correction = self.client.post(reverse('upload_results', args=[token]),
                                      {'image_id': photo.id, 'index': 0, 'label': 'ripe'})
        self.assertEqual(correction.status_code, 200)
        photo.refresh_from_db()
        self.assertEqual(photo.label_corrections, {'0': 'ripe'})
        self.assertEqual(photo.mock_annotations[0]['css_class'], 'overripe')
        with patch('analyzer.pdf_export.scan_page_pdf') as export:
            from django.http import HttpResponse
            export.return_value = HttpResponse(b'%PDF-test', content_type='application/pdf')
            pdf = self.client.get(reverse('upload_results', args=[token]), {'download': 'pdf'})
            self.assertEqual(pdf['Content-Type'], 'application/pdf')
            context = export.call_args.args[1]
            self.assertEqual(context['scan'].fruit_count_total, 3)
            self.assertEqual(len(context['scan'].images.all()), 2)
            self.assertEqual(export.call_args.kwargs['template_name'], 'upload_results.html')

    def test_combined_legacy_percentages_are_weighted_by_fruit_count(self):
        owner = User.objects.get(username='grower')
        small = Scan.objects.create(created_by=owner, fruit_count_total=1, ripeness_unripe_pct=100)
        large = Scan.objects.create(created_by=owner, fruit_count_total=9, ripeness_ripe_pct=100)
        token = signing.dumps([small.id, large.id], salt='upload-results')
        response = self.client.get(reverse('upload_results', args=[token]))
        overall = response.context['overall']
        self.assertEqual(overall['total'], 10)
        self.assertFalse(overall['counts_available'])
        self.assertEqual([row['pct'] for row in overall['rows']], [10, 90, 0])
        self.assertTrue(all(row['count'] is None for row in overall['rows']))

    def test_combined_empty_results_have_zero_percentages(self):
        owner = User.objects.get(username='grower')
        scans = [Scan.objects.create(created_by=owner) for _ in range(3)]
        token = signing.dumps([scan.id for scan in scans], salt='upload-results')
        overall = self.client.get(reverse('upload_results', args=[token])).context['overall']
        self.assertEqual(overall['total'], 0)
        self.assertEqual([row['pct'] for row in overall['rows']], [0, 0, 0])
        self.assertEqual(overall['dominant'], 'none')
        self.assertIsNone(overall['quality_grade'])

    def test_combined_grade_uses_all_fruits_and_exact_thresholds(self):
        owner = User.objects.get(username='grower')
        cases = [
            ([9, 1], [100, 0], 'Best Quality'),
            ([3, 1], [100, 0], 'Best Quality'),
            ([1, 1], [100, 0], 'Good Quality'),
            ([1, 9], [100, 0], 'Average'),
            ([2, 3, 5], [100, 100, 0], 'Good Quality'),
            ([1, 1], [74.99, 74.99], 'Good Quality'),
            ([1, 1], [49.99, 49.99], 'Average'),
        ]
        for totals, percentages, expected in cases:
            with self.subTest(totals=totals, percentages=percentages):
                scans = [Scan.objects.create(created_by=owner, fruit_count_total=total,
                                              ripeness_unripe_pct=pct, ripeness_ripe_pct=100-pct,
                                              quality_grade='Rejected')
                         for total, pct in zip(totals, percentages)]
                token = signing.dumps([scan.id for scan in scans], salt='upload-results')
                response = self.client.get(reverse('upload_results', args=[token]))
                self.assertEqual(response.context['scan'].quality_grade, expected)
                self.assertEqual(response.context['overall']['quality_grade'], expected)
                self.assertNotContains(response, 'Mixed grades')
                self.assertContains(response, 'Based on overall ripeness across all images')
                # Group grading must never overwrite the saved individual grade.
                self.assertTrue(all(Scan.objects.get(pk=scan.id).quality_grade == 'Rejected' for scan in scans))

    @patch('analyzer.views.get_analysis_provider')
    def test_six_images_are_rejected_before_analysis(self, provider):
        images = [SimpleUploadedFile(f'{i}.jpg', b'image', content_type='image/jpeg') for i in range(6)]
        response = self.client.post('/upload/', {'images': images})
        self.assertContains(response, 'no more than 5 images')
        provider.assert_not_called()
        self.assertFalse(Scan.objects.exists())

    def test_group_results_check_ownership_and_signature(self):
        owner = User.objects.get(username='grower')
        other = User.objects.create_user(username='other-grower')
        first = Scan.objects.create(created_by=owner)
        second = Scan.objects.create(created_by=owner)
        unrelated = Scan.objects.create(created_by=owner)
        token = signing.dumps([first.id, second.id], salt='upload-results')
        url = reverse('upload_results', args=[token])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse('upload_results', args=[token + 'bad'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('report_detail', args=[unrelated.id]), {'group': token}).status_code, 404)
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)

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
