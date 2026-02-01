from decimal import Decimal
from datetime import date
import os
import json


# Load rating table from JSON config
_TABLE_PATH = os.path.join(os.path.dirname(__file__), 'rating_table.json')
try:
    with open(_TABLE_PATH, 'r', encoding='utf-8') as f:
        RATING = json.load(f)
except Exception:
    RATING = {}


def _get_decimal(v, default='0.0'):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(default)


def compute_adjustments(vehicle, coverage_type, driver_age, claims_history, no_claims_years):
    """Compute multipliers and discounts using `rating_table.json`."""
    notes = []
    multiplier = Decimal('1.0')

    # Vehicle age
    current_year = date.today().year
    vehicle_age = current_year - (getattr(vehicle, 'year', current_year) or current_year)
    if vehicle_age < RATING.get('vehicle_age', {}).get('new_less_than_years', 3):
        multiplier *= _get_decimal(RATING.get('vehicle_age', {}).get('multipliers', {}).get('new', 1.3))
        notes.append('new_vehicle_age')
    elif vehicle_age < 7:
        multiplier *= _get_decimal(RATING.get('vehicle_age', {}).get('multipliers', {}).get('medium', 1.1))
        notes.append('medium_vehicle_age')
    else:
        multiplier *= _get_decimal(RATING.get('vehicle_age', {}).get('multipliers', {}).get('older', 0.9))
        notes.append('older_vehicle_age')

    # Vehicle value tiers
    try:
        value = _get_decimal(getattr(vehicle, 'current_value', 0))
    except Exception:
        value = Decimal('0.00')

    vt = RATING.get('vehicle_value_tiers', {})
    if value > _get_decimal(vt.get('luxury_threshold', 50000)):
        multiplier *= _get_decimal(vt.get('multipliers', {}).get('luxury', 1.4))
        notes.append('luxury_vehicle')
    elif value > _get_decimal(vt.get('mid_threshold', 25000)):
        multiplier *= _get_decimal(vt.get('multipliers', {}).get('midrange', 1.2))
        notes.append('midrange_vehicle')
    else:
        multiplier *= _get_decimal(vt.get('multipliers', {}).get('economy', 0.9))
        notes.append('economy_vehicle')

    # Engine size
    try:
        engine = _get_decimal(getattr(vehicle, 'engine_size', 0))
    except Exception:
        engine = Decimal('0.0')

    es = RATING.get('engine_size_multipliers', {})
    if engine >= _get_decimal(es.get('large_threshold', 3.0)):
        multiplier *= _get_decimal(es.get('multipliers', {}).get('large', 1.2))
        notes.append('large_engine')
    elif engine >= _get_decimal(es.get('mid_threshold', 2.0)):
        multiplier *= _get_decimal(es.get('multipliers', {}).get('mid', 1.1))
        notes.append('mid_engine')

    # Driver age
    if driver_age is None:
        driver_age = 30

    da = RATING.get('driver_age', {})
    if driver_age < da.get('young_threshold', 25):
        multiplier *= _get_decimal(da.get('multipliers', {}).get('young', 1.5))
        notes.append('young_driver')
    elif driver_age < da.get('young_adult_threshold', 30):
        multiplier *= _get_decimal(da.get('multipliers', {}).get('young_adult', 1.2))
        notes.append('young_adult_driver')
    elif driver_age > da.get('senior_threshold', 65):
        multiplier *= _get_decimal(da.get('multipliers', {}).get('senior', 1.3))
        notes.append('senior_driver')

    # Claims history penalty
    claims_penalty_per = _get_decimal(RATING.get('claims_penalty_per_claim', 0.2))
    if claims_history and claims_history > 0:
        claims_mul = Decimal('1.0') + (claims_penalty_per * _get_decimal(claims_history))
        multiplier *= claims_mul
        notes.append(f'claims_penalty_{claims_history}')

    # No claims bonus
    per_year = _get_decimal(RATING.get('no_claims', {}).get('per_year', 0.05))
    no_claims_max = _get_decimal(RATING.get('no_claims', {}).get('max', 0.3))
    discount_percent = min(_get_decimal(no_claims_years) * per_year, no_claims_max)
    if discount_percent > 0:
        notes.append(f'no_claims_discount_{(discount_percent * 100):.0f}%')

    return {
        'multiplier': multiplier.quantize(Decimal('0.0001')),
        'discount_percent': discount_percent,
        'notes': notes,
        'vehicle_age': vehicle_age,
    }
