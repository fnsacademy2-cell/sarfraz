import unittest
from app import app
from db import init_db, get_db_connection
import models

class TestGroceryMIS(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        init_db()

    def test_exact_user_scenario_bill_600_pay_500_has_100_dues(self):
        """
        Verify: "if customer have 600 he is paying 500 he must have dues in his account"
        """
        # 1. Create a customer whose salary day is on the 5th
        cust_id = models.create_customer(
            name="Test Teacher Imran",
            phone="0300-1112233",
            salary_day=5,
            credit_limit=10000.0,
            opening_balance=0.0
        )
        self.assertIsNotNone(cust_id)

        # 2. Create bill: 600 total, 500 paid, 100 due
        bill_id = models.create_bill(
            customer_id=cust_id,
            bill_date="2026-11-10",
            items=[
                {"product_id": None, "item_name": "Sugar (2kg)", "unit": "kg", "quantity": 2, "unit_price": 140}, # 280
                {"product_id": None, "item_name": "Milk (1L)", "unit": "litre", "quantity": 1, "unit_price": 260}, # 260
                {"product_id": None, "item_name": "Salt (1 pkt)", "unit": "pkt", "quantity": 1, "unit_price": 60},  # 60 -> Total 600
            ],
            discount=0,
            paid_now=500,
            payment_method="Cash",
            notes="Customer paid Rs. 500, Rs. 100 due on salary day"
        )
        self.assertIsNotNone(bill_id)

        # 3. Check customer profile & balance
        cust = models.get_customer_by_id(cust_id)
        self.assertEqual(cust['total_billed'], 600.0)
        self.assertEqual(cust['total_paid'], 500.0)
        self.assertEqual(cust['current_balance'], 100.0, "Customer must have exactly 100 dues remaining!")

        # 4. Check bill object
        bill = models.get_bill_by_id(bill_id)
        self.assertEqual(bill['net_amount'], 600.0)
        self.assertEqual(bill['paid_amount'], 500.0)
        self.assertEqual(bill['due_amount'], 100.0)
        self.assertEqual(bill['payment_status'], 'partial')

        # 5. Check Ledger
        ledger = models.get_customer_ledger(cust_id)
        self.assertEqual(len(ledger), 2) # 1 bill debit (600), 1 payment credit (500)
        self.assertEqual(ledger[0]['debit'], 600.0)
        self.assertEqual(ledger[0]['balance'], 600.0)
        self.assertEqual(ledger[1]['credit'], 500.0)
        self.assertEqual(ledger[1]['balance'], 100.0)

        # 6. Test editable bill: User modifies bill to add another item of 100 (Total becomes 700), customer pays 500 -> Due becomes 200
        models.update_bill(
            bill_id=bill_id,
            bill_date="2026-11-10",
            items=[
                {"product_id": None, "item_name": "Sugar (2kg)", "unit": "kg", "quantity": 2, "unit_price": 140}, # 280
                {"product_id": None, "item_name": "Milk (1L)", "unit": "litre", "quantity": 1, "unit_price": 260}, # 260
                {"product_id": None, "item_name": "Salt (1 pkt)", "unit": "pkt", "quantity": 1, "unit_price": 60},  # 60
                {"product_id": None, "item_name": "Biscuits", "unit": "pcs", "quantity": 2, "unit_price": 50},     # 100 -> Total 700
            ],
            discount=0,
            paid_now=500,
            payment_method="Cash",
            notes="Added biscuits"
        )
        cust_after_edit = models.get_customer_by_id(cust_id)
        self.assertEqual(cust_after_edit['total_billed'], 700.0)
        self.assertEqual(cust_after_edit['current_balance'], 200.0, "Dues updated to 200 after editing bill!")

        # 7. Customer pays remaining 200 on salary day
        pay_id = models.record_payment(
            customer_id=cust_id,
            amount=200.0,
            payment_date="2026-11-10",
            payment_method="Cash",
            notes="Salary day settlement"
        )
        self.assertIsNotNone(pay_id)
        cust_cleared = models.get_customer_by_id(cust_id)
        self.assertEqual(cust_cleared['total_paid'], 700.0)
        self.assertEqual(cust_cleared['current_balance'], 0.0, "Dues cleared to 0 after salary payment!")

    def test_routes_status_codes(self):
        """Verify web routes render properly"""
        routes = [
            '/',
            '/customers',
            '/bills',
            '/bills/new',
            '/payments',
            '/salary-dues',
            '/products',
            '/reports',
            '/settings',
            '/reports/export/dues-csv'
        ]
        for route in routes:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, f"Failed on route {route}")

if __name__ == '__main__':
    unittest.main()

