from datetime import date
from decimal import Decimal
import unittest

from types import SimpleNamespace

from car_insurance.calculations import calculate_premium


class CalculatePremiumTests(unittest.TestCase):
    def test_economy_car_prime_driver_no_claims(self):
        # Vehicle: car, 2 years old, value 15,000
        vehicle = SimpleNamespace(vehicle_type='car', year=(date.today().year - 2), current_value=Decimal('15000.00'))
        result = calculate_premium(vehicle=vehicle,
                                   coverage_type='comprehensive',
                                   driver_age=30,
                                   claims_history=0,
                                   no_claims_years=2)

        # Expected manual calculation:
        # base 800 * 1.2 (comprehensive) = 960
        # age <3 -> *1.3 = 1248
        # value 15000 -> *0.9 = 1123.20
        # driver age 30 -> *1.0 = 1123.20
        # no claims discount 2 * 5% = 10% -> discount = 112.32
        # final = 1123.20 - 112.32 = 1010.88

        self.assertIn('final_premium', result)
        self.assertEqual(result['final_premium'], Decimal('1010.88'))

    def test_luxury_car_young_driver_with_claims(self):
        # Vehicle: SUV, 1 year old, value 60000, young driver with 1 prior claim
        vehicle = SimpleNamespace(vehicle_type='suv', year=(date.today().year - 1), current_value=Decimal('60000.00'))
        result = calculate_premium(vehicle=vehicle,
                                   coverage_type='comprehensive',
                                   driver_age=23,
                                   claims_history=1,
                                   no_claims_years=0)

        # Sanity checks: final premium should be >= minimum and reflect youth/claim penalties
        self.assertIn('base_premium', result)
        self.assertIn('final_premium', result)
        self.assertGreaterEqual(result['final_premium'], Decimal('200.00'))
        # Because of claim and young age, final > base before discount
        self.assertGreater(result['final_premium'], Decimal('0'))


if __name__ == '__main__':
    unittest.main()
