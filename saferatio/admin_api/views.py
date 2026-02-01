# في health_insurance/views.py أو أنشئ ملف views_admin.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Sum, Avg, Q, F
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_stats(request):
    """إحصائيات لوحة تحكم المسؤول"""
    # التحقق من صلاحية المسؤول
    if not (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'user_type', None) == 'admin'):
        return Response(
            {'error': 'غير مصرح بالوصول'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # استيراد النماذج
        from health_insurance.models import HealthInsurancePolicy, HealthInsuranceQuote, Company
        from car_insurance.models import CarPolicy, CarInsuranceQuote
        
        # إحصائيات المستخدمين
        users_stats = {
            'total': User.objects.count(),
            'active_today': User.objects.filter(
                last_login__date=timezone.now().date()
            ).count(),
            'new_today': User.objects.filter(
                date_joined__date=timezone.now().date()
            ).count(),
            'by_type': dict(User.objects.values_list('user_type')
                          .annotate(count=Count('id')).order_by('-count')),
        }
        
        # إحصائيات بوالص التأمين الصحي
        health_policies = HealthInsurancePolicy.objects.all()
        health_stats = {
            'total': health_policies.count(),
            'active': health_policies.filter(status='active').count(),
            'pending': health_policies.filter(status='pending').count(),
            'revenue': float(health_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
        }
        
        # إحصائيات بوالص تأمين السيارات
        car_policies = CarPolicy.objects.all()
        car_stats = {
            'total': car_policies.count(),
            'active': car_policies.filter(status='active').count(),
            'revenue': float(car_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
        }
        
        # إحصائيات عروض الأسعار
        health_quotes = HealthInsuranceQuote.objects.all()
        car_quotes = CarInsuranceQuote.objects.all()
        quotes_stats = {
            'pending': health_quotes.filter(status='pending').count() + 
                      car_quotes.filter(status='pending').count(),
            'accepted': health_quotes.filter(status='accepted').count() + 
                       car_quotes.filter(status='accepted').count(),
            'rejected': health_quotes.filter(status='rejected').count() + 
                       car_quotes.filter(status='rejected').count(),
        }
        
        # الشركات
        companies_stats = {
            'total': Company.objects.count(),
            'by_sector': list(Company.objects.values('sector')
                            .annotate(count=Count('id'))
                            .order_by('-count')),
        }
        
        # نشاطات حديثة
        recent_activities = get_recent_activities()
        
        stats = {
            'users': users_stats,
            'policies': {
                'health': health_stats,
                'car': car_stats,
                'total_active': health_stats['active'] + car_stats['active'],
                'total_revenue': health_stats['revenue'] + car_stats['revenue'],
            },
            'quotes': quotes_stats,
            'companies': companies_stats,
            'recent_activities': recent_activities,
        }
        
        return Response(stats)
        
    except Exception as e:
        print(f"Error in admin_dashboard_stats: {str(e)}")
        return Response(
            {'error': str(e), 'test': True},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ============= User CRUD APIs =============
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_users_list(request):
    """قائمة المستخدمين مع البحث والترشيح والترتيب"""
    # التحقق من صلاحية المسؤول
    if not (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'user_type', None) == 'admin'):
        return Response(
            {'error': 'غير مصرح بالوصول'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # الحصول على معاملات البحث
        search = request.GET.get('search', '')
        user_type = request.GET.get('user_type', '')
        status_filter = request.GET.get('status', '')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        sort_by = request.GET.get('sort_by', '-date_joined')
        
        # بناء الاستعلام
        users = User.objects.all()
        
        # البحث النصي
        if search:
            users = users.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(phone__icontains=search)
            )
        
        # تصفية حسب النوع
        if user_type:
            users = users.filter(user_type=user_type)
        
        # تصفية حسب الحالة
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)
        
        # الترتيب
        if sort_by in ['username', 'email', 'first_name', 'last_name', 'date_joined', 'last_login']:
            users = users.order_by(sort_by)
        elif sort_by == '-date_joined':
            users = users.order_by('-date_joined')
        elif sort_by == '-last_login':
            users = users.order_by('-last_login')
        
        # التقسيم للصفحات
        total_count = users.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        # الحصول على البيانات
        users_data = []
        for user in users[start_index:end_index]:
            user_dict = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'user_type': user.user_type,
                'phone': user.phone,
                'country': user.country,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
            }
            
            try:
                user_dict['profile_completed'] = user.profile_completed
            except:
                user_dict['profile_completed'] = False
            
            users_data.append(user_dict)
        
        return Response({
            'users': users_data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            },
            'filters': {
                'search': search,
                'user_type': user_type,
                'status': status_filter,
                'sort_by': sort_by
            }
        })
        
    except Exception as e:
        print(f"Error in admin_users_list: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_user_detail(request, user_id):
    """تفاصيل مستخدم معين"""
    if not (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'user_type', None) == 'admin'):
        return Response(
            {'error': 'غير مصرح بالوصول'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from users.serializers import UserProfileSerializer
        from users.models import Profile
        from health_insurance.models import HealthInsurancePolicy, Company
        from car_insurance.models import CarPolicy, Vehicle
        
        user = User.objects.get(id=user_id)
        
        # البيانات الأساسية
        user_data = UserProfileSerializer(user, context={'request': request}).data
        
        # الملف الشخصي
        profile_data = {}
        try:
            profile = Profile.objects.get(user=user)
            profile_data = {
                'age': profile.age,
                'gender': profile.gender,
                'marital_status': profile.marital_status,
                'occupation': profile.occupation,
                'date_of_birth': profile.date_of_birth,
                'driving_license_number': profile.driving_license_number,
                'national_id': profile.national_id,
                'sensitive_info_completed': profile.sensitive_info_completed,
                'sensitive_info_locked': profile.sensitive_info_locked
            }
        except Profile.DoesNotExist:
            profile_data = {'error': 'لا يوجد ملف شخصي'}
        
        # الإحصائيات
        health_policies = HealthInsurancePolicy.objects.filter(user=user)
        car_policies = CarPolicy.objects.filter(user=user)
        companies = Company.objects.filter(user=user)
        vehicles = Vehicle.objects.filter(user=user)
        
        stats = {
            'health_policies_count': health_policies.count(),
            'car_policies_count': car_policies.count(),
            'companies_count': companies.count(),
            'vehicles_count': vehicles.count(),
            'total_premiums': float(
                (health_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0) +
                (car_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0)
            )
        }
        
        # أحدث السجلات
        recent_items = {
            'health_policies': list(health_policies.order_by('-created_at')[:5].values(
                'id', 'policy_number', 'status', 'total_premium', 'created_at'
            )),
            'car_policies': list(car_policies.order_by('-created_at')[:5].values(
                'id', 'policy_number', 'status', 'total_premium', 'created_at'
            )),
            'companies': list(companies.order_by('-created_at')[:5].values(
                'id', 'name', 'sector', 'total_employees'
            )),
            'vehicles': list(vehicles.order_by('-created_at')[:5].values(
                'id', 'make', 'model', 'license_plate', 'current_value'
            ))
        }
        
        return Response({
            'user': user_data,
            'profile': profile_data,
            'stats': stats,
            'recent_items': recent_items
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'المستخدم غير موجود'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"Error in admin_user_detail: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_create_user(request):
    """إنشاء مستخدم جديد"""
    if not (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'user_type', None) == 'admin'):
        return Response(
            {'error': 'غير مصرح بالوصول'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from users.serializers import UserRegistrationSerializer
        
        data = request.data.copy()
        
        # إذا لم يتم إدخال كلمة مرور، إنشاء كلمة مرور عشوائية
        if 'password' not in data or not data['password']:
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(alphabet) for i in range(12))
            data['password'] = password
            data['password2'] = password
            data['auto_generated_password'] = True
        
        serializer = UserRegistrationSerializer(data=data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # إرسال بريد إلكتروني إذا كان مطلوب
            if data.get('send_email', False) and user.email:
                send_welcome_email(user, data['password'])
            
            return Response({
                'success': True,
                'message': 'تم إنشاء المستخدم بنجاح',
                'user': UserProfileSerializer(user, context={'request': request}).data,
                'password': data.get('auto_generated_password') and data['password'] or None
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        print(f"Error in admin_create_user: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_update_user(request, user_id):
    """تحديث بيانات مستخدم"""
    if not (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'user_type', None) == 'admin'):
        return Response(
            {'error': 'غير مصرح بالوصول'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        user = User.objects.get(id=user_id)
        
        # البيانات المسموح بتحديثها
        allowed_fields = [
            'first_name', 'last_name', 'email', 'phone', 
            'user_type', 'is_active', 'country', 'language'
        ]
        
        update_data = {}
        for field in allowed_fields:
            if field in request.data:
                update_data[field] = request.data[field]
        
        # تحديث كلمة المرور إذا تم إدخالها
        if 'password' in request.data and request.data['password']:
            user.set_password(request.data['password'])
        
        # تحديث الحقول
        for field, value in update_data.items():
            setattr(user, field, value)
        
        user.save()
        
        from users.serializers import UserProfileSerializer
        return Response({
            'success': True,
            'message': 'تم تحديث المستخدم بنجاح',
            'user': UserProfileSerializer(user, context={'request': request}).data
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'المستخدم غير موجود'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"Error in admin_update_user: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def admin_delete_user(request, user_id):
    """حذف مستخدم"""
    if not (request.user.is_staff or request.user.is_superuser or getattr(request.user, 'user_type', None) == 'admin'):
        return Response(
            {'error': 'غير مصرح بالوصول'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        user = User.objects.get(id=user_id)
        
        # لا يمكن حذف المستخدم الحالي
        if user == request.user:
            return Response(
                {'error': 'لا يمكن حذف حسابك الخاص'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # لا يمكن حذف المستخدم superuser
        if user.is_superuser:
            return Response(
                {'error': 'لا يمكن حذف المستخدم الرئيسي'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # الحذف
        username = user.username
        user.delete()
        
        return Response({
            'success': True, 
            'message': f'تم حذف المستخدم "{username}" بنجاح'
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'المستخدم غير موجود'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"Error in admin_delete_user: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ============= Helper Functions =============
def get_recent_activities():
    """الحصول على النشاطات الحديثة"""
    try:
        from health_insurance.models import HealthInsurancePolicy
        
        activities = []
        
        # المستخدمين الجدد
        new_users = User.objects.filter(
            date_joined__gte=timezone.now() - timedelta(days=1)
        ).order_by('-date_joined')[:5]
        
        for user in new_users:
            activities.append({
                'type': 'user',
                'description': f'مستخدم جديد مسجل: {user.get_full_name() or user.username}',
                'time': user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                'user': user.get_full_name() or user.username
            })
        
        return activities[:10]
    except Exception as e:
        print(f"Error in get_recent_activities: {str(e)}")
        return []

def send_welcome_email(user, password):
    """إرسال بريد ترحيبي للمستخدم الجديد"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        subject = 'مرحباً بك في SafeRatio'
        message = f"""
        مرحباً {user.get_full_name() or user.username},
        
        تم إنشاء حسابك في نظام SafeRatio.
        
        بيانات الدخول:
        - اسم المستخدم: {user.username}
        - كلمة المرور: {password}
        - رابط الدخول: {settings.FRONTEND_URL}/login
        
        يرجى تغيير كلمة المرور بعد أول دخول.
        
        شكراً لانضمامك إلينا!
        فريق SafeRatio
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
        
        print(f"Welcome email sent to {user.email}")
        
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")

# ============= Admin Dashboard Endpoints =============
# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def admin_dashboard_stats(request):
#     """إحصائيات لوحة تحكم المسؤول"""
#     # التحقق من صلاحية المسؤول
#     if not (request.user.is_staff or request.user.is_superuser or request.user.user_type == 'admin'):
#         return Response(
#             {'error': 'غير مصرح بالوصول'},
#             status=status.HTTP_403_FORBIDDEN
#         )
    
#     try:
#         from health_insurance.models import HealthInsurancePolicy, HealthInsuranceQuote, Company
#         from car_insurance.models import CarPolicy, CarInsuranceQuote
#         from users.models import CustomUser
        
#         # الفترة الزمنية
#         time_range = request.GET.get('time_range', 'month')
#         end_date = timezone.now()
        
#         if time_range == 'day':
#             start_date = end_date - timedelta(days=1)
#         elif time_range == 'week':
#             start_date = end_date - timedelta(weeks=1)
#         elif time_range == 'month':
#             start_date = end_date - timedelta(days=30)
#         else:  # year
#             start_date = end_date - timedelta(days=365)
        
#         # إحصائيات المستخدمين
#         users_stats = {
#             'total': CustomUser.objects.count(),
#             'active_today': CustomUser.objects.filter(
#                 last_login__date=timezone.now().date()
#             ).count(),
#             'new_today': CustomUser.objects.filter(
#                 date_joined__date=timezone.now().date()
#             ).count(),
#             'by_type': dict(CustomUser.objects.values_list('user_type')
#                           .annotate(count=Count('id')).order_by('-count')),
#             'growth': get_user_growth(start_date, end_date)
#         }
        
#         # إحصائيات بوالص التأمين الصحي
#         health_policies = HealthInsurancePolicy.objects.all()
#         health_stats = {
#             'total': health_policies.count(),
#             'active': health_policies.filter(status='active').count(),
#             'pending': health_policies.filter(status='pending').count(),
#             'revenue': float(health_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
#             'avg_premium': float(health_policies.aggregate(Avg('total_premium'))['total_premium__avg'] or 0),
#         }
        
#         # إحصائيات بوالص تأمين السيارات
#         car_policies = CarPolicy.objects.all()
#         car_stats = {
#             'total': car_policies.count(),
#             'active': car_policies.filter(status='active').count(),
#             'revenue': float(car_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
#             'avg_premium': float(car_policies.aggregate(Avg('total_premium'))['total_premium__avg'] or 0),
#         }
        
#         # إحصائيات عروض الأسعار
#         health_quotes = HealthInsuranceQuote.objects.all()
#         car_quotes = CarInsuranceQuote.objects.all()
#         quotes_stats = {
#             'pending': health_quotes.filter(status='pending').count() + 
#                       car_quotes.filter(status='pending').count(),
#             'accepted': health_quotes.filter(status='accepted').count() + 
#                        car_quotes.filter(status='accepted').count(),
#             'rejected': health_quotes.filter(status='rejected').count() + 
#                        car_quotes.filter(status='rejected').count(),
#             'conversion_rate': calculate_conversion_rate()
#         }
        
#         # الشركات
#         companies_stats = {
#             'total': Company.objects.count(),
#             'by_sector': list(Company.objects.values('sector')
#                             .annotate(count=Count('id'))
#                             .order_by('-count')),
#         }
        
#         # نشاطات حديثة
#         recent_activities = get_recent_activities()
        
#         stats = {
#             'users': users_stats,
#             'policies': {
#                 'health': health_stats,
#                 'car': car_stats,
#                 'total_active': health_stats['active'] + car_stats['active'],
#                 'total_revenue': health_stats['revenue'] + car_stats['revenue'],
#             },
#             'quotes': quotes_stats,
#             'companies': companies_stats,
#             'recent_activities': recent_activities,
#             'period': {
#                 'start_date': start_date,
#                 'end_date': end_date,
#                 'range': time_range
#             }
#         }
        
#         return Response(stats)
        
#     except Exception as e:
#         return Response(
#             {'error': str(e)},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def admin_users_list(request):
#     """قائمة المستخدمين للمسؤول"""
#     if not (request.user.is_staff or request.user.is_superuser or request.user.user_type == 'admin'):
#         return Response(
#             {'error': 'غير مصرح بالوصول'},
#             status=status.HTTP_403_FORBIDDEN
#         )
    
#     try:
#         from users.serializers import UserProfileSerializer
        
#         # البحث والترتيب
#         search = request.GET.get('search', '')
#         user_type = request.GET.get('user_type', '')
#         page = int(request.GET.get('page', 1))
#         page_size = int(request.GET.get('page_size', 20))
        
#         # بناء الاستعلام
#         users = User.objects.all()
        
#         if search:
#             users = users.filter(
#                 Q(username__icontains=search) |
#                 Q(email__icontains=search) |
#                 Q(first_name__icontains=search) |
#                 Q(last_name__icontains=search)
#             )
        
#         if user_type:
#             users = users.filter(user_type=user_type)
        
#         # الترتيب
#         sort_by = request.GET.get('sort_by', '-date_joined')
#         users = users.order_by(sort_by)
        
#         # التقسيم للصفحات
#         total_count = users.count()
#         start_index = (page - 1) * page_size
#         end_index = start_index + page_size
#         paginated_users = users[start_index:end_index]
        
#         serializer = UserProfileSerializer(paginated_users, many=True, context={'request': request})
        
#         return Response({
#             'users': serializer.data,
#             'pagination': {
#                 'page': page,
#                 'page_size': page_size,
#                 'total_count': total_count,
#                 'total_pages': (total_count + page_size - 1) // page_size
#             }
#         })
        
#     except Exception as e:
#         return Response(
#             {'error': str(e)},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def admin_user_detail(request, user_id):
#     """تفاصيل مستخدم معين"""
#     if not (request.user.is_staff or request.user.is_superuser or request.user.user_type == 'admin'):
#         return Response(
#             {'error': 'غير مصرح بالوصول'},
#             status=status.HTTP_403_FORBIDDEN
#         )
    
#     try:
#         from users.serializers import UserProfileSerializer, ProfileSerializer
#         from health_insurance.models import HealthInsurancePolicy, Company
#         from car_insurance.models import CarPolicy, Vehicle
        
#         user = User.objects.get(id=user_id)
        
#         # البيانات الأساسية
#         user_data = UserProfileSerializer(user, context={'request': request}).data
        
#         # الملف الشخصي
#         profile_data = {}
#         if hasattr(user, 'profile'):
#             profile_data = ProfileSerializer(user.profile).data
        
#         # البوالص
#         health_policies = HealthInsurancePolicy.objects.filter(user=user)
#         car_policies = CarPolicy.objects.filter(user=user)
        
#         # الشركات (للمؤسسات)
#         companies = []
#         if user.user_type == 'organization':
#             companies = Company.objects.filter(user=user)
        
#         # المركبات (للأفراد)
#         vehicles = []
#         if user.user_type == 'individual':
#             vehicles = Vehicle.objects.filter(user=user)
        
#         # الإحصائيات
#         stats = {
#             'health_policies_count': health_policies.count(),
#             'car_policies_count': car_policies.count(),
#             'companies_count': companies.count(),
#             'vehicles_count': vehicles.count(),
#             'total_premiums': float(
#                 (health_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0) +
#                 (car_policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0)
#             )
#         }
        
#         return Response({
#             'user': user_data,
#             'profile': profile_data,
#             'stats': stats,
#             'health_policies': list(health_policies.values('id', 'policy_number', 'status', 'total_premium')[:10]),
#             'car_policies': list(car_policies.values('id', 'policy_number', 'status', 'total_premium')[:10]),
#             'companies': list(companies.values('id', 'name', 'sector')[:10]),
#             'vehicles': list(vehicles.values('id', 'make', 'model', 'license_plate')[:10])
#         })
        
#     except User.DoesNotExist:
#         return Response(
#             {'error': 'المستخدم غير موجود'},
#             status=status.HTTP_404_NOT_FOUND
#         )
#     except Exception as e:
#         return Response(
#             {'error': str(e)},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def admin_update_user(request, user_id):
#     """تحديث بيانات مستخدم"""
#     if not (request.user.is_staff or request.user.is_superuser or request.user.user_type == 'admin'):
#         return Response(
#             {'error': 'غير مصرح بالوصول'},
#             status=status.HTTP_403_FORBIDDEN
#         )
    
#     try:
#         user = User.objects.get(id=user_id)
        
#         # الحقول المسموح بتحديثها
#         allowed_fields = ['first_name', 'last_name', 'email', 'phone', 'user_type', 'is_active']
        
#         for field, value in request.data.items():
#             if field in allowed_fields and hasattr(user, field):
#                 setattr(user, field, value)
        
#         user.save()
        
#         from users.serializers import UserProfileSerializer
#         return Response(UserProfileSerializer(user, context={'request': request}).data)
        
#     except User.DoesNotExist:
#         return Response(
#             {'error': 'المستخدم غير موجود'},
#             status=status.HTTP_404_NOT_FOUND
#         )
#     except Exception as e:
#         return Response(
#             {'error': str(e)},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )

# @api_view(['DELETE'])
# @permission_classes([IsAuthenticated])
# def admin_delete_user(request, user_id):
#     """حذف مستخدم"""
#     if not (request.user.is_staff or request.user.is_superuser or request.user.user_type == 'admin'):
#         return Response(
#             {'error': 'غير مصرح بالوصول'},
#             status=status.HTTP_403_FORBIDDEN
#         )
    
#     try:
#         user = User.objects.get(id=user_id)
        
#         # لا يمكن حذف المستخدم الحالي
#         if user == request.user:
#             return Response(
#                 {'error': 'لا يمكن حذف حسابك الخاص'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         # الحذف
#         user.delete()
        
#         return Response({'success': True, 'message': 'تم حذف المستخدم بنجاح'})
        
#     except User.DoesNotExist:
#         return Response(
#             {'error': 'المستخدم غير موجود'},
#             status=status.HTTP_404_NOT_FOUND
#         )
#     except Exception as e:
#         return Response(
#             {'error': str(e)},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )

# ============= Admin Reports Endpoints =============
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_generate_report(request):
    """توليد تقرير"""
    if not (request.user.is_staff or request.user.is_superuser or request.user.user_type == 'admin'):
        return Response(
            {'error': 'غير مصرح بالوصول'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        report_type = request.GET.get('type', 'financial')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date', timezone.now().date().isoformat())
        
        if start_date:
            start_date = timezone.datetime.fromisoformat(start_date)
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        end_date = timezone.datetime.fromisoformat(end_date)
        
        if report_type == 'financial':
            report_data = generate_financial_report(start_date, end_date)
        elif report_type == 'users':
            report_data = generate_users_report(start_date, end_date)
        elif report_type == 'policies':
            report_data = generate_policies_report(start_date, end_date)
        else:
            return Response(
                {'error': 'نوع التقرير غير مدعوم'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(report_data)
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ============= Helper Functions =============
def get_user_growth(start_date, end_date):
    """حساب نمو المستخدمين"""
    from users.models import CustomUser
    
    # المستخدمين الجدد في الفترة
    new_users = CustomUser.objects.filter(
        date_joined__range=[start_date, end_date]
    ).count()
    
    # المستخدمين النشطين في الفترة
    active_users = CustomUser.objects.filter(
        last_login__range=[start_date, end_date]
    ).count()
    
    # النمو الشهري
    months = []
    for i in range(6):
        month_start = end_date - timedelta(days=30*(i+1))
        month_end = end_date - timedelta(days=30*i)
        month_users = CustomUser.objects.filter(
            date_joined__range=[month_start, month_end]
        ).count()
        months.append({
            'month': month_start.strftime('%Y-%m'),
            'users': month_users
        })
    
    months.reverse()
    
    return {
        'new_users': new_users,
        'active_users': active_users,
        'monthly_growth': months
    }

def calculate_conversion_rate():
    """حساب معدل تحويل عروض الأسعار"""
    from health_insurance.models import HealthInsuranceQuote
    from car_insurance.models import CarInsuranceQuote
    
    total_quotes = HealthInsuranceQuote.objects.count() + CarInsuranceQuote.objects.count()
    accepted_quotes = (
        HealthInsuranceQuote.objects.filter(status='accepted').count() +
        CarInsuranceQuote.objects.filter(status='accepted').count()
    )
    
    if total_quotes > 0:
        return round((accepted_quotes / total_quotes) * 100, 2)
    return 0

# def get_recent_activities():
#     """الحصول على النشاطات الحديثة"""
#     from health_insurance.models import HealthInsurancePolicy, HealthInsuranceQuote
#     from car_insurance.models import CarPolicy, CarInsuranceQuote
#     from users.models import CustomUser
    
#     activities = []
    
#     # المستخدمين الجدد
#     new_users = CustomUser.objects.filter(
#         date_joined__gte=timezone.now() - timedelta(days=1)
#     ).order_by('-date_joined')[:5]
    
#     for user in new_users:
#         activities.append({
#             'type': 'user',
#             'description': f'مستخدم جديد مسجل: {user.get_full_name() or user.username}',
#             'time': user.date_joined,
#             'user': user.get_full_name() or user.username
#         })
    
#     # البوالص الجديدة
#     new_policies = HealthInsurancePolicy.objects.filter(
#         created_at__gte=timezone.now() - timedelta(days=1)
#     ).order_by('-created_at')[:5]
    
#     for policy in new_policies:
#         activities.append({
#             'type': 'policy',
#             'description': f'تم إنشاء بوليصة تأمين صحي جديدة: {policy.policy_number}',
#             'time': policy.created_at,
#             'user': policy.company.name if policy.company else 'غير معروف'
#         })
    
#     return activities[:10]  # أخر 10 نشاطات فقط

def generate_financial_report(start_date, end_date):
    """توليد تقرير مالي"""
    from health_insurance.models import HealthInsurancePolicy
    from car_insurance.models import CarPolicy
    
    # الإيرادات
    health_revenue = HealthInsurancePolicy.objects.filter(
        created_at__range=[start_date, end_date]
    ).aggregate(Sum('total_premium'))['total_premium__sum'] or 0
    
    car_revenue = CarPolicy.objects.filter(
        created_at__range=[start_date, end_date]
    ).aggregate(Sum('total_premium'))['total_premium__sum'] or 0
    
    total_revenue = float(health_revenue + car_revenue)
    
    # التوزيع حسب الشهر
    monthly_data = []
    current = start_date
    while current <= end_date:
        month_end = current.replace(day=28) + timedelta(days=4)
        month_end = month_end - timedelta(days=month_end.day)
        
        if month_end > end_date:
            month_end = end_date
        
        month_health = HealthInsurancePolicy.objects.filter(
            created_at__range=[current, month_end]
        ).aggregate(Sum('total_premium'))['total_premium__sum'] or 0
        
        month_car = CarPolicy.objects.filter(
            created_at__range=[current, month_end]
        ).aggregate(Sum('total_premium'))['total_premium__sum'] or 0
        
        monthly_data.append({
            'month': current.strftime('%Y-%m'),
            'health': float(month_health),
            'car': float(month_car),
            'total': float(month_health + month_car)
        })
        
        current = month_end + timedelta(days=1)
    
    return {
        'period': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'revenue': {
            'total': total_revenue,
            'health': float(health_revenue),
            'car': float(car_revenue),
            'average_daily': total_revenue / max((end_date - start_date).days, 1)
        },
        'monthly_data': monthly_data,
        'summary': {
            'total_policies': HealthInsurancePolicy.objects.filter(
                created_at__range=[start_date, end_date]
            ).count() + CarPolicy.objects.filter(
                created_at__range=[start_date, end_date]
            ).count(),
            'avg_premium_per_policy': total_revenue / max(
                HealthInsurancePolicy.objects.filter(
                    created_at__range=[start_date, end_date]
                ).count() + CarPolicy.objects.filter(
                    created_at__range=[start_date, end_date]
                ).count(), 1
            )
        }
    }

# 2. أضف هذه الدوال البسيطة أولاً
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_companies_stats(request):
    """إحصائيات الشركات (دالة بسيطة أولاً)"""
    return Response({
        'total': 40,
        'message': 'Companies stats will be implemented soon'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_system_logs(request):
    """سجلات النظام (دالة بسيطة أولاً)"""
    return Response({
        'logs': ['System is running', 'Admin dashboard accessed'],
        'timestamp': timezone.now().isoformat()
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_users_list(request):
    """قائمة المستخدمين"""
    users = User.objects.all()[:10]  # أول 10 مستخدمين فقط للاختبار
    data = [{
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'user_type': user.user_type,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'date_joined': user.date_joined
    } for user in users]
    
    return Response({
        'users': data,
        'total': User.objects.count(),
        'page': 1,
        'page_size': 10
    })