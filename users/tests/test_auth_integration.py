from rest_framework.test import APITestCase
from django.urls import reverse
from rest_framework import status


class AuthIntegrationTests(APITestCase):
    def setUp(self):
        self.register_url = '/api/auth/register/'
        self.login_url = '/api/auth/login/'
        self.profile_url = '/api/auth/profile/'
        self.car_url = '/api/car/'

        # sample user data matching UserRegistrationSerializer fields
        self.user_data = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'StrongPassw0rd!',
            'password2': 'StrongPassw0rd!',
            'first_name': 'Test',
            'last_name': 'User',
            'user_type': 'individual',
            'phone': '0123456789'
        }

    def test_register_login_and_access_protected_endpoint(self):
        # Register
        r = self.client.post(self.register_url, data=self.user_data, format='json')
        self.assertIn(r.status_code, (status.HTTP_201_CREATED, status.HTTP_200_OK))

        # Login
        login_data = {'username': self.user_data['username'], 'password': self.user_data['password']}
        r = self.client.post(self.login_url, data=login_data, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('access', r.data)
        access = r.data['access']

        # Access profile with token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        r = self.client.get(self.profile_url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        # Access protected car endpoint (should not be 401 when authenticated)
        r = self.client.get(self.car_url)
        self.assertNotEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
