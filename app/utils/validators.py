# validators.py
from datetime import datetime, date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class InsuranceDataValidator:
    """محقق شامل لبيانات التأمين الطبي"""
    
    # تعريف قواعد كل نوع تأمين
    INSURANCE_RULES = {
        'A': {
            'name': 'التغطية الشاملة',
            'includes_family': True,
            'min_children_ratio': 1.0,  # عدد الأبناء >= عدد الموظفين
            'min_parents_ratio': 0.5,   # عدد الوالدين >= 50% من الموظفين
            'age_range': (0, 65),
            'inpatient_coinsurance': Decimal('0.10'),
            'outpatient_coinsurance': Decimal('0.15'),
            'emergency_overseas': Decimal('0.80'),
            'selective_overseas': Decimal('0.00'),
            'limits': {
                'inpatient_annual': 10000,
                'inpatient_case': 5000,
                'outpatient_annual': 2000,
                'optical': 50,
                'dental': 100,
                'chronic_medication_monthly': 50
            }
        },
        'B': {
            'name': 'تغطية الموظفين فقط',
            'includes_family': False,
            'age_range': (18, 65),
            'inpatient_coinsurance': Decimal('0.20'),
            'outpatient_coinsurance': Decimal('0.25'),
            'emergency_overseas': Decimal('0.70'),
            'selective_overseas': Decimal('0.50'),
            'limits': {
                'inpatient_annual': 8000,
                'inpatient_case': 4000,
                'outpatient_annual': 1500,
                'optical': 30,
                'dental': 80,
                'chronic_medication_monthly': 50
            }
        },
        'C': {
            'name': 'التغطية الأساسية',
            'includes_family': True,
            'min_children_ratio': 1.0,
            'min_parents_ratio': 0.5,
            'age_range': (0, 65),
            'inpatient_coinsurance': Decimal('0.15'),
            'outpatient_coinsurance': Decimal('0.25'),
            'emergency_overseas': Decimal('0.50'),
            'selective_overseas': Decimal('0.00'),
            'limits': {
                'inpatient_annual': 6000,
                'inpatient_case': 3000,
                'outpatient_annual': 1000,
                'dental': 50,
                'chronic_medication_monthly': 30
            }
        }
    }
    
    @staticmethod
    def calculate_age(birth_date):
        """حساب العمر من تاريخ الميلاد"""
        if not birth_date:
            return None
        
        today = date.today()
        age = today.year - birth_date.year
        
        # تعديل إذا لم يحن عيد الميلاد بعد هذا العام
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    
    @classmethod
    def validate_employee_data(cls, employees_data, insurance_type):
        """
        التحقق من صحة بيانات الموظفين
        """
        errors = []
        valid_employees = []
        excluded_employees = []
        
        rules = cls.INSURANCE_RULES.get(insurance_type)
        if not rules:
            raise ValidationError(_(f"نوع التأمين غير صحيح: {insurance_type}"))
        
        age_min, age_max = rules['age_range']
        
        for idx, emp in enumerate(employees_data):
            # التحقق من الحقول المطلوبة
            required_fields = ['full_name', 'date_of_birth', 'gender', 'salary']
            for field in required_fields:
                if field not in emp or not emp[field]:
                    errors.append(f"الموظف {idx+1}: حقل '{field}' مطلوب")
                    continue
            
            # التحقق من تاريخ الميلاد
            try:
                birth_date = emp.get('date_of_birth')
                if isinstance(birth_date, str):
                    birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
                
                age = cls.calculate_age(birth_date)
                if age is None:
                    errors.append(f"الموظف {emp.get('full_name')}: تاريخ الميلاد غير صحيح")
                    continue
                
                # التحقق من العمر حسب نوع التأمين
                if age < age_min or age > age_max:
                    excluded_employees.append({
                        'employee': emp,
                        'reason': f"العمر {age} خارج النطاق المسموح ({age_min}-{age_max})"
                    })
                    continue
                
                emp['age'] = age
                valid_employees.append(emp)
                
            except Exception as e:
                errors.append(f"الموظف {emp.get('full_name')}: خطأ في معالجة البيانات - {str(e)}")
        
        return {
            'valid_employees': valid_employees,
            'excluded_employees': excluded_employees,
            'errors': errors,
            'is_valid': len(errors) == 0
        }
    
    @classmethod
    def validate_family_requirements(cls, insurance_type, employees_count, family_data):
        """
        التحقق من شروط العائلة للأنواع A و C
        """
        rules = cls.INSURANCE_RULES.get(insurance_type)
        
        if not rules['includes_family']:
            return {
                'is_valid': True,
                'message': "النوع لا يشمل العائلة"
            }
        
        children_count = family_data.get('children', 0)
        parents_count = family_data.get('parents', 0)
        
        # التحقق من شروط العائلة
        violations = []
        
        # شرط 1: عدد الأبناء يجب أن يكون على الأقل مثل عدد الموظفين
        min_children = employees_count * rules['min_children_ratio']
        if children_count < min_children:
            violations.append(
                f"عدد الأبناء ({children_count}) أقل من الحد الأدنى ({min_children})"
            )
        
        # شرط 2: عدد الوالدين يجب أن يكون على الأقل 50% من الموظفين
        min_parents = employees_count * rules['min_parents_ratio']
        if parents_count < min_parents:
            violations.append(
                f"عدد الوالدين ({parents_count}) أقل من الحد الأدنى ({min_parents})"
            )
        
        return {
            'is_valid': len(violations) == 0,
            'violations': violations,
            'requirements': {
                'min_children': min_children,
                'min_parents': min_parents,
                'actual_children': children_count,
                'actual_parents': parents_count
            }
        }
    
    @classmethod
    def calculate_premium_breakdown(cls, insurance_type, employees, family_data, coverage_options):
        """
        حساب تفصيلي للأقساط
        """
        rules = cls.INSURANCE_RULES.get(insurance_type)
        
        # إحصاءات الموظفين
        total_employees = len(employees)
        
        # حساب عدد المشتركين الإجمالي
        total_insured = total_employees
        if rules['includes_family']:
            total_insured += sum(family_data.values())
        
        # القسط الأساسي (حسب نوع التأمين)
        base_premium_per_person = {
            'A': Decimal('1800'),
            'B': Decimal('1200'),
            'C': Decimal('1500')
        }
        
        base_premium = total_insured * base_premium_per_person[insurance_type]
        
        # حساب خصم نسبة التحمل
        coinsurance_discount = base_premium * rules['inpatient_coinsurance']
        premium_after_coinsurance = base_premium - coinsurance_discount
        
        # حساب التكاليف الإضافية
        additional_costs = cls._calculate_additional_costs(coverage_options, total_insured)
        
        # القسط الإجمالي
        total_premium = premium_after_coinsurance + additional_costs
        
        # تفاصيل الحساب
        breakdown = {
            'total_employees': total_employees,
            'total_insured': total_insured,
            'base_premium_per_person': float(base_premium_per_person[insurance_type]),
            'base_premium': float(base_premium),
            'coinsurance_rate': float(rules['inpatient_coinsurance']),
            'coinsurance_discount': float(coinsurance_discount),
            'premium_after_coinsurance': float(premium_after_coinsurance),
            'additional_costs': float(additional_costs),
            'total_premium': float(total_premium),
            'limits': rules['limits']
        }
        
        # حساب التكلفة حسب طريقة الدفع
        payment_methods = cls._calculate_payment_methods(total_premium)
        breakdown.update(payment_methods)
        
        return breakdown
    
    @staticmethod
    def _calculate_additional_costs(coverage_options, total_insured):
        """
        حساب تكاليف التغطيات الإضافية
        """
        costs = Decimal('0')
        rates = {
            'maternity': Decimal('200'),
            'dental': Decimal('100'),
            'optical': Decimal('50'),
            'chronic_medication': Decimal('360'),  # 30 × 12 شهر
            'overseas_treatment': Decimal('500')
        }
        
        for option, included in coverage_options.items():
            if included and option in rates:
                costs += rates[option] * total_insured
        
        return costs
    
    @staticmethod
    def _calculate_payment_methods(total_premium):
        """
        حساب التكلفة حسب طريقة الدفع
        """
        total = Decimal(str(total_premium))
        
        multipliers = {
            'annual': Decimal('1.00'),
            'semi_annual': Decimal('1.05'),
            'quarterly': Decimal('1.10'),
            'monthly': Decimal('1.15')
        }
        
        payment_methods = {}
        for method, multiplier in multipliers.items():
            method_total = total * multiplier
            monthly = method_total / Decimal('12')
            
            payment_methods[f'{method}_total'] = float(method_total)
            payment_methods[f'{method}_monthly'] = float(monthly)
        
        return payment_methods
    
    @classmethod
    def validate_coverage_options(cls, insurance_type, coverage_options):
        """
        التحقق من توافق خيارات التغطية مع نوع التأمين
        """
        rules = cls.INSURANCE_RULES.get(insurance_type)
        warnings = []
        
        # بعض التغطيات غير متوفرة في أنواع معينة
        if insurance_type == 'B' and coverage_options.get('maternity', False):
            warnings.append("النوع B لا يشمل تغطية الحمل والولادة للموظفات فقط")
        
        if insurance_type == 'C' and coverage_options.get('optical', False):
            warnings.append("النوع C لا يشمل تغطية النظارات الطبية")
        
        return {
            'is_valid': len(warnings) == 0,
            'warnings': warnings
        }
    
    @classmethod
    def generate_validation_report(cls, insurance_type, employees_data, family_data, coverage_options):
        """
        إنشاء تقرير شامل للتحقق
        """
        # 1. التحقق من بيانات الموظفين
        employee_validation = cls.validate_employee_data(employees_data, insurance_type)
        
        # 2. التحقق من شروط العائلة
        family_validation = cls.validate_family_requirements(
            insurance_type, 
            len(employee_validation['valid_employees']), 
            family_data
        )
        
        # 3. التحقق من خيارات التغطية
        coverage_validation = cls.validate_coverage_options(insurance_type, coverage_options)
        
        # 4. حساب الأقساط إذا كانت جميع البيانات صحيحة
        premium_breakdown = None
        if (employee_validation['is_valid'] and 
            family_validation['is_valid'] and 
            coverage_validation['is_valid']):
            
            premium_breakdown = cls.calculate_premium_breakdown(
                insurance_type,
                employee_validation['valid_employees'],
                family_data,
                coverage_options
            )
        
        # تجميع التقرير
        report = {
            'insurance_type': insurance_type,
            'insurance_name': cls.INSURANCE_RULES[insurance_type]['name'],
            'employee_validation': employee_validation,
            'family_validation': family_validation,
            'coverage_validation': coverage_validation,
            'premium_breakdown': premium_breakdown,
            'overall_valid': (
                employee_validation['is_valid'] and 
                family_validation['is_valid'] and 
                coverage_validation['is_valid']
            ),
            'timestamp': datetime.now().isoformat()
        }
        
        return report
    
    @classmethod
    def validate_excel_template(cls, excel_data):
        """
        التحقق من قالب Excel المرفوع
        """
        required_columns = [
            'الاسم الكامل',
            'تاريخ الميلاد',
            'الجنس',
            'الراتب',
            'الحالة الاجتماعية',
            'عدد الأبناء',
            'يشمل الوالدين'
        ]
        
        errors = []
        warnings = []
        
        # التحقق من وجود الأعمدة المطلوبة
        if not excel_data or len(excel_data) == 0:
            errors.append("الملف فارغ أو لا يحتوي على بيانات")
            return {'errors': errors, 'warnings': warnings, 'is_valid': False}
        
        first_row = excel_data[0]
        missing_columns = []
        
        for column in required_columns:
            if column not in first_row:
                missing_columns.append(column)
        
        if missing_columns:
            errors.append(f"الأعمدة المفقودة: {', '.join(missing_columns)}")
        
        # التحقق من صحة البيانات
        for idx, row in enumerate(excel_data, start=2):  # start=2 لأن Excel يبدأ من السطر 2
            # التحقق من تاريخ الميلاد
            birth_date = row.get('تاريخ الميلاد')
            if birth_date:
                try:
                    if isinstance(birth_date, str):
                        datetime.strptime(birth_date, '%Y-%m-%d')
                    age = cls.calculate_age(birth_date if isinstance(birth_date, date) else None)
                    if age and age > 100:
                        warnings.append(f"السطر {idx}: العمر ({age}) غير طبيعي")
                except:
                    errors.append(f"السطر {idx}: تاريخ الميلاد غير صحيح")
            
            # التحقق من الراتب
            salary = row.get('الراتب')
            if salary and (not isinstance(salary, (int, float)) or salary < 0):
                errors.append(f"السطر {idx}: الراتب غير صحيح")
        
        return {
            'errors': errors,
            'warnings': warnings,
            'is_valid': len(errors) == 0,
            'total_rows': len(excel_data),
            'valid_rows': len(excel_data) - len(errors)
        }


# وظائف مساعدة
def validate_yemeni_id(id_number):
    """التحقق من صحة الرقم القومي اليمني"""
    if not id_number or len(str(id_number)) != 9:
        return False
    # إضافة المزيد من التحقق إذا لزم
    return True

def validate_phone_number(phone):
    """التحقق من صحة رقم الهاتف اليمني"""
    if not phone:
        return False
    
    phone_str = str(phone).strip()
    # تنسيقات الأرقام اليمنية
    valid_prefixes = ['71', '73', '77', '70', '01', '05']
    
    for prefix in valid_prefixes:
        if phone_str.startswith(prefix) and len(phone_str) in [9, 10]:
            return True
    
    return False

def format_premium_breakdown_for_pdf(breakdown):
    """تنسيق تفاصيل الأقساط لملف PDF"""
    if not breakdown:
        return {}
    
    formatted = {
        'البيانات الأساسية': {
            'إجمالي الموظفين': breakdown['total_employees'],
            'إجمالي المشتركين': breakdown['total_insured'],
            'القسط الأساسي للفرد': f"{breakdown['base_premium_per_person']:,.2f} دولار"
        },
        'تفاصيل الحساب': {
            'القسط الأساسي الإجمالي': f"{breakdown['base_premium']:,.2f} دولار",
            'نسبة التحمل': f"{breakdown['coinsurance_rate'] * 100}%",
            'خصم نسبة التحمل': f"{breakdown['coinsurance_discount']:,.2f} دولار",
            'القسط بعد الخصم': f"{breakdown['premium_after_coinsurance']:,.2f} دولار",
            'التكاليف الإضافية': f"{breakdown['additional_costs']:,.2f} دولار"
        },
        'القسط النهائي': {
            'الإجمالي السنوي': f"{breakdown['total_premium']:,.2f} دولار",
            'الشهري (سنوي)': f"{breakdown['annual_monthly']:,.2f} دولار",
            'الشهري (شهري)': f"{breakdown['monthly_monthly']:,.2f} دولار",
            'الربع سنوي': f"{breakdown['quarterly_total']:,.2f} دولار",
            'نصف سنوي': f"{breakdown['semi_annual_total']:,.2f} دولار"
        }
    }
    
    return formatted