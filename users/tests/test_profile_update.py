from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profuser', email='prof@example.com', password='TestPass123!')
        self.login_url = '/api/auth/login/'
        self.profile_url = '/api/auth/profile/'

    def authenticate(self):
        resp = self.client.post(self.login_url, {'username': 'profuser', 'password': 'TestPass123!'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        token = resp.data.get('access')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_update_profile_success(self):
        self.authenticate()
        payload = {'first_name': 'Updated', 'last_name': 'User', 'phone': '0551234567'}
        resp = self.client.patch(self.profile_url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'User')
        self.assertEqual(self.user.phone, '0551234567')

    def test_profile_requires_auth(self):
        # no auth -> 401
        resp = self.client.get(self.profile_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile_email_conflict(self):
        # create another user with an email
        other = User.objects.create_user(username='other', email='other@example.com', password='OtherPass123!')
        self.authenticate()
        # attempt to change to other user's email
        payload = {'email': other.email}
        resp = self.client.patch(self.profile_url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_profile_invalid_phone(self):
        self.authenticate()
        payload = {'phone': 'invalid_phone!@#'}
        resp = self.client.patch(self.profile_url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
