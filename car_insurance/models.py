from django.db import models
from django.conf import settings
from users.models import CustomUser
from decimal import Decimal
import uuid

# # Helper functions for default values (not lambdas)
# def default_license_plate():
#     return f"TEMP_{uuid.uuid4().hex[:8].upper()}"

# def default_vin():
#     return f"VIN_{uuid.uuid4().hex[:12].upper()}"

# def default_quote_number():
#     return f"QUOTE_{uuid.uuid4().hex[:8].upper()}"

# def default_policy_number():
#     return f"POL_{uuid.uuid4().hex[:8].upper()}"

# def default_claim_number():
#     return f"CLM_{uuid.uuid4().hex[:8].upper()}"

def generate_policy_number():
    """Generate unique policy number"""
    return f"POL-{uuid.uuid4().hex[:8].upper()}"

class Vehicle(models.Model):
    VEHICLE_TYPES = (
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('truck', 'Truck'),
        ('suv', 'SUV'),
    )
    
    FUEL_TYPES = (
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
    )

    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    make = models.CharField(max_length=50, default="Toyota")
    model = models.CharField(max_length=50, default="Camry")
    year = models.IntegerField(default=2020)
    license_plate = models.CharField(max_length=20, unique=True, verbose_name="License Plate")
    vin = models.CharField(max_length=17, blank=True, null=True, verbose_name="Vehicle Identification Number")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default='car')
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPES, default='petrol')
    engine_size = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('1.6'), help_text="Engine size in liters")
    purchase_date = models.DateField(auto_now_add=True)
    current_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_commercial = models.BooleanField(default=False)
    annual_mileage = models.IntegerField(default=10000, help_text="Annual mileage in kilometers")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def driver_age(self):
        """استخدم عمر المستخدم من الملف الشخصي"""
        if self.user and hasattr(self.user, 'profile'):
            try:
                return self.user.profile.age
            except:
                pass
        return 30  # قيمة افتراضية إذا لم يكن العمر متاحًا
    
    class Meta:
        db_table = 'car_insurance_vehicle'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.year} {self.make} {self.model} ({self.license_plate})"

class CarInsuranceQuote(models.Model):
    COVERAGE_TYPES = (
        ('third_party', 'Third Party Only'),
        ('third_party_fire_theft', 'Third Party Fire & Theft'),
        ('comprehensive', 'Comprehensive'),
    )
    
    QUOTE_STATUS = (
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('quoted', 'Quoted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    )
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    quote_number = models.CharField(max_length=20, unique=True)
    coverage_type = models.CharField(max_length=25, choices=COVERAGE_TYPES, default='comprehensive')
    premium_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    excess_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('500.00'))
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=QUOTE_STATUS, default='draft')
    
    # Risk factors for calculation
    # driver_age = models.IntegerField(default=30)
    claims_history = models.IntegerField(default=0, help_text="Number of previous claims")
    no_claims_years = models.IntegerField(default=0, help_text="Years of no claims bonus")
    
    # Calculated fields
    base_premium = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    final_premium = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'car_insurance_quote'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Quote {self.quote_number} - {self.vehicle}"

class CarPolicy(models.Model):
    POLICY_STATUS = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    
    quote = models.OneToOneField(CarInsuranceQuote, on_delete=models.CASCADE, related_name='policy')
    policy_number = models.CharField(max_length=50, unique=True,  default=generate_policy_number)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vehicle = models.ForeignKey('Vehicle', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=POLICY_STATUS, default='pending')
    document_url = models.FileField(upload_to='policy_documents/', null=True, blank=True)
    
    # Policy details
    inception_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    # معلومات الدفع
    total_premium = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_status = models.CharField(max_length=20, default='pending')
    
    # معلومات إضافية
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    documents = models.JSONField(default=dict, blank=True)  # لتخزين روابط المستندات
    
    class Meta:
        db_table = 'car_insurance_policy'
        ordering = ['-created_at']
        verbose_name_plural = 'Car policies'
    
    def __str__(self):
        return f"Policy {self.policy_number} - {self.vehicle}"
    
    def save(self, *args, **kwargs):
        # إذا كان policy_number فارغاً، أنشئ واحداً
        if not self.policy_number:
            self.policy_number = f"POL-{uuid.uuid4().hex[:8].upper()}"
        
        # إذا كان expiry_date فارغاً، احسبه من inception_date
        if not self.expiry_date and self.inception_date:
            from datetime import timedelta
            self.expiry_date = self.inception_date + timedelta(days=365)
        
        super().save(*args, **kwargs)
    
    def generate_policy_document(self):
        """Generate policy document content"""
        return {
            'policy_number': self.policy_number,
            'insured_name': self.user.get_full_name(),
            'vehicle': str(self.vehicle),
            'coverage_type': self.quote.get_coverage_type_display(),
            'inception_date': self.inception_date,
            'expiry_date': self.expiry_date,
            'total_premium': str(self.total_premium),
            'excess_amount': str(self.quote.excess_amount),
            'terms_and_conditions': self.get_terms_and_conditions()
        }
    
    def get_terms_and_conditions(self):
        """Get policy terms and conditions"""
        return [
            "الوثيقة سارية من تاريخ البدء إلى تاريخ الانتهاء",
            "يجب الإبلاغ عن أي حادث خلال 24 ساعة",
            "مبلغ التحمل يطبق على كل مطالبة",
            "شروط وأحكام إضافية حسب نوع التغطية"
        ]   

class Claim(models.Model):
    CLAIM_STATUS = (
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    )
    
    policy = models.ForeignKey(CarPolicy, on_delete=models.CASCADE)
    claim_number = models.CharField(max_length=20, unique=True)
    claim_date = models.DateField(auto_now_add=True)
    incident_date = models.DateField(auto_now_add=True)
    description = models.TextField(default="No description provided")
    estimated_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=CLAIM_STATUS, default='submitted')
    
    # Claim details
    incident_type = models.CharField(max_length=100, default="Accident")
    third_party_involved = models.BooleanField(default=False)
    police_report = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'car_insurance_claim'
        ordering = ['-claim_date']
    
    def __str__(self):
        return f"Claim {self.claim_number} - {self.policy}"

class VehicleDocument(models.Model):
    DOCUMENT_TYPES = (
        ('registration', 'Vehicle Registration'),
        ('insurance', 'Insurance Certificate'),
        ('inspection', 'Inspection Report'),
        ('accident', 'Accident Report'),
        ('other', 'Other'),
    )
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    document_file = models.FileField(upload_to='vehicle_documents/')
    description = models.CharField(max_length=200, blank=True, default="No description")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'car_insurance_vehicledocument'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.document_type} - {self.vehicle}"