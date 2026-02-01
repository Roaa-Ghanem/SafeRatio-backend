from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('individual', 'Individual'),
        ('organization', 'Organization'),
        ('admin', 'Admin'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='individual')
    phone = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=50, default='Yemen')
    language = models.CharField(max_length=10, default='ar')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    class Meta:
        db_table = 'users_customuser'

    def __str__(self):
        return f"{self.username} ({self.user_type})"
    
    @property
    def profile_completed(self):
        """تحقق إذا كان الملف الشخصي مكتملاً"""
        try:
            profile = self.profile
            return bool(profile.date_of_birth and profile.driving_license_number)
        except Profile.DoesNotExist:
            return False
    
    @property
    def age(self):
        """احسب العمر من تاريخ الميلاد"""
        try:
            profile = self.profile
            if profile.date_of_birth:
                today = timezone.now().date()
                return today.year - profile.date_of_birth.year - (
                    (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
                )
        except Profile.DoesNotExist:
            pass
        return None

class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    
    # المعلومات الأساسية
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='تاريخ الميلاد')
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female')], blank=True)
    
    # المعلومات الحساسة (لا يمكن تعديلها بعد الإدخال)
    driving_license_number = models.CharField(
        max_length=50, 
        null=True, 
        blank=True, 
        unique=True,
        verbose_name='رقم رخصة القيادة'
    )
    driving_license_issue_date = models.DateField(null=True, blank=True, verbose_name='تاريخ إصدار الرخصة')
    national_id = models.CharField(max_length=20, null=True, blank=True, unique=True, verbose_name='رقم الهوية')
    
    # معلومات شخصية إضافية
    marital_status = models.CharField(max_length=20, choices=[
        ('single', 'Single'), 
        ('married', 'Married'), 
        ('divorced', 'Divorced'), 
        ('widowed', 'Widowed')
    ], blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    
    # معلومات مالية
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    monthly_expenses = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    savings = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    debts = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # معلومات صحية
    smoking_status = models.BooleanField(default=False)
    health_notes = models.TextField(blank=True)
    
    # تاريخ الإنشاء والتحديث
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # حقول للتحكم في التعديل
    sensitive_info_locked = models.BooleanField(default=False, verbose_name='المعلومات الحساسة مقفلة')
    
    class Meta:
        db_table = 'users_profile'
        verbose_name = 'ملف شخصي'
        verbose_name_plural = 'الملفات الشخصية'

    def __str__(self):
        return f"Profile of {self.user.username}"
    
    @property
    def age(self):
        """احسب العمر من تاريخ الميلاد"""
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    @property
    def sensitive_info_completed(self):
        """تحقق إذا كانت المعلومات الحساسة مكتملة"""
        return bool(self.date_of_birth and self.driving_license_number)
    
    def save(self, *args, **kwargs):
        # إذا كانت المعلومات الحساسة مكتملة، قفلها
        if self.sensitive_info_completed and not self.sensitive_info_locked:
            self.sensitive_info_locked = True
        
        # إذا تم محاولة تعديل المعلومات الحساسة وهي مقفلة
        if self.pk and self.sensitive_info_locked:
            old_profile = Profile.objects.get(pk=self.pk)
            sensitive_fields = ['date_of_birth', 'driving_license_number', 'national_id']
            
            for field in sensitive_fields:
                old_value = getattr(old_profile, field)
                new_value = getattr(self, field)
                
                if old_value and new_value and old_value != new_value:
                    raise ValueError(f"لا يمكن تعديل {field} بعد الإدخال الأول")
        
        super().save(*args, **kwargs)
    
    def create_profile_for_user(sender, instance, created, **kwargs):
        """إشارة لإنشاء ملف شخصي تلقائيًا عند إنشاء مستخدم"""
        if created:
            Profile.objects.create(user=instance)

# إضافة الإشارة
from django.db.models.signals import post_save
post_save.connect(Profile.create_profile_for_user, sender=CustomUser)