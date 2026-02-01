from django.contrib import admin
from .models import Vehicle, CarInsuranceQuote, CarPolicy, Claim, VehicleDocument

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['make', 'model', 'year', 'license_plate', 'user', 'vehicle_type']
    list_filter = ['vehicle_type', 'fuel_type', 'is_commercial', 'created_at']
    search_fields = ['make', 'model', 'license_plate', 'vin']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(CarInsuranceQuote)
class CarInsuranceQuoteAdmin(admin.ModelAdmin):
    list_display = ['quote_number', 'vehicle', 'user', 'coverage_type', 'premium_amount', 'status']
    list_filter = ['coverage_type', 'status', 'created_at']
    search_fields = ['quote_number', 'vehicle__make', 'vehicle__model']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(CarPolicy)
class CarPolicyAdmin(admin.ModelAdmin):
    list_display = ['policy_number', 'quote', 'status', 'inception_date', 'expiry_date']
    list_filter = ['status', 'inception_date', 'expiry_date']
    search_fields = ['policy_number', 'quote__quote_number']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ['claim_number', 'policy', 'claim_date', 'estimated_amount', 'status']
    list_filter = ['status', 'claim_date', 'incident_type']
    search_fields = ['claim_number', 'policy__policy_number']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'document_type', 'uploaded_at', 'valid_until']
    list_filter = ['document_type', 'uploaded_at']
    search_fields = ['vehicle__make', 'vehicle__model']