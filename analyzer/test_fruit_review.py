from django.test import TestCase
from django.contrib.auth.models import User
from .models import Scan, ScanImage

class FruitReviewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner')
        self.other = User.objects.create_user(username='other')
        self.scan = Scan.objects.create(created_by=self.owner, fruit_count_total=1, quality_grade='Good Quality')
        self.original = [{'x': 10, 'y': 10, 'width': 30, 'height': 30, 'css_class': 'ripe', 'label': 'Ripe 75%'}]
        self.image = ScanImage.objects.create(scan=self.scan, mock_annotations=self.original)
        self.client.force_login(self.owner)
        self.url = f'/reports/{self.scan.id}/'

    def test_save_restore_and_preserve_original(self):
        payload = {'image_id': self.image.id, 'index': 0, 'label': 'overripe'}
        self.assertEqual(self.client.post(self.url, payload).status_code, 200)
        self.image.refresh_from_db()
        self.scan.refresh_from_db()
        self.assertEqual(self.image.label_corrections, {'0': 'overripe'})
        self.assertEqual(self.image.mock_annotations, self.original)
        self.assertEqual(self.scan.quality_grade, 'Good Quality')
        payload['label'] = 'original'
        self.assertEqual(self.client.post(self.url, payload).status_code, 200)
        self.image.refresh_from_db()
        self.assertEqual(self.image.label_corrections, {})

    def test_reject_invalid_and_other_users(self):
        payload = {'image_id': self.image.id, 'index': 9, 'label': 'ripe'}
        self.assertEqual(self.client.post(self.url, payload).status_code, 400)
        payload.update(index=0, label='bad')
        self.assertEqual(self.client.post(self.url, payload).status_code, 400)
        self.client.force_login(self.other)
        payload['label'] = 'ripe'
        self.assertEqual(self.client.post(self.url, payload).status_code, 404)

    def test_page_contains_inspector_and_saved_review(self):
        self.image.image = 'scans/inspector-test.jpg'
        self.image.label_corrections = {'0': 'overripe'}
        self.image.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fruit-inspector')
        self.assertContains(response, 'data-fruit-index="0"')
        self.assertContains(response, 'Ripe 75%')
        self.assertContains(response, '"0": "overripe"')
        # Avoid invoking file-storage deletion on a synthetic image path.
        self.image.image = ''
        self.image.save()

    def test_other_scan_image_rejected(self):
        other_scan = Scan.objects.create(created_by=self.owner)
        other_image = ScanImage.objects.create(scan=other_scan, mock_annotations=self.original)
        response = self.client.post(self.url, {'image_id': other_image.id, 'index': 0, 'label': 'overripe'})
        self.assertEqual(response.status_code, 404)

