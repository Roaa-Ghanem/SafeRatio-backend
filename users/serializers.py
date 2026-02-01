from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
import os
from .models import CustomUser, Profile

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    user_type = serializers.ChoiceField(
        choices=CustomUser.USER_TYPE_CHOICES, 
        required=True,
        initial='individual'
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password', 'password2', 'first_name', 'last_name', 'user_type', 'phone')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        if CustomUser.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({"username": "A user with that username already exists."})
            
        if CustomUser.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "A user with that email already exists."})
            
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        
        defaults = {
            'country': 'Yemen',
            'language': 'ar'
        }
        
        user_data = {**defaults, **validated_data}
        password = user_data.pop('password')
        
        user = CustomUser(**user_data)
        user.set_password(password)
        user.save()
        
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    avatar = serializers.ImageField(write_only=True, required=False, allow_null=True)
    age = serializers.ReadOnlyField()
    profile_completed = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 
            'user_type', 'phone', 'country', 'language', 'date_joined',
            'avatar_url', 'avatar', 'age', 'profile_completed'
        )
        read_only_fields = ('username', 'user_type', 'age', 'profile_completed')

    def get_avatar_url(self, obj):
        """الحصول على رابط الصورة الشخصية"""
        if obj.avatar:
            # في التطوير
            if self.context.get('request'):
                return self.context['request'].build_absolute_uri(obj.avatar.url)
            # أو الرابط المباشر
            return f"http://localhost:8000{obj.avatar.url}"
        return None
    
        def update(self, instance, validated_data):
            avatar = validated_data.pop('avatar', None)
            
            # تحديث البيانات الأخرى
            instance = super().update(instance, validated_data)
            
            # تحديث الصورة إذا تم رفعها
            if avatar is not None:
                # احذف الصورة القديمة إذا كانت موجودة
                if instance.avatar:
                    old_avatar_path = instance.avatar.path
                    if os.path.exists(old_avatar_path):
                        os.remove(old_avatar_path)
                
                # احفظ الصورة الجديدة
                instance.avatar = avatar
                instance.save()
            
            return instance

    def validate_avatar(self, value):
        """التحقق من صحة الصورة المرفوعة"""
        if value:
            # التحقق من حجم الملف
            max_size = 5 * 1024 * 1024  # 5MB
            if value.size > max_size:
                raise serializers.ValidationError(
                    'حجم الصورة كبير جداً. الحد الأقصى 5 ميجابايت.'
                )
            
            # التحقق من نوع الملف
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/jpg']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError(
                    'نوع الملف غير مدعوم. يرجى رفع صورة بصيغة JPG, PNG أو GIF.'
                )
            
            # التحقق من امتداد الملف
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in valid_extensions:
                raise serializers.ValidationError(
                    'امتداد الملف غير مدعوم. يرجى رفع صورة بصيغة JPG, PNG أو GIF.'
                )
        
        return value

class SensitiveInfoSerializer(serializers.ModelSerializer):
    """سيريالايزر للمعلومات الحساسة (الإدخال الأول فقط)"""
    
    class Meta:
        model = Profile
        fields = ['date_of_birth', 'driving_license_number', 'driving_license_issue_date', 'national_id', 'gender']
    
    def validate_date_of_birth(self, value):
        if value:
            # تحقق أن تاريخ الميلاد ليس في المستقبل
            if value > timezone.now().date():
                raise serializers.ValidationError("تاريخ الميلاد لا يمكن أن يكون في المستقبل")
            
            # تحقق أن العمر أكبر من 18 سنة
            age = timezone.now().date().year - value.year - (
                (timezone.now().date().month, timezone.now().date().day) < (value.month, value.day)
            )
            
            if age < 18:
                raise serializers.ValidationError("يجب أن يكون عمر المستخدم 18 سنة على الأقل")
            
            if age > 100:
                raise serializers.ValidationError("يرجى التحقق من تاريخ الميلاد")
        
        return value
    
    def validate_driving_license_number(self, value):
        if value and len(value) < 5:
            raise serializers.ValidationError("رقم رخصة القيادة يجب أن يحتوي على 5 أحرف على الأقل")
        return value
    
    def validate(self, data):
        # تأكد من وجود الحقول المطلوبة للإدخال الأول
        required_fields = ['date_of_birth', 'driving_license_number']
        
        for field in required_fields:
            if field not in data or not data[field]:
                raise serializers.ValidationError({
                    field: "هذا الحقل مطلوب لإكمال ملفك الشخصي"
                })
        
        # تحقق إذا كانت المعلومات مقفلة بالفعل
        if self.instance and self.instance.sensitive_info_locked:
            raise serializers.ValidationError("المعلومات الحساسة مقفلة ولا يمكن تعديلها")
        
        return data

class ProfileSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    age = serializers.ReadOnlyField()
    sensitive_info_completed = serializers.ReadOnlyField()
    
    class Meta:
        model = Profile
        fields = '__all__'
        read_only_fields = ('user', 'sensitive_info_locked', 'created_at', 'updated_at')
    
    def validate(self, data):
        # منع تعديل المعلومات الحساسة إذا كانت مقفلة
        if self.instance and self.instance.sensitive_info_locked:
            sensitive_fields = ['date_of_birth', 'driving_license_number', 'national_id']
            
            for field in sensitive_fields:
                if field in data and getattr(self.instance, field):
                    if data[field] != getattr(self.instance, field):
                        raise serializers.ValidationError({
                            field: f"لا يمكن تعديل {field} بعد الإدخال الأول"
                        })
        
        return data

class ProfileUpdateSerializer(serializers.ModelSerializer):
    """سيريالايزر لتحديث المعلومات غير الحساسة فقط"""
    
    class Meta:
        model = Profile
        fields = [
            'gender', 'marital_status', 'occupation',
            'monthly_income', 'monthly_expenses', 'savings', 'debts',
            'smoking_status', 'health_notes'
        ]