from django.test import TestCase
from django.contrib.auth import get_user_model
from car_insurance.models import Vehicle
from car_insurance import rules, calculations
from decimal import Decimal


User = get_user_model()


class RulesEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')

    def test_compute_adjustments_economy_driver_prime(self):
        v = Vehicle.objects.create(user=self.user, make='Toyota', model='Yaris', year=2020, current_value=Decimal('8000.00'), engine_size=Decimal('1.3'), vehicle_type='car')
        adj = rules.compute_adjustments(v, 'comprehensive', driver_age=35, claims_history=0, no_claims_years=2)
        # economy vehicle multiplier should include economy multiplier and medium/new age depending on year
        self.assertIn('economy_vehicle', adj['notes'])
        self.assertGreaterEqual(adj['multiplier'], Decimal('0.0'))
        self.assertGreaterEqual(adj['discount_percent'], Decimal('0.0'))

    def test_young_driver_and_claims(self):
        v = Vehicle.objects.create(user=self.user, make='Honda', model='Civic', year=2024, current_value=Decimal('30000.00'), engine_size=Decimal('2.2'), vehicle_type='car')
        adj = rules.compute_adjustments(v, 'comprehensive', driver_age=23, claims_history=1, no_claims_years=0)
        self.assertIn('young_driver', adj['notes'])
        self.assertIn('claims_penalty_1', adj['notes'])
        # multiplier should be > 1 due to young driver and claim
        self.assertTrue(adj['multiplier'] > Decimal('1.0'))

    def test_calculate_premium_integration(self):
        v = Vehicle.objects.create(user=self.user, make='BMW', model='X5', year=2022, current_value=Decimal('60000.00'), engine_size=Decimal('3.5'), vehicle_type='suv')
        result = calculations.calculate_premium(v, 'comprehensive', driver_age=45, claims_history=0, no_claims_years=1)
        # result keys exist and values sensible
        self.assertIn('final_premium', result)
        self.assertIn('base_premium', result)
        self.assertTrue(Decimal(result['final_premium']) >= Decimal('0.00'))
