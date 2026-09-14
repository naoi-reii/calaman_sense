from django.contrib.auth.models import User
from django.test import Client, TestCase


class LogoutCsrfTests(TestCase):
    def test_rotated_token_logout_and_invalid_token_rejection(self):
        User.objects.create_user(username='csrf-user', password='SamplePass123!')
        client = Client(enforce_csrf_checks=True)
        client.get('/login/')
        old_token = client.cookies['csrftoken'].value
        response = client.post('/login/', {
            'username': 'csrf-user', 'password': 'SamplePass123!',
            'csrfmiddlewaretoken': old_token,
        })
        self.assertEqual(response.status_code, 302)
        current_token = client.cookies['csrftoken'].value
        self.assertNotEqual(old_token, current_token)
        response = client.post('/logout/', {'csrfmiddlewaretoken': old_token})
        self.assertEqual(response.status_code, 403)
        self.assertIn('_auth_user_id', client.session)
        response = client.post('/logout/', {'csrfmiddlewaretoken': current_token})
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', client.session)

    def test_missing_token_does_not_log_user_out(self):
        user = User.objects.create_user(username='protected-user')
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.post('/logout/').status_code, 403)
        self.assertIn('_auth_user_id', client.session)
