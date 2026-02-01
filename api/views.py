from django.shortcuts import render

# Create your views here.
# api/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, JSONParser
from django.db import transaction
import pandas as pd
import io
import json

class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    parser_classes = [MultiPartParser, JSONParser]
    
    def get_queryset(self):
        company_id = self.kwargs.get('company_id')
        return Employee.objects.filter(company_id=company_id)
    
    # @action(detail=True, methods=['post'], url_path='upload-employees')
    # def upload_employees(self, request, pk=None):
    #     """
    #     رفع ملف Excel/CSV للموظفين
    #     """
    #     try:
    #         company = self.get_object()
            
    #         if 'employees_file' not in request.FILES:
    #             return Response(
    #                 {'error': 'لم يتم توفير ملف'},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )
            
    #         file = request.FILES['employees_file']
            
    #         # قراءة الملف حسب نوعه
    #         if file.name.endswith('.csv'):
    #             df = pd.read_csv(io.StringIO(file.read().decode('utf-8')))
    #         elif file.name.endswith(('.xlsx', '.xls')):
    #             df = pd.read_excel(file)
    #         else:
    #             return Response(
    #                 {'error': 'نوع الملف غير مدعوم'},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )
            
    #         # التحقق من الأعمدة المطلوبة
    #         required_columns = ['name', 'age', 'gender', 'position', 'department', 'base_salary']
    #         missing_columns = [col for col in required_columns if col not in df.columns]
            
    #         if missing_columns:
    #             return Response(
    #                 {'error': f'أعمدة مفقودة: {missing_columns}'},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )
            
    #         # معالجة البيانات
    #         employees_created = 0
    #         errors = []
            
    #         with transaction.atomic():
    #             for index, row in df.iterrows():
    #                 try:
    #                     # إنشاء الموظف
    #                     employee = Employee(
    #                         company=company,
    #                         name=row.get('name', '').strip(),
    #                         age=int(row.get('age', 25)),
    #                         gender=row.get('gender', 'male').lower(),
    #                         marital_status=row.get('marital_status', 'single').lower(),
    #                         position=row.get('position', '').strip(),
    #                         department=row.get('department', '').strip(),
    #                         base_salary=float(row.get('base_salary', 0)),
    #                         monthly_allowances=float(row.get('monthly_allowances', 0)),
    #                         has_children=row.get('has_children', 'False').lower() == 'true',
    #                         number_of_children=int(row.get('number_of_children', 0)),
    #                         spouse_age=int(row.get('spouse_age', 0)) if row.get('spouse_age') else None
    #                     )
    #                     employee.full_clean()
    #                     employee.save()
    #                     employees_created += 1
                        
    #                 except Exception as e:
    #                     errors.append({
    #                         'row': index + 2,
    #                         'error': str(e),
    #                         'data': row.to_dict()
    #                     })
            
    #         # تحديث عدد موظفي الشركة
    #         company.total_employees = Employee.objects.filter(company=company).count()
    #         company.save()
            
    #         return Response({
    #             'success': True,
    #             'message': f'تم رفع {employees_created} موظف بنجاح',
    #             'employees_created': employees_created,
    #             'errors': errors if errors else None,
    #             'total_employees': company.total_employees
    #         })
            
    #     except Company.DoesNotExist:
    #         return Response(
    #             {'error': 'الشركة غير موجودة'},
    #             status=status.HTTP_404_NOT_FOUND
    #         )
    #     except Exception as e:
    #         return Response(
    #             {'error': str(e)},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request, company_id=None):
        """
        إنشاء موظفين بشكل جماعي باستخدام JSON
        """
        try:
            company = Company.objects.get(id=company_id)
            employees_data = request.data.get('employees', [])
            
            if not employees_data:
                return Response(
                    {'error': 'لا توجد بيانات للموظفين'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            employees_created = 0
            errors = []
            
            with transaction.atomic():
                for emp_data in employees_data:
                    try:
                        employee = Employee(
                            company=company,
                            name=emp_data.get('name', '').strip(),
                            age=emp_data.get('age', 25),
                            gender=emp_data.get('gender', 'male'),
                            marital_status=emp_data.get('marital_status', 'single'),
                            position=emp_data.get('position', '').strip(),
                            department=emp_data.get('department', '').strip(),
                            base_salary=emp_data.get('base_salary', 0),
                            monthly_allowances=emp_data.get('monthly_allowances', 0),
                            has_children=emp_data.get('has_children', False),
                            number_of_children=emp_data.get('number_of_children', 0),
                            spouse_age=emp_data.get('spouse_age')
                        )
                        employee.full_clean()
                        employee.save()
                        employees_created += 1
                        
                    except Exception as e:
                        errors.append({
                            'employee': emp_data.get('name', 'غير معروف'),
                            'error': str(e)
                        })
            
            # تحديث عدد موظفي الشركة
            company.total_employees = Employee.objects.filter(company=company).count()
            company.save()
            
            return Response({
                'success': True,
                'message': f'تم إنشاء {employees_created} موظف بنجاح',
                'employees_created': employees_created,
                'errors': errors if errors else None
            })
            
        except Company.DoesNotExist:
            return Response(
                {'error': 'الشركة غير موجودة'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def report(self, request, company_id=None):
        """
        توليد تقرير عن موظفي الشركة
        """
        try:
            company = Company.objects.get(id=company_id)
            employees = Employee.objects.filter(company=company)
            
            # إحصائيات
            total_employees = employees.count()
            total_salary = employees.aggregate(Sum('base_salary'))['base_salary__sum'] or 0
            avg_salary = total_salary / total_employees if total_employees > 0 else 0
            
            # توزيع حسب القسم
            department_stats = employees.values('department').annotate(
                count=Count('id'),
                avg_salary=Avg('base_salary'),
                total_salary=Sum('base_salary')
            )
            
            # توزيع حسب الجنس
            gender_stats = employees.values('gender').annotate(
                count=Count('id')
            )
            
            return Response({
                'company': company.name,
                'total_employees': total_employees,
                'total_monthly_salary': total_salary,
                'average_salary': avg_salary,
                'department_stats': list(department_stats),
                'gender_stats': list(gender_stats),
                'employees': EmployeeSerializer(employees, many=True).data
            })
            
        except Company.DoesNotExist:
            return Response(
                {'error': 'الشركة غير موجودة'},
                status=status.HTTP_404_NOT_FOUND
            )
        
