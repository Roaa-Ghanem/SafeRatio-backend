from django.urls import reverse
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class AvatarUploadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='avatuser', email='avat@example.com', password='Pass12345!')
        self.login_url = '/api/auth/login/'
        self.upload_url = '/api/auth/upload-avatar/'

    def authenticate(self):
        resp = self.client.post(self.login_url, {'username': 'avatuser', 'password': 'Pass12345!'}, format='json')
        token = resp.data.get('access')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_upload_valid_image(self):
        self.authenticate()
        img = SimpleUploadedFile('test.png', b'\x89PNG\r\n\x1a\n' + b'a' * 1000, content_type='image/png')
        resp = self.client.post(self.upload_url, {'avatar': img}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('avatar_url', resp.data)

    def test_upload_invalid_type(self):
        self.authenticate()
        f = SimpleUploadedFile('test.txt', b'hello world', content_type='text/plain')
        resp = self.client.post(self.upload_url, {'avatar': f}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_too_large(self):
        self.authenticate()
        # create large file ~6MB
        big = SimpleUploadedFile('big.jpg', b'a' * (6 * 1024 * 1024), content_type='image/jpeg')
        resp = self.client.post(self.upload_url, {'avatar': big}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
