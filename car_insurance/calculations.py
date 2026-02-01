from decimal import Decimal
from datetime import date, timedelta
from .rules import compute_adjustments, RATING
from .models import Vehicle, CarInsuranceQuote
from django.db import transaction 
import uuid

def calculate_premium(vehicle, coverage_type='comprehensive', driver_age=30, 
                     claims_history=0, no_claims_years=0):
    """
    Calculate insurance premium for a vehicle
    
    Args:
        vehicle: Vehicle instance
        coverage_type: 'third_party', 'third_party_fire_theft', or 'comprehensive'
        driver_age: Age of the main driver
        claims_history: Number of previous claims
        no_claims_years: Years of no claims bonus
    
    Returns:
        Dictionary with premium breakdown
    """
    
    # Get base rate for vehicle type
    vehicle_type = vehicle.vehicle_type if vehicle.vehicle_type in ['car', 'suv', 'truck', 'motorcycle'] else 'car'
    base_rate = Decimal(str(RATING.get('base_rates', {}).get(vehicle_type, 800.00)))
    
    # Get coverage multiplier
    coverage_multiplier = Decimal(str(RATING.get('coverage_multipliers', {}).get(coverage_type, 1.2)))
    
    # Calculate base premium
    base_premium = base_rate * coverage_multiplier
    
    # Compute adjustments
    adjustments = compute_adjustments(
        vehicle=vehicle,
        coverage_type=coverage_type,
        driver_age=driver_age,
        claims_history=claims_history,
        no_claims_years=no_claims_years
    )
    
    # Apply multiplier
    adjusted_premium = base_premium * adjustments['multiplier']
    
    # Apply no claims discount
    discount_amount = adjusted_premium * adjustments['discount_percent']
    premium_after_discount = adjusted_premium - discount_amount
    
    # Apply minimum premium
    min_premium = Decimal(str(RATING.get('min_premium', 200.00)))
    final_base_premium = max(premium_after_discount, min_premium)
    
    # Calculate excess (default or from rating table)
    standard_excess = Decimal(str(RATING.get('standard_excess', 500.00)))
    
    return {
        'base_premium': round(float(base_premium), 2),
        'adjusted_premium': round(float(adjusted_premium), 2),
        'discount_amount': round(float(discount_amount), 2),
        'final_premium': round(float(final_base_premium), 2),
        'excess_amount': round(float(standard_excess), 2),
        'breakdown': {
            'base_rate': float(base_rate),
            'coverage_multiplier': float(coverage_multiplier),
            'adjustment_multiplier': float(adjustments['multiplier']),
            'no_claims_discount_percent': float(adjustments['discount_percent'] * 100),
            'vehicle_age': adjustments['vehicle_age'],
            'notes': adjustments['notes']
        }
    }

def calculate_short_term_premium(annual_premium, duration_days):
    """
    Calculate premium for short-term insurance
    
    Args:
        annual_premium: Annual premium amount
        duration_days: Duration of coverage in days
    
    Returns:
        Short-term premium amount
    """
    duration_days = int(duration_days)
    rates = RATING.get('short_term_rates_percent_of_annual', {})
    
    # Find the appropriate rate
    if duration_days <= 15:
        rate_percent = rates.get('15_days', 12.5)
    elif duration_days <= 30:
        rate_percent = rates.get('1_month', 25)
    elif duration_days <= 60:
        rate_percent = rates.get('2_months', 37.5)
    elif duration_days <= 90:
        rate_percent = rates.get('3_months', 50)
    elif duration_days <= 120:
        rate_percent = rates.get('4_months', 60)
    elif duration_days <= 150:
        rate_percent = rates.get('5_months', 70)
    elif duration_days <= 180:
        rate_percent = rates.get('6_months', 75)
    elif duration_days <= 210:
        rate_percent = rates.get('7_months', 80)
    elif duration_days <= 240:
        rate_percent = rates.get('8_months', 85)
    else:
        rate_percent = rates.get('more_than_8_months', 100)
    
    premium = Decimal(str(annual_premium)) * (Decimal(str(rate_percent)) / Decimal('100.0'))
    return round(float(premium), 2)

def calculate_depreciation(vehicle_value, vehicle_year, loss_type='partial'):
    """
    Calculate depreciation for claim settlement
    
    Args:
        vehicle_value: Current vehicle value
        vehicle_year: Vehicle manufacturing year
        loss_type: 'partial' or 'total'
    
    Returns:
        Depreciated value
    """
    current_year = date.today().year
    vehicle_age = current_year - vehicle_year
    
    # Get depreciation percentage from rating table
    depreciation_table = RATING.get('depreciation_by_age_years_percent', {})
    
    if vehicle_age <= 1:
        dep_percent = depreciation_table.get('0_to_1', 10)
    elif vehicle_age == 2:
        dep_percent = depreciation_table.get('2', 15)
    elif vehicle_age == 3:
        dep_percent = depreciation_table.get('3', 20)
    elif vehicle_age == 4:
        dep_percent = depreciation_table.get('4', 25)
    elif vehicle_age == 5:
        dep_percent = depreciation_table.get('5', 30)
    elif vehicle_age == 6:
        dep_percent = depreciation_table.get('6', 35)
    elif vehicle_age == 7:
        dep_percent = depreciation_table.get('7', 40)
    elif vehicle_age == 8:
        dep_percent = depreciation_table.get('8', 45)
    else:
        dep_percent = depreciation_table.get('9_plus', 50)
    
    # For total loss, use higher depreciation
    if loss_type == 'total':
        dep_percent = min(dep_percent + 10, 80)
    
    depreciated_value = Decimal(str(vehicle_value)) * (1 - Decimal(str(dep_percent)) / 100)
    return {
        'original_value': float(vehicle_value),
        'vehicle_age_years': vehicle_age,
        'depreciation_percent': dep_percent,
        'depreciated_value': round(float(depreciated_value), 2)
    }

def create_quote_from_vehicle(vehicle, user, coverage_type='comprehensive', 
                             driver_age=30, claims_history=0, no_claims_years=0):
    """
    Create an insurance quote for a vehicle
    """
    try:
        with transaction.atomic():
            # توليد رقم اقتباس فريد
            quote_number = f"QTE-{uuid.uuid4().hex[:8].upper()}"
        # Calculate premium
        premium_result = calculate_premium(
            vehicle=vehicle,
            coverage_type=coverage_type,
            driver_age=driver_age,
            claims_history=claims_history,
            no_claims_years=no_claims_years
        )
    
        # Create quote
        quote = CarInsuranceQuote.objects.create(
            vehicle=vehicle,
            user=user,
            quote_number=quote_number,
            coverage_type=coverage_type,
            premium_amount=premium_result.get('final_premium', Decimal('0.00')),
            excess_amount=premium_result.get('excess_amount', Decimal('0.00')),
            # driver_age=driver_age,
            claims_history=claims_history,            no_claims_years=no_claims_years,
            base_premium=premium_result.get('base_premium', Decimal('0.00')),
            discount_amount=premium_result.get('discount_amount', Decimal('0.00')),
            final_premium=premium_result.get('final_premium', Decimal('0.00')),
            status='quoted'
        )
    
        # Set dates (1 year validity)
        quote.start_date = date.today()
        quote.end_date = date.today() + timedelta(days=30)  # Quote valid for 30 days
        quote.save()
        
        return quote, premium_result
    except Exception as e:
        # سجل الخطأ للتصحيح
        import traceback
        print(f"Error in create_quote_from_vehicle: {str(e)}")
        print(traceback.format_exc())
        raise