# car_insurance/reports.py
# import google.generativeai as genai
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.http import HttpResponse
import tempfile
import json
import markdown
from datetime import datetime
import arabic_reshaper
from bidi.algorithm import get_display

# تكوين Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

class InsuranceReportGenerator:
    """Generate comprehensive insurance reports using Gemini AI"""
    
    @staticmethod
    def generate_quote_report(quote):
        """Generate detailed report for a specific quote"""
        vehicle = quote.vehicle
        user = quote.user
        
        # حساب القسط مع تفاصيل كاملة
        premium_data = InsuranceReportGenerator.calculate_premium_with_breakdown(quote)
        
        # إنشاء prompt محسن
        prompt = f"""
        أنت مستشار تأمين كبير في شركة تأمين رائدة.
        اكتب تقرير "تحليل شامل للمخاطر والتأمين" للعميل باللغة العربية.
        
        ### بيانات العميل والمركبة:
        - اسم العميل: {user.get_full_name() or user.email}
        - المركبة: {vehicle.year} {vehicle.make} {vehicle.model}
        - القيمة التقديرية: ${vehicle.current_value}
        - سعة المحرك: {vehicle.engine_size} لتر
        - نوع الوقود: {vehicle.fuel_type}
        - رقم اللوحة: {vehicle.license_plate}
        
        ### نوع التغطية:
        {quote.get_coverage_type_display()}
        
        ### تحليل القسط:
        - القسط النهائي: ${premium_data['final_premium']:.2f}
        - القسط الأساسي: ${premium_data['base_premium']:.2f}
        - خصم عدم المطالبات: {premium_data['no_claim_discount_percent']}%
        - مبلغ التحمل: ${premium_data['excess_amount']:.2f}
        
        ### عوامل الخطر:
        - تاريخ المطالبات: {quote.claims_history} مطالبة/مطالبات
        - سنوات عدم المطالبة: {quote.no_claims_years} سنة/سنوات
        - عمر المركبة: {premium_data['vehicle_age']} سنة/سنوات
        - مستوى الخطر: {premium_data['risk_level']}
        
        ### هيكل التقرير المطلوب (استخدم Markdown):
        1. **الملخص التنفيذي**: نظرة عامة على الوثيقة والمزايا الرئيسية.
        2. **تقييم مخاطر المركبة**: تحليل كيف أثر عمر المركبة وسعة المحرك ونوع الوقود على السعر.
        3. **تحليل التغطية**: شرح مفصل لما تغطيه "{quote.get_coverage_type_display()}" لهذه المركبة تحديداً.
        4. **منطق تسعير القسط**: شرح "نهج التوازن" - كيف وازننا بين مخاطر القيمة العالية ومكافأة عدم المطالبات.
        5. **نقاط القوة والضعف**: 
           - نقاط القوة في هذه الوثيقة
           - المجالات التي يمكن تحسينها
        6. **التوصيات الإستراتيجية**: 3-4 نصائح مهنية للعميل لتقليل المخاطر وأقساط المستقبل.
        7. **بدائل التغطية**: مقارنة سريعة مع أنواع تغطية أخرى.
        8. **إخلاء المسؤولية القانوني**: إخلاء مسؤولية التأمين القياسي.
        
        ### متطلبات إضافية:
        - استخدم العناوين والفواصل لجعل التقرير سهل القراءة
        - أضف نقاطاً أو أرقاماً للقوائم
        - كن واضحاً بشأن ما يتم تغطيته وما لا يتم تغطيته
        - قدم أمثلة عملية عندما يكون ذلك مناسباً
        - الطول: مفصل (حوالي 1000-1200 كلمة)
        
        ### النبرة:
        احترافية، شفافة، ومفيدة. اشرح المصطلحات المعقدة بلغة بسيطة.
        """
        
        try:
            response = model.generate_content(prompt)
            report_markdown = response.text
            
            # تحويل Markdown إلى HTML للعرض
            report_html = markdown.markdown(report_markdown, extensions=['extra', 'tables'])
            
            return {
                'success': True,
                'report_markdown': report_markdown,
                'report_html': report_html,
                'premium_data': premium_data,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'report_id': f"REP-{quote.id}-{datetime.now().strftime('%Y%m%d')}"
            }
            
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return {
                'success': False,
                'error': str(e),
                'fallback_report': InsuranceReportGenerator.generate_fallback_report(quote, premium_data)
            }
    
    @staticmethod
    def calculate_premium_with_breakdown(quote):
        """Calculate premium with detailed breakdown"""
        vehicle = quote.vehicle
        
        # حساب عمر المركبة
        current_year = datetime.now().year
        vehicle_age = current_year - vehicle.year
        
        # القسط الأساسي بناءً على القيمة
        base_value = float(vehicle.current_value or 10000)
        
        # معدلات التغطية
        coverage_rates = {
            'third_party': 0.02,  # 2%
            'third_party_fire_theft': 0.03,  # 3%
            'comprehensive': 0.04  # 4%
        }
        
        base_premium = base_value * coverage_rates.get(quote.coverage_type, 0.04)
        
        # عوامل الخطر
        risk_multiplier = 1.0
        notes = []
        
        # عامل عمر المركبة
        if vehicle_age > 10:
            risk_multiplier *= 1.3
            notes.append("زيادة بسبب عمر المركبة (>10 سنوات)")
        elif vehicle_age > 5:
            risk_multiplier *= 1.1
            notes.append("زيادة طفيفة بسبب عمر المركبة (5-10 سنوات)")
        else:
            notes.append("عمر المركبة ضمن المعدل الطبيعي")
        
        # عامل سعة المحرك
        if vehicle.engine_size > 3.0:
            risk_multiplier *= 1.4
            notes.append("زيادة كبيرة بسبب سعة المحرك الكبيرة")
        elif vehicle.engine_size > 2.0:
            risk_multiplier *= 1.2
            notes.append("زيادة بسبب سعة المحرك المتوسطة")
        
        # عامل تاريخ المطالبات
        if quote.claims_history > 2:
            risk_multiplier *= 1.5
            notes.append("زيادة كبيرة بسبب تاريخ المطالبات")
        elif quote.claims_history > 0:
            risk_multiplier *= 1.2
            notes.append("زيادة بسبب وجود مطالبات سابقة")
        
        # خصم سنوات عدم المطالبة
        no_claim_discount_percent = min(quote.no_claims_years * 5, 50)  # 5% لكل سنة بحد أقصى 50%
        no_claim_discount = base_premium * (no_claim_discount_percent / 100)
        
        if quote.no_claims_years > 0:
            notes.append(f"خصم {no_claim_discount_percent}% لسنوات عدم المطالبة")
        
        # حساب القسط النهائي
        adjusted_premium = base_premium * risk_multiplier
        final_premium = adjusted_premium - no_claim_discount
        
        # التأكد من الحد الأدنى
        min_premium = 100.0
        if final_premium < min_premium:
            final_premium = min_premium
            notes.append("تطبيق الحد الأدنى للقسط")
        
        # تحديد مستوى الخطر
        if risk_multiplier > 1.5:
            risk_level = "عالي"
        elif risk_multiplier > 1.2:
            risk_level = "متوسط إلى عالي"
        elif risk_multiplier > 1.0:
            risk_level = "متوسط"
        else:
            risk_level = "منخفض"
        
        return {
            'base_premium': round(base_premium, 2),
            'adjusted_premium': round(adjusted_premium, 2),
            'no_claim_discount': round(no_claim_discount, 2),
            'no_claim_discount_percent': no_claim_discount_percent,
            'final_premium': round(final_premium, 2),
            'excess_amount': 500.0,
            'vehicle_age': vehicle_age,
            'risk_multiplier': round(risk_multiplier, 2),
            'risk_level': risk_level,
            'notes': notes,
            'breakdown': {
                'coverage_rate': coverage_rates.get(quote.coverage_type, 0.04) * 100,
                'vehicle_value': base_value,
                'calculation_details': notes
            }
        }
    
    @staticmethod
    def generate_fallback_report(quote, premium_data):
        """Generate fallback report if Gemini fails"""
        return f"""
        # تقرير تأمين - {quote.vehicle.make} {quote.vehicle.model}
        
        ## الملخص التنفيذي
        هذا التقرير يقدم تحليلاً شاملاً لوثيقة تأمين مركبتك.
        
        ## تفاصيل المركبة
        - الماركة: {quote.vehicle.make}
        - الموديل: {quote.vehicle.model}
        - السنة: {quote.vehicle.year}
        - القيمة: ${quote.vehicle.current_value}
        
        ## تحليل القسط
        - القسط الأساسي: ${premium_data['base_premium']}
        - القسط النهائي: ${premium_data['final_premium']}
        - مستوى الخطر: {premium_data['risk_level']}
        
        ## التوصيات
        1. الصيانة الدورية للمركبة
        2. قيادة آمنة لتجنب المطالبات
        3. النظر في زيادة مبلغ التحمل لتخفيض القسط
        """
    
    @staticmethod
    def create_pdf_report(quote, gemini_report):
        """Create PDF report from Gemini analysis"""
        try:
            # إنشاء ملف PDF مؤقت
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            
            # إنشاء مستند PDF
            doc = SimpleDocTemplate(
                temp_file.name,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            story = []
            styles = getSampleStyleSheet()
            
            # إضافة أنماط للغة العربية
            arabic_style = ParagraphStyle(
                'ArabicStyle',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=11,
                alignment=2,  # RIGHT alignment
                spaceAfter=6
            )
            
            # العنوان
            title_text = f"تقرير تأمين شامل - {quote.vehicle.make} {quote.vehicle.model}"
            title = Paragraph(title_text, styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # معلومات الاقتباس
            quote_info = [
                ['رقم الاقتباس', quote.quote_number],
                ['تاريخ الإنشاء', quote.created_at.strftime('%Y-%m-%d')],
                ['نوع التغطية', quote.get_coverage_type_display()],
                ['حالة الاقتباس', quote.get_status_display()],
            ]
            
            quote_table = Table(quote_info, colWidths=[2*inch, 3*inch])
            quote_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#f8f9fa')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(quote_table)
            story.append(Spacer(1, 20))
            
            # معلومات المركبة
            vehicle_info = [
                ['الماركة', quote.vehicle.make],
                ['الموديل', quote.vehicle.model],
                ['السنة', quote.vehicle.year],
                ['رقم اللوحة', quote.vehicle.license_plate],
                ['سعة المحرك', f"{quote.vehicle.engine_size} لتر"],
                ['نوع الوقود', quote.vehicle.fuel_type],
                ['القيمة الحالية', f"${quote.vehicle.current_value}"],
            ]
            
            vehicle_table = Table(vehicle_info, colWidths=[2*inch, 3*inch])
            vehicle_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(vehicle_table)
            story.append(Spacer(1, 20))
            
            # تحليل القسط
            premium_data = gemini_report.get('premium_data', {})
            premium_info = [
                ['العنصر', 'القيمة', 'التفسير'],
                ['القسط الأساسي', f"${premium_data.get('base_premium', 0):.2f}", 'بناءً على قيمة المركبة'],
                ['عامل الخطر', f"{premium_data.get('risk_multiplier', 1.0):.1f}x", premium_data.get('risk_level', 'غير متوفر')],
                ['خصم عدم المطالبات', f"{premium_data.get('no_claim_discount_percent', 0)}%", f"{quote.no_claims_years} سنة/سنوات"],
                ['القسط النهائي', f"${premium_data.get('final_premium', 0):.2f}", 'بعد تطبيق جميع العوامل'],
                ['مبلغ التحمل', f"${premium_data.get('excess_amount', 500):.2f}", 'المبلغ المدفوع عند كل مطالبة'],
            ]
            
            premium_table = Table(premium_info, colWidths=[1.5*inch, 1*inch, 2.5*inch])
            premium_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.white]),
            ]))
            story.append(premium_table)
            story.append(Spacer(1, 20))
            
            # تحليل Gemini (مقتطف)
            if gemini_report.get('success'):
                report_section = Paragraph("تحليل المخاطر والتوصيات (بواسطة الذكاء الاصطناعي)", styles['Heading2'])
                story.append(report_section)
                story.append(Spacer(1, 10))
                
                # أخذ أول 1000 حرف من التقرير
                report_preview = gemini_report['report_markdown'][:1000] + "..."
                analysis_para = Paragraph(report_preview, arabic_style)
                story.append(analysis_para)
                story.append(Spacer(1, 10))
                
                note = Paragraph("ملاحظة: هذا ملخص للتحليل الكامل. للحصول على التقرير الكامل، يرجى زيارة المنصة الإلكترونية.", styles['Italic'])
                story.append(note)
            
            # التوقيع
            story.append(Spacer(1, 30))
            signature = Paragraph("مع خالص التقدير،<br/>فريق SafeRatio Insurance", styles['Normal'])
            story.append(signature)
            
            # تذييل الصفحة
            footer = Paragraph(f"تم إنشاء التقرير في: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>رقم التقرير: {gemini_report.get('report_id', 'N/A')}", styles['Small'])
            story.append(footer)
            
            # بناء PDF
            doc.build(story)
            return temp_file.name
            
        except Exception as e:
            print(f"PDF Generation Error: {e}")
            raise