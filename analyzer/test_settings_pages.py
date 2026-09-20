from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse


class SettingsPagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='settings-user', password='OriginalPass123!')
        self.client.force_login(self.user)

    def test_settings_and_guide_navigation(self):
        response = self.client.get(reverse('settings'))
        self.assertContains(response, 'App Preferences')
        for page in ('about', 'scanning', 'help', 'user-guide'):
            url = reverse('settings_guide', args=[page])
            self.assertContains(response, url)
            guide = self.client.get(url)
            self.assertEqual(guide.status_code, 200)
            self.assertContains(guide, 'Back to Settings')
        self.assertEqual(self.client.get('/settings/unknown/').status_code, 404)

    def test_language_and_authentication(self):
        response = self.client.post(reverse('settings'), {'language': 'fil'})
        self.assertEqual(response.cookies['calamansense_language'].value, 'fil')
        self.assertContains(self.client.get(reverse('settings')), 'Mga Kagustuhan')
        self.assertContains(self.client.get('/settings/help/'), 'Bumalik sa Mga Setting')
        self.assertEqual(self.client.post(reverse('settings'), {'language': 'invalid'}).status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get('/settings/help/').status_code, 302)

    def test_password_errors_and_success(self):
        response = self.client.post(reverse('settings'), {'new_password1': 'short', 'new_password2': 'different'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['password_form'].errors)
        response = self.client.post(reverse('settings'), {'new_password1': 'FreshHarvest982!', 'new_password2': 'FreshHarvest982!'})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('FreshHarvest982!'))
        self.assertEqual(self.client.get(reverse('settings')).status_code, 200)
