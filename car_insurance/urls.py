from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'vehicles', views.VehicleViewSet, basename='vehicle')
router.register(r'quotes', views.CarInsuranceQuoteViewSet, basename='quote')
router.register(r'policies', views.CarPolicyViewSet, basename='policy')
router.register(r'claims', views.ClaimViewSet, basename='claim')
router.register(r'reports', views.VehicleDocumentViewSet, basename='reports')

urlpatterns = [
    path('', include(router.urls)),
    path('calculator/', views.PremiumCalculatorView.as_view(), name='premium-calculator'),
    path('api/car-insurance/policies/<int:pk>/certificate/', 
         views.CarPolicyViewSet.as_view({'get': 'certificate'}), 
         name='policy-certificate'),
    # path('quotes/<int:pk>/generate_detailed_report/', 
    #     views.CarInsuranceQuoteViewSet.as_view({'get': 'generate_detailed_report'}), 
    #     name='quote-generate-detailed-report'),
    # path('quotes/compare_quotes/', 
    #     views.CarInsuranceQuoteViewSet.as_view({'get': 'compare_quotes'}),
    #     name='quote-compare-quotes'),
    # path('generate-report/', views.GenerateReportFromPremiumView.as_view(), name='generate-report'),
    # path('api/car-insurance/quotes/<int:pk>/generate_detailed_report/', 
    #     views.CarInsuranceQuoteViewSet.as_view({'get': 'generate_detailed_report'})),
    # path('api/car-insurance/quotes/compare_quotes/', 
    #     views.CarInsuranceQuoteViewSet.as_view({'get': 'compare_quotes'})),
] + router.get_urls()