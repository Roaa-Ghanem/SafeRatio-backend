# health_insurance/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Company,
    HealthCoveragePlan,
    HealthInsuranceQuote,
    HealthInsurancePolicy,
    HealthCalculationLog,
    SectorPricingFactor
)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'sector', 'size_category', 'total_employees', 'city', 'created_at']
    list_filter = ['sector', 'size_category', 'city', 'created_at']
    search_fields = ['name', 'cr_number', 'email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('user', 'name', 'sector', 'sub_sector', 'size_category')  # ✅ تحديث
        }),
        ('معلومات الاتصال', {
            'fields': ('cr_number', 'address', 'city', 'phone', 'email')
        }),
        ('معلومات الموظفين', {
            'fields': ('total_employees', 'establishment_age')  # ✅ تحديث
        }),
        ('معلومات المخاطر', {
            'fields': ('work_environment', 'risk_level')  # ✅ إضافة
        }),
        ('معلومات التأمين', {
            'fields': ('has_previous_insurance', 'previous_insurance_years')  # ✅ تحديث
        }),
        ('الملف', {
            'fields': ('employees_file',)  # ✅ إضافة
        }),
        ('معلومات إضافية', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

@admin.register(HealthCoveragePlan)
class HealthCoveragePlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'plan_type', 'base_price_per_employee', 'is_active']
    list_filter = ['plan_type', 'is_active']
    search_fields = ['name', 'description']
    fieldsets = (
        ('معلومات الخطة', {
            'fields': ('name', 'plan_type', 'description', 'is_active')
        }),
        ('حدود التغطية', {
            'fields': ('outpatient_limit', 'inpatient_limit', 'dental_limit', 
                      'optical_limit', 'emergency_limit')  # ✅ إزالة maternity_limit
        }),
        ('نسب التغطية (%)', {
            'fields': ('outpatient_coverage', 'inpatient_coverage', 'dental_coverage',
                      'optical_coverage')  # ✅ إزالة maternity_coverage
        }),
        ('المعلومات المالية', {
            'fields': ('base_price_per_employee',)
        }),
        ('المميزات', {
            'fields': ('includes_preventive_care', 'includes_chronic_medication',
                      'includes_work_accidents')  # ✅ تحديث
        }),
    )
    
    def plan_type_display(self, obj):
        return obj.get_plan_type_display()
    plan_type_display.short_description = 'نوع الخطة'

@admin.register(HealthInsuranceQuote)
class HealthInsuranceQuoteAdmin(admin.ModelAdmin):
    list_display = ['quote_number', 'company', 'coverage_plan', 'total_premium', 'status_display', 'created_at']
    list_filter = ['status', 'coverage_plan', 'created_at']
    search_fields = ['quote_number', 'company__name']
    readonly_fields = ['quote_number', 'created_at', 'updated_at']
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('user', 'company', 'coverage_plan', 'quote_number')
        }),
        ('تفاصيل الاقتباس', {
            'fields': ('insured_employees_count', 'coverage_period', 'status', 'valid_until')
        }),
        ('عوامل الحساب', {
            'fields': ('company_sector_factor', 'company_size_factor', 'company_age_factor',
                      'risk_level_factor', 'work_env_factor', 'location_factor', 'claims_history_factor')
        }),
        ('الأقساط', {
            'fields': ('base_premium', 'sector_adjusted_premium', 'total_premium', 'annual_premium', 'monthly_premium')
        }),
        ('التحليل', {
            'fields': ('employee_analysis', 'age_distribution', 'gender_distribution')
        }),
        ('ملاحظات ومستندات', {
            'fields': ('notes', 'supporting_documents', 'employees_file')
        }),
        ('معلومات إضافية', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def status_display(self, obj):
        colors = {
            'draft': 'gray',
            'pending': 'orange',
            'quoted': 'blue',
            'accepted': 'green',
            'rejected': 'red',
            'expired': 'darkgray'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'الحالة'
    status_display.admin_order_field = 'status'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

@admin.register(HealthInsurancePolicy)
class HealthInsurancePolicyAdmin(admin.ModelAdmin):
    list_display = ['policy_number', 'company', 'total_premium', 'status_display', 'inception_date', 'days_remaining']
    list_filter = ['status', 'inception_date']
    search_fields = ['policy_number', 'company__name']
    readonly_fields = ['policy_number', 'created_at', 'updated_at', 'days_remaining']
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('quote', 'company', 'user', 'policy_number', 'coverage_plan')
        }),
        ('فترة التغطية', {
            'fields': ('inception_date', 'expiry_date')
        }),
        ('المعلومات المالية', {
            'fields': ('total_premium', 'annual_premium', 'monthly_premium', 
                      'paid_amount', 'due_amount')
        }),
        ('الحالة', {
            'fields': ('status', 'payment_status')
        }),
        ('التغطية الخاصة', {
            'fields': ('includes_work_accident', 'includes_occupational_disease')
        }),
        ('معلومات إضافية', {
            'fields': ('documents', 'broker_name', 'broker_contact', 
                      'days_remaining', 'is_expiring_soon')
        }),
    )
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'active': 'green',
            'expired': 'red',
            'cancelled': 'darkgray',
            'suspended': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'حالة الوثيقة'
    
    def days_remaining(self, obj):
        days = obj.days_remaining
        if days <= 0:
            return format_html('<span style="color: red; font-weight: bold;">منتهي</span>')
        elif days <= 30:
            return format_html('<span style="color: orange; font-weight: bold;">{} يوم</span>', days)
        else:
            return format_html('<span style="color: green;">{} يوم</span>', days)
    days_remaining.short_description = 'الأيام المتبقية'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

@admin.register(HealthCalculationLog)
class HealthCalculationLogAdmin(admin.ModelAdmin):
    list_display = ['company_sector_display', 'company_size_display', 'employee_count', 'calculated_premium', 'created_at']
    list_filter = ['company_sector', 'company_size', 'created_at']
    search_fields = ['company_sector']
    readonly_fields = ['created_at']
    
    def company_sector_display(self, obj):
        from .models import Company
        return dict(Company.SECTOR_CHOICES).get(obj.company_sector, obj.company_sector)
    company_sector_display.short_description = 'قطاع الشركة'
    
    def company_size_display(self, obj):
        from .models import Company
        return dict(Company.SIZE_CHOICES).get(obj.company_size, obj.company_size)
    company_size_display.short_description = 'حجم الشركة'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

@admin.register(SectorPricingFactor)
class SectorPricingFactorAdmin(admin.ModelAdmin):
    list_display = ['sector_display', 'base_factor', 'risk_adjustment', 'total_factor_display', 'is_active']
    list_filter = ['is_active']
    search_fields = ['sector']
    
    def sector_display(self, obj):
        from .models import Company
        return dict(Company.SECTOR_CHOICES).get(obj.sector, obj.sector)
    sector_display.short_description = 'القطاع'
    
    def total_factor_display(self, obj):
        total = obj.base_factor + obj.risk_adjustment
        if total > Decimal('1.3'):
            color = 'red'
        elif total > Decimal('1.1'):
            color = 'orange'
        elif total < Decimal('0.9'):
            color = 'green'
        else:
            color = 'blue'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
            color,
            total
        )
    total_factor_display.short_description = 'العامل الإجمالي'

# إعدادات لوحة التحكم
admin.site.site_header = "إدارة نظام التأمين الصحي - SafeRatio"
admin.site.site_title = "نظام التأمين الصحي"
admin.site.index_title = "مرحباً بك في لوحة إدارة التأمين الصحي"