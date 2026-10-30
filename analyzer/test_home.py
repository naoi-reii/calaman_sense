from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


class HomePageTests(TestCase):
    def test_opening_and_account_pages_always_use_light_theme(self):
        for url in ('/', '/login/', '/register/'):
            self.assertContains(self.client.get(url), 'data-theme-policy="light"')
        self.client.force_login(User.objects.create_user(username='theme-user'))
        self.assertContains(self.client.get('/dashboard/'), 'data-theme-policy="user"')

    def test_existing_mobile_opening_is_connected_only_to_login(self):
        login = self.client.get('/login/')
        self.assertContains(login, 'id="mobile-opening"', count=1)
        self.assertContains(login, 'id="mobile-onboarding"', count=1)
        self.assertContains(login, 'mobile_opening.css')
        self.assertContains(login, 'window.self !== window.top || !mobile.matches')
        self.assertNotContains(self.client.get('/'), 'id="mobile-opening"')
        self.assertNotContains(self.client.get('/register/'), 'id="mobile-opening"')
        self.assertContains(self.client.get('/'), "window.location.replace('/login/?opening=1')")

    def test_mobile_entry_opens_photo_splash_and_logout_opens_login(self):
        agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile Safari'
        self.assertRedirects(self.client.get('/', HTTP_USER_AGENT=agent), '/login/?opening=1', fetch_redirect_response=False)
        opening = self.client.get('/login/?opening=1', HTTP_USER_AGENT=agent)
        self.assertContains(opening, 'images/mobile-opening.png')
        self.assertContains(opening, "entry.get('opening') === '1'")
        self.client.force_login(User.objects.create_user(username='mobile-logout-user'))
        response = self.client.post('/logout/', HTTP_USER_AGENT=agent)
        self.assertRedirects(response, '/login/?logged_out=1', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        login = self.client.get(response.url, HTTP_USER_AGENT=agent)
        self.assertContains(login, 'id="id_username"')
        self.assertContains(login, "if (entry.get('logged_out') === '1') return;")

    def test_mobile_viewport_logout_can_request_login_redirect(self):
        self.client.force_login(User.objects.create_user(username='viewport-logout-user'))
        self.assertRedirects(self.client.post('/logout/', {'next': '/login/?logged_out=1'}),
                             '/login/?logged_out=1', fetch_redirect_response=False)

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
