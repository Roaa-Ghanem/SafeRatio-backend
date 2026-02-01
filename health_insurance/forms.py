# health_insurance/forms.py
from django import forms
from django.core.validators import FileExtensionValidator
from .models import HealthEstablishment, HealthInsuranceQuote
import pandas as pd

class HealthEstablishmentForm(forms.ModelForm):
    """نموذج إضافة/تعديل منشأة صحية"""
    class Meta:
        model = HealthEstablishment
        fields = [
            'name', 'establishment_type', 'size_category', 'cr_number',
            'address', 'city', 'phone', 'email', 'total_employees',
            'establishment_age', 'annual_revenue', 'has_previous_insurance'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اسم المنشأة بالكامل'
            }),
            'establishment_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'size_category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'cr_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'رقم السجل التجاري'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'العنوان التفصيلي'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'المدينة'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'رقم الهاتف'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'البريد الإلكتروني'
            }),
            'total_employees': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'establishment_age': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'عدد سنوات العمل'
            }),
            'annual_revenue': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'الإيرادات السنوية بالدولار'
            }),
            'has_previous_insurance': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'name': 'اسم المنشأة',
            'establishment_type': 'نوع المنشأة',
            'size_category': 'حجم المنشأة',
            'cr_number': 'رقم السجل التجاري',
            'address': 'العنوان',
            'city': 'المدينة',
            'phone': 'رقم الهاتف',
            'email': 'البريد الإلكتروني',
            'total_employees': 'عدد الموظفين الكلي',
            'establishment_age': 'عمر المنشأة (سنوات)',
            'annual_revenue': 'الإيرادات السنوية (دولار)',
            'has_previous_insurance': 'لديه تأمين سابق'
        }

class HealthQuoteForm(forms.ModelForm):
    """نموذج إنشاء اقتباس صحي"""
    class Meta:
        model = HealthInsuranceQuote
        fields = ['coverage_plan', 'insured_employees_count', 'coverage_period', 'notes']
        widgets = {
            'coverage_plan': forms.Select(attrs={
                'class': 'form-control'
            }),
            'insured_employees_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'coverage_period': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 36,
                'value': 12
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'ملاحظات إضافية (اختياري)'
            })
        }
        labels = {
            'coverage_plan': 'خطة التغطية',
            'insured_employees_count': 'عدد الموظفين المؤمن عليهم',
            'coverage_period': 'فترة التغطية (شهر)',
            'notes': 'ملاحظات'
        }

class EmployeeExcelUploadForm(forms.Form):
    """نموذج رفع ملف Excel للموظفين"""
    excel_file = forms.FileField(
        label='ملف Excel للموظفين',
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )
    
    def clean_excel_file(self):
        """التأكد من صحة ملف Excel"""
        excel_file = self.cleaned_data['excel_file']
        
        try:
            # قراءة ملف Excel
            df = pd.read_excel(excel_file)
            
            # التحقق من الأعمدة المطلوبة
            required_columns = ['employee_id', 'full_name', 'birth_date', 'gender', 'marital_status', 'dependents_count']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise forms.ValidationError(
                    f'الأعمدة التالية مفقودة في الملف: {", ".join(missing_columns)}'
                )
            
            # التحقق من عدد الصفوف
            if len(df) > 1000:
                raise forms.ValidationError('الحد الأقصى لعدد الموظفين في الملف هو 1000')
            
            # التحقق من أنواع البيانات
            try:
                df['dependents_count'] = pd.to_numeric(df['dependents_count'], errors='raise')
                df['dependents_count'] = df['dependents_count'].fillna(0).astype(int)
                
                # التأكد من أن أرقام المعالين غير سالبة
                if (df['dependents_count'] < 0).any():
                    raise forms.ValidationError('عدد المعالين يجب أن يكون عدداً صحيحاً غير سالب')
                
            except ValueError:
                raise forms.ValidationError('يجب أن يكون عمود dependents_count أرقاماً صحيحة')
            
            # التحقق من الجنس
            valid_genders = ['ذكر', 'أنثى', 'M', 'F', 'male', 'female']
            invalid_genders = df[~df['gender'].isin(valid_genders)]['gender'].unique()
            if len(invalid_genders) > 0:
                raise forms.ValidationError(f'قيم غير صالحة للجنس: {", ".join(invalid_genders)}')
            
            # التحقق من الحالة الاجتماعية
            valid_statuses = ['أعزب', 'متزوج', 'مطلق', 'أرمل', 'single', 'married', 'divorced', 'widowed']
            invalid_statuses = df[~df['marital_status'].isin(valid_statuses)]['marital_status'].unique()
            if len(invalid_statuses) > 0:
                raise forms.ValidationError(f'قيم غير صالحة للحالة الاجتماعية: {", ".join(invalid_statuses)}')
            
            # حفظ البيانات المؤقتة في cleaned_data
            self.cleaned_data['employee_data'] = df.to_dict('records')
            
            return excel_file
            
        except pd.errors.EmptyDataError:
            raise forms.ValidationError('الملف فارغ')
        except pd.errors.ParserError:
            raise forms.ValidationError('الملف غير صالح أو تالف')
        except Exception as e:
            raise forms.ValidationError(f'خطأ في قراءة الملف: {str(e)}')

class HealthPremiumCalculatorForm(forms.Form):
    """نموذج حاسبة الأقساط الصحية"""
    ESTABLISHMENT_TYPE_CHOICES = [
        ('hospital', 'مستشفى'),
        ('center', 'مركز طبي'),
        ('clinic', 'عيادة'),
        ('lab', 'مختبر'),
        ('pharmacy', 'صيدلية'),
        ('other', 'أخرى')
    ]
    
    establishment_type = forms.ChoiceField(
        label='نوع المنشأة',
        choices=ESTABLISHMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'establishment_type'
        })
    )
    
    employee_count = forms.IntegerField(
        label='عدد الموظفين',
        min_value=1,
        max_value=10000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'employee_count',
            'placeholder': 'أدخل عدد الموظفين'
        })
    )
    
    city = forms.CharField(
        label='المدينة',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'city',
            'placeholder': 'المدينة الرئيسية'
        })
    )
    
    has_previous_insurance = forms.BooleanField(
        label='لديه تأمين صحي سابق',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'has_previous_insurance'
        })
    )
    
    coverage_plan = forms.ModelChoiceField(
        label='خطة التغطية (اختياري)',
        queryset=None,
        required=False,
        empty_label="اختر خطة التغطية",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'coverage_plan'
        })
    )
    
    custom_base_price = forms.DecimalField(
        label='السعر الأساسي المخصص (دولار/موظف)',
        required=False,
        min_value=500,
        max_value=5000,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'custom_base_price',
            'placeholder': '500 - 5000 دولار',
            'step': '50'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import HealthCoveragePlan
        self.fields['coverage_plan'].queryset = HealthCoveragePlan.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # التحقق من عدد الموظفين
        employee_count = cleaned_data.get('employee_count')
        if employee_count and employee_count > 10000:
            raise forms.ValidationError({
                'employee_count': 'الحد الأقصى لعدد الموظفين هو 10000'
            })
        
        # التحقق من السعر المخصص
        custom_base_price = cleaned_data.get('custom_base_price')
        if custom_base_price and custom_base_price < 500:
            raise forms.ValidationError({
                'custom_base_price': 'السعر الأساسي يجب أن يكون 500 دولار على الأقل'
            })
        
        return cleaned_data

class HealthReportFilterForm(forms.Form):
    """نموذج فلترة التقارير"""
    REPORT_TYPE_CHOICES = [
        ('summary', 'ملخص شامل'),
        ('establishment', 'تقرير المنشآت'),
        ('premium', 'تقرير الأقساط'),
        ('quotes', 'تقرير الاقتباسات'),
        ('policies', 'تقرير الوثائق')
    ]
    
    FORMAT_CHOICES = [
        ('html', 'عرض على الموقع'),
        ('pdf', 'تحميل PDF'),
        ('excel', 'تحميل Excel')
    ]
    
    report_type = forms.ChoiceField(
        label='نوع التقرير',
        choices=REPORT_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    start_date = forms.DateField(
        label='من تاريخ',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        label='إلى تاريخ',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    establishment = forms.ModelChoiceField(
        label='المنشأة',
        queryset=None,
        required=False,
        empty_label="جميع المنشآت",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    format = forms.ChoiceField(
        label='صيغة التقرير',
        choices=FORMAT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from .models import HealthEstablishment
            self.fields['establishment'].queryset = HealthEstablishment.objects.filter(user=user)
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('تاريخ البداية يجب أن يكون قبل تاريخ النهاية')
        
        return cleaned_data