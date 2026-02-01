# car_insurance/static_reports.py
import json
import re
import tempfile
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

class StaticReportGenerator:
    """Generate static insurance reports based on rules and inputs"""
    
    # قواعد وتصنيفات المخاطر
    RISK_RULES = {
        'vehicle_age': {
            (0, 3): {'risk': 'منخفض', 'factor': 0.9, 'note': 'مركبة جديدة'},
            (4, 7): {'risk': 'متوسط', 'factor': 1.0, 'note': 'مركبة حديثة'},
            (8, 12): {'risk': 'مرتفع قليلاً', 'factor': 1.2, 'note': 'مركبة متوسطة العمر'},
            (13, 20): {'risk': 'مرتفع', 'factor': 1.4, 'note': 'مركبة قديمة'},
            (21, 100): {'risk': 'مرتفع جداً', 'factor': 1.6, 'note': 'مركبة قديمة جداً'}
        },
        'engine_size': {
            (0, 1.5): {'risk': 'منخفض', 'factor': 0.9, 'note': 'محرك صغير'},
            (1.6, 2.5): {'risk': 'متوسط', 'factor': 1.0, 'note': 'محرك متوسط'},
            (2.6, 3.5): {'risk': 'مرتفع قليلاً', 'factor': 1.3, 'note': 'محرك كبير'},
            (3.6, 100): {'risk': 'مرتفع', 'factor': 1.6, 'note': 'محرك كبير جداً'}
        },
        'vehicle_value': {
            (0, 30000): {'risk': 'منخفض', 'factor': 1.0, 'note': 'قيمة منخفضة'},
            (30001, 60000): {'risk': 'متوسط', 'factor': 1.2, 'note': 'قيمة متوسطة'},
            (60001, 100000): {'risk': 'مرتفع قليلاً', 'factor': 1.4, 'note': 'قيمة عالية'},
            (100001, 1000000): {'risk': 'مرتفع', 'factor': 1.6, 'note': 'قيمة مرتفعة جداً'}
        },
        'claims_history': {
            0: {'risk': 'منخفض', 'factor': 0.9, 'note': 'لا توجد مطالبات سابقة'},
            1: {'risk': 'متوسط', 'factor': 1.1, 'note': 'مطالبة واحدة سابقة'},
            2: {'risk': 'مرتفع قليلاً', 'factor': 1.3, 'note': 'مطالبتين سابقتين'},
            3: {'risk': 'مرتفع', 'factor': 1.5, 'note': 'ثلاث مطالبات سابقة'},
            4: {'risk': 'مرتفع جداً', 'factor': 1.8, 'note': 'أربع مطالبات سابقة أو أكثر'}
        }
    }
    
    # متوسطات السوق (بيانات وهمية لأغراض المقارنة)
    MARKET_AVERAGES = {
        'comprehensive': {
            'sedan': 1200,
            'suv': 1500,
            'truck': 1800,
            'luxury': 2500
        },
        'third_party': {
            'sedan': 600,
            'suv': 750,
            'truck': 900,
            'luxury': 1200
        },
        'third_party_fire_theft': {
            'sedan': 800,
            'suv': 1000,
            'truck': 1200,
            'luxury': 1600
        }
    }
    
    # أنواع المركبات
    VEHICLE_TYPES = {
        'sedan': 'سيارة سيدان',
        'suv': 'سيارة دفع رباعي',
        'truck': 'شاحنة',
        'luxury': 'سيارة فاخرة'
    }
    
    @staticmethod
    def generate_comprehensive_report(quote):
        """Generate comprehensive static report"""
        vehicle = quote.vehicle
        user = quote.user
        
        # تحليل البيانات
        analysis = StaticReportGenerator.analyze_vehicle(vehicle, quote)
        
        # إنشاء التقرير
        report_html = StaticReportGenerator.create_report_html(vehicle, quote, analysis, user)
        
        return {
            'success': True,
            'ai_generated': False,
            'report_type': 'static_comprehensive',
            'report_html': report_html,
            'report_data': analysis,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'report_id': f"STATIC-REP-{quote.id}-{datetime.now().strftime('%Y%m%d')}"
        }
    
    @staticmethod
    def analyze_vehicle(vehicle, quote):
        """Analyze vehicle based on rules"""
        current_year = datetime.now().year
        vehicle_age = current_year - vehicle.year
        
        # تحديد نوع المركبة
        vehicle_type = StaticReportGenerator.detect_vehicle_type(vehicle)
        
        # تحليل كل عامل خطر
        analyses = {
            'vehicle_age': StaticReportGenerator.get_risk_analysis('vehicle_age', vehicle_age),
            'engine_size': StaticReportGenerator.get_risk_analysis('engine_size', float(vehicle.engine_size or 1.6)),
            'vehicle_value': StaticReportGenerator.get_risk_analysis('vehicle_value', float(vehicle.current_value or 10000)),
            'claims_history': StaticReportGenerator.get_risk_analysis('claims_history', quote.claims_history),
            'no_claims_years': {
                'years': quote.no_claims_years,
                'discount_percent': min(quote.no_claims_years * 5, 50),
                'note': f"خصم {min(quote.no_claims_years * 5, 50)}% لسنوات عدم المطالبة"
            }
        }
        
        # حساب إجمالي عامل الخطر
        total_risk_factor = 1.0
        risk_notes = []
        
        for key, analysis in analyses.items():
            if 'factor' in analysis:
                total_risk_factor *= analysis['factor']
                risk_notes.append(analysis.get('note', ''))
        
        # تحديد مستوى الخطر العام
        if total_risk_factor < 1.0:
            overall_risk = 'منخفض جداً'
        elif total_risk_factor < 1.2:
            overall_risk = 'منخفض'
        elif total_risk_factor < 1.5:
            overall_risk = 'متوسط'
        elif total_risk_factor < 2.0:
            overall_risk = 'مرتفع'
        else:
            overall_risk = 'مرتفع جداً'
        
        # مقارنة مع السوق
        market_comparison = StaticReportGenerator.compare_with_market(
            quote.coverage_type, 
            vehicle_type, 
            float(quote.final_premium or 0)
        )
        
        # التوصيات بناءً على التحليل
        recommendations = StaticReportGenerator.generate_recommendations(analyses, vehicle, quote)
        
        # نصائح السلامة
        safety_tips = StaticReportGenerator.generate_safety_tips(vehicle_type, vehicle_age)
        
        return {
            'vehicle_type': vehicle_type,
            'vehicle_type_ar': StaticReportGenerator.VEHICLE_TYPES.get(vehicle_type, 'سيارة'),
            'vehicle_age': vehicle_age,
            'analyses': analyses,
            'total_risk_factor': round(total_risk_factor, 2),
            'overall_risk': overall_risk,
            'risk_notes': [note for note in risk_notes if note],
            'market_comparison': market_comparison,
            'recommendations': recommendations,
            'safety_tips': safety_tips,
            'coverage_analysis': StaticReportGenerator.analyze_coverage(quote.coverage_type)
        }
    
    @staticmethod
    def get_risk_analysis(rule_type, value):
        """Get risk analysis based on rules"""
        rules = StaticReportGenerator.RISK_RULES.get(rule_type, {})
        
        for range_val, analysis in rules.items():
            if isinstance(range_val, tuple):
                if range_val[0] <= value <= range_val[1]:
                    return analysis
            elif range_val == value:
                return analysis
        
        # القيمة الافتراضية إذا لم توجد في القواعد
        return {'risk': 'متوسط', 'factor': 1.0, 'note': 'ضمن المعدل الطبيعي'}
    
    @staticmethod
    def detect_vehicle_type(vehicle):
        """Detect vehicle type based on make/model/value"""
        make_lower = vehicle.make.lower() if vehicle.make else ''
        model_lower = vehicle.model.lower() if vehicle.model else ''
        value = float(vehicle.current_value or 0)
        
        # قواعد الاكتشاف
        if any(word in make_lower + model_lower for word in ['range', 'land cruiser', 'lexus', 'mercedes', 'bmw', 'audi']):
            return 'luxury'
        elif any(word in make_lower + model_lower for word in ['truck', 'pickup', 'van', 'bus']):
            return 'truck'
        elif any(word in make_lower + model_lower for word in ['suv', '4x4', 'jeep', 'prado']):
            return 'suv'
        elif value > 80000:
            return 'luxury'
        elif value > 50000:
            return 'suv'
        else:
            return 'sedan'
    
    @staticmethod
    def compare_with_market(coverage_type, vehicle_type, actual_premium):
        """Compare premium with market averages"""
        market_avg = StaticReportGenerator.MARKET_AVERAGES.get(
            coverage_type, 
            StaticReportGenerator.MARKET_AVERAGES['comprehensive']
        ).get(vehicle_type, 1000)
        
        difference = actual_premium - market_avg
        difference_percent = (difference / market_avg * 100) if market_avg > 0 else 0
        
        if difference_percent < -20:
            comparison = 'أقل من السوق بكثير'
            advice = 'سعر ممتاز'
        elif difference_percent < -10:
            comparison = 'أقل من السوق'
            advice = 'سعر جيد'
        elif abs(difference_percent) <= 10:
            comparison = 'مماثل للسوق'
            advice = 'سعر معقول'
        elif difference_percent <= 20:
            comparison = 'أعلى من السوق قليلاً'
            advice = 'يمكن التفاوض'
        else:
            comparison = 'أعلى من السوق بكثير'
            advice = 'يوصى بالمقارنة مع شركات أخرى'
        
        return {
            'market_average': market_avg,
            'actual_premium': actual_premium,
            'difference': round(difference, 2),
            'difference_percent': round(difference_percent, 1),
            'comparison': comparison,
            'advice': advice
        }
    
    @staticmethod
    def generate_recommendations(analyses, vehicle, quote):
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # توصيات بناءً على عمر المركبة
        vehicle_age_analysis = analyses.get('vehicle_age', {})
        if vehicle_age_analysis.get('risk') in ['مرتفع', 'مرتفع جداً']:
            recommendations.append({
                'category': 'الصيانة',
                'title': 'زيادة فترات الصيانة',
                'description': 'نظراً لعمر المركبة، نوصي بتكرار فحوصات الصيانة كل 3 أشهر بدلاً من 6 أشهر',
                'impact': 'يقلل من مخاطر الأعطال المفاجئة'
            })
        
        # توصيات بناءً على سعة المحرك
        engine_analysis = analyses.get('engine_size', {})
        if engine_analysis.get('risk') in ['مرتفع', 'مرتفع جداً']:
            recommendations.append({
                'category': 'الاقتصاد',
                'title': 'تحسين استهلاك الوقود',
                'description': 'المحرك الكبير يستهلك وقوداً أكثر، نوصي بقيادة اقتصادية',
                'impact': 'يوفر في تكاليف الوقود ويقلل الانبعاثات'
            })
        
        # توصيات بناءً على تاريخ المطالبات
        claims_analysis = analyses.get('claims_history', {})
        if claims_analysis.get('risk') in ['مرتفع', 'مرتفع جداً']:
            recommendations.append({
                'category': 'السلامة',
                'title': 'دورة قيادة دفاعية',
                'description': 'نوصي بحضور دورة قيادة دفاعية لتقليل احتمالية الحوادث',
                'impact': 'يحسن مهارات القيادة ويقلل المخاطر'
            })
        
        # توصيات عامة
        recommendations.extend([
            {
                'category': 'التأمين',
                'title': 'زيادة مبلغ التحمل',
                'description': 'يمكن تخفيض القسط الشهري بزيادة مبلغ التحمل (Excess)',
                'impact': 'تخفيض يصل إلى 15% في القسط'
            },
            {
                'category': 'التأمين',
                'title': 'تركيب نظام تتبع',
                'description': 'تركيب نظام تتبع للمركبة يخفض من قسط التأمين',
                'impact': 'تخفيض يصل إلى 10% في القسط'
            },
            {
                'category': 'المركبة',
                'title': 'نظام كاميرات الرجوع الخلفي',
                'description': 'تركيب كاميرات للمساعدة في الرجوع الخلفي يقلل من حوادث الاصطدام',
                'impact': 'يقلل من مطالبات الأضرار البسيطة'
            }
        ])
        
        return recommendations
    
    @staticmethod
    def generate_safety_tips(vehicle_type, vehicle_age):
        """Generate safety tips based on vehicle type and age"""
        tips = []
        
        # نصائح عامة
        tips.append("الالتزام بحدود السرعة المقررة")
        tips.append("استخدام حزام الأمان دائماً")
        tips.append("عدم استخدام الهاتف أثناء القيادة")
        tips.append("الابتعاد عن القيادة في حال التعب")
        
        # نصائح حسب نوع المركبة
        if vehicle_type == 'suv' or vehicle_type == 'truck':
            tips.append("الانتباه لمركز الثقل في المركبات الكبيرة")
            tips.append("زيادة مسافة الأمان مع المركبات الأخرى")
            tips.append("التحقق من ضغط الإطارات بانتظام")
        
        if vehicle_type == 'luxury':
            tips.append("توخي الحذر في أماكن الانتظار العامة")
            tips.append("تفعيل أنظمة الأمان المتقدمة")
            tips.append("تأمين المركبة في أماكن مغلقة عند الإمكان")
        
        # نصائح حسب عمر المركبة
        if vehicle_age > 10:
            tips.append("فحص المكابح بشكل دوري")
            tips.append("التأكد من سلامة نظام التعليق")
            tips.append("مراقبة أداء المحرك عن كثب")
        
        return tips
    
    @staticmethod
    def analyze_coverage(coverage_type):
        """Analyze coverage type"""
        coverages = {
            'third_party': {
                'name': 'تأمين الطرف الثالث',
                'covers': ['أضرار الطرف الآخر', 'إصابة الطرف الآخر', 'تلف ممتلكات الغير'],
                'not_covered': ['أضرار مركبتك', 'سرقة مركبتك', 'حريق مركبتك'],
                'best_for': 'المركبات القديمة أو منخفضة القيمة'
            },
            'third_party_fire_theft': {
                'name': 'تأمين الطرف الثالث مع الحريق والسرقة',
                'covers': ['أضرار الطرف الآخر', 'إصابة الطرف الآخر', 'تلف ممتلكات الغير', 'حريق المركبة', 'سرقة المركبة'],
                'not_covered': ['أضرار مركبتك من حوادث', 'الأعطال الميكانيكية'],
                'best_for': 'معظم المركبات العائلية'
            },
            'comprehensive': {
                'name': 'التأمين الشامل',
                'covers': ['جميع أضرار الطرف الآخر', 'أضرار مركبتك من الحوادث', 'حريق المركبة', 'سرقة المركبة', 'الأضرار الطبيعية'],
                'not_covered': ['التلف الناتج عن الإهمال', 'الأعطال الميكانيكية الطبيعية'],
                'best_for': 'المركبات الجديدة أو مرتفعة القيمة'
            }
        }
        
        return coverages.get(coverage_type, coverages['comprehensive'])
    
    @staticmethod
    def create_report_html(vehicle, quote, analysis, user):
        """Create comprehensive HTML report"""
        
        # تحليل البيانات
        market = analysis['market_comparison']
        coverage = analysis['coverage_analysis']
        
        report_html = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>تقرير تأمين شامل - {vehicle.make} {vehicle.model}</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px; }}
                .report-container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #2c3e50, #3498db); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
                .header .subtitle {{ font-size: 16px; opacity: 0.9; }}
                .meta-info {{ background: #f8f9fa; padding: 20px; border-bottom: 1px solid #ddd; }}
                .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
                .meta-item {{ background: white; padding: 15px; border-radius: 5px; border: 1px solid #e0e0e0; }}
                .meta-label {{ color: #666; font-size: 14px; margin-bottom: 5px; }}
                .meta-value {{ font-weight: bold; color: #2c3e50; }}
                .section {{ padding: 30px; border-bottom: 1px solid #eee; }}
                .section:last-child {{ border-bottom: none; }}
                .section-title {{ color: #2c3e50; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #3498db; font-size: 22px; }}
                .risk-badge {{ display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; margin: 5px; }}
                .risk-low {{ background: #d4edda; color: #155724; }}
                .risk-medium {{ background: #fff3cd; color: #856404; }}
                .risk-high {{ background: #f8d7da; color: #721c24; }}
                .comparison-card {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 15px 0; border-right: 4px solid #3498db; }}
                .recommendation-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                .recommendation-card {{ background: white; border-radius: 8px; padding: 20px; border: 1px solid #e0e0e0; transition: transform 0.3s; }}
                .recommendation-card:hover {{ transform: translateY(-5px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
                .rec-category {{ color: #3498db; font-size: 14px; font-weight: bold; margin-bottom: 10px; }}
                .rec-title {{ color: #2c3e50; font-size: 18px; margin-bottom: 10px; }}
                .rec-desc {{ color: #666; margin-bottom: 10px; }}
                .rec-impact {{ color: #27ae60; font-size: 14px; }}
                .tip-list {{ list-style: none; }}
                .tip-list li {{ padding: 10px 0; padding-right: 30px; position: relative; }}
                .tip-list li:before {{ content: "✓"; position: absolute; right: 0; color: #27ae60; font-weight: bold; }}
                .coverage-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .coverage-table th, .coverage-table td {{ padding: 12px; text-align: right; border: 1px solid #ddd; }}
                .coverage-table th {{ background: #2c3e50; color: white; }}
                .coverage-table tr:nth-child(even) {{ background: #f9f9f9; }}
                .covers {{ color: #27ae60; }}
                .not-covers {{ color: #e74c3c; }}
                .footer {{ background: #2c3e50; color: white; padding: 20px; text-align: center; margin-top: 30px; }}
                @media (max-width: 768px) {{ 
                    .meta-grid, .recommendation-grid {{ grid-template-columns: 1fr; }}
                    .section {{ padding: 20px; }}
                }}
            </style>
        </head>
        <body>
            <div class="report-container">
                
                <!-- العنوان الرئيسي -->
                <div class="header">
                    <h1>📊 تقرير تأمين شامل وتحليل مخاطر</h1>
                    <div class="subtitle">{vehicle.year} {vehicle.make} {vehicle.model} | {quote.quote_number}</div>
                </div>
                
                <!-- معلومات عامة -->
                <div class="meta-info">
                    <div class="meta-grid">
                        <div class="meta-item">
                            <div class="meta-label">العميل</div>
                            <div class="meta-value">{user.get_full_name() or user.email}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">نوع المركبة</div>
                            <div class="meta-value">{analysis['vehicle_type_ar']}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">عمر المركبة</div>
                            <div class="meta-value">{analysis['vehicle_age']} سنة</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">مستوى الخطر العام</div>
                            <div class="meta-value">
                                <span class="risk-badge {'risk-high' if 'مرتفع' in analysis['overall_risk'] else 'risk-medium' if 'متوسط' in analysis['overall_risk'] else 'risk-low'}">
                                    {analysis['overall_risk']}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- القسم 1: الملخص التنفيذي -->
                <div class="section">
                    <h2 class="section-title">📈 الملخص التنفيذي</h2>
                    <p>هذا التقرير يقدم تحليلاً شاملاً لوثيقة تأمين مركبتك {vehicle.make} {vehicle.model} موديل {vehicle.year}. بناءً على تحليل {len(analysis['recommendations'])} عامل خطر رئيسي، تم تقييم مستوى الخطر العام للمركبة بأنه <strong>{analysis['overall_risk']}</strong>.</p>
                    <p>القسط الحالي (${quote.final_premium}) هو <strong>{market['comparison']}</strong> مقارنة بمتوسط أسعار السوق. {market['advice']}.</p>
                </div>
                
                <!-- القسم 2: تحليل المخاطر التفصيلي -->
                <div class="section">
                    <h2 class="section-title">🔍 تحليل المخاطر التفصيلي</h2>
                    <div class="meta-grid">
                        <div class="meta-item">
                            <div class="meta-label">عمر المركبة</div>
                            <div class="meta-value">{analysis['analyses']['vehicle_age'].get('note', '')}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">سعة المحرك</div>
                            <div class="meta-value">{analysis['analyses']['engine_size'].get('note', '')}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">القيمة السوقية</div>
                            <div class="meta-value">{analysis['analyses']['vehicle_value'].get('note', '')}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">تاريخ المطالبات</div>
                            <div class="meta-value">{analysis['analyses']['claims_history'].get('note', '')}</div>
                        </div>
                    </div>
                    
                    <div class="comparison-card">
                        <h3>📊 مقارنة مع سوق التأمين</h3>
                        <p>متوسط سوق التأمين للمركبات من نوع <strong>{analysis['vehicle_type_ar']}</strong> مع تغطية <strong>{coverage['name']}</strong> هو <strong>${market['market_average']}</strong> سنوياً.</p>
                        <p>قسطك الحالي: <strong>${market['actual_premium']}</strong> ({market['difference_percent']}% {['أعلى', 'أقل'][market['difference'] < 0]} من المتوسط)</p>
                        <p><strong>التوصية:</strong> {market['advice']}</p>
                    </div>
                </div>
                
                <!-- القسم 3: تحليل التغطية -->
                <div class="section">
                    <h2 class="section-title">🛡️ تحليل التغطية: {coverage['name']}</h2>
                    
                    <table class="coverage-table">
                        <thead>
                            <tr>
                                <th width="50%">ما يتم تغطيته</th>
                                <th width="50%">ما لا يتم تغطيته</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td class="covers">
                                    <ul class="tip-list">
                                        {''.join(f'<li>{item}</li>' for item in coverage['covers'])}
                                    </ul>
                                </td>
                                <td class="not-covers">
                                    <ul class="tip-list">
                                        {''.join(f'<li>{item}</li>' for item in coverage['not_covered'])}
                                    </ul>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    
                    <p><strong>الأنسب لـ:</strong> {coverage['best_for']}</p>
                </div>
                
                <!-- القسم 4: التوصيات الإستراتيجية -->
                <div class="section">
                    <h2 class="section-title">💡 التوصيات الإستراتيجية</h2>
                    <p>بناءً على تحليل مركبتك، نقدم التوصيات التالية لتقليل المخاطر وتحسين تجربة التأمين:</p>
                    
                    <div class="recommendation-grid">
                        {''.join(f'''
                        <div class="recommendation-card">
                            <div class="rec-category">{rec['category']}</div>
                            <div class="rec-title">{rec['title']}</div>
                            <div class="rec-desc">{rec['description']}</div>
                            <div class="rec-impact">🗲 {rec['impact']}</div>
                        </div>
                        ''' for rec in analysis['recommendations'][:6])}
                    </div>
                </div>
                
                <!-- القسم 5: نصائح السلامة -->
                <div class="section">
                    <h2 class="section-title">🚗 نصائح السلامة المرورية</h2>
                    <ul class="tip-list">
                        {''.join(f'<li>{tip}</li>' for tip in analysis['safety_tips'][:8])}
                    </ul>
                </div>
                
                <!-- القسم 6: جدول الأقساط -->
                <div class="section">
                    <h2 class="section-title">💰 جدول الأقساط والتخفيضات</h2>
                    <table class="coverage-table">
                        <thead>
                            <tr>
                                <th>البند</th>
                                <th>القيمة</th>
                                <th>التأثير على القسط</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>القسط الأساسي</td>
                                <td>${analysis['analyses']['vehicle_value'].get('factor', 1) * 1000:.2f}</td>
                                <td>حساب أولي بناءً على قيمة المركبة</td>
                            </tr>
                            <tr>
                                <td>عامل المخاطر الإجمالي</td>
                                <td>{analysis['total_risk_factor']}x</td>
                                <td>ضرب في جميع عوامل الخطر</td>
                            </tr>
                            <tr>
                                <td>خصم عدم المطالبات</td>
                                <td>{analysis['analyses']['no_claims_years']['discount_percent']}%</td>
                                <td>خصم لـ {quote.no_claims_years} سنوات بدون مطالبات</td>
                            </tr>
                            <tr style="background: #e8f5e8;">
                                <td><strong>القسط النهائي</strong></td>
                                <td><strong>${quote.final_premium}</strong></td>
                                <td><strong>بعد تطبيق جميع العوامل</strong></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- التذييل -->
                <div class="footer">
                    <p>تم إنشاء هذا التقرير في: {analysis['generated_at']}</p>
                    <p>رقم التقرير: {analysis['report_id']}</p>
                    <p>مع خالص التقدير،<br>فريق SafeRatio Insurance</p>
                    <p style="font-size: 12px; margin-top: 10px; opacity: 0.8;">
                        ملاحظة: هذا التقرير لأغراض إعلامية فقط. للتفاصيل الكاملة يرجى الرجوع لوثيقة التأمين الموقعة.
                    </p>
                </div>
                
            </div>
        </body>
        </html>
        """
        
        return report_html
    
    @staticmethod
    def generate_policy_report(policy):
        """Generate comprehensive policy report"""
        quote = policy.quote
        vehicle = policy.vehicle
        user = policy.user
        
        # تحليل الوثيقة
        days_remaining = (policy.expiry_date - datetime.now().date()).days
        coverage_percentage = (365 - days_remaining) / 365 * 100
        
        report_html = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
                .section {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                .policy-number {{ font-size: 24px; font-weight: bold; color: #3498db; }}
                .status-badge {{ display: inline-block; padding: 5px 15px; border-radius: 20px; }}
                .status-active {{ background: #27ae60; color: white; }}
                .status-pending {{ background: #f39c12; color: white; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>وثيقة تأمين مركبة</h1>
                <div class="policy-number">{policy.policy_number}</div>
            </div>
            
            <div class="section">
                <h2>معلومات الوثيقة</h2>
                <p><strong>الحالة:</strong> <span class="status-badge status-{policy.status}">{policy.get_status_display()}</span></p>
                <p><strong>الفترة:</strong> {policy.inception_date} إلى {policy.expiry_date} ({days_remaining} يوم متبق)</p>
                <p><strong>نسبة التغطية المستخدمة:</strong> {coverage_percentage:.1f}%</p>
            </div>
            
            <div class="section">
                <h2>معلومات المركبة</h2>
                <p><strong>المركبة:</strong> {vehicle.year} {vehicle.make} {vehicle.model}</p>
                <p><strong>رقم اللوحة:</strong> {vehicle.license_plate}</p>
                <p><strong>القيمة:</strong> ${vehicle.current_value}</p>
            </div>
            
            <div class="section">
                <h2>التغطية والشروط</h2>
                <p><strong>نوع التغطية:</strong> {quote.get_coverage_type_display()}</p>
                <p><strong>مبلغ التحمل:</strong> ${quote.excess_amount}</p>
                <p><strong>الشروط:</strong></p>
                <ul>
                    <li>الإبلاغ عن الحوادث خلال 24 ساعة</li>
                    <li>تقديم تقرير شرطة في حالة السرقة</li>
                    <li>صيانة دورية للمركبة</li>
                </ul>
            </div>
            
            <div class="section">
                <h2>المعلومات المالية</h2>
                <p><strong>القسط الإجمالي:</strong> ${policy.total_premium}</p>
                <p><strong>القسط الشهري:</strong> ${policy.total_premium / 12:.2f}</p>
                <p><strong>المبلغ المدفوع:</strong> ${policy.paid_amount}</p>
                <p><strong>الحالة المالية:</strong> {policy.payment_status}</p>
            </div>
            
            <div class="section">
                <h2>خطوات التالية</h2>
                <ol>
                    <li>إكمال عملية الدفع لتفعيل الوثيقة</li>
                    <li>تحميل شهادة التأمين</li>
                    <li>مراجعة شروط وأحكام الوثيقة</li>
                    <li>الاتصال بالدعم في حالة الاستفسارات</li>
                </ol>
            </div>
        </body>
        </html>
        """
        
        return {
            'success': True,
            'policy_number': policy.policy_number,
            'status': policy.status,
            'days_remaining': days_remaining,
            'coverage_percentage': coverage_percentage,
            'report_html': report_html,
            'documents': {
                'certificate': f'/api/car-insurance/policies/{policy.id}/certificate/',
                'terms': f'/api/car-insurance/policies/{policy.id}/terms/',
                'full_report': f'/api/car-insurance/policies/{policy.id}/report/'
            },
            'contact_info': {
                'support_phone': '+966 800 123 4567',
                'support_email': 'support@saferatio.com',
                'emergency_contact': '+966 555 123 456'
            }
        }
    
    @staticmethod
    def create_pdf_report(quote, report_data):
        """Create PDF version of the report"""
        # يمكن إضافة دالة لإنشاء PDF لاحقاً
        return None