# health_insurance/serializers.py
from rest_framework import serializers
from .models import (
    Company,  # تغيير من HealthEstablishment
    HealthCoveragePlan, 
    HealthInsuranceQuote, 
    HealthInsurancePolicy,
    HealthCalculationLog,
    SectorPricingFactor
)
from users.serializers import UserProfileSerializer
from datetime import date
from django.conf import settings


# ============= Company Serializers (بدلاً من HealthEstablishment) =============
class CompanySerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    sector_display = serializers.CharField(source='get_sector_display', read_only=True)
    size_category_display = serializers.CharField(source='get_size_category_display', read_only=True)
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    work_environment_display = serializers.CharField(source='get_work_environment_display', read_only=True)
    quotes_count = serializers.SerializerMethodField()
    policies_count = serializers.SerializerMethodField()
    is_healthcare_sector = serializers.SerializerMethodField()
    is_high_risk_sector = serializers.SerializerMethodField()
    sector_group = serializers.SerializerMethodField()
    employees_data = serializers.JSONField(read_only=True)
    
    # ✅ إضافة حقل employees_file للقراءة والكتابة
    employees_file = serializers.FileField(
        required=False,
        allow_null=True,
        write_only=True  # للكتابة فقط، ليس للقراءة
    )
    class Meta:
        model = Company
        fields = [
            'id', 'user', 'name', 'sector', 'sector_display', 'sector_group',
            'sub_sector', 'size_category', 'size_category_display',
            'cr_number', 'tax_number', 'address', 'city', 'country',
            'phone', 'email', 'website', 'total_employees', 'male_employees',
            'female_employees', 'insured_employees', 'establishment_age',
            'risk_level', 'risk_level_display', 'work_environment', 'work_environment_display',
            'annual_revenue', 'has_previous_insurance', 'previous_insurance_years',
            'claims_history', 'sector_data', 'founded_date',
            'quotes_count', 'policies_count',
            'is_healthcare_sector', 'is_high_risk_sector',
            'created_at', 'updated_at', 'employees_data',
            'employees_file'  # تضمين حقل employees_file هنا
        ]
        read_only_fields = ('id', 'user', 'created_at', 'updated_at', 'employees_data')
    
    def get_quotes_count(self, obj):
        return obj.quotes.count()
    
    def get_policies_count(self, obj):
        return HealthInsurancePolicy.objects.filter(company=obj).count()
    
    def get_sector_group(self, obj):
        # Simple sector grouping
        if obj.sector.startswith('health_'):
            return 'صحي'
        elif obj.sector.startswith('tech_'):
            return 'تكنولوجيا'
        elif obj.sector.startswith('construction_'):
            return 'مقاولات'
        elif obj.sector.startswith('manufacturing_'):
            return 'صناعة'
        elif obj.sector.startswith('services_'):
            return 'خدمات'
        else:
            return 'أخرى'
        
    def get_is_healthcare_sector(self, obj):
        """هل القطاع صحي؟"""
        return obj.sector.startswith('health_')
    
    def get_is_high_risk_sector(self, obj):
        """هل القطاع عالي المخاطر؟"""
        high_risk_sectors = [
            'construction_civil',
            'construction_electrical',
            'construction_mechanical',
            'construction_roads',
            'health_hospital',
            'services_transport',
            'services_logistics'
        ]
        return obj.sector in high_risk_sectors
    
    def validate_cr_number(self, value):
        """التحقق من رقم السجل التجاري"""
        if len(value) < 5:
            raise serializers.ValidationError("رقم السجل التجاري يجب أن يكون 5 أحرف على الأقل")
        return value
    
    def validate_total_employees(self, value):
        """التحقق من عدد الموظفين"""
        if value < 1:
            raise serializers.ValidationError("عدد الموظفين يجب أن يكون 1 على الأقل")
        if value > 10000:
            raise serializers.ValidationError("عدد الموظفين لا يمكن أن يتجاوز 10000")
        return value

class CompanyCreateSerializer(serializers.ModelSerializer):
    """سيريالايزر لإنشاء شركة جديدة"""
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'sector', 'sub_sector', 'size_category',
            'cr_number', 'tax_number', 'address', 'city', 'country',
            'phone', 'email', 'website', 'total_employees', 'male_employees',
            'female_employees', 'establishment_age', 'work_environment',
            'risk_level', 'annual_revenue', 'has_previous_insurance',
            'previous_insurance_years', 'claims_history', 'sector_data',
            'founded_date', 'employees_data'
        ]
        read_only_fields = ('id',)

    def validate_name(self, value):
        """التحقق من أن اسم الشركة فريد للمستخدم"""
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            return value
        
        # تنظيف الاسم
        name = value.strip()
        
        # التحقق من أن الاسم ليس فارغاً
        if not name:
            raise serializers.ValidationError("اسم الشركة لا يمكن أن يكون فارغاً")
        
        # التحقق من الطول
        if len(name) < 2:
            raise serializers.ValidationError("اسم الشركة يجب أن يكون على الأقل حرفين")
        
        if len(name) > 200:
            raise serializers.ValidationError("اسم الشركة لا يمكن أن يتجاوز 200 حرف")
        
        # التحقق من التكرار (تجاهل الحالة الحالية إذا كانت في التحديث)
        instance = self.instance
        if instance:
            # في حالة التحديث، تحقق من الشركات الأخرى غير هذه الشركة
            existing_companies = Company.objects.filter(
                user=user,
                name=name
            ).exclude(id=instance.id)
        else:
            # في حالة الإنشاء، تحقق من جميع الشركات
            existing_companies = Company.objects.filter(
                user=user,
                name=name
            )
        
        if existing_companies.exists():
            raise serializers.ValidationError(f"لديك بالفعل شركة باسم '{name}'. الرجاء اختيار اسم آخر")
        
        return name
    
    def validate_cr_number(self, value):
        """التحقق من رقم السجل التجاري"""
        cr_number = value.strip()
        
        # التحقق من الطول
        if len(cr_number) < 5:
            raise serializers.ValidationError("رقم السجل التجاري يجب أن يكون 5 أحرف على الأقل")
        
        if len(cr_number) > 50:
            raise serializers.ValidationError("رقم السجل التجاري لا يمكن أن يتجاوز 50 حرفاً")
        
        # التحقق من التكرار عالمياً
        instance = self.instance
        if instance:
            # في حالة التحديث
            existing = Company.objects.filter(
                cr_number=cr_number
            ).exclude(id=instance.id)
        else:
            # في حالة الإنشاء
            existing = Company.objects.filter(cr_number=cr_number)
        
        if existing.exists():
            raise serializers.ValidationError("رقم السجل التجاري هذا مسجل مسبقاً")
        
        return cr_number
    
    def validate(self, data):
        """التحقق الإضافي"""
        # التحقق من صحة البريد الإلكتروني
        email = data.get('email')
        if email:
            # تحقق بسيط من صيغة البريد
            if '@' not in email or '.' not in email:
                raise serializers.ValidationError({
                    'email': 'صيغة البريد الإلكتروني غير صحيحة'
                })
        
        # التحقق من رقم الهاتف
        phone = data.get('phone')
        if phone:
            # تنظيف رقم الهاتف
            clean_phone = ''.join(filter(str.isdigit, str(phone)))
            if len(clean_phone) < 7:
                raise serializers.ValidationError({
                    'phone': 'رقم الهاتف غير صالح'
                })
            data['phone'] = clean_phone
        
        return data
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    # def validate(self, data):
    #     """التحقق الإضافي"""
    #     # تحقق من أن عدد الذكور + الإناث = العدد الكلي
    #     total = data.get('total_employees', 0)
    #     male = data.get('male_employees', 0)
    #     female = data.get('female_employees', 0)
        
    #     if male + female > total:
    #         raise serializers.ValidationError({
    #             'male_employees': 'مجموع الموظفين الذكور والإناث لا يمكن أن يتجاوز العدد الكلي',
    #             'female_employees': 'مجموع الموظفين الذكور والإناث لا يمكن أن يتجاوز العدد الكلي'
    #         })
        
    #     # تحقق من بيانات القطاع إذا كانت موجودة
    #     sector = data.get('sector')
    #     sector_data = data.get('sector_data', {})
        
    #     if sector in Company.SECTOR_SPECIFIC_FIELDS:
    #         required_fields = Company.SECTOR_SPECIFIC_FIELDS[sector].get('required', [])
    #         for field in required_fields:
    #             if field not in sector_data or not sector_data[field]:
    #                 label = Company.SECTOR_SPECIFIC_FIELDS[sector]['labels'].get(field, field)
    #                 raise serializers.ValidationError({
    #                     'sector_data': f'حقل {label} مطلوب لهذا القطاع'
    #                 })
        
    #     return data
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

# ============= Health Coverage Plan Serializers =============
class HealthCoveragePlanSerializer(serializers.ModelSerializer):
    plan_type_display = serializers.CharField(source='get_plan_type_display', read_only=True)
    applicable_to_display = serializers.CharField(source='get_applicable_to_display', read_only=True)
    features_summary = serializers.SerializerMethodField()
    estimated_price_range = serializers.SerializerMethodField()
    sector_factors_display = serializers.SerializerMethodField()
    
    class Meta:
        model = HealthCoveragePlan
        fields = [
            'id', 'name', 'plan_type', 'plan_type_display', 'description',
            'applicable_to', 'applicable_to_display', 'custom_sectors',
            'outpatient_limit', 'inpatient_limit', 'dental_limit', 'optical_limit',
            'emergency_limit', 'work_accident_limit', 'occupational_disease_limit',
            'outpatient_coverage', 'inpatient_coverage', 'dental_coverage',
            'optical_coverage', 'work_accident_coverage',
            'base_price_per_employee', 'min_employees', 'max_employees',
            'sector_factors', 'sector_factors_display',
            'includes_preventive_care', 'includes_chronic_medication',
            'includes_work_accidents', 'includes_occupational_diseases',
            'is_active', 'features_summary', 'estimated_price_range',
            'created_at'
        ]
    
    def get_features_summary(self, obj):
        """ملخص مميزات الخطة"""
        features = []
        if obj.includes_preventive_care:
            features.append("الرعاية الوقائية")
        if obj.includes_chronic_medication:
            features.append("الأدوية المزمنة")
        if obj.includes_work_accidents:
            features.append("إصابات العمل")
        if obj.includes_occupational_diseases:
            features.append("الأمراض المهنية")
        return features
    
    def get_estimated_price_range(self, obj):
        """تقدير نطاق السعر"""
        return {
            'min': float(obj.base_price_per_employee * obj.min_employees),
            'max': float(obj.base_price_per_employee * obj.max_employees),
            'per_employee': float(obj.base_price_per_employee)
        }
    
    def get_sector_factors_display(self, obj):
        """عرض معاملات القطاعات بشكل مقروء"""
        if obj.sector_factors:
            display = []
            for sector, factor in obj.sector_factors.items():
                sector_display = dict(Company.SECTOR_CHOICES).get(sector, sector)
                display.append(f"{sector_display}: {factor}x")
            return display
        return []

class HealthCoveragePlanSimpleSerializer(serializers.ModelSerializer):
    """سيريالايزر مبسط لخطة التغطية"""
    plan_type_display = serializers.CharField(source='get_plan_type_display', read_only=True)
    
    class Meta:
        model = HealthCoveragePlan
        fields = ['id', 'name', 'plan_type', 'plan_type_display', 'base_price_per_employee']

# ============= Health Insurance Quote Serializers =============
class HealthInsuranceQuoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthInsuranceQuote
        fields = [
            'quote_number', 'company', 'coverage_plan', 
            'insured_employees_count', 'coverage_period',
            'base_premium', 'total_premium', 'annual_premium',
            'monthly_premium', 'status', 'valid_until', 'notes'
        ]
    
    def create(self, validated_data):
        # إضافة المستخدم الحالي
        validated_data['user'] = self.context['request'].user
        
        # تحويل القيم العشرية
        for field in ['base_premium', 'total_premium', 'annual_premium', 'monthly_premium']:
            if field in validated_data and isinstance(validated_data[field], float):
                validated_data[field] = Decimal(str(validated_data[field]))
        
        return super().create(validated_data)


class HealthInsuranceQuoteSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    insurance_type_name = serializers.SerializerMethodField()  # ✅
    calculated_in_frontend = serializers.SerializerMethodField()  # ✅
    coverage_details = serializers.JSONField(read_only=True)  # ✅
    calculation_data = serializers.JSONField(read_only=True)  # ✅
    
    class Meta:
        model = HealthInsuranceQuote
        fields = [
            'id', 'quote_number', 'company', 'company_name',
            'coverage_plan', 'insurance_type', 'insurance_type_name',  # ✅
            'insured_employees_count', 'coverage_period',
            'base_premium', 'total_premium', 'annual_premium',
            'monthly_premium', 'status', 'valid_until', 'notes',
            'calculation_data', 'coverage_details',  # ✅
            'calculated_in_frontend',  # ✅
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_insurance_type_name(self, obj):
        names = {
            'A': 'التغطية الشاملة',
            'B': 'التغطية القياسية',
            'C': 'التغطية الأساسية'
        }
        return names.get(obj.insurance_type, f'النوع {obj.insurance_type}')
    
    def get_calculated_in_frontend(self, obj):
        return obj.calculation_data is not None and len(obj.calculation_data) > 0

class HealthInsuranceQuoteCreateSerializer(serializers.ModelSerializer):
    """سيريالايزر لإنشاء اقتباس جديد"""
    coverage_plan_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = HealthInsuranceQuote
        fields = [
            'company', 'coverage_plan_id', 'insured_employees_count',
            'insured_dependents_count', 'coverage_period', 'notes'
        ]
    
    def validate(self, data):
        """التحقق من صحة البيانات"""
        company = data.get('company')
        coverage_plan_id = data.get('coverage_plan_id')
        insured_count = data.get('insured_employees_count', 1)
        
        # التحقق من أن الشركة تابعة للمستخدم
        request = self.context.get('request')
        if request and company.user != request.user:
            raise serializers.ValidationError("هذه الشركة لا تنتمي إليك")
        
        # التحقق من خطة التغطية
        try:
            coverage_plan = HealthCoveragePlan.objects.get(id=coverage_plan_id, is_active=True)
        except HealthCoveragePlan.DoesNotExist:
            raise serializers.ValidationError("خطة التغطية غير موجودة أو غير نشطة")
        
        # التحقق من أن الخطة تنطبق على القطاع
        if not coverage_plan.is_applicable_to_company(company):
            raise serializers.ValidationError("هذه الخطة غير متاحة لقطاع شركتك")
        
        # التحقق من عدد الموظفين
        if insured_count < 1:
            raise serializers.ValidationError("عدد الموظفين يجب أن يكون 1 على الأقل")
        
        if insured_count > company.total_employees:
            raise serializers.ValidationError("عدد الموظفين المؤمن عليهم لا يمكن أن يتجاوز العدد الكلي")
        
        if insured_count < coverage_plan.min_employees:
            raise serializers.ValidationError(f"الحد الأدنى للموظفين لهذه الخطة هو {coverage_plan.min_employees}")
        
        if insured_count > coverage_plan.max_employees:
            raise serializers.ValidationError(f"الحد الأقصى للموظفين لهذه الخطة هو {coverage_plan.max_employees}")
        
        return data
    
    def create(self, validated_data):
        """إنشاء اقتباس جديد مع احتساب القسط"""
        request = self.context.get('request')
        coverage_plan_id = validated_data.pop('coverage_plan_id')
        
        # الحصول على خطة التغطية
        coverage_plan = HealthCoveragePlan.objects.get(id=coverage_plan_id)
        
        # احتساب القسط (سيتم تحديثه لاحقاً عند رفع ملف الموظفين)
        from .calculations import calculate_health_premium
        premium_result = calculate_health_premium(
            company=validated_data['company'],
            coverage_plan=coverage_plan,
            insured_count=validated_data['insured_employees_count']
        )
        
        # إنشاء الاقتباس
        quote = HealthInsuranceQuote.objects.create(
            user=request.user,
            coverage_plan=coverage_plan,
            base_premium=premium_result.get('base_premium', 0),
            sector_adjusted_premium=premium_result.get('sector_adjusted_premium', 0),
            total_premium=premium_result.get('total_premium', 0),
            annual_premium=premium_result.get('annual_premium', 0),
            monthly_premium=premium_result.get('monthly_premium', 0),
            company_sector_factor=premium_result.get('sector_factor', 1.0),
            company_size_factor=premium_result.get('size_factor', 1.0),
            company_age_factor=premium_result.get('age_factor', 1.0),
            risk_level_factor=premium_result.get('risk_factor', 1.0),
            work_env_factor=premium_result.get('environment_factor', 1.0),
            location_factor=premium_result.get('location_factor', 1.0),
            claims_history_factor=premium_result.get('claims_factor', 1.0),
            status='draft',  # مسودة حتى يتم رفع ملف الموظفين
            **validated_data
        )
        
        return quote

# ============= Health Insurance Policy Serializers =============
class HealthInsurancePolicySerializer(serializers.ModelSerializer):
    """سيريالايزر لوثيقة التأمين"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    quote_number = serializers.CharField(source='quote.quote_number', read_only=True)
    coverage_plan_name = serializers.SerializerMethodField()
    coverage_plan_details = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    insurance_type = serializers.SerializerMethodField()
    family_members = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    coverage_type = serializers.SerializerMethodField()
    due_amount = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = HealthInsurancePolicy
        fields = [
            'id', 'policy_number', 'quote', 'quote_number', 'company', 'company_name',
            'total_premium', 'annual_premium', 'monthly_premium', 'insurance_type',
            'inception_date', 'expiry_date', 'created_at', 'coverage_plan_details',
            'total_employees', 'policy_details', 'coverage_plan_name', 
            'payment_status_display', 'status_display', 'days_remaining',
            'payment_method', 'coverage_type', 'status', 'payment_status',
            'family_members', 'coverage_details', 'calculation_data',
            'due_amount', 'paid_amount'
        ]
        read_only_fields = ['created_at']

    def get_coverage_plan_name(self, obj):
        # Get coverage plan name from policy_details or coverage_details
        if obj.policy_details and 'coverage_plan_name' in obj.policy_details:
            return obj.policy_details['coverage_plan_name']
        
        if obj.coverage_details:
            # Try to parse coverage_details if it's a string
            coverage_details = obj.coverage_details
            if isinstance(coverage_details, str):
                try:
                    coverage_details = json.loads(coverage_details)
                except:
                    coverage_details = {}
            
            if 'insurance_type_data' in coverage_details:
                insurance_data = coverage_details['insurance_type_data']
                if isinstance(insurance_data, dict) and 'name' in insurance_data:
                    return insurance_data['name']
        
        # Map insurance_type to plan name
        plan_names = {
            'A': 'التغطية الشاملة',
            'B': 'التغطية المتوسطة',
            'C': 'التغطية الأساسية',
            'comprehensive': 'التغطية الشاملة',
            'medium': 'التغطية المتوسطة',
            'basic': 'التغطية الأساسية'
        }
        
        # Get insurance_type from obj or policy_details
        insurance_type = self.get_insurance_type(obj)
        return plan_names.get(insurance_type, f'خطة {insurance_type}')
    
    def get_family_members(self, obj):
        """استخراج أفراد العائلة من مصادر متعددة"""
        family_members = {'spouses': 0, 'children': 0, 'parents': 0}
        
        # 1. من حقل family_members المباشر
        if obj.family_members:
            if isinstance(obj.family_members, str):
                try:
                    family_members = json.loads(obj.family_members)
                except:
                    pass
            elif isinstance(obj.family_members, dict):
                family_members = obj.family_members
        
        # 2. من calculation_data
        if obj.calculation_data:
            calculation_data = obj.calculation_data
            if isinstance(calculation_data, str):
                try:
                    calculation_data = json.loads(calculation_data)
                except:
                    calculation_data = {}
            
            if 'family_data' in calculation_data:
                family_data = calculation_data['family_data']
                family_members.update({
                    'spouses': family_data.get('spouses', family_members['spouses']),
                    'children': family_data.get('children', family_members['children']),
                    'parents': family_data.get('parents', family_members['parents'])
                })
        
        # 3. من coverage_details
        if obj.coverage_details:
            coverage_details = obj.coverage_details
            if isinstance(coverage_details, str):
                try:
                    coverage_details = json.loads(coverage_details)
                except:
                    coverage_details = {}
            
            if 'family_members' in coverage_details:
                family_members.update({
                    'spouses': coverage_details['family_members'].get('spouses', family_members['spouses']),
                    'children': coverage_details['family_members'].get('children', family_members['children']),
                    'parents': coverage_details['family_members'].get('parents', family_members['parents'])
                })
        
        # 4. من policy_details
        if obj.policy_details and 'family_members' in obj.policy_details:
            family_members.update({
                'spouses': obj.policy_details['family_members'].get('spouses', family_members['spouses']),
                'children': obj.policy_details['family_members'].get('children', family_members['children']),
                'parents': obj.policy_details['family_members'].get('parents', family_members['parents'])
            })
        
        return family_members
    
    def get_coverage_plan_details(self, obj):
        """الحصول على تفاصيل خطة التغطية"""
        if obj.coverage_plan:
            return {
                'id': obj.coverage_plan.id,
                'name': obj.coverage_plan.name,
                'code': obj.coverage_plan.code,
                'description': obj.coverage_plan.description,
                'base_rate': obj.coverage_plan.base_rate,
                'coverage_type': obj.coverage_plan.coverage_type,
                'max_annual_limit': obj.coverage_plan.max_annual_limit,
                'hospital_room_limit': obj.coverage_plan.hospital_room_limit,
                'outpatient_limit': obj.coverage_plan.outpatient_limit,
                'maternity_coverage': obj.coverage_plan.maternity_coverage,
                'dental_coverage': obj.coverage_plan.dental_coverage,
                'optical_coverage': obj.coverage_plan.optical_coverage,
                'chronic_diseases_coverage': obj.coverage_plan.chronic_diseases_coverage
            }
        return None
    
    def get_days_remaining(self, obj):
        """حساب الأيام المتبقية"""
        from datetime import date
        today = date.today()
        if obj.expiry_date:
            remaining = (obj.expiry_date - today).days
            return max(0, remaining)
        return 0
    
    def get_insurance_type(self, obj):
        """استخراج نوع التأمين من مصادر متعددة"""
        # 1. من policy_details
        if obj.policy_details and 'insurance_type' in obj.policy_details:
            return obj.policy_details['insurance_type']
        
        # 2. من coverage_details
        if obj.coverage_details:
            coverage_details = obj.coverage_details
            if isinstance(coverage_details, str):
                try:
                    coverage_details = json.loads(coverage_details)
                except:
                    coverage_details = {}
            
            if 'insurance_type' in coverage_details:
                return coverage_details['insurance_type']
            
            if 'insurance_type_data' in coverage_details:
                insurance_data = coverage_details['insurance_type_data']
                if isinstance(insurance_data, dict) and 'code' in insurance_data:
                    return insurance_data['code']
        
        # 3. من quote notes
        if obj.quote and obj.quote.notes:
            try:
                notes_data = json.loads(obj.quote.notes)
                if 'insurance_type' in notes_data:
                    return notes_data['insurance_type']
            except:
                pass
        
        # 4. من quote مباشرة
        if obj.quote and obj.quote.insurance_type:
            return obj.quote.insurance_type
        
        return 'B'
    
    def get_payment_method(self, obj):
        """استخراج طريقة الدفع"""
        # 1. من policy_details
        if obj.policy_details and 'payment_method' in obj.policy_details:
            return obj.policy_details['payment_method']
        
        # 2. من coverage_details
        if obj.coverage_details:
            coverage_details = obj.coverage_details
            if isinstance(coverage_details, str):
                try:
                    coverage_details = json.loads(coverage_details)
                except:
                    coverage_details = {}
            
            if 'payment_method' in coverage_details:
                return coverage_details['payment_method']
        
        # 3. من quote
        if obj.quote and obj.quote.payment_method:
            return obj.quote.payment_method
        
        return 'annual'
    
    # In health_insurance/serializers.py - UPDATE HealthInsurancePolicySerializer:
    def get_coverage_type(self, obj):
        """استخراج نوع التغطية"""
        # 1. من policy_details
        if obj.policy_details and 'coverage_type' in obj.policy_details:
            return obj.policy_details['coverage_type']
        
        # 2. من coverage_details
        if obj.coverage_details:
            coverage_details = obj.coverage_details
            if isinstance(coverage_details, str):
                try:
                    coverage_details = json.loads(coverage_details)
                except:
                    coverage_details = {}
            
            if 'coverage_type' in coverage_details:
                return coverage_details['coverage_type']
        
        # 3. من quote coverage_details
        if obj.quote and obj.quote.coverage_details:
            quote_coverage = obj.quote.coverage_details
            if isinstance(quote_coverage, str):
                try:
                    quote_coverage = json.loads(quote_coverage)
                except:
                    quote_coverage = {}
            
            if 'coverage_type' in quote_coverage:
                return quote_coverage['coverage_type']
        
        # 4. Default based on insurance_type
        insurance_type = self.get_insurance_type(obj)
        if insurance_type == 'A':
            return 'comprehensive'
        elif insurance_type == 'B':
            return 'basic'
        elif insurance_type == 'C':
            return 'standard'
        
        return 'comprehensive'

    def get_due_amount(self, obj):
        """حساب المبلغ المستحق"""
        try:
            paid = float(obj.paid_amount or 0)
            total = float(obj.total_premium or 0)
            return total - paid
        except:
            return obj.total_premium or 0
    
    def get_paid_amount(self, obj):
        """الحصول على المبلغ المدفوع"""
        return obj.paid_amount or 0
    
    def to_representation(self, instance):
        """تعديل التمثيل النهائي للبيانات"""
        representation = super().to_representation(instance)
        
        # Ensure JSON fields are properly serialized
        if isinstance(representation.get('coverage_details'), str):
            try:
                representation['coverage_details'] = json.loads(representation['coverage_details'])
            except:
                pass
        
        if isinstance(representation.get('calculation_data'), str):
            try:
                representation['calculation_data'] = json.loads(representation['calculation_data'])
            except:
                pass
        
        if isinstance(representation.get('policy_details'), str):
            try:
                representation['policy_details'] = json.loads(representation['policy_details'])
            except:
                pass
        
        # Add debug info in development
        if settings.DEBUG:
            representation['_debug'] = {
                'has_quote': bool(instance.quote),
                'quote_id': instance.quote.id if instance.quote else None,
                'has_coverage_details': bool(instance.coverage_details),
                'has_calculation_data': bool(instance.calculation_data),
                'has_family_members': bool(instance.family_members),
                'model_fields': list(instance.__dict__.keys())
            }
        
        return representation

class HealthInsurancePolicySimpleSerializer(serializers.ModelSerializer):
    """سيريالايزر مبسط للوثيقة"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    company_sector = serializers.CharField(source='company.get_sector_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = HealthInsurancePolicy
        fields = [
            'id', 'policy_number', 'company_name', 'company_sector',
            'status', 'status_display', 'total_premium', 'monthly_premium',
            'inception_date', 'expiry_date'
        ]

# ============= Health Calculation Log Serializers =============
class HealthCalculationLogSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    company_sector_display = serializers.SerializerMethodField()
    company_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = HealthCalculationLog
        fields = [
            'id', 'user', 'company_sector', 'company_sector_display',
            'company_size', 'company_size_display', 'employee_count',
            'dependents_count', 'coverage_plan_name', 'calculated_premium',
            'factors_used', 'ip_address', 'created_at'
        ]
    
    def get_company_sector_display(self, obj):
        return dict(Company.SECTOR_CHOICES).get(obj.company_sector, obj.company_sector)
    
    def get_company_size_display(self, obj):
        return dict(Company.SIZE_CHOICES).get(obj.company_size, obj.company_size)

# ============= Premium Calculator Serializers =============
class HealthPremiumCalculatorSerializer(serializers.Serializer):
    """سيريالايزر حاسبة الأقساط الصحية"""
    sector = serializers.ChoiceField(
        choices=Company.SECTOR_CHOICES,
        required=True
    )
    size_category = serializers.ChoiceField(
        choices=Company.SIZE_CHOICES,
        default='small'
    )
    employee_count = serializers.IntegerField(min_value=1, max_value=10000, required=True)
    dependents_count = serializers.IntegerField(min_value=0, default=0)
    city = serializers.CharField(max_length=100, required=True)
    work_environment = serializers.ChoiceField(
        choices=Company.WORK_ENVIRONMENT_CHOICES,
        default='office'
    )
    risk_level = serializers.ChoiceField(
        choices=Company.RISK_LEVEL_CHOICES,
        default='medium'
    )
    has_previous_insurance = serializers.BooleanField(default=False)
    previous_insurance_years = serializers.IntegerField(min_value=0, default=0)
    claims_history = serializers.IntegerField(min_value=0, default=0)
    establishment_age = serializers.IntegerField(min_value=1, default=1)
    coverage_plan_id = serializers.IntegerField(required=False, allow_null=True)
    custom_base_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
        min_value=100, max_value=10000
    )
    
    def validate(self, data):
        """التحقق من صحة البيانات"""
        employee_count = data.get('employee_count')
        
        if employee_count < 1:
            raise serializers.ValidationError({
                'employee_count': 'عدد الموظفين يجب أن يكون 1 على الأقل'
            })
        
        if employee_count > 10000:
            raise serializers.ValidationError({
                'employee_count': 'عدد الموظفين لا يمكن أن يتجاوز 10000'
            })
        
        # إذا كان عدد سنوات التأمين السابقة أكثر من 0، يجب أن يكون has_previous_insurance = True
        if data.get('previous_insurance_years', 0) > 0 and not data.get('has_previous_insurance', False):
            raise serializers.ValidationError({
                'has_previous_insurance': 'يجب تحديد أن لديك تأميناً سابقاً إذا أدخلت عدد السنوات'
            })
        
        return data
    
    def calculate_premium(self):
        """احتساب القسط"""
        from .calculations import quick_health_calculator
        
        result = quick_health_calculator(
            sector=self.validated_data['sector'],
            size_category=self.validated_data['size_category'],
            employee_count=self.validated_data['employee_count'],
            dependents_count=self.validated_data.get('dependents_count', 0),
            city=self.validated_data['city'],
            work_environment=self.validated_data['work_environment'],
            risk_level=self.validated_data['risk_level'],
            has_previous_insurance=self.validated_data.get('has_previous_insurance', False),
            previous_insurance_years=self.validated_data.get('previous_insurance_years', 0),
            claims_history=self.validated_data.get('claims_history', 0),
            establishment_age=self.validated_data.get('establishment_age', 1)
        )
        
        # إذا كان هناك خطة محددة
        coverage_plan_id = self.validated_data.get('coverage_plan_id')
        if coverage_plan_id:
            try:
                coverage_plan = HealthCoveragePlan.objects.get(id=coverage_plan_id)
                result['coverage_plan'] = {
                    'name': coverage_plan.name,
                    'type': coverage_plan.get_plan_type_display
                }
            except HealthCoveragePlan.DoesNotExist:
                pass
        
        # إذا كان هناك سعر مخصص
        custom_base_price = self.validated_data.get('custom_base_price')
        if custom_base_price:
            result['custom_base_price'] = float(custom_base_price)
        
        return result

# ============= Sector Pricing Factor Serializers =============
class SectorPricingFactorSerializer(serializers.ModelSerializer):
    sector_display = serializers.CharField(source='get_sector_display', read_only=True)
    
    class Meta:
        model = SectorPricingFactor
        fields = [
            'id', 'sector', 'sector_display', 'base_factor', 'risk_adjustment',
            'min_premium_per_employee', 'max_premium_per_employee'
        ]
    
    def get_sector_display(self, obj):
        return dict(Company.SECTOR_CHOICES).get(obj.sector, obj.sector)

# ============= Report Serializers =============
class HealthInsuranceReportSerializer(serializers.Serializer):
    """سيريالايزر تقارير التأمين الصحي"""
    report_type = serializers.CharField(max_length=50)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    company_id = serializers.IntegerField(required=False)
    sector = serializers.ChoiceField(
        choices=Company.SECTOR_CHOICES,
        required=False,
        allow_null=True
    )
    format = serializers.ChoiceField(choices=['json', 'html', 'pdf'], default='json')
    
    def validate(self, data):
        """التحقق من صحة البيانات"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                'start_date': 'تاريخ البداية لا يمكن أن يكون بعد تاريخ النهاية'
            })
        
        return data