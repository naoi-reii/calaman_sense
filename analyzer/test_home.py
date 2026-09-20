from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


class HomePageTests(TestCase):
    def test_auth_popup_pages_allow_only_same_origin_frames(self):
        for url in ('/login/', '/register/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['X-Frame-Options'], 'SAMEORIGIN')
            self.assertContains(response, 'Back to Home')
        self.assertContains(self.client.get('/'), 'id="auth-dialog"')

    def test_public_home_and_protected_dashboard(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Smarter scanning.')
        self.assertContains(response, reverse('login'))
        self.assertContains(response, reverse('register'))
        self.assertEqual(reverse('dashboard'), '/dashboard/')
        self.assertRedirects(self.client.get('/dashboard/'), '/login/?next=/dashboard/')

    def test_signed_in_home_and_login_destination(self):
        User.objects.create_user(username='home-user', password='HarvestPass123!')
        response = self.client.post('/login/', {'username':'home-user', 'password':'HarvestPass123!'})
        self.assertRedirects(response, '/dashboard/')
        response = self.client.get('/')
        self.assertRedirects(response, '/dashboard/')
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)

    def test_logout_opens_public_home(self):
        user = User.objects.create_user(username='leaving-user')
        self.client.force_login(user)
        response = self.client.post('/logout/', follow=True)
        self.assertRedirects(response, '/')
        self.assertContains(response, '>Login<')
        self.assertContains(response, '>Sign Up<')
        self.assertNotContains(response, 'Open Dashboard')
        self.assertNotIn('_auth_user_id', self.client.session)
