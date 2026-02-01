"""
URL configuration for saferatio project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# saferatio/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from users import views as user_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Home page
    path('', TemplateView.as_view(template_name='dashboard/home.html'), name='home'),
    
    # Dashboard
    path('dashboard/', TemplateView.as_view(template_name='dashboard/index.html'), name='dashboard'),
    
    # Authentication URLs
    path('api/auth/', include('users.urls')),
    path('api/car-insurance/', include('car_insurance.urls')),
    path('api/health/', include('health_insurance.urls')),  # أضف هذا
    path('api/admin/', include('saferatio.admin_api.urls')),    
    
    # path('auth/login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    # path('auth/logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    # path('auth/register/individual/', TemplateView.as_view(template_name='users/register_individual.html'), name='register_individual'),
    # path('auth/register/organization/', TemplateView.as_view(template_name='users/register_organization.html'), name='register_organization'),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# else:
#     # للإنتاج - يمكنك استخدام serve أو nginx/apache
#     urlpatterns += [
#         path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
#         path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
#     ]