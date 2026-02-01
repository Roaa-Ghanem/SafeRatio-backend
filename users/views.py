from rest_framework import status, generics, permissions    
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login, logout
from .models import CustomUser, Profile
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer, 
    SensitiveInfoSerializer, ProfileSerializer, ProfileUpdateSerializer
)
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
import os
import time
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

User = get_user_model()

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    data = request.data
    
    # قائمة الحقول المسموح بتحديثها
    allowed_fields = ['first_name', 'last_name', 'email', 'phone', 'country', 'language']
    
    # تحديث الحقول المسموح بها فقط
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
    
    # التحقق من أن البريد الإلكتروني فريد
    if 'email' in data:
        if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
            return Response(
                {'email': ['البريد الإلكتروني مستخدم بالفعل']},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    try:
        user.save()
        return Response({
            'message': 'تم تحديث الملف الشخصي بنجاح',
            'user': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'country': user.country,
                'language': user.language,
                'avatar_url': user.avatar_url if hasattr(user, 'avatar_url') else None
            }
        })
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def user_login(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)
    
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data
        })
    return Response(
        {'error': 'Invalid credentials'}, 
        status=status.HTTP_401_UNAUTHORIZED
    )

@api_view(['POST'])
@permission_classes([AllowAny])
def user_register(request):
    try:
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_logout(request):
    try:
        refresh_token = request.data.get('refresh_token')
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(status=status.HTTP_205_RESET_CONTENT)
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )

class CompleteSensitiveInfoView(APIView):
    """إكمال المعلومات الحساسة للمرة الأولى"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """الحصول على حالة المعلومات الحساسة"""
        try:
            profile = request.user.profile
            return Response({
                'sensitive_info_completed': profile.sensitive_info_completed,
                'sensitive_info_locked': profile.sensitive_info_locked,
                'has_date_of_birth': bool(profile.date_of_birth),
                'has_driving_license': bool(profile.driving_license_number),
                'age': profile.age,
                'warning': '⚠️ لا يمكن تعديل تاريخ الميلاد أو رقم رخصة القيادة بعد الحفظ' 
                if profile.sensitive_info_locked else None
            })
        except Profile.DoesNotExist:
            return Response({
                'sensitive_info_completed': False,
                'sensitive_info_locked': False,
                'has_date_of_birth': False,
                'has_driving_license': False,
                'age': None
            })
    
    def post(self, request):
        """إدخال المعلومات الحساسة للمرة الأولى"""
        user = request.user
        
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            # إنشاء ملف شخصي إذا لم يكن موجودًا
            profile = Profile.objects.create(user=user)
        
        # تحقق إذا كانت المعلومات مقفلة بالفعل
        if profile.sensitive_info_locked:
            return Response({
                'error': 'المعلومات الحساسة مقفلة بالفعل ولا يمكن تعديلها',
                'completed': True,
                'message': 'يجب الاتصال بالدعم لإجراء أي تغييرات'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # تحقق إذا كانت المعلومات مكتملة بالفعل
        if profile.sensitive_info_completed:
            return Response({
                'error': 'المعلومات الحساسة مكتملة بالفعل',
                'completed': True
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SensitiveInfoSerializer(profile, data=request.data)
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                'success': True,
                'message': 'تم حفظ المعلومات الحساسة بنجاح',
                'warning': '⚠️ تحذير: لا يمكن تعديل تاريخ الميلاد أو رقم رخصة القيادة أو رقم الهوية لاحقًا. يرجى التحقق من صحتها.',
                'profile': ProfileSerializer(profile).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AuthProfileView(APIView):
    """الحصول على وتحديث الملف الشخصي الكامل"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """الحصول على الملف الشخصي الكامل"""
        try:
            profile = request.user.profile
            serializer = ProfileSerializer(profile)
            return Response(serializer.data)
        except Profile.DoesNotExist:
            # إنشاء ملف شخصي إذا لم يكن موجودًا
            profile = Profile.objects.create(user=request.user)
            serializer = ProfileSerializer(profile)
            return Response(serializer.data)
    
    def put(self, request):
        """تحديث المعلومات غير الحساسة فقط"""
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=request.user)
        
        # استخدم سيريالايزر تحديث المعلومات غير الحساسة
        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            # الحصول على البيانات المحدثة كاملة
            profile_serializer = ProfileSerializer(profile)
            return Response({
                'success': True,
                'message': 'تم تحديث الملف الشخصي بنجاح',
                'profile': profile_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_object(self):
        return self.request.user

class UserSensitiveInfoView(APIView):
    """عرض المعلومات الحساسة فقط (للقراءة فقط)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """الحصول على المعلومات الحساسة (قراءة فقط)"""
        try:
            profile = request.user.profile
            sensitive_data = {
                'date_of_birth': profile.date_of_birth,
                'age': profile.age,
                'driving_license_number': profile.driving_license_number,
                'driving_license_issue_date': profile.driving_license_issue_date,
                'national_id': profile.national_id,
                'gender': profile.gender,
                'sensitive_info_locked': profile.sensitive_info_locked,
                'sensitive_info_completed': profile.sensitive_info_completed,
                'warning': 'المعلومات الحساسة مقفلة ولا يمكن تعديلها' if profile.sensitive_info_locked else None
            }
            return Response(sensitive_data)
        except Profile.DoesNotExist:
            return Response({
                'date_of_birth': None,
                'age': None,
                'driving_license_number': None,
                'sensitive_info_locked': False,
                'sensitive_info_completed': False
            })
        

@api_view(['GET'])
@permission_classes([AllowAny])
def test_endpoint(request):
    """
    API root for the users/auth namespace. Returns available auth endpoints.
    """
    base = '/api/auth'
    return Response({
        "register": f"{base}/register/",
        "login": f"{base}/login/",
        "logout": f"{base}/logout/",
        "token_refresh": f"{base}/token/refresh/",
        "profile": f"{base}/profile/",
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def send_verification(request):
    """Send email verification link to a user (by email)."""
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required.'}, status=400)
    try:
        user = CustomUser.objects.filter(email=email).first()
        if not user:
            return Response({'error': 'User with that email not found.'}, status=404)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_link = request.build_absolute_uri(f"/api/auth/confirm-verification/?uid={uid}&token={token}")

        # render simple text email
        subject = 'Verify your SafeRatio account'
        message = render_to_string('emails/verification_email.txt', {'user': user, 'confirm_link': confirm_link})
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
        return Response({'detail': 'Verification email sent.'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_avatar(request):
    """Accepts an uploaded file (multipart/form-data) under key 'avatar', saves to MEDIA_ROOT/avatars/, and returns absolute URL."""
    user = request.user
    avatar = request.FILES.get('avatar')
    if not avatar:
        return Response({'error': 'No avatar provided.'}, status=400)
    try:
        # basic validations
        max_size = getattr(settings, 'MAX_AVATAR_UPLOAD_SIZE', 5 * 1024 * 1024)  # 5 MB default
        content_type = avatar.content_type
        if not content_type.startswith('image/'):
            return Response({'error': 'Invalid file type.'}, status=400)
        if avatar.size > max_size:
            return Response({'error': 'File too large.'}, status=400)

        # ensure profile exists (CustomUser now has avatar field; save there)
        # save to user.avatar
        filename = f"avatar_{user.pk}_{int(time.time())}{os.path.splitext(avatar.name)[1]}"
        user.avatar.save(filename, avatar, save=True)
        # build absolute URL
        avatar_url = None
        try:
            avatar_url = request.build_absolute_uri(user.avatar.url)
        except Exception:
            avatar_url = None
        return Response({'avatar_url': avatar_url})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def confirm_verification(request):
    uidb64 = request.query_params.get('uid')
    token = request.query_params.get('token')
    if not uidb64 or not token:
        return Response({'error': 'Missing uid or token.'}, status=400)
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
        if default_token_generator.check_token(user, token):
            # mark active if not active
            if not user.is_active:
                user.is_active = True
                user.save()
            return Response({'detail': 'Email confirmed.'})
        return Response({'error': 'Invalid token.'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def send_password_reset(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required.'}, status=400)
    try:
        user = CustomUser.objects.filter(email=email).first()
        if not user:
            return Response({'error': 'User with that email not found.'}, status=404)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = request.build_absolute_uri(f"/api/auth/reset-password/?uid={uid}&token={token}")

        subject = 'Reset your SafeRatio password'
        message = render_to_string('emails/reset_email.txt', {'user': user, 'reset_link': reset_link})
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
        return Response({'detail': 'Password reset email sent.'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    uidb64 = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    new_password2 = request.data.get('new_password2')
    if not uidb64 or not token or not new_password:
        return Response({'error': 'uid, token and new_password are required.'}, status=400)
    if new_password != new_password2:
        return Response({'error': 'Passwords do not match.'}, status=400)
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
        if default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            return Response({'detail': 'Password has been reset.'})
        return Response({'error': 'Invalid token.'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=400)