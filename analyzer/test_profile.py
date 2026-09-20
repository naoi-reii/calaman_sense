import tempfile
from io import BytesIO
from PIL import Image
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import UserProfile

class ProfileTests(TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        setting=override_settings(MEDIA_ROOT=directory.name)
        setting.enable(); self.addCleanup(setting.disable)
        self.user=User.objects.create_user(username='owner')
        self.other=User.objects.create_user(username='other')
        self.client.force_login(self.user)

    def test_edit_photo_and_remove(self):
        photo=BytesIO(); Image.new('RGB',(16,16),'green').save(photo,format='PNG')
        response=self.client.post('/profile/',{'first_name':'Juan','email':'juan@example.com','farm_name':'Sample Farm'})
        self.assertEqual(response.status_code,302)
        response=self.client.post('/profile/',{'action':'photo','first_name':'Unwanted change','photo':SimpleUploadedFile('avatar.png',photo.getvalue(),content_type='image/png')})
        self.assertEqual(response.status_code,302)
        self.user.refresh_from_db(); self.other.refresh_from_db()
        self.assertEqual(self.user.first_name,'Juan'); self.assertEqual(self.other.first_name,'')
        profile=UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.photo.storage.exists(profile.photo.name))
        self.assertEqual(profile.farm_name,'Sample Farm')
        self.assertContains(self.client.get('/profile/'),'Sample Farm')
        self.client.post('/profile/',{'first_name':'Juan','email':'juan@example.com','farm_name':'Sample Farm','remove_photo':'on'})
        profile.refresh_from_db(); self.assertTrue(profile.photo)
        self.client.post('/profile/',{'action':'photo','remove_photo':'on'})
        profile.refresh_from_db(); self.assertFalse(profile.photo)
        self.user.refresh_from_db(); self.assertEqual(self.user.email,'juan@example.com')
        self.assertEqual(profile.farm_name,'Sample Farm')

    def test_invalid_photo_and_email_not_saved(self):
        response=self.client.post('/profile/',{'email':'invalid','photo':SimpleUploadedFile('bad.png',b'not an image',content_type='image/png')})
        self.assertEqual(response.status_code,200)
        self.user.refresh_from_db(); self.assertEqual(self.user.email,'')
        self.assertFalse(UserProfile.objects.get(user=self.user).photo)

    def test_invalid_photo_does_not_change_information(self):
        self.user.first_name = 'Original'
        self.user.save()
        response = self.client.post('/profile/', {'action':'photo', 'first_name':'Changed',
            'photo':SimpleUploadedFile('bad.png', b'not an image', content_type='image/png')})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['photo_form'].errors)
        self.assertFalse(response.context['profile_form'].is_bound)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Original')

    def test_photo_requires_selection(self):
        response = self.client.post('/profile/', {'action':'photo'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('photo', response.context['photo_form'].errors)
