from django.apps import AppConfig


class HealthInsuranceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'health_insurance'
    verbose_name = 'التأمين الصحي'
    
    # def ready(self):
    #     """تهيئة التطبيق"""
    #     import health_insurance.signals