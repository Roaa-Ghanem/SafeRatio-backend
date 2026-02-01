# health_insurance/calculations.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from .models import SectorPricingFactor, HealthCoveragePlan

def calculate_health_premium(company, coverage_plan, insured_count):
    """
    احتساب قسط التأمين الصحي للشركة
    
    Args:
        company: كائن Company
        coverage_plan: كائن HealthCoveragePlan
        insured_count: عدد الموظفين المؤمن عليهم
    
    Returns:
        dict: تفاصيل الحساب
    """
    # التحقق من المدخلات
    if insured_count < 1:
        insured_count = 1
    
    if hasattr(coverage_plan, 'max_employees') and insured_count > coverage_plan.max_employees:
        insured_count = coverage_plan.max_employees
    
    # السعر الأساسي للموظف الواحد
    base_price = Decimal(str(coverage_plan.base_price_per_employee))
    
    # احتساب جميع العوامل
    factors = {
        'sector_factor': get_sector_factor(company.sector),
        'size_factor': get_size_factor(company.size_category),
        'age_factor': get_age_factor(company.establishment_age),
        'risk_factor': get_risk_factor(company.risk_level),
        'environment_factor': get_environment_factor(company.work_environment),
        'city_factor': get_city_factor(company.city),
        'claims_factor': get_claims_factor(company.claims_history),
        'insurance_history_factor': get_insurance_history_factor(
            company.has_previous_insurance,
            company.previous_insurance_years
        )
    }
    
    # القسط الأساسي
    base_premium = base_price * Decimal(str(insured_count))
    
    # تطبيق العوامل
    total_factor = Decimal('1.0')
    for factor_name, factor_value in factors.items():
        if isinstance(factor_value, (Decimal, int, float)):
            total_factor *= Decimal(str(factor_value))
    
    # احتساب الأقساط
    total_premium = base_premium * total_factor
    annual_premium = total_premium
    monthly_premium = total_premium / Decimal('12')
    
    # تقريب النتائج
    total_premium = total_premium.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    annual_premium = annual_premium.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    monthly_premium = monthly_premium.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    base_premium = base_premium.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # تحويل العوامل
    simple_factors = {}
    for key, value in factors.items():
        if isinstance(value, Decimal):
            simple_factors[key] = float(value)
        else:
            simple_factors[key] = value
    
    return {
        'base_premium': float(base_premium),
        'total_premium': float(total_premium),
        'annual_premium': float(annual_premium),
        'monthly_premium': float(monthly_premium),
        'insured_count': insured_count,
        'factors': simple_factors,
        'premium_per_employee': float(total_premium / insured_count) if insured_count > 0 else 0.0,
        'plan_details': {
            'name': coverage_plan.name,
            'type': coverage_plan.plan_type,
            'base_price_per_employee': float(base_price)
        }
    }

def quick_health_calculator(sector='tech_software', size_category='small', 
                           employee_count=10, dependents_count=0, city='صنعاء',
                           work_environment='office', risk_level='medium',
                           has_previous_insurance=False, previous_insurance_years=0,
                           claims_history=0, establishment_age=1):
    """
    حاسبة سريعة للأقساط الصحية
    
    Returns:
        dict: تقدير القسط
    """
    from .models import HealthCoveragePlan
    
    # الحصول على خطة افتراضية
    try:
        coverage_plan = HealthCoveragePlan.objects.filter(
            is_active=True,
            plan_type='basic'
        ).first()
        
        if not coverage_plan:
            coverage_plan = HealthCoveragePlan.objects.filter(is_active=True).first()
        
        if not coverage_plan:
            # خطة افتراضية
            coverage_plan = type('obj', (object,), {
                'base_price_per_employee': Decimal('1000'),
                'name': 'خطة أساسية',
                'plan_type': 'basic'
            })()
    except:
        coverage_plan = type('obj', (object,), {
            'base_price_per_employee': Decimal('1000'),
            'name': 'خطة أساسية',
            'plan_type': 'basic'
        })()
    
    # إنشاء كائن شركة افتراضي
    class MockCompany:
        def __init__(self):
            self.sector = sector
            self.size_category = size_category
            self.total_employees = employee_count
            self.city = city
            self.work_environment = work_environment
            self.risk_level = risk_level
            self.has_previous_insurance = has_previous_insurance
            self.previous_insurance_years = previous_insurance_years
            self.claims_history = claims_history
            self.establishment_age = establishment_age
    
    mock_company = MockCompany()
    
    # استدعاء الحساب الرئيسي
    return calculate_health_premium(mock_company, coverage_plan, employee_count)

# ============= دوال العوامل =============

def get_sector_factor(sector):
    """عامل القطاع"""
    try:
        factor = SectorPricingFactor.objects.get(sector=sector)
        return factor.base_factor
    except:
        # عوامل افتراضية
        sector_factors = {
            'health_hospital': Decimal('1.5'),
            'health_clinic': Decimal('1.3'),
            'health_pharmacy': Decimal('1.1'),
            'tech_software': Decimal('1.0'),
            'construction_civil': Decimal('1.8'),
            'retail_store': Decimal('1.2'),
            'default': Decimal('1.0')
        }
        return sector_factors.get(sector, sector_factors['default'])

def get_size_factor(size):
    """عامل حجم الشركة"""
    size_factors = {
        'micro': Decimal('1.3'),
        'small': Decimal('1.1'),
        'medium': Decimal('1.0'),
        'large': Decimal('0.9'),
        'enterprise': Decimal('0.8')
    }
    return size_factors.get(size, Decimal('1.0'))

def get_age_factor(age):
    """عامل عمر الشركة"""
    if age < 1:
        return Decimal('1.3')
    elif age < 3:
        return Decimal('1.2')
    elif age < 5:
        return Decimal('1.1')
    elif age < 10:
        return Decimal('1.0')
    elif age < 20:
        return Decimal('0.9')
    else:
        return Decimal('0.8')

def get_risk_factor(risk_level):
    """عامل مستوى المخاطر"""
    risk_factors = {
        'low': Decimal('0.8'),
        'medium': Decimal('1.0'),
        'high': Decimal('1.3'),
        'very_high': Decimal('1.6')
    }
    return risk_factors.get(risk_level, Decimal('1.0'))

def get_environment_factor(environment):
    """عامل بيئة العمل"""
    env_factors = {
        'office': Decimal('0.9'),
        'field': Decimal('1.4'),
        'mixed': Decimal('1.1'),
        'remote': Decimal('0.8'),
        'hazardous': Decimal('1.7')
    }
    return env_factors.get(environment, Decimal('1.0'))

def get_city_factor(city):
    """عامل المدينة"""
    city_factors = {
        'صنعاء': Decimal('1.0'),
        'عدن': Decimal('1.1'),
        'تعز': Decimal('1.05'),
        'حضرموت': Decimal('1.0'),
        'الحديدة': Decimal('1.0'),
        'إب': Decimal('1.0')
    }
    return city_factors.get(city, Decimal('1.0'))

def get_claims_factor(claims_count):
    """عامل المطالبات"""
    if claims_count == 0:
        return Decimal('0.9')
    elif claims_count <= 3:
        return Decimal('1.0')
    elif claims_count <= 10:
        return Decimal('1.2')
    else:
        return Decimal('1.5')

def get_insurance_history_factor(has_previous, years):
    """عامل تاريخ التأمين"""
    if not has_previous:
        return Decimal('1.1')
    elif years >= 3:
        return Decimal('0.85')
    elif years >= 1:
        return Decimal('0.9')
    else:
        return Decimal('1.0')