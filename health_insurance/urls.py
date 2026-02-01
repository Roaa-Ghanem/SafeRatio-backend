# health_insurance/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# تسجيل ViewSets
router.register(r'companies', views.CompanyViewSet, basename='company')
router.register(r'health-coverage-plans', views.HealthCoveragePlanViewSet, basename='health-coverage-plan')
router.register(r'health-insurance-quotes', views.HealthInsuranceQuoteViewSet, basename='health-insurance-quote')
router.register(r'health-insurance-policies', views.HealthInsurancePolicyViewSet, basename='health-insurance-policy')
router.register(r'health-calculation-logs', views.HealthCalculationLogViewSet, basename='health-calculation-log')
# router.register(r'sector-pricing-factors', views.SectorPricingFactor, basename='sector-pricing-factor')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
    
    # حاسبة الأقساط
    path('api/health-premium/calculate/', views.HealthPremiumCalculatorView.as_view(), name='health-premium-calculate'),
    
    # التقارير
    path('api/health-reports/', views.HealthInsuranceReportsView.as_view(), name='health-insurance-reports'),
    
    # لوحة التحكم
    path('api/health-dashboard/', views.HealthInsuranceDashboardView.as_view(), name='health-insurance-dashboard'),
    
    # API endpoints للتحميل والمرفقات (لاحقاً)
#     path('api/health-establishments/<int:pk>/upload-employees/', 
#          views.CompanyViewSet.as_view({'post': 'upload_employees'}), 
#          name='upload-employees'),
    
    # إحصائيات عامة
    path('api/health-insurance/stats/', 
         views.CompanyViewSet.as_view({'get': 'stats'}), 
         name='health-insurance-stats'),
    
    path('api/sectors-data/', views.get_sectors_data, name='sectors-data'),
    path('sectors-data/', views.get_sectors_data, name='sectors-data'),
    path('companies/sectors-data/', views.CompanyViewSet.as_view({'get': 'sectors_data'}), name='companies-sectors-data'),
    path('companies/sectors_data/', views.CompanyViewSet.as_view({'get': 'sectors_data'}), name='companies-sectors-data-underscore'),

#     path('companies/<int:pk>/upload-employees/', 
#          views.CompanyViewSet.as_view({'post': 'upload_employees'}), 
#          name='company-upload-employees'),
    
    path('/<int:pk>/employees/', 
         views.CompanyViewSet.as_view({'post': 'add_employees'}), 
         name='company-add-employees'),
     path('<int:pk>/upload-employees/', 
         views.CompanyViewSet.as_view({'post': 'upload_employees'}), 
         name='company-upload-employees'),
    
    path('/<int:pk>/get-extracted-employees/', 
         views.CompanyViewSet.as_view({'get': 'get_extracted_employees'}), 
         name='company-get-extracted-employees'),
    
    path('/<int:pk>/extract-employees/', 
         views.CompanyViewSet.as_view({'post': 'extract_employees'}), 
         name='company-extract-employees'),
    
    # الحاسبة المتقدمة
    path('advanced-calculate/', 
         views.AdvancedPremiumCalculationView.as_view(), 
         name='advanced-calculate'),
    
    # تنزيل دليل PDF
    path('api/health/download-insurance-guide/', 
         views.DownloadInsuranceGuidePDF.as_view(), 
         name='download-insurance-guide'),
    
    # تحميل قالب Excel المحسن
    path('api/health/download-enhanced-excel-template/', 
         views.download_enhanced_excel_template, 
         name='download-enhanced-excel-template'),

       # قبول ورفض الاقتباسات
    path('health-insurance-quotes/<int:pk>/accept/',
         views.HealthInsuranceQuoteViewSet.as_view({'post': 'accept'}),
         name='health-insurance-quote-accept'),
    
    path('health-insurance-quotes/<int:pk>/reject/',
         views.HealthInsuranceQuoteViewSet.as_view({'post': 'reject'}),
         name='health-insurance-quote-reject'),
     # إنشاء PDF للوثيقة
    path('health-insurance-policies/<int:pk>/generate_pdf/',
         views.HealthInsurancePolicyViewSet.as_view({'get': 'generate_pdf'}),
         name='health-insurance-policy-generate-pdf'),
    
    # إرسال البريد الإلكتروني
    path('health-insurance-policies/<int:pk>/send_email/',
         views.HealthInsurancePolicyViewSet.as_view({'post': 'send_email'}),
         name='health-insurance-policy-send-email'),
    path('health-insurance-policies/<int:pk>/policy_data_for_pdf/',
         views.HealthInsurancePolicyViewSet.as_view({'get': 'policy_data_for_pdf'}),
         name='health-insurance-policy-data-for-pdf'),
    path('health-insurance-policies/<int:pk>/generate_and_save_pdf/',
         views.HealthInsurancePolicyViewSet.as_view({'post': 'generate_and_save_pdf'}),
         name='health-insurance-policy-generate-save-pdf'),
    # معلومات PDF المحفوظ
    path('health-insurance-policies/<int:pk>/get_pdf_info/',
         views.HealthInsurancePolicyViewSet.as_view({'get': 'get_pdf_info'}),
         name='health-insurance-policy-get-pdf-info'),
    # تحميل PDF من قاعدة البيانات
    path('health-insurance-policies/<int:pk>/download_pdf/',
         views.HealthInsurancePolicyViewSet.as_view({'get': 'download_pdf'}),
         name='health-insurance-policy-download-pdf'),
]


# Health URLs الرئيسية للتطبيق
# health_urls = [
#     path('api/health/', include(urlpatterns)),
# ]