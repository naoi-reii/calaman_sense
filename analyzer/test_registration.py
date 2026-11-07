from django.contrib.auth.models import User
from django.test import TestCase


class RegistrationTests(TestCase):
    def test_password_length_is_enforced_on_server(self):
        from .registration_forms import RegistrationForm
        for length in (7, 8, 16, 17):
            with self.subTest(length=length):
                payload = self.payload()
                payload['password1'] = payload['password2'] = 'Az!9' + 'x' * (length - 4)
                form = RegistrationForm(payload)
                form.is_valid()
                self.assertEqual('password1' in form.errors, length not in (8, 16))

    def payload(self, **changes):
        return dict(first_name='Mary Joy', last_name='Sabandal', username='maryjoy',
                    password1='FreshHarvest!937', password2='FreshHarvest!937', **changes)

    def test_registration_saves_names_and_shows_success_after_creation(self):
        response = self.client.post('/register/', self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You're all set!")
        user = User.objects.get(username='maryjoy')
        self.assertEqual((user.first_name, user.last_name), ('Mary Joy', 'Sabandal'))
        self.assertTrue(user.check_password('FreshHarvest!937'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        profile = self.client.get('/profile/')
        self.assertContains(profile, 'Mary Joy Sabandal')
        self.assertEqual(profile.context['profile_form']['first_name'].value(), 'Mary Joy')
        self.assertEqual(profile.context['profile_form']['last_name'].value(), 'Sabandal')

    def test_invalid_registration_does_not_create_or_login_user(self):
        payload = self.payload()
        payload['password2'] = 'DifferentPassword!937'
        response = self.client.post('/register/', payload)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(User.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_personal_information_is_required_on_server(self):
        payload = self.payload()
        payload['first_name'] = ''
        response = self.client.post('/register/', payload)
        self.assertIn('first_name', response.context['form'].errors)
        self.assertFalse(User.objects.exists())
