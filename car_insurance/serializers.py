from rest_framework import serializers
from .models import Vehicle, CarInsuranceQuote, CarPolicy, Claim, VehicleDocument
from users.serializers import UserProfileSerializer

class VehicleSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    driver_age = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ('user', 'created_at', 'updated_at')
        
    def get_driver_age(self, obj):
        return obj.driver_age

class VehicleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'make', 'model', 'year', 'vehicle_type', 'fuel_type',
            'engine_size', 'current_value', 'license_plate', 'annual_mileage',
            'is_commercial', 'vin'
        ]
        extra_kwargs = {
            'claims_history': {'required': False, 'default': 0},
            'driver_age': {'required': False, 'default': 30},
            'no_claims_years': {'required': False, 'default': 0}
        }
    
    def validate(self, data):
        # تحقق من صحة السنة
        from datetime import datetime
        current_year = datetime.now().year
        
        if 'year' in data:
            if data['year'] < 1900 or data['year'] > current_year:
                raise serializers.ValidationError({
                    'year': f'سنة التصنيع يجب أن تكون بين 1900 و {current_year}'
                })
        
        # تحقق من القيمة
        if 'current_value' in data:
            if data['current_value'] <= 0:
                raise serializers.ValidationError({
                    'current_value': 'قيمة المركبة يجب أن تكون أكبر من صفر'
                })
        
        # تحقق من سعة المحرك
        if 'engine_size' in data:
            if data['engine_size'] <= 0:
                raise serializers.ValidationError({
                    'engine_size': 'سعة المحرك يجب أن تكون أكبر من صفر'
                })
        
        # تحقق من المسافة السنوية
        if 'annual_mileage' in data:
            if data['annual_mileage'] < 0:
                raise serializers.ValidationError({
                    'annual_mileage': 'المسافة السنوية لا يمكن أن تكون سالبة'
                })
        
        # جعل vin اختياري
        if 'vin' in data and data['vin']:
            if len(data['vin']) < 10:
                raise serializers.ValidationError({
                    'vin': 'VIN يجب أن يحتوي على 10 أحرف على الأقل'
                })
        
        return data

# بقية السيريالايزرات تبقى كما هي
class CarInsuranceQuoteSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    user = UserProfileSerializer(read_only=True)
    policy_info = serializers.SerializerMethodField()
    
    class Meta:
        model = CarInsuranceQuote
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_policy_info(self, obj):
        """Get basic policy information without circular dependency"""
        if hasattr(obj, 'policy') and obj.policy:
            return {
                'id': obj.policy.id,
                'policy_number': obj.policy.policy_number,
                'status': obj.policy.status,
                'inception_date': obj.policy.inception_date,
                'expiry_date': obj.policy.expiry_date,
                'total_premium': str(obj.policy.total_premium),
                'url': f'/api/car-insurance/policies/{obj.policy.id}/'
            }
        return None

class CarInsuranceQuoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarInsuranceQuote
        fields = '__all__'
        read_only_fields = ('user', 'quote_number', 'base_premium', 'discount_amount', 'final_premium', 'created_at', 'updated_at')

class CarPolicySerializer(serializers.ModelSerializer):
    quote = CarInsuranceQuoteSerializer(read_only=True)
    id = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CarPolicy
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class ClaimSerializer(serializers.ModelSerializer):
    policy = CarPolicySerializer(read_only=True)
    
    class Meta:
        model = Claim
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class VehicleDocumentSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    
    class Meta:
        model = VehicleDocument
        fields = '__all__'
        read_only_fields = ('uploaded_at',)