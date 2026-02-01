#!/usr/bin/env python
import sys
import os

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python generate_token.py <username>')
        sys.exit(1)

    username = sys.argv[1]

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saferatio.settings')
    import django
    django.setup()

    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes
    from django.contrib.auth.tokens import default_token_generator
    from users.models import CustomUser

    try:
        user = CustomUser.objects.get(username=username)
    except CustomUser.DoesNotExist:
        print(f'User "{username}" not found')
        sys.exit(2)

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    print('uid=' + uid)
    print('token=' + token)
