# health_insurance/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import date, timedelta
import json

from .models import (
    HealthEstablishment,
    HealthCoveragePlan,
    HealthInsuranceQuote,
    HealthInsurancePolicy
)
from .calculations import calculate_health_premium, quick_health_calculator

User = get_user_model()

# ============= Model Tests =============
class HealthEstablishmentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_health_establishment(self):
        """اختبار إنشاء منشأة صحية"""
        establishment = HealthEstablishment.objects.create(
            user=self.user,
            name='مستشفى الاختبار',
            establishment_type='hospital',
            cr_number='CR123456',
            total_employees=50,
            establishment_age=5
        )
        
        self.assertEqual(establishment.name, 'مستشفى الاختبار')
        self.assertEqual(establishment.get_establishment_type_display, 'مستشفى')
        self.assertTrue(establishment.establishment_type == 'hospital')
        self.assertEqual(establishment.total_employees, 50)
        self.assertEqual(establishment.establishment_age, 5)

# ============= Calculation Tests =============
class HealthPremiumCalculationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calcuser',
            email='calc@example.com',
            password='testpass123'
        )
        
        self.establishment = HealthEstablishment.objects.create(
            user=self.user,
            name='عيادة الحساب',
            establishment_type='clinic',
            city='الرياض',
            total_employees=20,
            establishment_age=3,
            annual_revenue=1000000,
            has_previous_insurance=True
        )
        
        self.coverage_plan = HealthCoveragePlan.objects.create(
            name='خطة الاختبار',
            plan_type='standard',
            base_price_per_employee=1000
        )
    
    def test_quick_health_calculator(self):
        """اختبار الحاسبة السريعة"""
        result = quick_health_calculator(
            establishment_type='clinic',
            employee_count=10,
            city='الرياض',
            has_previous_insurance=True
        )
        
        self.assertIn('total_premium', result)
        self.assertIn('monthly_premium', result)
        self.assertIn('factors', result)
        
        # التأكد من أن القسط موجب
        self.assertGreater(result['total_premium'], 0)
        
    def test_calculate_health_premium(self):
        """اختبار احتساب القسط الكامل"""
        result = calculate_health_premium(
            establishment=self.establishment,
            coverage_plan=self.coverage_plan,
            insured_count=15
        )
        
        self.assertIn('total_premium', result)
        self.assertIn('monthly_premium', result)
        self.assertIn('factors', result)
        self.assertIn('coverage_details', result)
        self.assertIn('calculation_summary', result)
        
        # التأكد من وجود جميع العوامل
        expected_factors = ['size_factor', 'age_factor', 'type_factor', 
                           'location_factor', 'revenue_factor', 'insurance_history_factor']
        
        for factor in expected_factors:
            self.assertIn(factor, result['factors'])

# ============= API Tests =============
class HealthInsuranceAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.establishment = HealthEstablishment.objects.create(
            user=self.user,
            name='مستشفى API',
            establishment_type='hospital',
            cr_number='API123456',
            total_employees=100,
            establishment_age=10
        )
        
        self.coverage_plan = HealthCoveragePlan.objects.create(
            name='خطة API',
            plan_type='premium',
            base_price_per_employee=1500,
            is_active=True
        )
    
    def test_create_health_establishment(self):
        """اختبار إنشاء منشأة عبر API"""
        url = '/api/health/health-establishments/'
        data = {
            'name': 'مستشفى الاختبار API',
            'establishment_type': 'hospital',
            'size_category': 'medium',
            'cr_number': 'CR789012',
            'address': 'العنوان التجريبي',
            'city': 'جدة',
            'phone': '0512345678',
            'email': 'hospital@test.com',
            'total_employees': 75,
            'establishment_age': 8,
            'annual_revenue': 5000000,
            'has_previous_insurance': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], data['name'])
        self.assertEqual(response.data['establishment_type'], 'hospital')
        self.assertEqual(response.data['city'], 'جدة')
        
    def test_calculate_premium_api(self):
        """اختبار API حاسبة الأقساط"""
        url = '/api/health/health-premium/calculate/'
        data = {
            'establishment_type': 'clinic',
            'employee_count': 25,
            'city': 'الرياض',
            'has_previous_insurance': True,
            'coverage_plan_id': self.coverage_plan.id
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('calculation', response.data)
        self.assertIn('recommendations', response.data)
        
        calculation = response.data['calculation']
        self.assertIn('total_premium', calculation)
        self.assertIn('monthly_premium', calculation)
        self.assertIn('factors', calculation)
    
    def test_create_health_quote(self):
        """اختبار إنشاء اقتباس صحي"""
        url = '/api/health/health-insurance-quotes/'
        data = {
            'establishment': self.establishment.id,
            'coverage_plan_id': self.coverage_plan.id,
            'insured_employees_count': 50,
            'coverage_period': 12,
            'notes': 'اقتباس اختبار'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('quote', response.data)
        self.assertTrue(response.data['success'])
        
        quote_data = response.data['quote']
        self.assertIn('quote_number', quote_data)
        self.assertIn('total_premium', quote_data)
        self.assertIn('status', quote_data)
    
    def test_get_health_dashboard(self):
        """اختبار الحصول على لوحة التحكم"""
        url = '/api/health/health-insurance/dashboard/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('quick_stats', response.data)
        self.assertIn('recent_quotes', response.data)
        self.assertIn('active_policies', response.data)
        
        # التحقق من وجود البيانات الأساسية
        stats = response.data['quick_stats']
        self.assertIn('establishments_count', stats)
        self.assertIn('total_employees', stats)
        self.assertIn('quotes_count', stats)
        
    def test_get_health_reports(self):
        """اختبار الحصول على التقارير"""
        url = '/api/health/health-insurance/reports/?type=summary'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('establishments', response.data)
        self.assertIn('quotes', response.data)
        self.assertIn('policies', response.data)
    
    def test_accept_health_quote(self):
        """اختبار قبول اقتباس وإنشاء وثيقة"""
        # أولاً إنشاء اقتباس
        quote = HealthInsuranceQuote.objects.create(
            user=self.user,
            establishment=self.establishment,
            coverage_plan=self.coverage_plan,
            insured_employees_count=50,
            total_premium=75000,
            status='quoted'
        )
        
        # قبول الاقتباس
        url = f'/api/health/health-insurance-quotes/{quote.id}/accept/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('policy', response.data)
        self.assertIn('policy_number', response.data['policy'])
        
        # التحقق من تحديث حالة الاقتباس
        quote.refresh_from_db()
        self.assertEqual(quote.status, 'accepted')
        
        # التحقق من إنشاء الوثيقة
        policy = HealthInsurancePolicy.objects.get(quote=quote)
        self.assertEqual(policy.user, self.user)
        self.assertEqual(policy.establishment, self.establishment)
        self.assertEqual(policy.status, 'pending')

# ============= Permission Tests =============
class HealthInsurancePermissionTest(APITestCase):
    def setUp(self):
        # إنشاء مستخدمين
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        
        # إنشاء منشأة للمستخدم الأول
        self.establishment1 = HealthEstablishment.objects.create(
            user=self.user1,
            name='منشأة المستخدم 1',
            establishment_type='clinic',
            cr_number='CR111111'
        )
        
        # إنشاء اقتباس للمستخدم الأول
        coverage_plan = HealthCoveragePlan.objects.create(
            name='خطة الاختبار',
            base_price_per_employee=1000
        )
        
        self.quote1 = HealthInsuranceQuote.objects.create(
            user=self.user1,
            establishment=self.establishment1,
            coverage_plan=coverage_plan,
            total_premium=50000,
            status='quoted'
        )
    
    def test_user_cannot_access_other_user_establishments(self):
        """اختبار عدم قدرة المستخدم على الوصول لمنشآت مستخدم آخر"""
        # تسجيل دخول المستخدم الثاني
        self.client.force_authenticate(user=self.user2)
        
        # محاولة الوصول لمنشأة المستخدم الأول
        url = f'/api/health/health-establishments/{self.establishment1.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_user_cannot_access_other_user_quotes(self):
        """اختبار عدم قدرة المستخدم على الوصول لاقتباسات مستخدم آخر"""
        # تسجيل دخول المستخدم الثاني
        self.client.force_authenticate(user=self.user2)
        
        # محاولة الوصول لاقتباس المستخدم الأول
        url = f'/api/health/health-insurance-quotes/{self.quote1.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_user_cannot_modify_other_user_data(self):
        """اختبار عدم قدرة المستخدم على تعديل بيانات مستخدم آخر"""
        # تسجيل دخول المستخدم الثاني
        self.client.force_authenticate(user=self.user2)
        
        # محاولة تعديل منشأة المستخدم الأول
        url = f'/api/health/health-establishments/{self.establishment1.id}/'
        data = {'name': 'تم التعديل بدون صلاحية'}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

# ============= Edge Cases Tests =============
class HealthInsuranceEdgeCasesTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='edgeuser',
            email='edge@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_calculate_premium_with_minimum_values(self):
        """اختبار الحساب بالقيم الدنيا"""
        url = '/api/health/health-premium/calculate/'
        data = {
            'establishment_type': 'clinic',
            'employee_count': 1,  # أقل عدد ممكن
            'city': 'الرياض',
            'has_previous_insurance': False
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        calculation = response.data['calculation']
        self.assertGreater(calculation['total_premium'], 0)
    
    def test_calculate_premium_with_maximum_values(self):
        """اختبار الحساب بالقيم القصوى"""
        url = '/api/health/health-premium/calculate/'
        data = {
            'establishment_type': 'hospital',
            'employee_count': 10000,  # أقصى عدد ممكن
            'city': 'الرياض',
            'has_previous_insurance': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        calculation = response.data['calculation']
        self.assertGreater(calculation['total_premium'], 0)
        # التأكد من تطبيق خصم الحجم
        self.assertIn('factors', calculation)
    
    def test_create_quote_with_invalid_employee_count(self):
        """اختبار إنشاء اقتباس بعدد موظفين غير صالح"""
        # إنشاء منشأة وخطة تغطية أولاً
        establishment = HealthEstablishment.objects.create(
            user=self.user,
            name='مستشفى الحالات',
            establishment_type='hospital',
            cr_number='EDGE111',
            total_employees=50
        )
        
        coverage_plan = HealthCoveragePlan.objects.create(
            name='خطة الحالات',
            base_price_per_employee=1000,
            min_employees=10,
            max_employees=100
        )
        
        url = '/api/health/health-insurance-quotes/'
        
        # اختبار عدد موظفين أقل من الحد الأدنى
        data = {
            'establishment': establishment.id,
            'coverage_plan_id': coverage_plan.id,
            'insured_employees_count': 5,  # أقل من الحد الأدنى (10)
            'coverage_period': 12
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
        # اختبار عدد موظفين أكبر من الحد الأقصى
        data['insured_employees_count'] = 150  # أكبر من الحد الأقصى (100)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

# ============= Integration Tests =============
class HealthInsuranceIntegrationTest(APITestCase):
    """اختبارات التكامل الكاملة"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='integration',
            email='integration@example.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_full_health_insurance_flow(self):
        """اختبار سير العمل الكامل للتأمين الصحي"""
        
        # 1. إنشاء منشأة صحية
        establishment_url = '/api/health/health-establishments/'
        establishment_data = {
            'name': 'مستشفى التكامل',
            'establishment_type': 'hospital',
            'size_category': 'large',
            'cr_number': 'INTEG123',
            'address': 'شارع التكامل، الرياض',
            'city': 'الرياض',
            'phone': '0512345678',
            'email': 'integration@hospital.com',
            'total_employees': 150,
            'establishment_age': 8,
            'annual_revenue': 10000000,
            'has_previous_insurance': True
        }
        
        response = self.client.post(establishment_url, establishment_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        establishment_id = response.data['id']
        
        # 2. الحصول على خطط التغطية
        plans_url = '/api/health/health-coverage-plans/'
        response = self.client.get(plans_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
        
        # استخدام أول خطة نشطة
        plan_id = response.data[0]['id']
        
        # 3. احتساب قسط تجريبي
        calculate_url = '/api/health/health-premium/calculate/'
        calculate_data = {
            'establishment_type': 'hospital',
            'employee_count': 100,
            'city': 'الرياض',
            'has_previous_insurance': True,
            'coverage_plan_id': plan_id
        }
        
        response = self.client.post(calculate_url, calculate_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # 4. إنشاء اقتباس رسمي
        quotes_url = '/api/health/health-insurance-quotes/'
        quote_data = {
            'establishment': establishment_id,
            'coverage_plan_id': plan_id,
            'insured_employees_count': 100,
            'coverage_period': 12,
            'notes': 'اقتباس تجريبي للتكامل'
        }
        
        response = self.client.post(quotes_url, quote_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        quote_id = response.data['quote']['id']
        
        # 5. قبول الاقتباس وإنشاء وثيقة
        accept_url = f'/api/health/health-insurance-quotes/{quote_id}/accept/'
        response = self.client.post(accept_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        policy_id = response.data['policy']['id']
        
        # 6. الحصول على الوثيقة
        policy_url = f'/api/health/health-insurance-policies/{policy_id}/'
        response = self.client.get(policy_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 7. الحصول على لوحة التحكم
        dashboard_url = '/api/health/health-insurance/dashboard/'
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # التحقق من وجود البيانات
        stats = response.data['quick_stats']
        self.assertGreater(stats['establishments_count'], 0)
        self.assertGreater(stats['quotes_count'], 0)
        self.assertGreater(stats['policies_count'], 0)
        
        # 8. الحصول على تقرير
        report_url = '/api/health/health-insurance/reports/?type=summary'
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # التحقق من صحة البيانات في التقرير
        self.assertIn('establishments', response.data)
        self.assertIn('quotes', response.data)
        self.assertIn('policies', response.data)
        
        print("✅ تم اجتياز جميع اختبارات التكامل بنجاح!")