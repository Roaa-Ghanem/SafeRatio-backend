from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from . import views

urlpatterns = [
    path('', views.test_endpoint, name='index'),
    path('test/', views.test_endpoint, name='test'),
    path('login/', TokenObtainPairView.as_view(), name='login'), 
    path('register/', views.user_register, name='register'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),    # path('user/', views.UserView.as_view(), name='user'),
    path('send-verification/', views.send_verification, name='send_verification'),
    path('confirm-verification/', views.confirm_verification, name='confirm_verification'),
    path('logout/', views.user_logout, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', views.AuthProfileView.as_view(), name='profile'),
    # path('avatar/', UpdateAvatarView.as_view(), name='update_avatar'),
    path('send-reset/', views.send_password_reset, name='send_reset'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('sensitive-info/', views.CompleteSensitiveInfoView.as_view(), name='sensitive_info'),
    path('sensitive-info/view/', views.UserSensitiveInfoView.as_view(), name='view_sensitive_info'),
]