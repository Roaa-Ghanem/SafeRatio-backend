# health_insurance/models.py - CLEAN VERSION
from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid

def generate_health_quote_number():
    return f"HQ-{uuid.uuid4().hex[:8].upper()}"

def generate_health_policy_number():
    return f"HP-{uuid.uuid4().hex[:8].upper()}"

# ============= Company Model =============
class Company(models.Model):
    SECTOR_CHOICES = (
        # قطاع صحي
        ('health_hospital', 'مستشفى'),
        ('health_clinic', 'عيادة'),
        ('health_pharmacy', 'صيدلية'),
        ('health_lab', 'مختبر طبي'),
        ('health_center', 'مركز طبي'),
        ('health_dental', 'عيادة أسنان'),
        ('health_optical', 'مركز بصريات'),
        ('health_other', 'خدمات صحية أخرى'),
        
        # قطاع تكنولوجيا
        ('tech_software', 'شركة برمجيات'),
        ('tech_web', 'تطوير مواقع وتطبيقات'),
        ('tech_ai', 'ذكاء اصطناعي'),
        ('tech_cyber', 'أمن سيبراني'),
        ('tech_cloud', 'حوسبة سحابية'),
        ('tech_gaming', 'ألعاب إلكترونية'),
        ('tech_other', 'تكنولوجيا أخرى'),
        
        # قطاع مقاولات
        ('construction_civil', 'مقاولات إنشائية'),
        ('construction_electrical', 'مقاولات كهرباء'),
        ('construction_mechanical', 'مقاولات ميكانيكا'),
        ('construction_roads', 'مقاولات طرق وجسور'),
        ('construction_decoration', 'تشطيب وديكور'),
        ('construction_other', 'مقاولات أخرى'),
        
        # قطاع تجارة
        ('retail_store', 'متجر تجزئة'),
        ('wholesale', 'توزيع وتجارة جملة'),
        ('ecommerce', 'متجر إلكتروني'),
        ('retail_other', 'تجارة أخرى'),
        
        # قطاع خدمات
        ('services_logistics', 'شركة شحن ولوجستيات'),
        ('services_cleaning', 'خدمات نظافة'),
        ('services_maintenance', 'صيانة وخدمات فنية'),
        ('services_transport', 'نقل ومواصلات'),
        ('services_other', 'خدمات أخرى'),
        
        # أخرى
        ('other', 'أخرى'),
    )
    
    SIZE_CHOICES = (
        ('micro', 'صغيرة جدا (1-5 موظفين)'),
        ('small', 'صغيرة (6-50 موظفين)'),
        ('medium', 'متوسطة (51-250 موظفين)'),
        ('large', 'كبيرة (251-1000 موظفين)'),
        ('enterprise', 'عملاقة (1000+ موظفين)'),
    )
    
    RISK_LEVEL_CHOICES = (
        ('low', 'مخاطر منخفضة'),
        ('medium', 'مخاطر متوسطة'),
        ('high', 'مخاطر عالية'),
        ('very_high', 'مخاطر عالية جداً'),
    )
    
    WORK_ENVIRONMENT_CHOICES = (
        ('office', 'عمل مكتبي'),
        ('field', 'عمل ميداني'),
        ('mixed', 'مختلط (مكتبي وميداني)'),
        ('remote', 'عمل عن بعد'),
        ('hazardous', 'بيئة خطرة'),
    )
    
    # ========== CORE FIELDS ==========
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Basic Information
    name = models.CharField(max_length=200, unique=True)
    sector = models.CharField(max_length=50, choices=SECTOR_CHOICES)
    sub_sector = models.CharField(max_length=100, blank=True)
    size_category = models.CharField(max_length=20, choices=SIZE_CHOICES, default='small')
    employees_data = models.JSONField(default=dict, blank=True)

    # Contact Information
    cr_number = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    city = models.CharField(max_length=100, default='صنعاء')
    country = models.CharField(max_length=100, default='اليمن')
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    website = models.URLField(blank=True, null=True)
    tax_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Employee Information
    total_employees = models.IntegerField(default=1)
    male_employees = models.IntegerField(default=0)
    female_employees = models.IntegerField(default=0)
    insured_employees = models.IntegerField(default=0)
    establishment_age = models.IntegerField(default=1)
    founded_date = models.DateField(blank=True, null=True)
    
    # Risk Information
    work_environment = models.CharField(max_length=20, choices=WORK_ENVIRONMENT_CHOICES, default='office')
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default='medium')
    
    # Financial Information
    annual_revenue = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    
    # Previous Insurance
    has_previous_insurance = models.BooleanField(default=False)
    previous_insurance_years = models.IntegerField(default=0)
    claims_history = models.IntegerField(default=0)
    
    # Files
    employees_file = models.FileField(upload_to='companies/employee_files/', null=True, blank=True)
    
    # Additional Data
    sector_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'company'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_company_name_per_user',
                violation_error_message='يجب أن يكون اسم الشركة فريداً بالنسبة لك'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def extract_and_store_employees_data(self, file_path=None):
        """
        استخراج وتخزين بيانات الموظفين من ملف Excel
        """
        try:
            if not file_path and self.employees_file:
                file_path = self.employees_file.path
            
            if not file_path:
                print(f"❌ لا يوجد ملف لاستخراج البيانات للشركة {self.name}")
                return False
            
            print(f"🔍 جاري استخراج بيانات الموظفين من: {file_path}")
            
            import pandas as pd
            from datetime import datetime
            
            # قراءة ملف Excel
            df = pd.read_excel(file_path)
            
            # استخراج البيانات
            employees_list = []
            
            for index, row in df.iterrows():
                employee = {
                    'id': index + 1,
                    'row_number': index + 2,
                }
                
                # نسخ جميع الأعمدة
                for col in df.columns:
                    if pd.notna(row[col]):
                        employee[str(col)] = str(row[col])
                    else:
                        employee[str(col)] = ""
                
                # إضافة بيانات محسوبة
                employee['extracted_at'] = datetime.now().isoformat()
                employee['source_file'] = self.employees_file.name if self.employees_file else 'unknown'
                
                employees_list.append(employee)
            
            # تخزين البيانات في الحقل الجديد
            self.employees_data = {
                'employees': employees_list,
                'total_count': len(employees_list),
                'extracted_at': datetime.now().isoformat(),
                'file_name': self.employees_file.name if self.employees_file else 'unknown',
                'columns': list(df.columns),
                'stats': {
                    'total_rows': len(df),
                    'columns_count': len(df.columns),
                    'extraction_success': True
                }
            }
            
            self.save()
            
            print(f"✅ تم استخراج وتخزين {len(employees_list)} موظف للشركة {self.name}")
            return True
            
        except Exception as e:
            print(f"❌ خطأ في استخراج بيانات الموظفين: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # تخزين حالة الخطأ
            self.employees_data = {
                'employees': [],
                'total_count': 0,
                'extracted_at': datetime.now().isoformat(),
                'error': str(e),
                'extraction_success': False
            }
            self.save()
            
            return False
    
    def clean(self):
        """تنظيف وفحص البيانات قبل الحفظ"""
        # تنظيف الاسم
        if self.name:
            self.name = self.name.strip()
            
            # التحقق من أن الاسم ليس فارغاً
            if not self.name:
                raise ValidationError({'name': 'اسم الشركة لا يمكن أن يكون فارغاً'})
    
    def save(self, *args, **kwargs):
        """حفظ مع التحقق من التكرار"""
        self.full_clean()  # تشغيل التنظيف
        super().save(*args, **kwargs)
    
    @property
    def get_sector_display(self):
        return dict(self.SECTOR_CHOICES).get(self.sector, self.sector)
    

class Employee(models.Model):  # ✅ هذا النموذج يجب أن يكون موجوداً
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employees')
    name = models.CharField(max_length=200)
    age = models.IntegerField()
    gender = models.CharField(max_length=10, choices=[('male', 'ذكر'), ('female', 'أنثى')])
    marital_status = models.CharField(max_length=20, choices=[('single', 'أعزب'), ('married', 'متزوج')])
    position = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)
    monthly_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    number_of_children = models.IntegerField(default=0)
    has_children = models.BooleanField(default=False)
    children_count = models.IntegerField(default=0, verbose_name="عدد الأبناء")
    employee_number = models.CharField(max_length=50, blank=True, null=True)
    include_parents = models.BooleanField(default=False, verbose_name="يشمل الوالدين")
    parents_count = models.IntegerField(default=0, verbose_name="عدد الوالدين المشمولين")
    insurance_profile = models.JSONField(default=dict, blank=True)
    wives_count = models.IntegerField(default=0, verbose_name="عدد الزوجات")
    chronic_diseases = models.BooleanField(default=False, verbose_name="أمراض مزمنة")
    include_parents = models.BooleanField(default=False, verbose_name="يشمل الوالدين")
    parents_count = models.IntegerField(default=0, verbose_name="عدد الوالدين")

    class Meta:
        verbose_name = 'موظف'
        verbose_name_plural = 'الموظفين'
    
    def __str__(self):
        return f"{self.name} - {self.company.name}"
    
    @property
    def has_children(self):
        """هل لديه أبناء؟"""
        return self.children_count > 0
    
    @property
    def is_married(self):
        """هل هو متزوج؟"""
        return self.marital_status == 'married'
    
    @property
    def total_family_members(self):
        """إجمالي أفراد العائلة"""
        return self.wives_count + self.children_count + self.parents_count
    
    def save(self, *args, **kwargs):
        # إذا كان متزوجاً وليس لديه زوجات، افترض زوجة واحدة
        if self.is_married and self.wives_count == 0:
            self.wives_count = 1
        
        # إذا كان يشمل الوالدين وليس لديهم عدد، افترض 2
        if self.include_parents and self.parents_count == 0:
            self.parents_count = 2
        
        super().save(*args, **kwargs)

# ============= Health Coverage Plan =============
class HealthCoveragePlan(models.Model):
    PLAN_TYPES = (
        ('basic', 'أساسي'),
        ('standard', 'قياسي'),
        ('premium', 'متميز'),
        ('custom', 'مخصص'),
    )
    
    # Basic Information
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, default='standard')
    description = models.TextField(blank=True)
    
    # Coverage Limits
    outpatient_limit = models.DecimalField(max_digits=10, decimal_places=2, default=5000)
    inpatient_limit = models.DecimalField(max_digits=10, decimal_places=2, default=50000)
    dental_limit = models.DecimalField(max_digits=10, decimal_places=2, default=2000)
    optical_limit = models.DecimalField(max_digits=10, decimal_places=2, default=1500)
    emergency_limit = models.DecimalField(max_digits=10, decimal_places=2, default=10000)
    
    # Coverage Percentages
    outpatient_coverage = models.IntegerField(default=80)
    inpatient_coverage = models.IntegerField(default=90)
    dental_coverage = models.IntegerField(default=70)
    optical_coverage = models.IntegerField(default=80)
    
    # Pricing
    base_price_per_employee = models.DecimalField(max_digits=8, decimal_places=2, default=1000)
    
    # Features
    includes_preventive_care = models.BooleanField(default=True)
    includes_chronic_medication = models.BooleanField(default=True)
    includes_work_accidents = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'health_coverage_plan'
        ordering = ['base_price_per_employee']
    
    def __str__(self):
        return f"{self.name}"

# ============= Health Insurance Quote =============
class HealthInsuranceQuote(models.Model):
    QUOTE_STATUS = (
        ('draft', 'مسودة'),
        ('pending', 'قيد المراجعة'),
        ('quoted', 'مقتبس'),
        ('accepted', 'مقبول'),
        ('rejected', 'مرفوض'),
        ('expired', 'منتهي'),
    )
    
    # Relationships
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='quotes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    coverage_plan = models.ForeignKey(HealthCoveragePlan, on_delete=models.SET_NULL, null=True, blank=True)
    calculation_data = models.JSONField(default=dict, blank=True)
    coverage_details = models.JSONField(default=dict, blank=True) 

    # Quote Information
    quote_number = models.CharField(max_length=20, unique=True, default=generate_health_quote_number)
    insurance_type = models.CharField(max_length=10, default='B', blank=True)
    insured_employees_count = models.IntegerField(default=1)
    coverage_period = models.IntegerField(default=12)
    
    # Premiums
    base_premium = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_premium = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    annual_premium = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_premium = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=QUOTE_STATUS, default='draft')
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Files
    employees_file = models.FileField(upload_to='employee_files/quotes/', null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'health_insurance_quote'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Quote {self.quote_number}"

# ============= Health Insurance Policy =============
class HealthInsurancePolicy(models.Model):
    quote = models.ForeignKey(
        'HealthInsuranceQuote', 
        on_delete=models.CASCADE,
        related_name='policies'
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE,
        related_name='health_policies'
    )
    policy_number = models.CharField(max_length=100, unique=True)
    total_premium = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_premium = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_premium = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    insurance_type = models.CharField(max_length=10, default='B')
    payment_method = models.CharField(max_length=20, default='annual')
    coverage_options = models.JSONField(default=dict, blank=True)
    
    # Coverage information
    coverage_plan = models.ForeignKey(
        'CoveragePlan', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # IMPORTANT: Add these fields to your model
    coverage_details = models.JSONField(default=dict, blank=True)
    calculation_data = models.JSONField(default=dict, blank=True)
    family_members = models.JSONField(default=dict, blank=True)
    policy_details = models.JSONField(default=dict, blank=True)
    
    # Status fields
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('pending', 'معلق'),
        ('active', 'نشط'),
        ('expired', 'منتهي'),
        ('cancelled', 'ملغي'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'قيد الدفع'),
        ('partial', 'مدفوع جزئياً'),
        ('paid', 'مدفوع'),
        ('overdue', 'متأخر'),
        ('cancelled', 'ملغي'),
    ]
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Dates
    inception_date = models.DateField()
    expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Employee count
    total_employees = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.policy_number} - {self.company.name}"
    
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    
    def get_payment_status_display(self):
        return dict(self.PAYMENT_STATUS_CHOICES).get(self.payment_status, self.payment_status)

class CoveragePlan(models.Model):
    name = models.CharField(max_length=200, verbose_name="اسم الخطة")
    code = models.CharField(max_length=50, unique=True, verbose_name="رمز الخطة")
    description = models.TextField(blank=True, verbose_name="الوصف")
    base_rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="السعر الأساسي")
    coverage_type = models.CharField(max_length=50, verbose_name="نوع التغطية")
    max_annual_limit = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="الحد السنوي الأقصى")
    hospital_room_limit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="حد غرفة المستشفى")
    outpatient_limit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="حد العيادات الخارجية")
    maternity_coverage = models.BooleanField(default=False, verbose_name="تغطية الأمومة")
    dental_coverage = models.BooleanField(default=False, verbose_name="تغطية الأسنان")
    optical_coverage = models.BooleanField(default=False, verbose_name="تغطية النظارات")
    chronic_diseases_coverage = models.BooleanField(default=False, verbose_name="تغطية الأمراض المزمنة")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "خطة تغطية"
        verbose_name_plural = "خطط التغطية"

# ============= Other Models =============
class HealthCalculationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    company_sector = models.CharField(max_length=50, choices=Company.SECTOR_CHOICES)
    company_size = models.CharField(max_length=20, choices=Company.SIZE_CHOICES)
    employee_count = models.IntegerField()
    coverage_plan_name = models.CharField(max_length=100)
    calculated_premium = models.DecimalField(max_digits=10, decimal_places=2)
    factors_used = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'health_calculation_log'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Calculation {self.id}"

class SectorPricingFactor(models.Model):
    sector = models.CharField(max_length=50, choices=Company.SECTOR_CHOICES, unique=True)
    base_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    risk_adjustment = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sector_pricing_factor'
    
    def __str__(self):
        return f"{self.sector}: {self.base_factor}"