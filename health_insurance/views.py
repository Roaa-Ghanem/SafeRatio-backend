# health_insurance/views.py
from django.forms import ValidationError
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Avg, Min, Max
from datetime import datetime, timedelta
import uuid
from django.utils import timezone
from datetime import timedelta
import time
import os
import tempfile
import pandas as pd
from .services.universal_pricing_engine import UniversalPricingEngine
from django.http import JsonResponse
import json
from django.conf import settings
from django.db import transaction
import io
from decimal import Decimal
from django.db import IntegrityError
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from .models import (
    Company,
    Employee,
    HealthCoveragePlan, 
    HealthInsuranceQuote, 
    HealthInsurancePolicy,
    HealthCalculationLog,
    SectorPricingFactor,
)
from .serializers import (
    CompanySerializer,  # تغيير
    CompanyCreateSerializer,  # تغيير
    HealthCoveragePlanSerializer,
    HealthInsuranceQuoteSerializer,
    HealthInsuranceQuoteCreateSerializer,
    HealthInsurancePolicySerializer,
    HealthInsurancePolicySimpleSerializer,
    HealthPremiumCalculatorSerializer,
    HealthCalculationLogSerializer,
)
from .services.universal_pricing_engine import UniversalPricingEngine  # جديد
from .calculations import calculate_health_premium, quick_health_calculator

# ============= Company Views (بدلاً من HealthEstablishment) =============
class CompanyViewSet(viewsets.ModelViewSet):
    """واجهة إدارة الشركات"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CompanyCreateSerializer
        return CompanySerializer
    
    def get_queryset(self):
        """الاستعلام عن الشركات الخاصة بالمستخدم فقط"""
        print(f"🔍 CompanyViewSet.get_queryset() - User: {self.request.user}")
        
        # فلترة حسب المستخدم الحالي
        queryset = Company.objects.filter(user=self.request.user).order_by('-created_at')
        
        print(f"   عدد الشركات للمستخدم: {queryset.count()}")
        
        return queryset
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CompanyCreateSerializer
        return CompanySerializer
    
    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except IntegrityError as e:
            # معالجة أخطاء قاعدة البيانات (التكرار)
            if 'unique_company_name_per_user' in str(e):
                raise ValidationError({
                    'name': 'اسم الشركة هذا مستخدم بالفعل. الرجاء اختيار اسم آخر.'
                })
            elif 'company_cr_number_key' in str(e):
                raise ValidationError({
                    'cr_number': 'رقم السجل التجاري هذا مسجل مسبقاً.'
                })
            else:
                raise ValidationError('حدث خطأ في قاعدة البيانات. يرجى المحاولة مرة أخرى.')
            
        def handle_exception(self, exc):
            """معالجة الاستثناءات بشكل مخصص"""
            if isinstance(exc, ValidationError):
                # إذا كان خطأ تحقق
                return Response(
                    {'error': exc.detail if hasattr(exc, 'detail') else str(exc)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif isinstance(exc, IntegrityError):
                # إذا كان خطأ تكامل قاعدة البيانات
                return Response(
                    {'error': 'حدث خطأ في قاعدة البيانات. قد يكون هناك تكرار في البيانات.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return super().handle_exception(exc)
    
    @action(detail=True, methods=['get'])
    def quotes(self, request, pk=None):
        """الحصول على جميع اقتباسات الشركة"""
        company = self.get_object()
        quotes = HealthInsuranceQuote.objects.filter(company=company)
        serializer = HealthInsuranceQuoteSerializer(quotes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def policies(self, request, pk=None):
        """الحصول على جميع وثائق الشركة"""
        company = self.get_object()
        policies = HealthInsurancePolicy.objects.filter(company=company)
        serializer = HealthInsurancePolicySerializer(policies, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def calculate_premium(self, request, pk=None):
        """احتساب قسط تأمين صحي"""
        company = self.get_object()
        
        # التحقق من صلاحيات المستخدم
        if company.user != request.user:
            return Response(
                {'error': 'ليس لديك صلاحية للوصول إلى هذه الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # الحصول على معلمات الحساب
        coverage_plan_id = request.data.get('coverage_plan_id')
        insured_count = request.data.get('insured_employees', company.total_employees)
        
        if not coverage_plan_id:
            return Response(
                {'error': 'معرف خطة التغطية مطلوب'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            coverage_plan = HealthCoveragePlan.objects.get(id=coverage_plan_id, is_active=True)
        except HealthCoveragePlan.DoesNotExist:
            return Response(
                {'error': 'خطة التغطية غير موجودة أو غير نشطة'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # التحقق من أن الخطة تنطبق على قطاع الشركة
        if not coverage_plan.is_applicable_to_company(company):
            return Response(
                {'error': 'هذه الخطة غير متاحة لقطاع شركتك'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # التحقق من عدد الموظفين
        try:
            insured_count = int(insured_count)
            if insured_count < 1:
                insured_count = 1
            if insured_count > company.total_employees:
                insured_count = company.total_employees
        except (ValueError, TypeError):
            insured_count = company.total_employees
        
        # احتساب القسط (استخدام المحرك الجديد إذا كان ملف الموظفين موجوداً)
        if hasattr(company, 'employees_file') and company.employees_file:
            try:
                # استخدام المحرك الشامل
                pricing_engine = UniversalPricingEngine()
                file_path = company.employees_file.path
                
                # حساب القسط الشامل
                premium_result = calculate_health_premium(
                    company=company,
                    coverage_plan=coverage_plan,
                    insured_count=insured_count
                )
                
            except Exception as e:
                # في حالة خطأ، استخدم الحساب التقليدي
                premium_result = calculate_health_premium(
                    company=company,
                    coverage_plan=coverage_plan,
                    insured_count=insured_count
                )
        else:
            # استخدام الحساب التقليدي (لأن لا يوجد ملف موظفين)
            premium_result = calculate_health_premium(
                company=company,
                coverage_plan=coverage_plan,
                insured_count=insured_count
            )
        
        # تسجيل الحساب
        HealthCalculationLog.objects.create(
            user=request.user,
            company_sector=company.sector,
            company_size=company.size_category,
            employee_count=insured_count,
            coverage_plan_name=coverage_plan.name,
            calculated_premium=premium_result['total_premium'],
            factors_used=premium_result.get('factors', {}),
            ip_address=self._get_client_ip(request)
        )
        
        return Response({
            'success': True,
            'company': {
                'id': company.id,
                'name': company.name,
                'sector': company.get_sector_display(),
                'size': company.total_employees,
                'age': company.establishment_age
            },
            'coverage_plan': {
                'id': coverage_plan.id,
                'name': coverage_plan.name,
                'type': coverage_plan.get_plan_type_display,
                'base_price': float(coverage_plan.base_price_per_employee)
            },
            'calculation': premium_result,
            'next_steps': [
                'إنشاء اقتباس رسمي',
                'مراجعة تفاصيل التغطية',
                'طلب عرض نهائي'
            ]
        })
    
    @action(detail=True, methods=['post'], url_path='upload-employees')
    def upload_employees(self, request, pk=None):
        """
        رفع ملف Excel / CSV للموظفين
        """
        try:
            company = self.get_object()

            if 'employees_file' not in request.FILES:
                return Response(
                    {'error': 'لم يتم توفير ملف'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            file = request.FILES['employees_file']

            # 🔹 قراءة الملف
            if file.name.endswith('.csv'):
                df = pd.read_csv(io.StringIO(file.read().decode('utf-8')))
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                return Response(
                    {'error': 'نوع الملف غير مدعوم'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            print(f"📊 الأعمدة: {list(df.columns)}")
            print(f"📊 عدد الصفوف: {len(df)}")

            # 🔹 الأعمدة المطلوبة
            required_columns = [
                'الاسم_الكامل',
                'الجنس',
                'الحالة_الاجتماعية',
                'الراتب'
            ]

            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                return Response({
                    'error': f'أعمدة مفقودة: {missing}',
                    'available_columns': list(df.columns)
                }, status=status.HTTP_400_BAD_REQUEST)

            employees_created = 0
            errors = []

            with transaction.atomic():
                Employee.objects.filter(company=company).delete()
                for index, row in df.iterrows():
                    try:
                        # 🔹 البيانات الأساسية
                        name = str(row['الاسم_الكامل']).strip()
                        gender_raw = str(row['الجنس']).strip()
                        marital_raw = str(row['الحالة_الاجتماعية']).strip()
                        salary = float(row['الراتب']) if pd.notna(row['الراتب']) else 0

                        # 🔹 تحويل الجنس
                        gender = 'male' if gender_raw == 'ذكر' else 'female'

                        # 🔹 تحويل الحالة الاجتماعية
                        marital_status = 'married' if marital_raw == 'متزوج' else 'single'

                        # 🔹 حساب العمر
                        age = 30
                        if 'تاريخ_الميلاد' in df.columns and pd.notna(row.get('تاريخ_الميلاد')):
                            try:
                                birth = pd.to_datetime(row['تاريخ_الميلاد'])
                                today = pd.Timestamp.today()
                                age = today.year - birth.year
                            except:
                                age = 30

                        # 🔹 عدد الأبناء
                        children_count = 0
                        if 'عدد_الأبناء' in df.columns and pd.notna(row.get('عدد_الأبناء')):
                            try:
                                children_count = int(float(row['عدد_الأبناء']))
                            except:
                                children_count = 0
                        
                        # 🔹 عدد الزوجات - مهم جداً!
                        wives_count = 0
                        if 'عدد_الزوجات' in df.columns and pd.notna(row.get('عدد_الزوجات')):
                            try:
                                wives_raw = str(row['عدد_الزوجات']).strip()
                                # تحويل القيم المختلفة
                                if wives_raw == '':
                                    wives_count = 0
                                else:
                                    wives_count = int(float(row['عدد_الزوجات']))
                            except:
                                wives_count = 0
                            
                        # إذا كان متزوجاً ولم يُدخل عدد زوجات، نفترض زوجة واحدة
                        if marital_status == 'married' and wives_count == 0:
                            wives_count = 1
                        
                        # 🔹 عدد الوالدين - مهم جداً!
                        parents_count = 0
                        if 'عدد_الوالدان' in df.columns and pd.notna(row.get('عدد_الوالدان')):
                            try:
                                parents_raw = str(row['عدد_الوالدان']).strip()
                                if parents_raw == '':
                                    parents_count = 0
                                else:
                                    parents_count = int(float(row['عدد_الوالدان']))
                            except:
                                parents_count = 0

                        # 🔹 يشمل الوالدين
                        include_parents = False
                        if 'يشمل_الوالدين' in df.columns and pd.notna(row.get('يشمل_الوالدين')):
                            include_value = str(row['يشمل_الوالدين']).strip().lower()
                            include_parents = include_value in ['نعم', 'yes', 'true', '1']

                        # 🔹 الأمراض المزمنة
                        chronic_diseases = False
                        if 'الأمراض_المزمنة' in df.columns and pd.notna(row.get('الأمراض_المزمنة')):
                            chronic_value = str(row['الأمراض_المزمنة']).strip().lower()
                            chronic_diseases = chronic_value in ['نعم', 'yes', 'true', '1']

                        # 🔹 الرقم الوظيفي
                        employee_number = ''
                        if 'الرقم_الوظيفي' in df.columns and pd.notna(row.get('الرقم_الوظيفي')):
                            employee_number = str(row['الرقم_الوظيفي']).strip()


                        # 🔹 إنشاء الموظف (فقط الحقول الموجودة في المودل)
                        Employee.objects.create(
                            company=company,
                            name=name,
                            gender=gender,
                            marital_status=marital_status,
                            age=age,
                            base_salary=salary,
                            number_of_children=children_count,
                            employee_number=str(row.get('الرقم_الوظيفي', '')).strip(),
                            wives_count=wives_count,  # ✅ حفظ عدد الزوجات
                            parents_count=parents_count,  # ✅ حفظ عدد الوالدين
                            include_parents=include_parents,  # ✅ حفظ يشمل الوالدين
                            chronic_diseases=chronic_diseases,  # ✅ حفظ الأمراض المزمنة
                            insurance_profile={
                                'uploaded_from_excel': True,
                                'excel_row': index + 2,
                                'original_data': {
                                    'الاسم': name,
                                    'الجنس': gender_raw,
                                    'الحالة': marital_raw,
                                    'عدد_الزوجات_الأصلي': str(row.get('عدد_الزوجات', '')),
                                    'عدد_الوالدان_الأصلي': str(row.get('عدد_الوالدان', '')),
                                    'يشمل_الوالدين_الأصلي': str(row.get('يشمل_الوالدين', ''))
                                }
                            }
                        )

                        employees_created += 1
                        print(f"✅ موظف محفوظ: {name} - زوجات: {wives_count} - والدين: {parents_count}")

                    except Exception as e:
                        errors.append({
                            'row': index + 2,
                            'name': name if 'name' in locals() else 'غير معروف',
                            'error': str(e)
                        })
                        print(f"❌ خطأ في الصف {index + 2}: {e}")

            # 🔹 تحديث عدد الموظفين
            company.total_employees = Employee.objects.filter(company=company).count()
            company.save()

            return Response({
                'success': True,
                'message': f'تم رفع {employees_created} موظف بنجاح',
                'employees_created': employees_created,
                'total_employees': company.total_employees,
                'errors': errors if errors else [],
                'statistics': {
                    'total_processed': len(df),
                    'male_count': len(df[df['الجنس'] == 'ذكر']),
                    'female_count': len(df[df['الجنس'] == 'أنثى']),
                    'married_count': len(df[df['الحالة_الاجتماعية'] == 'متزوج']),
                    'total_children': df['عدد_الأبناء'].sum() if 'عدد_الأبناء' in df.columns else 0,
                    'total_wives': df['عدد_الزوجات'].sum() if 'عدد_الزوجات' in df.columns else 0,
                    'total_parents': df['عدد_الوالدان'].sum() if 'عدد_الوالدان' in df.columns else 0,
                    'include_parents_count': len(df[df['يشمل_الوالدين'] == 'نعم']) if 'يشمل_الوالدين' in df.columns else 0
                }
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'خطأ في معالجة الملف: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='employees')
    def employees(self, request, pk=None):
        """
        الحصول على موظفي الشركة من قاعدة البيانات
        """
        try:
            company = self.get_object()
            
            # ✅ الخيار 1: جلب من قاعدة البيانات (الأفضل)
            try:
                from .models import Employee
                employees = Employee.objects.filter(company=company)
                
                if employees.exists():
                    # إنشاء بيانات بسيطة بدون serializer
                    employees_data = []
                    for emp in employees:
                        employees_data.append({
                            'id': emp.id,
                            'name': emp.name,
                            'age': emp.age,
                            'gender': emp.gender,
                            'marital_status': emp.marital_status,
                            'position': emp.position,
                            'department': emp.department,
                            'base_salary': float(emp.base_salary) if emp.base_salary else 0,
                            'number_of_children': emp.number_of_children,
                            'children_count': emp.number_of_children,
                            'has_children': emp.has_children,
                            'employee_number': emp.employee_number,
                            'monthly_allowances': float(emp.monthly_allowances) if emp.monthly_allowances else 0,
                            'include_parents': emp.include_parents,  # ✅
                            'parents_count': emp.parents_count,  # ✅
                            'wives_count': emp.wives_count,  # ✅
                            'chronic_diseases': emp.chronic_diseases,  # ✅
                            'insurance_profile': emp.insurance_profile
                        })
                    
                    return Response({
                        'success': True,
                        'company_id': company.id,
                        'company_name': company.name,
                        'total_employees': employees.count(),
                        'employees': employees_data,
                        'source': 'database',
                        'data_summary': {
                        'total_children': sum(emp['children_count'] for emp in employees_data),
                        'total_wives': sum(emp['wives_count'] for emp in employees_data),
                        'total_parents': sum(emp['parents_count'] for emp in employees_data),
                        'include_parents_count': sum(1 for emp in employees_data if emp['include_parents'])
                        }
                    })
            except Exception as db_error:
                print(f"⚠️ خطأ في جلب الموظفين من DB: {db_error}")
            
            # ✅ الخيار 2: جلب من employees_data (إذا تم رفع ملف)
            if hasattr(company, 'employees_data') and company.employees_data:
                employees_list = company.employees_data.get('employees', [])
                
                return Response({
                    'success': True,
                    'company_id': company.id,
                    'company_name': company.name,
                    'total_employees': len(employees_list),
                    'employees': employees_list,
                    'source': 'employees_data'
                })
            
            # ✅ الخيار 3: لا توجد بيانات
            return Response({
                'success': True,
                'company_id': company.id,
                'company_name': company.name,
                'total_employees': 0,
                'employees': [],
                'message': 'لا توجد بيانات موظفين. يرجى رفع ملف الموظفين أولاً.'
            })
            
        except Exception as e:
            print(f"❌ خطأ في employees action: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ✅ إضافة API لجلب البيانات المستخرجة
    @action(detail=True, methods=['get'], url_path='get-extracted-employees', url_name='get-extracted-employees')
    def get_extracted_employees(self, request, pk=None):
        """جلب بيانات الموظفين المستخرجة والمخزنة"""
        company = self.get_object()
        
        if company.user != request.user:
            return Response(
                {'error': 'ليس لديك صلاحية للوصول إلى هذه الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # التحقق من وجود بيانات مستخرجة
        if not company.employees_data or 'employees' not in company.employees_data:
            return Response({
                'success': False,
                'has_data': False,
                'message': 'لا توجد بيانات موظفين مستخرجة لهذه الشركة',
                'has_file': bool(company.employees_file),
                'instructions': 'يرجى رفع ملف Excel أولاً لاستخراج البيانات'
            }, status=status.HTTP_404_NOT_FOUND)
        
        employees_data = company.employees_data.get('employees', [])
        stats = company.employees_data.get('stats', {})
        
        return Response({
            'success': True,
            'has_data': True,
            'company': {
                'id': company.id,
                'name': company.name,
                'has_file': bool(company.employees_file),
                'file_name': company.employees_file.name if company.employees_file else None
            },
            'employees_data': employees_data,
            'stats': stats,
            'extraction_info': {
                'extracted_at': company.employees_data.get('extracted_at'),
                'total_employees': len(employees_data),
                'extraction_success': company.employees_data.get('extraction_success', False)
            },
            'columns': company.employees_data.get('columns', [])
        })

    @action(detail=True, methods=['post'], url_path='extract-employees', url_name='extract-employees')
    def extract_employees(self, request, pk=None):
        """استخراج بيانات الموظفين من الملف المرفوع"""
        company = self.get_object()
        
        if company.user != request.user:
            return Response(
                {'error': 'ليس لديك صلاحية للوصول إلى هذه الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # التحقق من وجود ملف
        if not company.employees_file:
            return Response({
                'success': False,
                'error': 'لا يوجد ملف موظفين مرفوع لهذه الشركة'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # استخراج البيانات
            extraction_result = company.extract_and_store_employees_data()
            
            if extraction_result:
                return Response({
                    'success': True,
                    'message': f'تم استخراج {company.employees_data.get("total_count", 0)} موظف بنجاح',
                    'company': {
                        'id': company.id,
                        'name': company.name,
                        'employees_count': company.employees_data.get('total_count', 0)
                    },
                    'stats': company.employees_data.get('stats', {}),
                    'extracted_at': company.employees_data.get('extracted_at')
                })
            else:
                return Response({
                    'success': False,
                    'message': 'فشل استخراج البيانات',
                    'error': company.employees_data.get('error', 'خطأ غير معروف')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            print(f"❌ خطأ في استخراج البيانات: {str(e)}")
            return Response({
                'success': False,
                'error': f'خطأ في استخراج البيانات: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def create_quote(self, request, pk=None):
        """إنشاء اقتباس جديد للشركة"""
        company = self.get_object()
        
        # التحقق من صلاحيات المستخدم
        if company.user != request.user:
            return Response(
                {'error': 'ليس لديك صلاحية للوصول إلى هذه الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # استخدام السيريالايزر لإنشاء الاقتباس
        serializer = HealthInsuranceQuoteCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            # إضافة الشركة إلى البيانات
            validated_data = serializer.validated_data
            validated_data['company'] = company  # تغيير من establishment
            
            quote = serializer.create(validated_data)
            
            return Response({
                'success': True,
                'message': 'تم إنشاء الاقتباس بنجاح',
                'quote': HealthInsuranceQuoteSerializer(quote).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def sectors_data(self, request):
        """الحصول على بيانات القطاعات"""
        # مجموعات القطاعات
        groups = dict(Company.SECTOR_GROUPS)
        
        # جميع القطاعات
        sectors = []
        for value, label in Company.SECTOR_CHOICES:
            group = value.split('_')[0]
            sectors.append({
                'value': value,
                'label': label,
                'group': group,
                'description': self._get_sector_description(value)
            })
        
        # الحقول الخاصة بكل قطاع
        sector_fields = {}
        for sector in Company.SECTOR_SPECIFIC_FIELDS:
            sector_fields[sector] = Company.SECTOR_SPECIFIC_FIELDS[sector]
        
        return Response({
            'groups': groups,
            'sectors': sectors,
            'sector_fields': sector_fields
        })
    
    def _validate_employees_file(self, file_path):
        """التحقق من صحة ملف الموظفين"""
        try:
            df = pd.read_excel(file_path)
            
            # التحقق من الأعمدة الأساسية
            required_columns = ['الاسم', 'الجنس', 'تاريخ_الميلاد', 'الراتب', 'المعالين']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    'valid': False,
                    'error': f"الأعمدة المفقودة: {', '.join(missing_columns)}"
                }
            
            # التحقق من صحة البيانات
            errors = []
            
            # التحقق من الجنس
            valid_genders = ['ذكر', 'أنثى']
            invalid_genders = df[~df['الجنس'].isin(valid_genders)]
            if not invalid_genders.empty:
                errors.append(f"قيم غير صحيحة في عمود الجنس: {invalid_genders['الجنس'].unique()}")
            
            # التحقق من تاريخ الميلاد
            try:
                pd.to_datetime(df['تاريخ_الميلاد'])
            except:
                errors.append("تواريخ ميلاد غير صالحة")
            
            # التحقق من الرواتب
            if (df['الراتب'] < 0).any():
                errors.append("يوجد رواتب بقيم سالبة")
            
            # التحقق من عدد المعالين
            if (df['المعالين'] < 0).any():
                errors.append("يوجد عدد معالين بقيم سالبة")
            
            if errors:
                return {
                    'valid': False,
                    'error': " | ".join(errors)
                }
            
            # معلومات الملف
            info = {
                'total_rows': len(df),
                'male_count': len(df[df['الجنس'] == 'ذكر']),
                'female_count': len(df[df['الجنس'] == 'أنثى']),
                'total_dependents': int(df['المعالين'].sum()),
                'columns': list(df.columns)
            }
            
            return {
                'valid': True,
                'info': info
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"خطأ في قراءة الملف: {str(e)}"
            }
    
    def _get_sector_description(self, sector):
        """الحصول على وصف القطاع"""
        descriptions = {
            'health_hospital': 'مؤسسة طبية توفر رعاية صحية شاملة ومتخصصة',
            'tech_software': 'شركة متخصصة في تطوير البرمجيات والحلول التقنية',
            'construction_civil': 'شركة مقاولات تنفذ مشاريع إنشائية وبنية تحتية',
            'security_guarding': 'شركة توفر خدمات حراسة أمنية وحماية للمنشآت',
            'retail_store': 'متجر يبيع منتجات للمستهلكين مباشرة',
            'education_school': 'مؤسسة تعليمية تقدم التعليم النظامي',
            'manufacturing_food': 'مصنع ينتج مواد غذائية ومعالجة',
            'services_logistics': 'شركة متخصصة في الشحن والتوزيع واللوجستيات',
        }
        return descriptions.get(sector, 'شركة في هذا القطاع')
    
    def _get_client_ip(self, request):
        """الحصول على عنوان IP الخاص بالعميل"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=True, methods=['get'], url_path='get-employees-data', url_name='get-employees-data')
    def get_employees_data(self, request, pk=None):
        """
        جلب بيانات الموظفين المحفوظة للشركة
        """
        company = self.get_object()
        
        # التحقق من الصلاحية
        if company.user != request.user:
            return Response(
                {'error': 'ليس لديك صلاحية للوصول إلى هذه الشركة'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # التحقق من وجود بيانات موظفين
        if not company.employees_data:
            return Response({
                'success': False,
                'error': 'لا توجد بيانات موظفين لهذه الشركة',
                'has_file': bool(company.employees_file),
                'instructions': [
                    '1. قم برفع ملف Excel للموظفين أولاً',
                    '2. استخدم زر "رفع ملف الموظفين"',
                    '3. عد إلى هذه الصفحة'
                ]
            }, status=status.HTTP_404_NOT_FOUND)
        
        # استخراج البيانات
        employees_data = company.employees_data.get('raw_data', [])
        stats = company.employees_data.get('stats', {})
        
        return Response({
            'success': True,
            'company': {
                'id': company.id,
                'name': company.name,
                'total_employees': len(employees_data)
            },
            'employees_data': employees_data,
            'stats': stats,
            'total_employees': len(employees_data),
            'processed_at': company.employees_data.get('processed_at'),
            'file_name': str(company.employees_file) if company.employees_file else None
        })

# ============= Health Coverage Plan Views =============
class HealthCoveragePlanViewSet(viewsets.ReadOnlyModelViewSet):
    """واجهة خطط التغطية الصحية (للقراءة فقط)"""
    permission_classes = [IsAuthenticated]
    serializer_class = HealthCoveragePlanSerializer
    
    def get_queryset(self):
        queryset = HealthCoveragePlan.objects.filter(is_active=True)
        
        # فلترة حسب القطاع إذا كان موجوداً
        sector = self.request.query_params.get('sector')
        company_id = self.request.query_params.get('company_id')
        
        if sector:
            filtered_plans = []
            for plan in queryset:
                # محاكاة كائن شركة للتحقق
                class MockCompany:
                    def __init__(self, sector_value):
                        self.sector = sector_value
                        self.is_healthcare_sector = sector_value.startswith('health_')
                        self.work_environment = 'office'  # قيمة افتراضية
                        self.is_high_risk_sector = any(sector_value.startswith(risk) 
                        for risk in ['construction', 'manufacturing', 'security_guarding'])
                        self.risk_level = 'medium'
                
                mock_company = MockCompany(sector)
                if plan.is_applicable_to_company(mock_company):
                    filtered_plans.append(plan)
            return filtered_plans
        
        elif company_id:
            try:
                company = Company.objects.get(id=company_id, user=self.request.user)
                filtered_plans = [plan for plan in queryset if plan.is_applicable_to_company(company)]
                return filtered_plans
            except Company.DoesNotExist:
                return queryset
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def compare(self, request):
        """مقارنة خطط التغطية"""
        plans = self.get_queryset()
        
        comparison_data = []
        for plan in plans:
            comparison_data.append({
                'id': plan.id,
                'name': plan.name,
                'type': plan.get_plan_type_display,
                'base_price': float(plan.base_price_per_employee),
                'limits': {
                    'outpatient': float(plan.outpatient_limit),
                    'inpatient': float(plan.inpatient_limit),
                    'dental': float(plan.dental_limit),
                    'optical': float(plan.optical_limit),
                    'emergency': float(plan.emergency_limit),
                    'work_accident': float(plan.work_accident_limit) if plan.includes_work_accidents else 0
                },
                'coverage': {
                    'outpatient': plan.outpatient_coverage,
                    'inpatient': plan.inpatient_coverage,
                    'dental': plan.dental_coverage,
                    'optical': plan.optical_coverage,
                    'work_accident': plan.work_accident_coverage if plan.includes_work_accidents else 0
                },
                'features': {
                    'preventive_care': plan.includes_preventive_care,
                    'chronic_medication': plan.includes_chronic_medication,
                    'work_accidents': plan.includes_work_accidents,
                    'occupational_diseases': plan.includes_occupational_diseases
                },
                'applicable_to': plan.get_applicable_to_display()
            })
        
        return Response({
            'plans': comparison_data,
            'total_plans': len(comparison_data),
            'recommendation': self._get_recommendation(comparison_data)
        })
    
    def _get_recommendation(self, plans):
        """توصية بأفضل خطة"""
        if not plans:
            return "لا توجد خطط متاحة"
        
        # توصية حسب السعر والتغطية
        balanced_plans = [p for p in plans if p['type'] == 'قياسي']
        if balanced_plans:
            return f"الخطة القياسية توفر أفضل قيمة مقابل السعر"
        
        return f"نوصي بخطة {plans[0]['name']} كبداية جيدة"

# ============= Health Insurance Quote Views =============
class HealthInsuranceQuoteViewSet(viewsets.ModelViewSet):
    """واجهة اقتباسات التأمين الصحي"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return HealthInsuranceQuoteCreateSerializer
        return HealthInsuranceQuoteSerializer
    
    def get_queryset(self):
        return HealthInsuranceQuote.objects.filter(user=self.request.user).order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    # health_insurance/views.py - Updated accept method
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept a health insurance quote and create policy - SIMPLIFIED"""
        quote = self.get_object()
        
        print(f"🎯 قبول الاقتباس {quote.id} - حالة: {quote.status}")
        
        # Allow both quoted and pending status
        if quote.status not in ['quoted', 'pending']:
            return Response(
                {'error': f'لا يمكن قبول اقتباس بحالة {quote.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get data from quote
            coverage_details = quote.coverage_details or {}
            calculation_data = quote.calculation_data or {}
            
            print(f"📊 بيانات الاقتباس: coverage_details={bool(coverage_details)}, calculation_data={bool(calculation_data)}")
            
            # Extract insurance type and payment method
            insurance_type = coverage_details.get('insurance_type', 'B')
            payment_method = coverage_details.get('payment_method', 'annual')
            coverage_options = coverage_details.get('coverage_options', {})
            family_members = coverage_details.get('family_members', {})
            
            # Get total employees
            total_employees = quote.insured_employees_count
            
            # Create policy - SIMPLE AND CLEAN
            policy_data = {
                # Relationships
                'quote': quote,
                'company': quote.company,
                'user': quote.user,
                
                # Basic info
                'policy_number': f"HP-{uuid.uuid4().hex[:8].upper()}",
                'insurance_type': insurance_type,
                'payment_method': payment_method,
                'total_employees': total_employees,
                
                # Premiums
                'total_premium': quote.total_premium or 0,
                'annual_premium': quote.annual_premium or 0,
                'monthly_premium': quote.monthly_premium or 0,
                'due_amount': quote.total_premium or 0,
                
                # Coverage data
                'coverage_details': coverage_details,
                'calculation_data': calculation_data,
                'family_members': family_members,
                'coverage_options': coverage_options,
                
                # Dates
                'inception_date': timezone.now().date(),
                'expiry_date': timezone.now().date() + timedelta(days=365),
                
                # Status
                'status': 'active',
                'payment_status': 'pending'
            }
            
            print(f"📝 إنشاء وثيقة بالبيانات: {policy_data.keys()}")
            
            policy = HealthInsurancePolicy.objects.create(**policy_data)
            
            # Update quote
            quote.status = 'accepted'
            quote.accepted_at = timezone.now()
            quote.save()
            
            print(f"✅ تم إنشاء الوثيقة {policy.policy_number}")
            
            # Return success with minimal data
            return Response({
                'success': True,
                'message': 'تم قبول الاقتباس وإنشاء الوثيقة بنجاح',
                'policy': {
                    'id': policy.id,
                    'policy_number': policy.policy_number,
                    'insurance_type': insurance_type,
                    'total_premium': float(policy.total_premium),
                    'monthly_premium': float(policy.monthly_premium),
                    'status': policy.status,
                    'inception_date': policy.inception_date,
                    'expiry_date': policy.expiry_date
                }
            })
            
        except Exception as e:
            import traceback
            print(f"❌ خطأ في قبول الاقتباس {quote.id}: {str(e)}")
            traceback.print_exc()
            return Response(
                {'error': f'حدث خطأ في إنشاء الوثيقة: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def generate_policy_number(self):
        """Generate unique policy number"""
        import time
        import random
        import string
        timestamp = int(time.time())
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"HP-{random_str}"
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """رفض الاقتباس"""
        try:
            quote = self.get_object()
            
            # التحقق من صلاحية المستخدم
            if quote.user != request.user:
                return Response(
                    {'error': 'ليس لديك صلاحية لرفض هذا الاقتباس'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # التحقق من حالة الاقتباس - يجب أن يكون في حالة 'quoted' أو 'pending'
            if quote.status not in ['quoted', 'pending']:
                return Response(
                    {'error': f'لا يمكن رفض الاقتباس. حالته الحالية: {quote.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # الحصول على سبب الرفض إذا وجد
            rejection_reason = request.data.get('rejection_reason', '')
            
            print(f"🔍 رفض الاقتباس {quote.id}: حالة {quote.status}، السبب: {rejection_reason}")
            
            # تحديث حالة الاقتباس
            quote.status = 'rejected'
            
            # تحديث الملاحظات إذا كان هناك سبب
            if rejection_reason and rejection_reason.strip():
                current_notes = quote.notes or ''
                
                # تحقق إذا كانت notes عبارة عن JSON
                try:
                    if current_notes and current_notes.strip().startswith('{'):
                        notes_data = json.loads(current_notes)
                        notes_data['rejection_reason'] = rejection_reason
                        notes_data['rejected_at'] = datetime.now().isoformat()
                        quote.notes = json.dumps(notes_data, ensure_ascii=False)
                    else:
                        # إذا كانت نص عادي
                        new_notes = f"{current_notes}\n\nسبب الرفض: {rejection_reason}\nتاريخ الرفض: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        quote.notes = new_notes
                except:
                    # في حالة خطأ، أضف ببساطة
                    quote.notes = f"{current_notes}\n\nسبب الرفض: {rejection_reason}"
            else:
                # إذا لم يكن هناك سبب، أضف تاريخ الرفض فقط
                current_notes = quote.notes or ''
                try:
                    if current_notes and current_notes.strip().startswith('{'):
                        notes_data = json.loads(current_notes)
                        notes_data['rejected_at'] = datetime.now().isoformat()
                        quote.notes = json.dumps(notes_data, ensure_ascii=False)
                    else:
                        quote.notes = f"{current_notes}\n\nتم الرفض في: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                except:
                    quote.notes = f"{current_notes}\n\nتم الرفض"
            
            quote.save()
            
            # سجل النشاط
            ActivityLog.objects.create(
                user=request.user,
                action='rejected_health_quote',
                description=f'رفض اقتباس التأمين الصحي #{quote.quote_number}',
                metadata={
                    'quote_id': quote.id,
                    'quote_number': quote.quote_number,
                    'rejection_reason': rejection_reason if rejection_reason else None,
                    'company_name': quote.company.name if quote.company else None
                }
            )
            
            return Response({
                'success': True,
                'message': 'تم رفض الاقتباس بنجاح',
                'quote_number': quote.quote_number,
                'status': quote.status,
                'rejected_at': datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"❌ خطأ في رفض الاقتباس: {str(e)}")
            return Response(
                {'error': f'حدث خطأ: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(detail=False, methods=['get'])
    def status_summary(self, request):
        """ملخص حالة الاقتباسات"""
        quotes = self.get_queryset()
        
        status_counts = quotes.values('status').annotate(
            count=Count('id'),
            total_premium=Sum('total_premium')
        )
        
        return Response({
            'total_quotes': quotes.count(),
            'status_summary': list(status_counts),
            'total_premium_all': quotes.aggregate(Sum('total_premium'))['total_premium__sum'] or 0,
            'average_premium': quotes.aggregate(Avg('total_premium'))['total_premium__avg'] or 0
        })
    

# ============= Health Insurance Policy Views =============
class HealthInsurancePolicyViewSet(viewsets.ModelViewSet):
    """واجهة وثائق التأمين الصحي"""
    permission_classes = [IsAuthenticated]
    serializer_class = HealthInsurancePolicySerializer
    
    def get_queryset(self):
        # الحصول على وثائق المستخدم
        return HealthInsurancePolicy.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=True, methods=['get'])
    def generate_certificate(self, request, pk=None):
        """إنشاء شهادة الوثيقة"""
        policy = self.get_object()
        
        if policy.user != request.user:
            return Response(
                {'error': 'ليس لديك صلاحية للوصول إلى هذه الوثيقة'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # إنشاء شهادة HTML بسيطة
        certificate_html = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <title>شهادة تأمين صحي - {policy.policy_number}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .certificate {{ border: 2px solid #000; padding: 30px; max-width: 800px; margin: 0 auto; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .content {{ line-height: 1.6; }}
                .signature {{ margin-top: 50px; text-align: left; }}
            </style>
        </head>
        <body>
            <div class="certificate">
                <div class="header">
                    <h1>شهادة تأمين صحي</h1>
                    <h2>رقم الوثيقة: {policy.policy_number}</h2>
                </div>
                <div class="content">
                    <p>نشهد بأن:</p>
                    <p><strong>الشركة:</strong> {policy.company.name}</p>
                    <p><strong>قطاع الشركة:</strong> {policy.company.get_sector_display()}</p>
                    <p><strong>خطة التغطية:</strong> {policy.coverage_plan.name if policy.coverage_plan else 'غير محدد'}</p>
                    <p><strong>فترة التغطية:</strong> من {policy.inception_date} إلى {policy.expiry_date}</p>
                    <p><strong>القسط الإجمالي:</strong> {policy.total_premium} ريال</p>
                    <p><strong>حالة الوثيقة:</strong> {policy.get_status_display()}</p>
                    <p>هذه الشهادة صادرة من نظام SafeRatio لأغراض العرض والتجربة فقط.</p>
                </div>
                <div class="signature">
                    <p>_________________________</p>
                    <p>SafeRatio Insurance</p>
                    <p>تاريخ الإصدار: {datetime.now().strftime('%Y-%m-%d')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return Response({
            'certificate_html': certificate_html,
            'policy_number': policy.policy_number,
            'download_url': f'/api/health/health-insurance-policies/{policy.id}/certificate/download/',
            'note': 'هذه شهادة تجريبية لأغراض العرض فقط'
        })
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """الوثائق النشطة"""
        active_policies = self.get_queryset().filter(status='active')
        serializer = self.get_serializer(active_policies, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """الوثائق التي على وشك الانتهاء"""
        from datetime import date, timedelta
        today = date.today()
        next_month = today + timedelta(days=30)
        
        expiring_policies = self.get_queryset().filter(
            status='active',
            expiry_date__range=[today, next_month]
        )
        serializer = self.get_serializer(expiring_policies, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """ملخص الوثائق"""
        policies = self.get_queryset()
        
        summary = {
            'total_policies': policies.count(),
            'active_policies': policies.filter(status='active').count(),
            'total_premium': float(policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
            'average_premium': float(policies.aggregate(Avg('total_premium'))['total_premium__avg'] or 0),
            'company_sectors': list(policies.values('company__sector').annotate(
                count=Count('id')
            )),
            'status_distribution': list(policies.values('status').annotate(
                count=Count('id'),
                total_premium=Sum('total_premium')
            ))
        }
        
        return Response(summary)
    
    @action(detail=True, methods=['get'])
    def generate_pdf(self, request, pk=None):
        """إنشاء PDF لوثيقة التأمين"""
        try:
            policy = self.get_object()
            
            # التحقق من صلاحية المستخدم
            if policy.user != request.user:
                return Response(
                    {'error': 'ليس لديك صلاحية للوصول إلى هذه الوثيقة'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # تجهيز بيانات الوثيقة للقالب
            context = self.get_policy_context(policy)
            
            # إنشاء HTML من القالب
            html_string = render_to_string('health_insurance/policy_pdf_template.html', context)
            
            # إعداد CSS للتصميم
            css_string = self.get_policy_css()
            
            # إنشاء PDF
            pdf_file = self.create_pdf_from_html(html_string, css_string)
            
            # إرجاع PDF كاستجابة
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="وثيقة_تأمين_{policy.policy_number}.pdf"'
            
            return response
            
        except Exception as e:
            print(f"❌ خطأ في إنشاء PDF: {str(e)}")
            return Response(
                {'error': f'حدث خطأ في إنشاء PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def generate_and_save_pdf(self, request, pk=None):
        """تلقي PDF من Frontend وحفظه في قاعدة البيانات"""
        try:
            policy = self.get_object()
            
            # التحقق من صلاحية المستخدم
            if policy.user != request.user:
                return Response(
                    {'error': 'ليس لديك صلاحية للوصول إلى هذه الوثيقة'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # الحصول على بيانات PDF من الطلب
            pdf_base64 = request.data.get('pdf_data')
            pdf_filename = request.data.get('filename', f'policy_{policy.policy_number}.pdf')
            
            if not pdf_base64:
                return Response(
                    {'error': 'بيانات PDF غير موجودة'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # تحويل Base64 إلى ملف
            try:
                # إزالة header إذا كان موجوداً
                if 'base64,' in pdf_base64:
                    pdf_base64 = pdf_base64.split('base64,')[1]
                
                # تحويل Base64 إلى bytes
                pdf_bytes = base64.b64decode(pdf_base64)
                
                # إنشاء اسم ملف فريد
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f'policy_{policy.policy_number}_{timestamp}.pdf'
                
                # حفظ الملف في الـ Model
                policy.pdf_document.save(
                    unique_filename,
                    ContentFile(pdf_bytes),
                    save=True
                )
                
                # تحديث معلومات PDF
                policy.pdf_generated_at = timezone.now()
                policy.pdf_file_size = len(pdf_bytes)
                policy.save()
                
                # معلومات الملف المحفوظ
                file_info = {
                    'id': policy.id,
                    'policy_number': policy.policy_number,
                    'pdf_url': policy.pdf_document.url if policy.pdf_document else None,
                    'pdf_filename': policy.pdf_document.name.split('/')[-1] if policy.pdf_document else None,
                    'pdf_size': policy.pdf_file_size,
                    'pdf_generated_at': policy.pdf_generated_at,
                    'download_url': request.build_absolute_uri(policy.pdf_document.url) if policy.pdf_document else None,
                }
                
                return Response({
                    'success': True,
                    'message': 'تم حفظ PDF بنجاح في قاعدة البيانات',
                    'file_info': file_info
                })
                
            except Exception as e:
                return Response({
                    'error': f'خطأ في حفظ الملف: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'error': f'حدث خطأ: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_pdf_info(self, request, pk=None):
        """الحصول على معلومات PDF المحفوظ"""
        try:
            policy = self.get_object()
            
            if policy.user != request.user:
                return Response(
                    {'error': 'ليس لديك صلاحية للوصول إلى هذه الوثيقة'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if not policy.pdf_document:
                return Response({
                    'has_pdf': False,
                    'message': 'لا يوجد PDF محفوظ لهذه الوثيقة'
                })
            
            return Response({
                'has_pdf': True,
                'pdf_info': {
                    'url': policy.pdf_document.url,
                    'filename': policy.pdf_document.name.split('/')[-1],
                    'size': policy.pdf_file_size,
                    'generated_at': policy.pdf_generated_at,
                    'download_url': request.build_absolute_uri(policy.pdf_document.url),
                }
            })
            
        except Exception as e:
            return Response({
                'error': f'حدث خطأ: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """تحميل PDF من قاعدة البيانات"""
        try:
            policy = self.get_object()
            
            if policy.user != request.user:
                return Response(
                    {'error': 'ليس لديك صلاحية للوصول إلى هذه الوثيقة'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if not policy.pdf_document:
                return Response(
                    {'error': 'لا يوجد PDF محفوظ لهذه الوثيقة'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # فتح الملف وإرساله
            pdf_file = policy.pdf_document.open('rb')
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{policy.pdf_document.name.split("/")[-1]}"'
            
            return response
            
        except Exception as e:
            return Response({
                'error': f'حدث خطأ: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_coverage_details(self, policy):
        """تفاصيل التغطية"""
        return {
            'employee_coverage': '100%',
            'spouse_coverage': '50%',
            'children_coverage': '50%',
            'parents_coverage': '30%',
            'annual_limit': '$50,000',
            'deductible': '$500',
            'co_payment': '20%',
            'emergency_coverage': 'مغطاة',
            'dental_coverage': 'محدودة',
            'optical_coverage': 'مغطاة جزئياً',
        }
    
    @action(detail=True, methods=['get'])
    def policy_data_for_pdf(self, request, pk=None):
        """إرجاع بيانات الوثيقة فقط لإنشاء PDF في Frontend"""
        try:
            policy = self.get_object()
            
            # التحقق من صلاحية المستخدم
            if policy.user != request.user:
                return Response(
                    {'error': 'ليس لديك صلاحية للوصول إلى هذه الوثيقة'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # تجهيز بيانات الوثيقة
            data = self.get_policy_data(policy)
            
            return Response(data)
            
        except Exception as e:
            return Response(
                {'error': f'حدث خطأ: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_policy_data(self, policy):
        """تجهيز بيانات الوثيقة مع بيانات العائلة الكاملة"""
        from datetime import datetime
        
        # استخراج بيانات العائلة من policy_details
        family_members = {}
        
        if hasattr(policy, 'policy_details') and policy.policy_details:
            if isinstance(policy.policy_details, dict):
                family_members = policy.policy_details.get('family_members', {})
            elif hasattr(policy.policy_details, 'family_members'):
                family_members = policy.policy_details.family_members
        
        # إذا لم توجد بيانات في policy_details، ابحث في مكان آخر
        if not family_members:
            # محاولة استخراج من quote إذا كان موجوداً
            if hasattr(policy, 'quote') and policy.quote:
                try:
                    from health_insurance.models import Quote
                    quote = Quote.objects.get(id=policy.quote.id)
                    if hasattr(quote, 'quote_details') and quote.quote_details:
                        if isinstance(quote.quote_details, dict):
                            family_members = quote.quote_details.get('family_members', {})
                except:
                    pass
        
        # تأكد من وجود جميع المفاتيح
        default_family = {
            'employees': 0,
            'spouses': 0,
            'children': 0,
            'parents': 0
        }
        
        # دمج البيانات مع القيم الافتراضية
        if isinstance(family_members, dict):
            for key in default_family.keys():
                if key not in family_members:
                    family_members[key] = 0
                else:
                    # تحويل إلى عدد صحيح
                    try:
                        family_members[key] = int(family_members[key])
                    except:
                        family_members[key] = 0
        else:
            family_members = default_family
        
        # حساب الإجماليات
        total_employees = family_members.get('employees', 0)
        total_spouses = family_members.get('spouses', 0)
        total_children = family_members.get('children', 0)
        total_parents = family_members.get('parents', 0)
        total_family = total_spouses + total_children + total_parents
        
        return {
            'id': policy.id,
            'policy_number': policy.policy_number,
            'company_name': policy.company_name,
            'coverage_plan_name': self.get_coverage_plan_name(policy),
            'insurance_type': policy.policy_details.get('insurance_type', 'B') if hasattr(policy, 'policy_details') and policy.policy_details else 'B',
            'insurance_type_name': self.get_insurance_type_name(policy.policy_details.get('insurance_type', 'B') if hasattr(policy, 'policy_details') and policy.policy_details else 'B'),
            'inception_date': policy.inception_date.strftime('%Y-%m-%d'),
            'inception_date_arabic': self.convert_to_arabic_date(policy.inception_date),
            'expiry_date': policy.expiry_date.strftime('%Y-%m-%d'),
            'expiry_date_arabic': self.convert_to_arabic_date(policy.expiry_date),
            'total_premium': float(policy.total_premium) if policy.total_premium else 0,
            'annual_premium': float(policy.annual_premium) if policy.annual_premium else 0,
            'monthly_premium': float(policy.monthly_premium) if policy.monthly_premium else 0,
            'paid_amount': float(policy.paid_amount) if policy.paid_amount else 0,
            'due_amount': float(policy.due_amount) if policy.due_amount else 0,
            'status': policy.status,
            'status_display': policy.get_status_display(),
            'payment_status': policy.payment_status,
            'payment_status_display': policy.get_payment_status_display(),
            'days_remaining': self.calculate_days_remaining(policy.expiry_date),
            'family_members': family_members,
            'total_employees': total_employees,
            'total_spouses': total_spouses,
            'total_children': total_children,
            'total_parents': total_parents,
            'total_family': total_family,
            'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'generated_date_arabic': self.convert_to_arabic_date(datetime.now().date()),
            'policy_details': policy.policy_details if hasattr(policy, 'policy_details') else {}
        }
    
    def get_policy_context(self, policy):
        """تجهيز بيانات الوثيقة للقالب"""
        # استخراج بيانات خطة التغطية
        coverage_plan_name = self.get_coverage_plan_name(policy)
        
        # استخراج بيانات العائلة
        family_members = policy.policy_details.get('family_members', {})
        
        # حساب الإحصائيات
        total_family = sum(family_members.values()) if family_members else 0
        
        return {
            'policy': policy,
            'company_name': policy.company_name,
            'policy_number': policy.policy_number,
            'coverage_plan_name': coverage_plan_name,
            'insurance_type': policy.policy_details.get('insurance_type', 'B'),
            'insurance_type_name': self.get_insurance_type_name(policy.policy_details.get('insurance_type', 'B')),
            'inception_date': policy.inception_date.strftime('%Y-%m-%d'),
            'inception_date_arabic': self.convert_to_arabic_date(policy.inception_date),
            'expiry_date': policy.expiry_date.strftime('%Y-%m-%d'),
            'expiry_date_arabic': self.convert_to_arabic_date(policy.expiry_date),
            'total_premium': f"{policy.total_premium:,.2f}",
            'annual_premium': f"{policy.annual_premium:,.2f}",
            'monthly_premium': f"{policy.monthly_premium:,.2f}",
            'paid_amount': f"{policy.paid_amount:,.2f}",
            'due_amount': f"{policy.due_amount:,.2f}",
            'status_display': policy.get_status_display(),
            'payment_status_display': policy.get_payment_status_display(),
            'days_remaining': self.calculate_days_remaining(policy.expiry_date),
            'family_members': family_members,
            'total_family_members': total_family,
            'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'generated_date_arabic': self.convert_to_arabic_date(datetime.now().date()),
        }
    
    def get_coverage_plan_name(self, policy):
        """الحصول على اسم خطة التغطية"""
        if policy.coverage_plan:
            return policy.coverage_plan.name
        
        insurance_type = policy.policy_details.get('insurance_type', 'B')
        if insurance_type == 'A':
            return 'التغطية الشاملة'
        elif insurance_type == 'B':
            return 'التغطية المتوسطة'
        elif insurance_type == 'C':
            return 'التغطية الأساسية'
        
        return policy.policy_details.get('coverage_plan_name', 'غير محدد')
    
    def get_insurance_type_name(self, insurance_type):
        """الحصول على اسم نوع التأمين"""
        types = {
            'A': 'ممتازة',
            'B': 'متوسطة',
            'C': 'أساسية'
        }
        return types.get(insurance_type, 'غير محدد')
    
    def convert_to_arabic_date(self, date_obj):
        """تحويل التاريخ إلى نص عربي"""
        try:
            arabic_months = {
                1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
                5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
                9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
            }
            
            day = date_obj.day
            month = arabic_months.get(date_obj.month, '')
            year = date_obj.year
            
            return f"{day} {month} {year}"
        except:
            return date_obj.strftime('%Y-%m-%d')
    
    def calculate_days_remaining(self, expiry_date):
        """حساب الأيام المتبقية"""
        from datetime import date
        today = date.today()
        remaining = (expiry_date - today).days
        return max(0, remaining)
    
    def get_policy_css(self):
        """CSS لتصميم PDF"""
        return """
        @page {
            size: A4;
            margin: 2cm;
            @bottom-right {
                content: "صفحة " counter(page) " من " counter(pages);
                font-size: 10px;
                color: #666;
            }
        }
        
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            direction: rtl;
            text-align: right;
            color: #333;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #007bff;
        }
        
        .header h1 {
            color: #007bff;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .header .subtitle {
            color: #666;
            font-size: 14px;
        }
        
        .section {
            margin-bottom: 25px;
            page-break-inside: avoid;
        }
        
        .section-title {
            background-color: #f8f9fa;
            padding: 10px 15px;
            border-right: 4px solid #007bff;
            margin-bottom: 15px;
            color: #007bff;
            font-weight: bold;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .info-item {
            padding: 10px;
            border-bottom: 1px dashed #dee2e6;
        }
        
        .info-label {
            font-weight: bold;
            color: #495057;
            margin-left: 10px;
        }
        
        .info-value {
            color: #212529;
        }
        
        .coverage-summary {
            background-color: #f0f8ff;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
            border: 1px solid #cce5ff;
        }
        
        .table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        
        .table th {
            background-color: #007bff;
            color: white;
            padding: 12px;
            text-align: right;
        }
        
        .table td {
            padding: 10px;
            border: 1px solid #dee2e6;
        }
        
        .table tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .total-row {
            background-color: #e8f5e8 !important;
            font-weight: bold;
        }
        
        .signature-section {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #dee2e6;
        }
        
        .signature-box {
            text-align: center;
            margin-top: 30px;
        }
        
        .signature-line {
            width: 300px;
            height: 1px;
            background-color: #000;
            margin: 40px auto 10px;
        }
        
        .footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
            font-size: 11px;
            color: #666;
            text-align: center;
        }
        
        .warning-box {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        
        .success-text {
            color: #28a745;
            font-weight: bold;
        }
        
        .danger-text {
            color: #dc3545;
            font-weight: bold;
        }
        
        .primary-text {
            color: #007bff;
            font-weight: bold;
        }
        """
    
    def create_pdf_from_html(self, html_string, css_string):
        """إنشاء PDF من HTML"""
        try:
            # إنشاء تكوين الخط
            font_config = FontConfiguration()
            
            # إنشاء HTML مع CSS
            html = HTML(string=html_string)
            css = CSS(string=css_string, font_config=font_config)
            
            # إنشاء PDF في ملف مؤقت
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                html.write_pdf(tmp_file.name, stylesheets=[css], font_config=font_config)
                
                # قراءة الملف
                with open(tmp_file.name, 'rb') as f:
                    pdf_data = f.read()
                
                # حذف الملف المؤقت
                os.unlink(tmp_file.name)
                
                return pdf_data
                
        except Exception as e:
            print(f"❌ خطأ في إنشاء PDF: {str(e)}")
            raise


# ============= Health Premium Calculator View =============
class HealthPremiumCalculatorView(APIView):
    """حاسبة أقساط التأمين الصحي العامة"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """احتساب قسط صحي"""
        serializer = HealthPremiumCalculatorSerializer(data=request.data)
        
        if serializer.is_valid():
            # احتساب القسط
            calculation_result = serializer.calculate_premium()
            
            # تسجيل الحساب
            HealthCalculationLog.objects.create(
                user=request.user,
                company_sector=serializer.validated_data.get('sector', 'other'),
                company_size=serializer.validated_data.get('size_category', 'small'),
                employee_count=serializer.validated_data['employee_count'],
                dependents_count=serializer.validated_data.get('dependents_count', 0),
                coverage_plan_name='حاسبة سريعة',
                calculated_premium=calculation_result['total_premium'],
                factors_used=calculation_result['factors'],
                ip_address=self._get_client_ip(request)
            )
            
            return Response({
                'success': True,
                'calculation': calculation_result,
                'recommendations': self._generate_recommendations(serializer.validated_data, calculation_result)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        """الحصول على إحصائيات الحسابات"""
        user_calculations = HealthCalculationLog.objects.filter(user=request.user)
        
        stats = {
            'total_calculations': user_calculations.count(),
            'average_premium': float(user_calculations.aggregate(Avg('calculated_premium'))['calculated_premium__avg'] or 0),
            'company_sectors': list(user_calculations.values('company_sector').annotate(
                count=Count('id'),
                avg_premium=Avg('calculated_premium')
            )),
            'recent_calculations': HealthCalculationLogSerializer(
                user_calculations.order_by('-created_at')[:10], 
                many=True
            ).data
        }
        
        return Response(stats)
    
    def _generate_recommendations(self, data, calculation):
        """توليد توصيات بناءً على الحساب"""
        recommendations = []
        
        employee_count = data['employee_count']
        premium_per_employee = calculation['premium_per_employee']
        sector = data.get('sector', 'other')
        
        if employee_count >= 50:
            recommendations.append(
                "بما أن عدد موظفيك يتجاوز 50، يمكنك الحصول على خصم جماعي يصل إلى 15%"
            )
        
        if premium_per_employee > 2000:
            recommendations.append(
                f"قسط الموظف ({premium_per_employee:.2f} ريال) مرتفع نسبياً. "
                "جرب خططاً أخرى أو تفاوض على شروط أفضل"
            )
        elif premium_per_employee < 800:
            recommendations.append(
                f"قسط ممتاز للموظف ({premium_per_employee:.2f} ريال). "
                "هذه خطة جيدة من حيث القيمة مقابل السعر"
            )
        
        if data.get('has_previous_insurance'):
            recommendations.append(
                "بما أن لديك تأميناً سابقاً، قد تكون مؤهلاً لخصومات إضافية"
            )
        
        # توصيات حسب القطاع
        if sector.startswith('health_'):
            recommendations.append("قطاعك الصحي يتطلب تغطية شاملة للعيادات والتنويم")
        elif sector.startswith('construction'):
            recommendations.append("نوصي بتأمين إصابات العمل بسبب طبيعة عملك الميدانية")
        elif sector.startswith('tech'):
            recommendations.append("يمكنك الاستفادة من خطط العمل عن بعد لتقليل التكاليف")
        
        return recommendations
    
    def _get_client_ip(self, request):
        """الحصول على عنوان IP الخاص بالعميل"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

# ============= Health Insurance Dashboard View =============
class HealthInsuranceDashboardView(APIView):
    """لوحة تحكم التأمين الصحي"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """الحصول على بيانات لوحة التحكم"""
        # البيانات الأساسية
        companies = Company.objects.filter(user=request.user)
        quotes = HealthInsuranceQuote.objects.filter(user=request.user)
        policies = HealthInsurancePolicy.objects.filter(user=request.user)
        
        # الاقتباسات الأخيرة
        recent_quotes = HealthInsuranceQuoteSerializer(
            quotes.order_by('-created_at')[:5], 
            many=True
        ).data
        
        # السياسات النشطة
        active_policies = HealthInsurancePolicySerializer(
            policies.filter(status='active').order_by('-created_at')[:5],
            many=True
        ).data
        
        # الإحصائيات السريعة
        quick_stats = {
            'companies_count': companies.count(),
            'total_employees': companies.aggregate(Sum('total_employees'))['total_employees__sum'] or 0,
            'quotes_count': quotes.count(),
            'active_quotes': quotes.filter(status='quoted').count(),
            'policies_count': policies.count(),
            'active_policies': policies.filter(status='active').count(),
            'total_premium': float(policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
            'monthly_payment': float(
                policies.filter(status='active').aggregate(Sum('monthly_premium'))['monthly_premium__sum'] or 0
            )
        }
        
        # التحذيرات والإشعارات
        warnings = []
        expiring_policies = policies.filter(status='active', expiry_date__lte=datetime.now().date() + timedelta(days=30))
        if expiring_policies.exists():
            warnings.append({
                'type': 'warning',
                'message': f'لديك {expiring_policies.count()} وثيقة على وشك الانتهاء',
                'items': HealthInsurancePolicySimpleSerializer(expiring_policies, many=True).data
            })
        
        pending_quotes = quotes.filter(status='quoted')
        if pending_quotes.exists():
            warnings.append({
                'type': 'info',
                'message': f'لديك {pending_quotes.count()} اقتباس بانتظار القرار',
                'items': HealthInsuranceQuoteSerializer(pending_quotes[:3], many=True).data
            })
        
        # النشاط الأخير
        recent_activity = []
        recent_calculations = HealthCalculationLog.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5]
        
        for calc in recent_calculations:
            recent_activity.append({
                'type': 'calculation',
                'message': f'حساب قسط لقطاع {calc.company_sector}',
                'details': f'{calc.employee_count} موظف، القسط: {calc.calculated_premium} ريال',
                'timestamp': calc.created_at,
                'premium': float(calc.calculated_premium)
            })
        
        # توزيع القطاعات
        sector_distribution = list(companies.values('sector').annotate(
            count=Count('id'),
            total_employees=Sum('total_employees')
        ))
        
        return Response({
            'user': {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email
            },
            'quick_stats': quick_stats,
            'sector_distribution': sector_distribution,
            'recent_quotes': recent_quotes,
            'active_policies': active_policies,
            'warnings': warnings,
            'recent_activity': recent_activity,
            'next_actions': [
                {'label': 'إنشاء شركة جديدة', 'url': '/api/companies/', 'method': 'POST'},
                {'label': 'احتساب قسط جديد', 'url': '/api/health-premium/calculate/', 'method': 'POST'},
                {'label': 'مشاهدة خطط التغطية', 'url': '/api/health-coverage-plans/', 'method': 'GET'},
                {'label': 'تحميل تقرير', 'url': '/api/health-insurance/reports/?type=summary', 'method': 'GET'}
            ]
        })

# ============= Health Calculation Log Views =============
class HealthCalculationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """واجهة سجل حسابات التأمين الصحي"""
    permission_classes = [IsAuthenticated]
    serializer_class = HealthCalculationLogSerializer
    
    def get_queryset(self):
        return HealthCalculationLog.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """إحصائيات الحسابات"""
        calculations = self.get_queryset()
        
        stats = {
            'total_calculations': calculations.count(),
            'first_calculation': calculations.last().created_at if calculations.exists() else None,
            'last_calculation': calculations.first().created_at if calculations.exists() else None,
            'company_sectors': list(calculations.values('company_sector').annotate(
                count=Count('id'),
                avg_premium=Avg('calculated_premium')
            )),
            'premium_range': {
                'min': float(calculations.aggregate(Min('calculated_premium'))['calculated_premium__min'] or 0),
                'max': float(calculations.aggregate(Max('calculated_premium'))['calculated_premium__max'] or 0),
                'average': float(calculations.aggregate(Avg('calculated_premium'))['calculated_premium__avg'] or 0)
            },
            'recent_activity': list(calculations.values('created_at__date').annotate(
                count=Count('id')
            ).order_by('-created_at__date')[:7])
        }
        
        return Response(stats)

# ============= Health Insurance Reports View =============
class HealthInsuranceReportsView(APIView):
    """تقارير التأمين الصحي"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """الحصول على التقارير"""
        report_type = request.query_params.get('type', 'summary')
        
        if report_type == 'summary':
            return self._get_summary_report(request)
        elif report_type == 'company':
            return self._get_company_report(request)
        elif report_type == 'premium':
            return self._get_premium_report(request)
        else:
            return Response(
                {'error': 'نوع التقرير غير معروف'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _get_summary_report(self, request):
        """تقرير ملخص"""
        # إحصائيات المستخدم
        companies = Company.objects.filter(user=request.user)
        quotes = HealthInsuranceQuote.objects.filter(user=request.user)
        policies = HealthInsurancePolicy.objects.filter(user=request.user)
        
        report = {
            'user': {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email
            },
            'companies': {
                'total': companies.count(),
                'by_sector': list(companies.values('sector').annotate(
                    count=Count('id'),
                    total_employees=Sum('total_employees')
                ))
            },
            'quotes': {
                'total': quotes.count(),
                'by_status': list(quotes.values('status').annotate(
                    count=Count('id'),
                    total_premium=Sum('total_premium')
                )),
                'total_premium': float(quotes.aggregate(Sum('total_premium'))['total_premium__sum'] or 0)
            },
            'policies': {
                'total': policies.count(),
                'by_status': list(policies.values('status').annotate(
                    count=Count('id'),
                    total_premium=Sum('total_premium')
                )),
                'active_policies': policies.filter(status='active').count(),
                'total_premium': float(policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0)
            },
            'calculations': {
                'total': HealthCalculationLog.objects.filter(user=request.user).count(),
                'average_premium': float(
                    HealthCalculationLog.objects.filter(user=request.user).aggregate(
                        Avg('calculated_premium')
                    )['calculated_premium__avg'] or 0
                )
            },
            'generated_at': datetime.now().isoformat()
        }
        
        return Response(report)
    
    def _get_company_report(self, request):
        """تقرير الشركات"""
        companies = Company.objects.filter(user=request.user)
        
        report = {
            'companies': CompanySerializer(companies, many=True).data,
            'total_employees': companies.aggregate(Sum('total_employees'))['total_employees__sum'] or 0,
            'average_employees': companies.aggregate(Avg('total_employees'))['total_employees__avg'] or 0,
            'sectors': list(companies.values('sector').annotate(
                count=Count('id'),
                avg_employees=Avg('total_employees'),
                avg_age=Avg('establishment_age')
            ))
        }
        
        return Response(report)
    
    def _get_premium_report(self, request):
        """تقرير الأقساط"""
        quotes = HealthInsuranceQuote.objects.filter(user=request.user)
        policies = HealthInsurancePolicy.objects.filter(user=request.user)
        
        # تحليل الأقساط
        premium_analysis = {
            'quotes': {
                'total': float(quotes.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
                'average': float(quotes.aggregate(Avg('total_premium'))['total_premium__avg'] or 0),
                'min': float(quotes.aggregate(Min('total_premium'))['total_premium__min'] or 0),
                'max': float(quotes.aggregate(Max('total_premium'))['total_premium__max'] or 0),
                'by_month': self._get_premium_by_month(quotes, 'created_at', 'total_premium')
            },
            'policies': {
                'total': float(policies.aggregate(Sum('total_premium'))['total_premium__sum'] or 0),
                'average': float(policies.aggregate(Avg('total_premium'))['total_premium__avg'] or 0),
                'min': float(policies.aggregate(Min('total_premium'))['total_premium__min'] or 0),
                'max': float(policies.aggregate(Max('total_premium'))['total_premium__max'] or 0),
                'by_month': self._get_premium_by_month(policies, 'created_at', 'total_premium')
            }
        }
        
        return Response(premium_analysis)
    
    def _get_premium_by_month(self, queryset, date_field, amount_field):
        """الحصول على الأقساط حسب الشهر"""
        from django.db.models.functions import TruncMonth
        
        monthly_data = queryset.annotate(
            month=TruncMonth(date_field)
        ).values('month').annotate(
            count=Count('id'),
            total=Sum(amount_field),
            average=Avg(amount_field)
        ).order_by('month')
        
        return list(monthly_data)

# ============= API Views مساعدة =============
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sectors_data(request):
    """الحصول على بيانات القطاعات"""
    from .models import Company
    
    # مجموعات القطاعات
    groups = {}
    for value, _ in Company.SECTOR_CHOICES:
        if '_' in value:
            group = value.split('_')[0]
            if group not in groups:
                # تسمية المجموعات
                group_labels = {
                    'health': 'قطاع صحي',
                    'tech': 'قطاع تكنولوجيا',
                    'construction': 'قطاع مقاولات',
                    'retail': 'قطاع تجارة',
                    'services': 'قطاع خدمات'
                }
                groups[group] = group_labels.get(group, 'أخرى')
    
    # جميع القطاعات
    sectors = []
    for value, label in Company.SECTOR_CHOICES:
        group = value.split('_')[0]
        sectors.append({
            'value': value,
            'label': label,
            'group': group,
            'description': _get_sector_description(value)
        })
    
    # الحقول الخاصة بكل قطاع
    sector_fields = {}
    for sector in Company.SECTOR_SPECIFIC_FIELDS:
        sector_fields[sector] = Company.SECTOR_SPECIFIC_FIELDS[sector]
    
    return Response({
        'success': True,
        'groups': groups,
        'sectors': sectors,
        'total_sectors': len(sectors)
    })

def _get_sector_description(sector):
    """الحصول على وصف القطاع (دالة مساعدة)"""
    descriptions = {
        'health_hospital': 'مؤسسة طبية توفر رعاية صحية شاملة ومتخصصة',
        'tech_software': 'شركة متخصصة في تطوير البرمجيات والحلول التقنية',
        'construction_civil': 'شركة مقاولات تنفذ مشاريع إنشائية وبنية تحتية',
        'security_guarding': 'شركة توفر خدمات حراسة أمنية وحماية للمنشآت',
        'retail_store': 'متجر يبيع منتجات للمستهلكين مباشرة',
        'education_school': 'مؤسسة تعليمية تقدم التعليم النظامي',
        'manufacturing_food': 'مصنع ينتج مواد غذائية ومعالجة',
        'services_logistics': 'شركة متخصصة في الشحن والتوزيع واللوجستيات',
    }
    return descriptions.get(sector, 'شركة في هذا القطاع')

def normalize_insurance_data(data):
    """
    تطبيع بيانات التأمين للتعامل مع تنسيقات مختلفة
    """
    normalized = data.copy()
    
    # تحويل keys من camelCase إلى snake_case والعكس
    key_mappings = {
        # Frontend → Backend
        'insuranceType': 'insurance_type',
        'company': 'company_id',
        'familyMembers': 'family_members',
        'coverageOptions': 'coverage_options',
        'paymentMethod': 'payment_method',
        
        # Backend → Frontend (للتوافق)
        'insurance_type': 'insuranceType',
        'company_id': 'company',
        'family_members': 'familyMembers',
        'coverage_options': 'coverageOptions',
        'payment_method': 'paymentMethod'
    }
    
    # تطبيق التحويلات
    for old_key, new_key in key_mappings.items():
        if old_key in normalized:
            normalized[new_key] = normalized.pop(old_key)
    
    # تنسيق family_members إذا كانت familyMembers
    if 'family_members' in normalized and isinstance(normalized['family_members'], dict):
        # التأكد من وجود جميع الحقول
        family = normalized['family_members']
        family.setdefault('spouses', 0)
        family.setdefault('children', 0)
        family.setdefault('parents', 0)
    
    # تنسيق coverage_options
    if 'coverage_options' in normalized and isinstance(normalized['coverage_options'], dict):
        coverage = normalized['coverage_options']
        # تحويل boolean إلى string إذا لزم الأمر
        for key in coverage:
            if isinstance(coverage[key], bool):
                coverage[key] = 'نعم' if coverage[key] else 'لا'
    
    return normalized

def generate_quote_number_uuid():
    """إنشاء رقم اقتباس فريد باستخدام UUID"""
    timestamp = datetime.now().strftime('%Y%m%d')
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"HQ-{timestamp}-{unique_id}"


class AdvancedPremiumCalculationView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            print("📥 استقبال طلب حساب متقدم...")
            print("📋 البيانات الخام:", request.data)
            
            # 🔧 استخراج البيانات
            data = request.data

            # التحقق من الحقول المطلوبة
            if 'company_id' not in data or 'insurance_type' not in data:
                return Response({
                    'success': False,
                    'error': 'بيانات غير مكتملة. company_id و insurance_type مطلوبان'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            company_id = data['company_id']
            insurance_type = data['insurance_type']
            
            # 🔧 الحصول على الشركة - MUST BE HERE!
            try:
                company = Company.objects.get(id=company_id, user=request.user)
                print(f"✅ تم العثور على الشركة: {company.name}")
            except Company.DoesNotExist:
                print(f"❌ الشركة غير موجودة: {company_id}")
                return Response({
                    'success': False,
                    'error': 'الشركة غير موجودة أو لا تملك صلاحية الوصول إليها'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 🔧 استخراج بيانات الحساب
            coverage_options = data.get('coverage_options', {})
            payment_method = data.get('payment_method', 'annual')
            family_members = data.get('family_members', {})
            calculation_data = data.get('calculation_data', {})
            employees_data = data.get('employees', [])
            
            # 🔧 التحقق من وجود بيانات الحساب الأساسية
            if not calculation_data or 'total_premium' not in calculation_data:
                return Response({
                    'success': False,
                    'error': 'بيانات الحساب غير مكتملة. يرجى إعادة الحساب في Frontend'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            total_premium = calculation_data.get('total_premium', 0)
            base_premium = calculation_data.get('base_premium', 0)
            monthly_premium = total_premium / 12 if total_premium > 0 else 0
            
            # 🔧 إنشاء رقم الاقتباس
            quote_number = generate_quote_number_uuid()
            print(f"✅ رقم الاقتباس المُولد: {quote_number}")
            
            # 🔧 إعداد تفاصيل التغطية
            coverage_details = {
                'insurance_type': insurance_type,
                'coverage_options': coverage_options,
                'payment_method': payment_method,
                'insurance_type_data': {
                    'A': {'name': 'التغطية الشاملة', 'base_rate': 1500},
                    'B': {'name': 'التغطية القياسية', 'base_rate': 1000},
                    'C': {'name': 'التغطية الأساسية', 'base_rate': 1200}
                }.get(insurance_type, {}),
                'family_members': family_members,
                'employees_count': len(employees_data),
                'calculation_summary': {
                    'total_employees': len(employees_data),
                    'total_family': family_members.get('spouses', 0) + 
                                    family_members.get('children', 0) + 
                                    family_members.get('parents', 0),
                    'payment_method': payment_method,
                    'calculated_at': timezone.now().isoformat()
                }
            }
            
            # 🔧 إنشاء الاقتباس - NOW company IS DEFINED!
            quote = HealthInsuranceQuote.objects.create(
                quote_number=quote_number,
                company=company,  # ✅ Now company is defined!
                user=request.user,
                insurance_type=insurance_type,
                insured_employees_count=len(employees_data),
                coverage_period=365,
                base_premium=Decimal(str(base_premium)),
                total_premium=Decimal(str(total_premium)),
                annual_premium=Decimal(str(total_premium)),
                monthly_premium=Decimal(str(monthly_premium)),
                calculation_data=calculation_data,
                coverage_details=coverage_details,
                status='pending',
                valid_until=timezone.now() + timedelta(days=30),
                notes=json.dumps({
                    'source': 'advanced_calculator_frontend',
                    'created_at': timezone.now().isoformat(),
                    'insurance_type': insurance_type,
                    'payment_method': payment_method,
                    'total_employees': len(employees_data),
                    'family_members': family_members,
                    'coverage_options': coverage_options,
                    'message': 'تم الحساب بالكامل في Frontend بواسطة الآلة الحاسبة المتقدمة'
                }, ensure_ascii=False)
            )
            
            print(f"🎉 تم إنشاء اقتباس: {quote.quote_number}")
            print(f"📊 تفاصيل الاقتباس:")
            print(f"   - الشركة: {company.name}")
            print(f"   - نوع التأمين: {insurance_type}")
            print(f"   - عدد الموظفين: {len(employees_data)}")
            print(f"   - القسط السنوي: ${total_premium}")
            print(f"   - القسط الشهري: ${monthly_premium}")
            print(f"   - أفراد العائلة: {family_members}")
            
            return Response({
                'success': True,
                'message': 'تم إنشاء عرض السعر بنجاح',
                'quote_id': quote.id,
                'quote_number': quote.quote_number,
                'quote_details': {
                    'company': company.name,
                    'company_id': company.id,
                    'insurance_type': insurance_type,
                    'insurance_type_name': self.get_insurance_type_name(insurance_type),
                    'total_employees': len(employees_data),
                    'annual_premium': float(quote.annual_premium),
                    'monthly_premium': float(quote.monthly_premium),
                    'status': quote.status,
                    'valid_until': quote.valid_until.isoformat(),
                    'calculated_in_frontend': True,
                    'family_members': family_members,
                    'coverage_options': coverage_options
                },
                'premium_breakdown': calculation_data,
                'family_members': family_members,
                'coverage_options': coverage_options,
                'next_steps': [
                    'مراجعة تفاصيل الاقتباس',
                    'قبول الاقتباس لإنشاء وثيقة',
                    'الاتصال بالدعم لأي استفسارات'
                ]
            }, status=status.HTTP_201_CREATED)
            
        except KeyError as e:
            print(f"❌ خطأ في بيانات الإدخال: {str(e)}")
            return Response({
                'success': False,
                'error': f'بيانات غير مكتملة: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print(f"❌ خطأ في الحساب المتقدم: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return Response({
                'success': False,
                'error': f'خطأ في الحساب: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_insurance_type_name(self, insurance_type):
        """الحصول على اسم نوع التأمين بالعربية"""
        names = {
            'A': 'التغطية الشاملة',
            'B': 'التغطية القياسية',
            'C': 'التغطية الأساسية'
        }
        return names.get(insurance_type, f'النوع {insurance_type}')


class DownloadInsuranceGuidePDF(APIView):
    """
    تنزيل دليل الاختيار PDF
    """
    def get(self, request):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from io import BytesIO
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import arabic_reshaper
            from bidi.algorithm import get_display
            
            # إنشاء buffer للـ PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
            
            # المحتوى
            elements = []
            styles = getSampleStyleSheet()
            
            # العنوان
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                alignment=1,  # center
                spaceAfter=30,
                textColor=colors.HexColor('#2c3e50')
            )
            
            elements.append(Paragraph("دليل اختيار نوع التأمين الطبي", title_style))
            elements.append(Spacer(1, 20))
            
            # جدول المقارنة
            data = [
                ['المعيار', 'النوع A (شامل)', 'النوع B (اقتصادي)', 'النوع C (أساسي)'],
                ['المشمولين', 'موظفون + عائلة', 'موظفون فقط', 'موظفون + عائلة'],
                ['نسبة التحمل (داخل)', '10%', '20%', '15%'],
                ['الحد السنوي الداخلي', '$10,000', '$8,000', '$6,000'],
                ['الحد السنوي الخارجي', '$2,000', '$1,500', '$1,000'],
                ['الحد العمري', '0-65 سنة', '18-65 سنة', '0-65 سنة'],
                ['التكلفة المتوقعة', 'مرتفعة', 'اقتصادية', 'متوسطة']
            ]
            
            table = Table(data, colWidths=[doc.width/4.0]*4)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 12),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 30))
            
            # بناء الـ PDF
            doc.build(elements)
            
            buffer.seek(0)
            
            # إرجاع الـ PDF
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="insurance_guide.pdf"'
            return response
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
        
def download_enhanced_excel_template(request):
        """
        تنزيل قالب Excel محسن
        """
        from django.http import HttpResponse
        import pandas as pd
        from io import BytesIO
        
        try:
            # إنشاء DataFrame للقالب
            data = {
                'الاسم الكامل': ['محمد أحمد', 'أحمد محمد'],
                'تاريخ الميلاد': ['1990-05-15', '1985-10-20'],
                'الجنس': ['ذكر', 'ذكر'],
                'الراتب': [5000, 6000],
                'الحالة الاجتماعية': ['متزوج', 'أعزب'],
                'عدد الأبناء': [2, 0],
                'يشمل الوالدين': ['نعم', 'لا'],
                'الوظيفة': ['مدير', 'مطور'],
                'البريد الإلكتروني': ['mohamed@example.com', 'ahmed@example.com'],
                'رقم الهاتف': ['771234567', '775432100']
            }
            
            df = pd.DataFrame(data)
            
            # إنشاء Excel في الذاكرة
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='الموظفين')
                
                # إضافة ورقة للإرشادات
                instructions = pd.DataFrame({
                    'التعليمات': [
                        '1. املأ جميع الحقول بدقة',
                        '2. تأكد من صحة تاريخ الميلاد (YYYY-MM-DD)',
                        '3. أرقام الهواتف يجب أن تكون 9 أرقام',
                        '4. الراتب بالأرقام فقط',
                        '5. عدد الأبناء: أدخل الرقم فقط',
                        '6. يشمل الوالدين: اكتب "نعم" أو "لا"',
                        '7. لا تحذف أي عمود من الأعمدة'
                    ]
                })
                instructions.to_excel(writer, index=False, sheet_name='التعليمات')
            
            output.seek(0)
            
            # إرجاع الملف
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="قالب_بيانات_الموظفين_المحسن.xlsx"'
            
            return response
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class AdminViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """إحصائيات عامة للمسؤول"""
        from django.db.models import Count, Sum, Avg
        from django.contrib.auth.models import User
        from datetime import datetime, timedelta
        
        # الإحصائيات
        stats = {
            'users': {
                'total': CustomUser.objects.count(),
                'active_today': CustomUser.objects.filter(
                    last_login__date=datetime.today()
                ).count(),
                'by_type': dict(CustomUser.objects.values_list('user_type')
                              .annotate(count=Count('id')).order_by('-count')),
            },
            'policies': {
                'total': CarPolicy.objects.count() + HealthInsurancePolicy.objects.count(),
                'active': CarPolicy.objects.filter(status='active').count() + 
                         HealthInsurancePolicy.objects.filter(status='active').count(),
                'revenue': {
                    'car': CarPolicy.objects.filter(status='active')
                           .aggregate(Sum('total_premium'))['total_premium__sum'] or 0,
                    'health': HealthInsurancePolicy.objects.filter(status='active')
                             .aggregate(Sum('total_premium'))['total_premium__sum'] or 0,
                }
            },
            'quotes': {
                'pending': CarInsuranceQuote.objects.filter(status='pending').count() +
                          HealthInsuranceQuote.objects.filter(status='pending').count(),
                'converted': CarInsuranceQuote.objects.filter(status='accepted').count() +
                            HealthInsuranceQuote.objects.filter(status='accepted').count(),
            },
            'recent_activities': self.get_recent_activities()
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def users_list(self, request):
        """قائمة المستخدمين للمسؤول"""
        users = CustomUser.objects.all().order_by('-date_joined')
        serializer = UserProfileSerializer(users, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def system_logs(self, request):
        """سجلات النظام"""
        import logging
        from django.core.paginator import Paginator
        
        # قراءة سجلات النظام
        logs = []
        try:
            with open('logs/system.log', 'r') as f:
                logs = f.readlines()[-100:]  # آخر 100 سطر
        except:
            logs = ["لا توجد سجلات متاحة"]
        
        return Response({'logs': logs})

        