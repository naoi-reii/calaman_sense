from django.test import TestCase
from django.contrib.auth.models import User
from .models import Scan

class CompareScanTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='owner')
        self.other=User.objects.create_user(username='other')
        self.client.force_login(self.user)
        self.a=Scan.objects.create(created_by=self.user,fruit_count_total=10,batch_name='Sample A')
        self.b=Scan.objects.create(created_by=self.user,fruit_count_total=13,batch_name='Sample A')

    def test_comparison(self):
        response=self.client.get('/reports/compare/',{'scan_ids':[self.a.pk,self.b.pk]})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'3 more fruits')
        self.assertEqual(len(response.context['cards']),2)
        self.assertTrue(response.context['same_sample'])

    def test_selection_and_access(self):
        self.assertEqual(self.client.get('/reports/compare/').status_code,400)
        self.assertEqual(self.client.get('/reports/compare/',{'scan_ids':[self.a.pk,self.a.pk]}).status_code,400)
        private=Scan.objects.create(created_by=self.other)
        self.assertEqual(self.client.get('/reports/compare/',{'scan_ids':[self.a.pk,private.pk]}).status_code,404)
