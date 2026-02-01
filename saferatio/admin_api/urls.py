# saferatio/admin_api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard-stats/', views.admin_dashboard_stats, name='admin-dashboard-stats'),
    path('users/', views.admin_users_list, name='admin-users-list'),
    path('users/create/', views.admin_create_user, name='admin-create-user'),
    path('users/<int:user_id>/', views.admin_user_detail, name='admin-user-detail'),
    path('users/<int:user_id>/update/', views.admin_update_user, name='admin-update-user'),
    path('users/<int:user_id>/delete/', views.admin_delete_user, name='admin-delete-user'),
    path('reports/', views.admin_generate_report, name='admin-generate-report'),
    path('companies-stats/', views.admin_companies_stats, name='admin-companies-stats'),
    path('system-logs/', views.admin_system_logs, name='admin-system-logs'),
]