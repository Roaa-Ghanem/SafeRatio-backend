from django.test import TestCase
from django.core import mail
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from users.models import CustomUser


class EmailResetTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='emailtest', email='emailtest@example.com', password='TestPass123!')
        self.send_ver_url = '/api/auth/send-verification/'
        self.confirm_url = '/api/auth/confirm-verification/'
        self.send_reset_url = '/api/auth/send-reset/'
        self.reset_url = '/api/auth/reset-password/'

    def test_send_verification_and_confirm(self):
        # send verification
        resp = self.client.post(self.send_ver_url, {'email': self.user.email}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        # email sent
        self.assertGreaterEqual(len(mail.outbox), 1)
        email = mail.outbox[-1]
        self.assertIn('Verify your SafeRatio account', email.subject)

        # simulate confirm by generating uid and token
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        resp = self.client.get(f"{self.confirm_url}?uid={uid}&token={token}")
        self.assertEqual(resp.status_code, 200)

    def test_password_reset_flow(self):
        # send reset
        resp = self.client.post(self.send_reset_url, {'email': self.user.email}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(mail.outbox), 1)
        email = mail.outbox[-1]
        self.assertIn('Reset your SafeRatio password', email.subject)

        # generate token and reset
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        new_password = 'NewStrongPass123!'
        resp = self.client.post(self.reset_url, {'uid': uid, 'token': token, 'new_password': new_password, 'new_password2': new_password}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        # login with new password
        login = self.client.post('/api/auth/login/', {'username': self.user.username, 'password': new_password}, content_type='application/json')
        self.assertEqual(login.status_code, 200)
