from db import init_db, get_db_connection
from models import create_customer, create_product, create_bill, record_payment
from datetime import date, timedelta

def seed():
    init_db()
    conn = get_db_connection()
    
    # Check if data already exists
    cust_count = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()['c']
    conn.close()

    if cust_count > 0:
        print("Data already exists in database. Skipping seed.")
        return

    print("Seeding grocery store inventory...")
    products = [
        ("Super Basmati Rice (1kg)", "Grains & Pulses", "kg", 320, 280, 150),
        ("Super Basmati Rice (5kg Bag)", "Grains & Pulses", "bag", 1550, 1400, 40),
        ("Fine Wheat Flour / Atta (10kg)", "Flour & Grains", "bag", 1350, 1220, 50),
        ("Pure Cooking Oil (1 Litre Pouch)", "Oils & Ghee", "litre", 480, 430, 80),
        ("Banaspati Ghee (1kg Pouch)", "Oils & Ghee", "packet", 510, 460, 60),
        ("Refined White Sugar (1kg)", "Essentials", "kg", 140, 128, 200),
        ("Premium Black Tea (450g Pack)", "Beverages", "packet", 680, 600, 45),
        ("Tetra Pak Fresh Milk (1 Litre)", "Dairy", "litre", 260, 235, 90),
        ("Daal Chana Special (1kg)", "Grains & Pulses", "kg", 240, 210, 70),
        ("Daal Masoor Red (1kg)", "Grains & Pulses", "kg", 290, 255, 65),
        ("Iodized Table Salt (800g)", "Spices & Seasoning", "packet", 60, 45, 120),
        ("Red Chili Powder (200g)", "Spices & Seasoning", "packet", 180, 150, 80),
        ("Turmeric / Haldi Powder (200g)", "Spices & Seasoning", "packet", 160, 130, 60),
        ("Washing Powder Detergent (1kg)", "Household & Cleaning", "packet", 380, 320, 50),
        ("Anti-Bacterial Bath Soap (Pack of 3)", "Personal Care", "pack", 340, 290, 75),
        ("Farm Fresh Eggs (1 Dozen)", "Dairy & Breakfast", "dozen", 310, 280, 60),
    ]

    prod_ids = {}
    for p in products:
        pid = create_product(*p)
        prod_ids[p[0]] = pid

    print("Seeding monthly salary credit customers...")
    # 1. Exact user example:
    # "if customer have 600 he is paying 500 he must ahve dues in his account"
    c1_id = create_customer(
        name="Muhammad Tariq (Teacher)",
        phone="0301-5551234",
        address="Street 3, Near Govt High School",
        salary_day=5,
        credit_limit=15000.0,
        notes="Gets salary on 5th of every month. Buys weekly ration on credit."
    )

    # Tariq's Bill: Total 600, Paid 500, Remaining Due 100
    create_bill(
        customer_id=c1_id,
        bill_date=(date.today() - timedelta(days=2)).isoformat(),
        items=[
            {"product_id": prod_ids["Refined White Sugar (1kg)"], "item_name": "Refined White Sugar (1kg)", "unit": "kg", "quantity": 2, "unit_price": 140}, # 280
            {"product_id": prod_ids["Tetra Pak Fresh Milk (1 Litre)"], "item_name": "Tetra Pak Fresh Milk (1 Litre)", "unit": "litre", "quantity": 1, "unit_price": 260}, # 260
            {"product_id": prod_ids["Iodized Table Salt (800g)"], "item_name": "Iodized Table Salt (800g)", "unit": "packet", "quantity": 1, "unit_price": 60}, # 60 -> Total 600
        ],
        discount=0,
        paid_now=500, # Customer gave 500, owes 100!
        payment_method="Cash",
        notes="Customer gave Rs. 500, remaining Rs. 100 will clear with salary."
    )

    # 2. Customer 2: Sarfraz Ahmed (Govt Employee) - Salary on 1st
    c2_id = create_customer(
        name="Sarfraz Ahmed (Govt Officer)",
        phone="0333-8884321",
        address="House 42, Block B, Civil Lines",
        salary_day=1,
        credit_limit=25000.0,
        notes="Monthly grocery khata. Salary arrives on 1st."
    )
    # Bill 1 for Sarfraz (earlier in month)
    b2_id = create_bill(
        customer_id=c2_id,
        bill_date=(date.today() - timedelta(days=12)).isoformat(),
        items=[
            {"product_id": prod_ids["Fine Wheat Flour / Atta (10kg)"], "item_name": "Fine Wheat Flour / Atta (10kg)", "unit": "bag", "quantity": 2, "unit_price": 1350},
            {"product_id": prod_ids["Pure Cooking Oil (1 Litre Pouch)"], "item_name": "Pure Cooking Oil (1 Litre Pouch)", "unit": "litre", "quantity": 4, "unit_price": 480},
            {"product_id": prod_ids["Premium Black Tea (450g Pack)"], "item_name": "Premium Black Tea (450g Pack)", "unit": "packet", "quantity": 2, "unit_price": 680},
        ],
        discount=80,
        paid_now=0, # Fully on credit
        notes="Monthly bulk grocery dispatch"
    )
    # Partial payment made by Sarfraz
    record_payment(
        customer_id=c2_id,
        amount=3000,
        payment_date=(date.today() - timedelta(days=5)).isoformat(),
        payment_method="Cash",
        notes="Partial advance salary payment received"
    )

    # 3. Customer 3: Rashid Minhas (Private Company) - Salary on 10th
    c3_id = create_customer(
        name="Rashid Minhas (Office Manager)",
        phone="0345-7779812",
        address="Flat 12, Gulshan Heights",
        salary_day=10,
        credit_limit=20000.0,
        notes="Clears account between 10th to 12th"
    )
    create_bill(
        customer_id=c3_id,
        bill_date=(date.today() - timedelta(days=4)).isoformat(),
        items=[
            {"product_id": prod_ids["Super Basmati Rice (5kg Bag)"], "item_name": "Super Basmati Rice (5kg Bag)", "unit": "bag", "quantity": 1, "unit_price": 1550},
            {"product_id": prod_ids["Daal Chana Special (1kg)"], "item_name": "Daal Chana Special (1kg)", "unit": "kg", "quantity": 2, "unit_price": 240},
            {"product_id": prod_ids["Farm Fresh Eggs (1 Dozen)"], "item_name": "Farm Fresh Eggs (1 Dozen)", "unit": "dozen", "quantity": 2, "unit_price": 310},
        ],
        discount=50,
        paid_now=1000,
        payment_method="Online Transfer",
        notes="Paid Rs. 1000 via online transfer"
    )

    print("Seed data successfully added!")

if __name__ == '__main__':
    seed()

