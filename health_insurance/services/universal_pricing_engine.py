# health_insurance/services/universal_pricing_engine.py
import pandas as pd
from decimal import Decimal
from datetime import datetime
from ..models import Company, HealthCoveragePlan, SectorPricingFactor

class UniversalPricingEngine:
    """محرك تسعير شامل لجميع أنواع الشركات"""
    
    def __init__(self):
        self.base_factors = self.load_base_factors()
        
    def load_base_factors(self):
        """تحميل عوامل التسعير الأساسية"""
        return {
            # عوامل حسب القطاع
            'sector_factors': self.get_sector_factors(),
            
            # عوامل حسب حجم الشركة
            'size_factors': {
                'micro': Decimal('1.2'),
                'small': Decimal('1.0'),
                'medium': Decimal('0.9'),
                'large': Decimal('0.8'),
                'enterprise': Decimal('0.7')
            },
            
            # عوامل حسب بيئة العمل
            'environment_factors': {
                'office': Decimal('0.9'),
                'field': Decimal('1.3'),
                'mixed': Decimal('1.1'),
                'remote': Decimal('0.8'),
                'hazardous': Decimal('1.5')
            },
            
            # عوامل حسب مستوى المخاطر
            'risk_factors': {
                'low': Decimal('0.8'),
                'medium': Decimal('1.0'),
                'high': Decimal('1.3'),
                'very_high': Decimal('1.6')
            },
            
            # عوامل حسب الموقع
            'city_factors': {
                'صنعاء': Decimal('1.0'),
                'عدن': Decimal('1.1'),
                'تعز': Decimal('1.05'),
                'حضرموت': Decimal('1.0'),
                # ... إضافة بقية المدن
            },
            
            # عوامل حسب تاريخ الشركة
            'age_factors': {
                '1-3': Decimal('1.2'),
                '4-7': Decimal('1.1'),
                '8-15': Decimal('1.0'),
                '16+': Decimal('0.9')
            }
        }
    
    def get_sector_factors(self):
        """الحصول على عوامل القطاعات من قاعدة البيانات"""
        factors = {}
        sector_factors = SectorPricingFactor.objects.all()
        for sf in sector_factors:
            factors[sf.sector] = {
                'base': sf.base_factor,
                'risk_adjustment': sf.risk_adjustment,
                'min': sf.min_premium_per_employee,
                'max': sf.max_premium_per_employee
            }
        return factors
    
    def calculate_company_premium(self, company, employees_file_path, coverage_plan):
        """
        حساب القسط الإجمالي للشركة
        
        الخطوات:
        1. تحليل ملف الموظفين
        2. حساب القسط الأساسي
        3. تطبيق العوامل
        4. حساب الإجمالي
        """
        try:
            # 1. تحليل ملف الموظفين
            employee_analysis = self.analyze_employees_file(employees_file_path)
            
            # 2. حساب القسط الأساسي حسب الخطة
            base_premium = self.calculate_base_premium(employee_analysis, coverage_plan)
            
            # 3. تطبيق عوامل الشركة
            company_factors = self.calculate_company_factors(company)
            
            # 4. حساب القسط المعدل
            adjusted_premium = base_premium * company_factors['total_factor']
            
            # 5. تطبيق الحدود الدنيا والقصوى
            final_premium = self.apply_limits(adjusted_premium, company, coverage_plan)
            
            # 6. إضافة التحميلات الإدارية
            final_premium = final_premium * Decimal('1.15')  # +15% تكاليف إدارية
            
            return {
                'base_premium': base_premium,
                'company_factors': company_factors,
                'employee_analysis': employee_analysis,
                'final_premium': final_premium,
                'annual_premium': final_premium,
                'monthly_premium': final_premium / Decimal('12')
            }
            
        except Exception as e:
            # في حالة خطأ، ارجع حساباً بسيطاً
            return self.calculate_simple_premium(company, coverage_plan)
    
    def analyze_employees_file(self, file_path):
        """تحليل ملف Excel للموظفين مع البيانات الجديدة"""
        try:
            df = pd.read_excel(file_path)
            
            # التحقق من الأعمدة المطلوبة
            required_columns = ['الاسم', 'الجنس', 'تاريخ_الميلاد', 'الراتب', 'المعالين']
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"العمود {col} غير موجود في الملف")
            
            analysis = {
                'total_employees': len(df),
                'male_count': len(df[df['الجنس'] == 'ذكر']),
                'female_count': len(df[df['الجنس'] == 'أنثى']),
                'total_dependents': int(df['المعالين'].sum()) if 'المعالين' in df.columns else 0,
                'average_salary': float(df['الراتب'].mean()) if 'الراتب' in df.columns else 3000,
                'average_age': self.calculate_average_age(df['تاريخ_الميلاد']),
                'age_distribution': self.get_age_distribution(df['تاريخ_الميلاد']),
                
                # البيانات الجديدة
                'marital_status_distribution': self.get_marital_distribution(df),
                'job_title_distribution': self.get_job_title_distribution(df),
                'department_distribution': self.get_department_distribution(df),
                'dependents_analysis': self.analyze_dependents(df),
                'salary_distribution': self.get_salary_distribution(df['الراتب'])
            }
            
            # حساب عوامل المخاطر
            analysis['risk_factors'] = {
                'age_risk': self.calculate_age_risk_factor(analysis['age_distribution']),
                'dependents_risk': self.calculate_dependents_risk(analysis['dependents_analysis']),
                'salary_risk': self.calculate_salary_risk(analysis['salary_distribution']),
                'gender_risk': self.calculate_gender_risk(analysis['male_count'], analysis['female_count']),
                'marital_risk': self.calculate_marital_risk(analysis['marital_status_distribution'])
            }
            
            return analysis
            
        except Exception as e:
            raise ValueError(f"خطأ في تحليل ملف الموظفين: {str(e)}")

    def analyze_dependents(self, df):
        """تحليل بيانات المعالين"""
        if 'المعالين' not in df.columns:
            return {'total': 0, 'average': 0, 'distribution': {}}
        
        dependents_series = df['المعالين'].fillna(0)
        
        return {
            'total': int(dependents_series.sum()),
            'average': float(dependents_series.mean()),
            'distribution': {
                '0': len(dependents_series[dependents_series == 0]),
                '1_2': len(dependents_series[(dependents_series >= 1) & (dependents_series <= 2)]),
                '3_4': len(dependents_series[(dependents_series >= 3) & (dependents_series <= 4)]),
                '5+': len(dependents_series[dependents_series >= 5])
            },
            'employees_with_dependents': len(dependents_series[dependents_series > 0]),
            'percentage_with_dependents': float(len(dependents_series[dependents_series > 0]) / len(df) * 100)
        }

    def calculate_dependents_risk(self, dependents_analysis):
        """احتساب خطر المعالين"""
        avg_dependents = dependents_analysis['average']
        
        if avg_dependents == 0:
            return Decimal('0.9')  # خصم 10% لعدم وجود معالين
        elif avg_dependents <= 2:
            return Decimal('1.0')  # خطر عادي
        elif avg_dependents <= 4:
            return Decimal('1.2')  # زيادة 20% للمعالين الكثر
        else:
            return Decimal('1.4')  # زيادة 40% للكثير من المعالين

    def calculate_base_premium(self, employee_analysis, coverage_plan):
        """حساب القسط الأساسي مع مراعاة المعالين"""
        base_per_employee = coverage_plan.base_price_per_employee
        
        # سعر أساسي للموظف
        base_premium = employee_analysis['total_employees'] * base_per_employee
        
        # إضافة تكلفة المعالين (50% من سعر الموظف لكل معال)
        if 'total_dependents' in employee_analysis:
            dependents_premium = employee_analysis['total_dependents'] * base_per_employee * Decimal('0.5')
            base_premium += dependents_premium
        
        # تطبيق عوامل المخاطر
        if 'risk_factors' in employee_analysis:
            total_risk_factor = Decimal('1.0')
            for risk_name, risk_value in employee_analysis['risk_factors'].items():
                total_risk_factor *= risk_value
            
            base_premium = base_premium * total_risk_factor
        
        return base_premium
    def calculate_base_premium(self, employee_analysis, coverage_plan):
        """حساب القسط الأساسي بناءً على تحليل الموظفين"""
        base_per_employee = coverage_plan.base_price_per_employee
        
        # حساب لكل موظف + معالينه
        total_insured = employee_analysis['total_employees'] + employee_analysis['total_dependents']
        
        # سعر أساسي للموظف + 50% لكل معال
        base_premium = (employee_analysis['total_employees'] * base_per_employee) + \
                      (employee_analysis['total_dependents'] * base_per_employee * Decimal('0.5'))
        
        # تعديل حسب العمر
        base_premium = base_premium * Decimal(str(employee_analysis.get('age_risk_factor', 1.0)))
        
        return base_premium
    
    def calculate_company_factors(self, company):
        """حساب عوامل الشركة"""
        factors = {
            'sector_factor': self.get_sector_factor(company.sector),
            'size_factor': self.base_factors['size_factors'].get(company.size_category, Decimal('1.0')),
            'environment_factor': self.base_factors['environment_factors'].get(company.work_environment, Decimal('1.0')),
            'risk_factor': self.base_factors['risk_factors'].get(company.risk_level, Decimal('1.0')),
            'city_factor': self.base_factors['city_factors'].get(company.city, Decimal('1.0')),
            'age_factor': self.get_age_factor(company.establishment_age),
            'claims_factor': self.get_claims_factor(company.claims_history),
            'insurance_history_factor': self.get_insurance_history_factor(
                company.has_previous_insurance, 
                company.previous_insurance_years
            )
        }
        
        # حساب العامل الإجمالي
        total_factor = Decimal('1.0')
        for factor in factors.values():
            total_factor *= factor
        
        factors['total_factor'] = total_factor
        
        return factors
    
    def get_sector_factor(self, sector):
        """الحصول على عامل القطاع"""
        sector_data = self.base_factors['sector_factors'].get(sector)
        if sector_data:
            return sector_data['base'] + sector_data['risk_adjustment']
        return Decimal('1.0')
    
    def get_age_factor(self, age):
        """عامل عمر الشركة"""
        if age <= 3:
            return self.base_factors['age_factors']['1-3']
        elif age <= 7:
            return self.base_factors['age_factors']['4-7']
        elif age <= 15:
            return self.base_factors['age_factors']['8-15']
        else:
            return self.base_factors['age_factors']['16+']
    
    def get_claims_factor(self, claims_count):
        """عامل تاريخ المطالبات"""
        if claims_count == 0:
            return Decimal('0.9')
        elif claims_count <= 3:
            return Decimal('1.0')
        elif claims_count <= 10:
            return Decimal('1.2')
        else:
            return Decimal('1.5')
    
    def get_insurance_history_factor(self, has_previous, years):
        """عامل تاريخ التأمين"""
        if not has_previous:
            return Decimal('1.1')
        elif years >= 3:
            return Decimal('0.85')
        else:
            return Decimal('1.0')
    
    def apply_limits(self, premium, company, coverage_plan):
        """تطبيق الحدود الدنيا والقصوى"""
        sector_data = self.base_factors['sector_factors'].get(company.sector)
        if sector_data:
            min_premium = sector_data['min'] * company.total_employees
            max_premium = sector_data['max'] * company.total_employees
            
            if premium < min_premium:
                return min_premium
            elif premium > max_premium:
                return max_premium
        
        return premium
    
    def calculate_simple_premium(self, company, coverage_plan):
        """حساب قسط بسيط في حالة عدم وجود ملف موظفين"""
        # حساب أساسي
        base_premium = company.total_employees * coverage_plan.base_price_per_employee
        
        # تطبيق عامل القطاع
        sector_factor = self.get_sector_factor(company.sector)
        adjusted_premium = base_premium * sector_factor
        
        # عوامل إضافية
        company_factors = self.calculate_company_factors(company)
        final_premium = adjusted_premium * company_factors['total_factor']
        
        # إضافة التحميلات الإدارية
        final_premium = final_premium * Decimal('1.15')
        
        return {
            'base_premium': base_premium,
            'company_factors': company_factors,
            'employee_analysis': {
                'total_employees': company.total_employees,
                'total_dependents': 0,
                'note': 'حساب بدون ملف الموظفين'
            },
            'final_premium': final_premium,
            'annual_premium': final_premium,
            'monthly_premium': final_premium / Decimal('12')
        }
    
    def calculate_average_age(self, birth_dates):
        """حساب متوسط العمر"""
        try:
            current_year = datetime.now().year
            ages = []
            for date in birth_dates:
                if pd.isna(date):
                    continue
                ages.append(current_year - pd.to_datetime(date).year)
            return sum(ages) / len(ages) if ages else 30.0  # متوسط 30 سنة إذا لم تكن البيانات متوفرة
        except:
            return 30.0
    
    def get_age_distribution(self, birth_dates):
        """توزيع الأعمار"""
        try:
            current_year = datetime.now().year
            ages = []
            for date in birth_dates:
                if pd.isna(date):
                    continue
                ages.append(current_year - pd.to_datetime(date).year)
            
            distribution = {
                'under_30': len([age for age in ages if age < 30]),
                '30_40': len([age for age in ages if 30 <= age < 40]),
                '40_50': len([age for age in ages if 40 <= age < 50]),
                '50_60': len([age for age in ages if 50 <= age < 60]),
                'over_60': len([age for age in ages if age >= 60])
            }
            
            return distribution
        except:
            return {
                'under_30': 0,
                '30_40': 0,
                '40_50': 0,
                '50_60': 0,
                'over_60': 0
            }
    
    def calculate_age_risk_factor(self, age_distribution):
        """عامل المخاطر حسب توزيع الأعمار"""
        try:
            total = sum(age_distribution.values())
            if total == 0:
                return 1.0
            
            # كل فئة عمرية لها وزن
            weights = {
                'under_30': Decimal('0.8'),
                '30_40': Decimal('1.0'),
                '40_50': Decimal('1.2'),
                '50_60': Decimal('1.5'),
                'over_60': Decimal('2.0')
            }
            
            weighted_sum = Decimal('0.0')
            for category, count in age_distribution.items():
                weighted_sum += weights[category] * Decimal(str(count))
            
            return float(weighted_sum / Decimal(str(total)))
        except:
            return 1.0
    
    def get_salary_distribution(self, salaries):
        """توزيع الرواتب"""
        try:
            valid_salaries = [s for s in salaries if not pd.isna(s)]
            return {
                'low': len([s for s in valid_salaries if s < 50000]),
                'medium': len([s for s in valid_salaries if 50000 <= s < 150000]),
                'high': len([s for s in valid_salaries if s >= 150000])
            }
        except:
            return {'low': 0, 'medium': 0, 'high': 0}
    
    def get_dependents_distribution(self, dependents):
        """توزيع عدد المعالين"""
        try:
            valid_dependents = [d for d in dependents if not pd.isna(d)]
            return {
                '0': len([d for d in valid_dependents if d == 0]),
                '1_2': len([d for d in valid_dependents if 1 <= d <= 2]),
                '3_4': len([d for d in valid_dependents if 3 <= d <= 4]),
                '5+': len([d for d in valid_dependents if d >= 5])
            }
        except:
            return {'0': 0, '1_2': 0, '3_4': 0, '5+': 0}