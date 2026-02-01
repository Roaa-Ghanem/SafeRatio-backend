from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
import uuid
from datetime import date, timedelta, datetime
from .models import Vehicle, CarInsuranceQuote, CarPolicy, Claim, VehicleDocument, generate_policy_number
# import google.generativeai as genai
from django.conf import settings
from django.http import HttpResponse
from reportlab.pdfgen import canvas
import io
import json
from .static_reports import StaticReportGenerator
# from .reports import InsuranceReportGenerator


from .serializers import (
    VehicleSerializer, VehicleCreateSerializer,
    CarInsuranceQuoteSerializer, CarInsuranceQuoteCreateSerializer,
    CarPolicySerializer, ClaimSerializer, VehicleDocumentSerializer
)
from .calculations import (
    calculate_premium, calculate_short_term_premium,
    calculate_depreciation, create_quote_from_vehicle
)

# Configure Gemini
# genai.configure(api_key=settings.GEMINI_API_KEY)
# model = genai.GenerativeModel('gemini-1.5-flash')

class VehicleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return VehicleCreateSerializer
        return VehicleSerializer
    
    def get_queryset(self):
        return Vehicle.objects.filter(user=self.request.user).order_by('-created_at')
    
    def perform_create(self, serializer):
        # إضافة المستخدم قبل الحفظ
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        try:
            # استخدم السيريالايزر المناسب مع تمرير السياق
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            return Response({
                'success': True,
                'message': 'تم إضافة المركبة بنجاح',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except serializer.ValidationError as e:
            return Response({
                'success': False,
                'message': 'خطأ في التحقق من البيانات',
                'errors': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'حدث خطأ: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def quotes(self, request, pk=None):
        """Get all quotes for a vehicle"""
        vehicle = self.get_object()
        quotes = CarInsuranceQuote.objects.filter(vehicle=vehicle, user=request.user)
        serializer = CarInsuranceQuoteSerializer(quotes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def calculate_premium(self, request, pk=None):
        """Calculate premium for this vehicle"""
        vehicle = self.get_object()
        
        # Get calculation parameters
        coverage_type = request.query_params.get('coverage_type', 'comprehensive')
        driver_age = int(request.query_params.get('driver_age', 30))
        claims_history = int(request.query_params.get('claims_history', 0))
        no_claims_years = int(request.query_params.get('no_claims_years', 0))
        
        # Calculate premium
        premium_result = calculate_premium(
            vehicle=vehicle,
            coverage_type=coverage_type,
            driver_age=driver_age,
            claims_history=claims_history,
            no_claims_years=no_claims_years
        )
        
        # Add vehicle info to result
        result = {
            'vehicle': {
                'id': vehicle.id,
                'make': vehicle.make,
                'model': vehicle.model,
                'year': vehicle.year,
                'license_plate': vehicle.license_plate,
                'current_value': str(vehicle.current_value)
            },
            'calculation_parameters': {
                'coverage_type': coverage_type,
                'driver_age': driver_age,
                'claims_history': claims_history,
                'no_claims_years': no_claims_years
            },
            **premium_result
        }
        
        return Response(result)

    
    @action(detail=True, methods=['post'])
    def create_quote(self, request, pk=None):
        """Create an insurance quote for this vehicle"""
        vehicle = self.get_object()
        
        # Get quote parameters
        coverage_type = request.data.get('coverage_type', 'comprehensive')
        driver_age = int(request.data.get('driver_age', 30))
        claims_history = int(request.data.get('claims_history', 0))
        no_claims_years = int(request.data.get('no_claims_years', 0))
        
        # Create quote
        quote, premium_result = create_quote_from_vehicle(
            vehicle=vehicle,
            user=request.user,
            coverage_type=coverage_type,
            driver_age=driver_age,
            claims_history=claims_history,
            no_claims_years=no_claims_years
        )
        
        serializer = CarInsuranceQuoteSerializer(quote)
        return Response({
            'quote': serializer.data,
            'premium_breakdown': premium_result
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def generate_detailed_report(self, request, pk=None):
        """Generate comprehensive static report"""
        try:
            quote = self.get_object()
            
            # التحقق من الصلاحيات
            if quote.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'ليس لديك صلاحية للوصول إلى هذا التقرير'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # إنشاء التقرير الثابت
            report_data = StaticReportGenerator.generate_comprehensive_report(quote)
            
            format_type = request.query_params.get('format', 'html')
            
            if format_type == 'pdf':
                # يمكن إضافة PDF لاحقاً
                return Response({
                    'message': 'PDF generation will be available soon',
                    'html_report': report_data
                })
                
            elif format_type == 'html':
                # إرجاع HTML للعرض في المتصفح
                return Response({
                    'success': True,
                    'report_type': 'static_comprehensive',
                    'report_html': report_data.get('report_html', ''),
                    'report_data': report_data.get('report_data', {}),
                    'quote_info': {
                        'quote_number': quote.quote_number,
                        'vehicle': f"{quote.vehicle.make} {quote.vehicle.model}",
                        'coverage_type': quote.get_coverage_type_display(),
                        'premium': str(quote.final_premium)
                    }
                })
                
            else:  # JSON افتراضي
                return Response(report_data)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'فشل في إنشاء التقرير'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=False, methods=['get'])
    def compare_quotes(self, request):
        """Compare multiple quotes and generate comparison report"""
        try:
            quote_ids = request.query_params.get('quote_ids', '').split(',')
            
            # تحقق من وجود IDs
            if not quote_ids or quote_ids[0] == '':
                return Response({
                    'error': 'يرجى تقديم معرّفات الاقتباسات للمقارنة',
                    'example': '/api/car-insurance/quotes/compare_quotes/?quote_ids=1,2,3'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # تحويل IDs إلى أعداد صحيحة
            try:
                quote_ids = [int(qid.strip()) for qid in quote_ids if qid.strip()]
            except ValueError:
                return Response({
                    'error': 'معرّفات الاقتباسات يجب أن تكون أرقاماً صحيحة'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # الحصول على الاقتباسات مع بيانات المركبات
            quotes = CarInsuranceQuote.objects.filter(
                id__in=quote_ids,
                user=request.user
            ).select_related('vehicle')
            
            if not quotes.exists():
                return Response({
                    'error': 'لا توجد اقتباسات مطابقة للمعرّفات المقدمة',
                    'requested_ids': quote_ids,
                    'found_ids': list(quotes.values_list('id', flat=True))
                }, status=status.HTTP_404_NOT_FOUND)
            
            # إذا كان عدد الاقتباسات المطلوبة أكبر مما وجد
            if len(quotes) < len(quote_ids):
                found_ids = list(quotes.values_list('id', flat=True))
                missing_ids = [qid for qid in quote_ids if qid not in found_ids]
                
                return Response({
                    'warning': f'تم العثور على {len(quotes)} من أصل {len(quote_ids)} اقتباس',
                    'missing_ids': missing_ids,
                    'found_ids': found_ids,
                    'message': 'سيتم مقارنة الاقتباسات المتاحة فقط'
                }, status=status.HTTP_206_PARTIAL_CONTENT)
            
            comparison_data = []
            all_reports = []
            
            for quote in quotes:
                # توليد تقرير لكل اقتباس باستخدام النظام الثابت
                report = StaticReportGenerator.generate_comprehensive_report(quote)
                report_data = report.get('report_data', {})
                
                # استخراج تحليل المخاطر
                risk_analysis = report_data.get('analyses', {})
                market_comparison = report_data.get('market_comparison', {})
                
                # تحليل المخاطر بشكل تفصيلي
                risk_score = self._calculate_risk_score(risk_analysis)
                
                comparison_data.append({
                    'quote_id': quote.id,
                    'quote_number': quote.quote_number,
                    'vehicle': {
                        'id': quote.vehicle.id,
                        'make': quote.vehicle.make,
                        'model': quote.vehicle.model,
                        'year': quote.vehicle.year,
                        'license_plate': quote.vehicle.license_plate,
                        'value': float(quote.vehicle.current_value or 0)
                    },
                    'coverage': {
                        'type': quote.coverage_type,
                        'display_name': quote.get_coverage_type_display(),
                        'coverage_analysis': report_data.get('coverage_analysis', {})
                    },
                    'financial': {
                        'premium': float(quote.final_premium or 0),
                        'excess': float(quote.excess_amount or 0),
                        'monthly_premium': float(quote.final_premium or 0) / 12,
                        'market_comparison': market_comparison
                    },
                    'risk_analysis': {
                        'overall_risk': report_data.get('overall_risk', 'غير متوفر'),
                        'risk_score': risk_score,
                        'vehicle_age_risk': risk_analysis.get('vehicle_age', {}).get('risk', 'غير متوفر'),
                        'engine_risk': risk_analysis.get('engine_size', {}).get('risk', 'غير متوفر'),
                        'value_risk': risk_analysis.get('vehicle_value', {}).get('risk', 'غير متوفر'),
                        'claims_risk': risk_analysis.get('claims_history', {}).get('risk', 'غير متوفر'),
                        'risk_factors': report_data.get('risk_notes', [])
                    },
                    'discounts': {
                        'no_claims_discount': report_data.get('analyses', {}).get('no_claims_years', {}).get('discount_percent', 0),
                        'no_claims_years': quote.no_claims_years
                    },
                    'summary': self._generate_quote_summary(quote, report_data),
                    'best_for': self._determine_best_use_case(quote, report_data)
                })
                
                all_reports.append(report)
            
            # فرز حسب معايير مختلفة
            sorted_by_premium = sorted(comparison_data, key=lambda x: x['financial']['premium'])
            sorted_by_risk = sorted(comparison_data, key=lambda x: x['risk_analysis']['risk_score'])
            sorted_by_value = sorted(comparison_data, key=lambda x: x['vehicle']['value'])
            
            # تحليل مقارن شامل
            comparison_analysis = self._analyze_comparison(comparison_data)
            
            # التوصيات
            recommendations = self._generate_comparison_recommendations(comparison_data)
            
            return Response({
                'success': True,
                'metadata': {
                    'total_quotes': len(comparison_data),
                    'compared_ids': quote_ids,
                    'generated_at': datetime.now().isoformat(),
                    'comparison_id': f"CMP-{'-'.join(str(qid) for qid in quote_ids)}"
                },
                'comparison_data': comparison_data,
                'sorted_results': {
                    'by_premium': sorted_by_premium,
                    'by_risk': sorted_by_risk,
                    'by_value': sorted_by_value
                },
                'analysis': comparison_analysis,
                'recommendations': recommendations,
                'best_options': {
                    'best_price': sorted_by_premium[0] if sorted_by_premium else None,
                    'best_risk': sorted_by_risk[0] if sorted_by_risk else None,
                    'best_value': self._find_best_value_option(comparison_data)
                }
            })
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Compare quotes error: {error_details}")
            
            return Response({
                'success': False,
                'error': str(e),
                'details': 'فشل في مقارنة الاقتباسات',
                'debug_info': {
                    'quote_ids': request.query_params.get('quote_ids', ''),
                    'user': request.user.id
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _calculate_risk_score(self, risk_analysis):
        """Calculate numeric risk score from analysis"""
        risk_mapping = {
            'منخفض جداً': 1,
            'منخفض': 2,
            'متوسط': 3,
            'مرتفع قليلاً': 4,
            'مرتفع': 5,
            'مرتفع جداً': 6
        }
        
        scores = []
        for key in ['vehicle_age', 'engine_size', 'vehicle_value', 'claims_history']:
            analysis = risk_analysis.get(key, {})
            risk_level = analysis.get('risk', 'متوسط')
            scores.append(risk_mapping.get(risk_level, 3))
        
        return sum(scores) / len(scores) if scores else 3

    def _generate_quote_summary(self, quote, report_data):
        """Generate summary for each quote"""
        vehicle = quote.vehicle
        market = report_data.get('market_comparison', {})
        
        summaries = []
        
        # ملخص التكلفة
        if market.get('difference_percent', 0) < -10:
            summaries.append(f"سعر ممتاز (أقل من السوق بمقدار {abs(market.get('difference_percent', 0))}%)")
        elif market.get('difference_percent', 0) > 20:
            summaries.append(f"سعر مرتفع (أعلى من السوق بمقدار {market.get('difference_percent', 0)}%)")
        else:
            summaries.append("سعر معقول مقارنة بالسوق")
        
        # ملخص التغطية
        coverage_type = quote.get_coverage_type_display()
        if coverage_type == 'تأمين شامل':
            summaries.append("تغطية شاملة للمخاطر")
        elif coverage_type == 'تأمين الطرف الثالث مع الحريق والسرقة':
            summaries.append("تغطية متوسطة مع حماية من الحريق والسرقة")
        else:
            summaries.append("تغطية أساسية للطرف الثالث")
        
        # ملخص المخاطر
        overall_risk = report_data.get('overall_risk', 'متوسط')
        if overall_risk in ['مرتفع', 'مرتفع جداً']:
            summaries.append("مستوى خطر مرتفع يتطلب احتياطات إضافية")
        elif overall_risk in ['منخفض', 'منخفض جداً']:
            summaries.append("مستوى خطر منخفض، مركبة آمنة")
        
        return " | ".join(summaries)

    def _determine_best_use_case(self, quote, report_data):
        """Determine best use case for this quote"""
        vehicle = quote.vehicle
        premium = float(quote.final_premium or 0)
        coverage_type = quote.coverage_type
        
        use_cases = []
        
        if coverage_type == 'third_party' and premium < 800:
            use_cases.append("مثالي للمركبات القديمة أو منخفضة القيمة")
        
        if coverage_type == 'comprehensive' and premium > 1500:
            use_cases.append("مناسب للمركبات الجديدة أو مرتفعة القيمة")
        
        if quote.no_claims_years >= 5:
            use_cases.append("مثالي للسائقين المتميزين بدون مطالبات")
        
        if float(vehicle.current_value or 0) > 50000:
            use_cases.append("يناسب المركبات الفاخرة")
        elif float(vehicle.current_value or 0) < 20000:
            use_cases.append("اقتصادي للمركبات الاقتصادية")
        
        return use_cases[:3]  # أول 3 استخدامات فقط

    def _analyze_comparison(self, comparison_data):
        """Analyze the comparison results"""
        if not comparison_data:
            return {}
        
        # إحصائيات
        premiums = [item['financial']['premium'] for item in comparison_data]
        risk_scores = [item['risk_analysis']['risk_score'] for item in comparison_data]
        
        analysis = {
            'price_range': {
                'min': min(premiums),
                'max': max(premiums),
                'average': sum(premiums) / len(premiums),
                'range': max(premiums) - min(premiums)
            },
            'risk_range': {
                'min_risk': min(risk_scores),
                'max_risk': max(risk_scores),
                'average_risk': sum(risk_scores) / len(risk_scores)
            },
            'coverage_distribution': {},
            'insights': []
        }
        
        # توزيع أنواع التغطية
        coverage_counts = {}
        for item in comparison_data:
            cov_type = item['coverage']['type']
            coverage_counts[cov_type] = coverage_counts.get(cov_type, 0) + 1
        
        analysis['coverage_distribution'] = coverage_counts
        
        # إحصاءات المخاطر
        risk_levels = {'منخفض': 0, 'متوسط': 0, 'مرتفع': 0}
        for item in comparison_data:
            risk = item['risk_analysis']['overall_risk']
            if 'منخفض' in risk:
                risk_levels['منخفض'] += 1
            elif 'مرتفع' in risk:
                risk_levels['مرتفع'] += 1
            else:
                risk_levels['متوسط'] += 1
        
        analysis['risk_distribution'] = risk_levels
        
        # تحليل العلاقة بين السعر والمخاطر
        price_risk_correlation = []
        for item in comparison_data:
            price_risk_correlation.append({
                'quote_id': item['quote_id'],
                'premium': item['financial']['premium'],
                'risk_score': item['risk_analysis']['risk_score'],
                'value_ratio': item['vehicle']['value'] / max(item['financial']['premium'], 1)
            })
        
        analysis['price_risk_correlation'] = price_risk_correlation
        
        # استنتاجات
        if analysis['price_range']['range'] > 1000:
            analysis['insights'].append("فروق سعرية كبيرة بين الاقتباسات - فرصة للتوفير")
        
        if risk_levels['مرتفع'] > len(comparison_data) / 2:
            analysis['insights'].append("معظم الاقتباسات لمستويات خطر مرتفعة")
        
        return analysis

    def _generate_comparison_recommendations(self, comparison_data):
        """Generate recommendations based on comparison"""
        recommendations = []
        
        if len(comparison_data) < 2:
            return ["أضف المزيد من الاقتباسات لمقارنة أفضل"]
        
        # العثور على أرخص اقتباس
        cheapest = min(comparison_data, key=lambda x: x['financial']['premium'])
        most_expensive = max(comparison_data, key=lambda x: x['financial']['premium'])
        
        price_difference = most_expensive['financial']['premium'] - cheapest['financial']['premium']
        price_difference_percent = (price_difference / cheapest['financial']['premium']) * 100
        
        if price_difference_percent > 30:
            recommendations.append(
                f"هناك فرق سعري كبير ({price_difference_percent:.1f}%) - {cheapest['quote_number']} أرخص بكثير"
            )
        
        # مقارنة المخاطر
        lowest_risk = min(comparison_data, key=lambda x: x['risk_analysis']['risk_score'])
        highest_risk = max(comparison_data, key=lambda x: x['risk_analysis']['risk_score'])
        
        if lowest_risk['quote_id'] != cheapest['quote_id']:
            recommendations.append(
                f"للحصول على أفضل سعر: {cheapest['quote_number']}، ولأقل مخاطر: {lowest_risk['quote_number']}"
            )
        
        # تحليل القيمة
        best_value = self._find_best_value_option(comparison_data)
        if best_value:
            recommendations.append(
                f"أفضل قيمة مقابل السعر: {best_value['quote_number']} (نسبة قيمة/قسط ممتازة)"
            )
        
        # توصيات عامة
        recommendations.append("قارن بين التغطيات المتاحة لكل اقتباس")
        recommendations.append("تأكد من أن مبلغ التحمل مناسب لميزانيتك")
        recommendations.append("ضع في اعتبارك سنوات عدم المطالبات عند الاختيار")
        
        return recommendations

    def _find_best_value_option(self, comparison_data):
        """Find the best value for money option"""
        if not comparison_data:
            return None
        
        # حساب نسبة القيمة إلى السعر
        value_scores = []
        for item in comparison_data:
            if item['financial']['premium'] > 0:
                value_score = item['vehicle']['value'] / item['financial']['premium']
                risk_adjusted = value_score / max(item['risk_analysis']['risk_score'], 0.1)
                value_scores.append({
                    'item': item,
                    'value_score': value_score,
                    'risk_adjusted_score': risk_adjusted
                })
        
        if not value_scores:
            return None
        
        # العثور على أفضل قيمة مع تعديل المخاطر
        best_value = max(value_scores, key=lambda x: x['risk_adjusted_score'])
        return best_value['item']
    
    def _get_best_recommendation(self, comparison_data):
        """Get AI-powered recommendation for best quote"""
        if not comparison_data:
            return "لا توجد بيانات كافية للتوصية"
        
        # أبسط توصية بناءً على السعر ومستوى الخطر
        best_by_price = min(comparison_data, key=lambda x: x['premium'])
        best_by_risk = min(comparison_data, key=lambda x: 
           0 if x['risk_level'] == 'منخفض' else 
           1 if x['risk_level'] == 'متوسط' else 2)
        
        if best_by_price['quote_id'] == best_by_risk['quote_id']:
            return f"الاقتباس {best_by_price['quote_number']} هو الأفضل من حيث السعر ومستوى المخاطر"
        else:
            return f"للحصول على أفضل سعر: {best_by_price['quote_number']}، ولأقل مخاطر: {best_by_risk['quote_number']}"

class CarInsuranceQuoteViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create']:
            return CarInsuranceQuoteCreateSerializer
        return CarInsuranceQuoteSerializer
    
    def get_queryset(self):
        return CarInsuranceQuote.objects.filter(user=self.request.user).order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    # In car_insurance/views.py
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Accept an insurance quote and create a policy
        """
        try:
            # Get the quote
            quote = CarInsuranceQuote.objects.get(
                id=pk, 
                user=request.user, 
                status='quoted'
            )
            
            # Create policy from quote
            policy = CarPolicy.objects.create(
                quote=quote,
                user=request.user,
                vehicle=quote.vehicle,
                policy_number=generate_policy_number(),
                status='pending',
                total_premium=quote.final_premium,
                paid_amount=0,
                payment_status='pending'
            )
            
            # Update quote status
            quote.status = 'accepted'
            quote.save()
            
            # Generate policy document
            try:
                policy_data = policy.generate_policy_document()
                
                # Update policy with generated data
                policy.document_url = f'policy_documents/policy_{policy.policy_number}.pdf'
                policy.save()
            except Exception as e:
                # Log the error but don't fail the acceptance
                print(f"Error generating policy document: {e}")
            
            # Return success response
            return Response({
                'success': True,
                'message': 'Quote accepted successfully. Policy created.',
                'policy': {
                    'id': policy.id,
                    'policy_number': policy.policy_number,  # Use the actual policy number
                    'status': policy.status,
                    'inception_date': policy.inception_date,
                    'expiry_date': policy.expiry_date,
                    'total_premium': str(policy.total_premium),
                    'vehicle': {
                        'make': quote.vehicle.make,
                        'model': quote.vehicle.model,
                        'license_plate': quote.vehicle.license_plate
                    },
                    'coverage_type': quote.get_coverage_type_display(),
                    'certificate_url': f'/api/car-insurance/policies/{policy.id}/certificate/',
                    'policy_document_url': f'/api/car-insurance/policies/{policy.id}/document/'
                }
            })
            
        except CarInsuranceQuote.DoesNotExist:
            return Response(
                {'error': 'Quote not found or already accepted'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error accepting quote: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _send_acceptance_notification(self, user, quote, policy):
        """Send notification to user about quote acceptance"""
        # يمكن إرسال بريد إلكتروني أو إشعار في التطبيق
        print(f"Notification: User {user.email} accepted quote {quote.quote_number}")
        print(f"Policy created: {policy.policy_number}")
        # هنا يمكن إضافة إرسال بريد إلكتروني فعلي
    
    @action(detail=True, methods=['get'])
    def short_term_calculation(self, request, pk=None):
        """Calculate short-term premium for this quote"""
        quote = self.get_object()
        duration_days = int(request.query_params.get('duration_days', 30))
        
        short_term_premium = calculate_short_term_premium(
            annual_premium=float(quote.final_premium),
            duration_days=duration_days
        )
        
        return Response({
            'quote_id': quote.id,
            'annual_premium': float(quote.final_premium),
            'duration_days': duration_days,
            'short_term_premium': short_term_premium
        })

class CarPolicyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CarPolicySerializer
    
    def get_queryset(self):
        # Get policies for user's quotes
        user_quotes = CarInsuranceQuote.objects.filter(user=self.request.user)
        return CarPolicy.objects.filter(quote__in=user_quotes).order_by('-created_at')
    
    @action(detail=True, methods=['get'])
    def claims(self, request, pk=None):
        """Get all claims for this policy"""
        policy = self.get_object()
        claims = Claim.objects.filter(policy=policy)
        serializer = ClaimSerializer(claims, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """Renew an insurance policy"""
        policy = self.get_object()
        
        if policy.status != 'active':
            return Response(
                {'error': 'Only active policies can be renewed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new quote based on original quote
        original_quote = policy.quote
        
        # Create new quote with updated dates
        new_quote, premium_result = create_quote_from_vehicle(
            vehicle=original_quote.vehicle,
            user=request.user,
            coverage_type=original_quote.coverage_type,
            driver_age=original_quote.driver_age,
            claims_history=original_quote.claims_history,
            no_claims_years=original_quote.no_claims_years + 1  # Add one more year of no claims
        )
        
        # Mark old policy as expired
        policy.status = 'expired'
        policy.save()
        
        return Response({
            'new_quote': CarInsuranceQuoteSerializer(new_quote).data,
            'premium_breakdown': premium_result,
            'message': 'Policy renewal quote created successfully'
        })
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active policies"""
        active_policies = self.get_queryset().filter(status='active')
        serializer = self.get_serializer(active_policies, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get policies expiring in the next 30 days"""
        from datetime import timedelta
        today = date.today()
        next_month = today + timedelta(days=30)
        
        expiring_policies = self.get_queryset().filter(
            status='active',
            expiry_date__range=[today, next_month]
        )
        serializer = self.get_serializer(expiring_policies, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def certificate(self, request, pk=None):
        """Generate policy certificate PDF"""
        policy = self.get_object()
        
        # إنشاء PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer)
        
        # محتوى الشهادة
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 800, "شهادة تأمين مركبة")
        
        p.setFont("Helvetica", 12)
        p.drawString(100, 770, f"رقم الوثيقة: {policy.policy_number}")
        p.drawString(100, 750, f"اسم المؤمن له: {policy.user.get_full_name()}")
        p.drawString(100, 730, f"المركبة: {policy.vehicle}")
        p.drawString(100, 710, f"فترة التغطية: {policy.inception_date} إلى {policy.expiry_date}")
        p.drawString(100, 690, f"القسط الإجمالي: ${policy.total_premium}")
        p.drawString(100, 670, f"مبلغ التحمل: ${policy.quote.excess_amount}")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')
    
    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """Get comprehensive policy report"""
        policy = self.get_object()
        
        # إنشاء تقرير شامل للوثيقة
        # report_data = StaticReportGenerator.generate_policy_report(policy)
        
        format_type = request.query_params.get('format', 'html')
        
        if format_type == 'pdf':
            # إنشاء PDF
            pdf_file = StaticReportGenerator.create_policy_pdf(policy, report_data)
            
            with open(pdf_file, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/pdf')
                filename = f"وثيقة_تأمين_{policy.policy_number}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
                
        else:
            return Response({
                'success': True,
                'policy': {
                    'number': policy.policy_number,
                    'status': policy.get_status_display(),
                    'dates': {
                        'start': policy.inception_date,
                        'end': policy.expiry_date,
                        'duration_days': 365
                    },
                    'financial': {
                        'total_premium': str(policy.total_premium),
                        'monthly_premium': str(policy.total_premium / 12),
                        'excess_amount': str(policy.quote.excess_amount)
                    },
                    'coverage': {
                        'type': policy.quote.get_coverage_type_display(),
                        'details': StaticReportGenerator.analyze_coverage(policy.quote.coverage_type)
                    }
                },
                'report': report_data
            })

class ClaimViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ClaimSerializer
    
    def get_queryset(self):
        # Get claims for user's policies
        user_quotes = CarInsuranceQuote.objects.filter(user=self.request.user)
        user_policies = CarPolicy.objects.filter(quote__in=user_quotes)
        return Claim.objects.filter(policy__in=user_policies).order_by('-claim_date')
    
    def perform_create(self, serializer):
        # Generate claim number
        claim_number = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        serializer.save(claim_number=claim_number)
    
    @action(detail=True, methods=['post'])
    def calculate_settlement(self, request, pk=None):
        """Calculate claim settlement amount with depreciation"""
        claim = self.get_object()
        
        # Get vehicle details from policy
        vehicle = claim.policy.quote.vehicle
        vehicle_year = vehicle.year
        vehicle_value = float(vehicle.current_value)
        loss_type = request.data.get('loss_type', 'partial')
        
        # Calculate depreciation
        depreciation_result = calculate_depreciation(
            vehicle_value=vehicle_value,
            vehicle_year=vehicle_year,
            loss_type=loss_type
        )
        
        # Calculate settlement (considering excess)
        excess_amount = float(claim.policy.quote.excess_amount)
        settlement_amount = max(
            depreciation_result['depreciated_value'] - excess_amount,
            0
        )
        
        return Response({
            'claim_id': claim.id,
            'estimated_loss': float(claim.estimated_amount),
            'depreciation_calculation': depreciation_result,
            'excess_amount': excess_amount,
            'proposed_settlement': settlement_amount,
            'notes': 'Amount is subject to policy terms and conditions'
        })

class PremiumCalculatorView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Standalone premium calculator"""
        data = request.data
        
        # Validate required fields
        required_fields = ['vehicle_type', 'year', 'current_value', 'coverage_type']
        for field in required_fields:
            if field not in data:
                return Response(
                    {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create a mock vehicle object
        class MockVehicle:
            def __init__(self, data):
                self.vehicle_type = data.get('vehicle_type', 'car')
                self.year = int(data.get('year', date.today().year))
                self.current_value = float(data.get('current_value', 10000.00))
                self.engine_size = float(data.get('engine_size', 1.6))
                self.make = data.get('make', 'Generic')
                self.model = data.get('model', 'Vehicle')
        
        mock_vehicle = MockVehicle(data)
        
        # Get calculation parameters
        coverage_type = data.get('coverage_type', 'comprehensive')
        driver_age = int(data.get('driver_age', 30))
        claims_history = int(data.get('claims_history', 0))
        no_claims_years = int(data.get('no_claims_years', 0))
        
        # Calculate premium
        premium_result = calculate_premium(
            vehicle=mock_vehicle,
            coverage_type=coverage_type,
            driver_age=driver_age,
            claims_history=claims_history,
            no_claims_years=no_claims_years
        )
        
        # Add input parameters to result
        result = {
            'input_parameters': {
                'vehicle_type': mock_vehicle.vehicle_type,
                'year': mock_vehicle.year,
                'current_value': mock_vehicle.current_value,
                'coverage_type': coverage_type,
                'driver_age': driver_age,
                'claims_history': claims_history,
                'no_claims_years': no_claims_years
            },
            **premium_result
        }
        
        return Response(result)

# Vehicle Document Views
class VehicleDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = VehicleDocumentSerializer
    
    def get_queryset(self):
        # Get documents for user's vehicles
        user_vehicles = Vehicle.objects.filter(user=self.request.user)
        return VehicleDocument.objects.filter(vehicle__in=user_vehicles).order_by('-uploaded_at')
    
    def perform_create(self, serializer):
        serializer.save()