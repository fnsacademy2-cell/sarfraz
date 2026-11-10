import sqlite3
from datetime import datetime, date
from db import get_db_connection

def get_settings():
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def update_settings(settings_dict):
    conn = get_db_connection()
    for k, v in settings_dict.items():
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

# ----------------- CUSTOMER MANAGEMENT -----------------

def get_all_customers(search_query=None, filter_status=None):
    conn = get_db_connection()
    query = """
        SELECT c.*,
            COALESCE(SUM(b.net_amount), 0) + c.opening_balance AS total_billed,
            COALESCE((SELECT SUM(amount) FROM payments WHERE customer_id = c.id), 0) AS total_paid
        FROM customers c
        LEFT JOIN bills b ON c.id = b.customer_id
    """
    params = []
    conditions = []

    if search_query:
        conditions.append("(c.name LIKE ? OR c.phone LIKE ? OR c.address LIKE ?)")
        search_param = f"%{search_query}%"
        params.extend([search_param, search_param, search_param])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " GROUP BY c.id ORDER BY c.name ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    customers = []
    current_day = date.today().day
    
    for row in rows:
        cust = dict(row)
        cust['current_balance'] = round(cust['total_billed'] - cust['total_paid'], 2)
        
        # Salary day status calculation
        sal_day = cust['salary_day'] or 1
        if cust['current_balance'] > 0:
            if current_day > sal_day:
                cust['salary_status'] = 'overdue'
                cust['salary_status_text'] = f"Overdue (Salary was on {sal_day}th)"
            elif current_day == sal_day:
                cust['salary_status'] = 'due_today'
                cust['salary_status_text'] = "Salary Due Today!"
            elif sal_day - current_day <= 5:
                cust['salary_status'] = 'due_soon'
                cust['salary_status_text'] = f"Due in {sal_day - current_day} days ({sal_day}th)"
            else:
                cust['salary_status'] = 'upcoming'
                cust['salary_status_text'] = f"Salary on {sal_day}th"
        else:
            cust['salary_status'] = 'cleared'
            cust['salary_status_text'] = "Account Cleared"

        if filter_status == 'has_dues' and cust['current_balance'] <= 0:
            continue
        if filter_status == 'overdue' and cust['salary_status'] != 'overdue':
            continue
        if filter_status == 'due_soon' and cust['salary_status'] not in ('due_soon', 'due_today'):
            continue

        customers.append(cust)

    return customers

def get_customer_by_id(customer_id):
    conn = get_db_connection()
    cust_row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not cust_row:
        conn.close()
        return None
    
    cust = dict(cust_row)

    # Calculate total billed (including opening balance)
    billed_res = conn.execute(
        "SELECT COALESCE(SUM(net_amount), 0) AS sum_bills FROM bills WHERE customer_id = ?",
        (customer_id,)
    ).fetchone()
    total_bills = billed_res['sum_bills'] if billed_res else 0.0
    cust['total_billed'] = round(total_bills + (cust['opening_balance'] or 0.0), 2)

    # Calculate total payments
    paid_res = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS sum_payments FROM payments WHERE customer_id = ?",
        (customer_id,)
    ).fetchone()
    cust['total_paid'] = round(paid_res['sum_payments'] if paid_res else 0.0, 2)

    cust['current_balance'] = round(cust['total_billed'] - cust['total_paid'], 2)

    current_day = date.today().day
    sal_day = cust['salary_day'] or 1
    if cust['current_balance'] > 0:
        if current_day > sal_day:
            cust['salary_status'] = 'overdue'
            cust['salary_status_text'] = f"Overdue (Salary was on {sal_day}th)"
        elif current_day == sal_day:
            cust['salary_status'] = 'due_today'
            cust['salary_status_text'] = "Salary Due Today!"
        elif sal_day - current_day <= 5:
            cust['salary_status'] = 'due_soon'
            cust['salary_status_text'] = f"Due in {sal_day - current_day} days ({sal_day}th)"
        else:
            cust['salary_status'] = 'upcoming'
            cust['salary_status_text'] = f"Salary on {sal_day}th"
    else:
        cust['salary_status'] = 'cleared'
        cust['salary_status_text'] = "All Dues Cleared"

    conn.close()
    return cust

def create_customer(name, phone, alternate_phone=None, address=None, salary_day=1, credit_limit=0.0, opening_balance=0.0, notes=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO customers (name, phone, alternate_phone, address, salary_day, credit_limit, opening_balance, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, phone, alternate_phone, address, salary_day, credit_limit, opening_balance, notes))
    cust_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return cust_id

def update_customer(customer_id, name, phone, alternate_phone=None, address=None, salary_day=1, credit_limit=0.0, opening_balance=0.0, notes=None):
    conn = get_db_connection()
    conn.execute("""
        UPDATE customers
        SET name = ?, phone = ?, alternate_phone = ?, address = ?, salary_day = ?,
            credit_limit = ?, opening_balance = ?, notes = ?
        WHERE id = ?
    """, (name, phone, alternate_phone, address, salary_day, credit_limit, opening_balance, notes, customer_id))
    conn.commit()
    conn.close()

def delete_customer(customer_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()

# ----------------- CUSTOMER LEDGER STATEMENT -----------------

def get_customer_ledger(customer_id):
    """
    Returns unified chronological ledger (debits from bills, credits from payments)
    with progressive running balance.
    """
    cust = get_customer_by_id(customer_id)
    if not cust:
        return []

    conn = get_db_connection()
    
    # 1. Bills (Debits)
    bills = conn.execute("""
        SELECT id, bill_number, bill_date AS tx_date, net_amount, 'bill' AS tx_type, notes
        FROM bills
        WHERE customer_id = ?
    """, (customer_id,)).fetchall()

    # 2. Payments (Credits)
    payments = conn.execute("""
        SELECT id, payment_number, payment_date AS tx_date, amount, payment_method, 'payment' AS tx_type, notes, bill_id
        FROM payments
        WHERE customer_id = ?
    """, (customer_id,)).fetchall()

    conn.close()

    entries = []

    # Opening balance if any
    if cust['opening_balance'] and cust['opening_balance'] > 0:
        entries.append({
            'date': cust['created_at'][:10] if cust['created_at'] else 'Initial',
            'type': 'opening_balance',
            'ref_no': 'OPENING',
            'description': 'Opening Balance brought forward',
            'debit': cust['opening_balance'],
            'credit': 0.0,
            'id': None
        })

    for b in bills:
        entries.append({
            'date': b['tx_date'],
            'type': 'bill',
            'ref_no': b['bill_number'],
            'description': f"Grocery Purchase (Bill #{b['bill_number']})",
            'debit': float(b['net_amount']),
            'credit': 0.0,
            'id': b['id'],
            'notes': b['notes']
        })

    for p in payments:
        desc = f"Payment Received ({p['payment_method']})"
        if p['bill_id']:
            desc += f" for Bill #{p['bill_id']}"
        entries.append({
            'date': p['tx_date'],
            'type': 'payment',
            'ref_no': p['payment_number'],
            'description': desc,
            'debit': 0.0,
            'credit': float(p['amount']),
            'id': p['id'],
            'notes': p['notes']
        })

    # Sort chronological by date, then debits before credits
    entries.sort(key=lambda x: (x['date'], 0 if x['debit'] > 0 else 1))

    # Compute running balance
    running_balance = 0.0
    for e in entries:
        running_balance += (e['debit'] - e['credit'])
        e['balance'] = round(running_balance, 2)

    return entries

# ----------------- BILLING & EDITABLE BILLS -----------------

def generate_bill_number():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) as count FROM bills").fetchone()['count']
    conn.close()
    return f"BILL-{datetime.now().strftime('%Y%m')}-{count + 1:04d}"

def generate_payment_number():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) as count FROM payments").fetchone()['count']
    conn.close()
    return f"REC-{datetime.now().strftime('%Y%m')}-{count + 1:04d}"

def create_bill(customer_id, bill_date, items, discount=0.0, paid_now=0.0, payment_method='Cash', notes=None):
    """
    Creates a new bill with items and automatically handles the paid amount (e.g. Total 600, Paid 500, Due 100).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    subtotal = sum(item['quantity'] * item['unit_price'] for item in items)
    discount = float(discount or 0.0)
    net_amount = round(max(0.0, subtotal - discount), 2)
    paid_now = round(float(paid_now or 0.0), 2)
    due_amount = round(max(0.0, net_amount - paid_now), 2)

    if due_amount == 0 and net_amount > 0:
        payment_status = 'paid'
    elif paid_now > 0 and paid_now < net_amount:
        payment_status = 'partial'
    else:
        payment_status = 'due'

    bill_number = generate_bill_number()

    cursor.execute("""
        INSERT INTO bills (bill_number, customer_id, bill_date, subtotal, discount, net_amount, paid_amount, due_amount, payment_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (bill_number, customer_id, bill_date, subtotal, discount, net_amount, paid_now, due_amount, payment_status, notes))
    bill_id = cursor.lastrowid

    # Insert items
    for item in items:
        tot = round(item['quantity'] * item['unit_price'], 2)
        cursor.execute("""
            INSERT INTO bill_items (bill_id, product_id, item_name, unit, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (bill_id, item.get('product_id'), item['item_name'], item.get('unit', 'pcs'), item['quantity'], item['unit_price'], tot))

    # If an amount was paid at billing time, record payment
    if paid_now > 0:
        pay_no = f"REC-B{bill_id:04d}"
        cursor.execute("""
            INSERT INTO payments (payment_number, customer_id, bill_id, payment_date, amount, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pay_no, customer_id, bill_id, bill_date, paid_now, payment_method, f"Paid at billing for Bill #{bill_number}"))

    conn.commit()
    conn.close()
    return bill_id

def update_bill(bill_id, bill_date, items, discount=0.0, paid_now=0.0, payment_method='Cash', notes=None):
    """
    Edits an existing bill, recalculates subtotal, net, due, updates items,
    and updates the associated billing payment record smoothly.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    old_bill = cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    if not old_bill:
        conn.close()
        return False

    subtotal = sum(item['quantity'] * item['unit_price'] for item in items)
    discount = float(discount or 0.0)
    net_amount = round(max(0.0, subtotal - discount), 2)
    paid_now = round(float(paid_now or 0.0), 2)
    due_amount = round(max(0.0, net_amount - paid_now), 2)

    if due_amount == 0 and net_amount > 0:
        payment_status = 'paid'
    elif paid_now > 0 and paid_now < net_amount:
        payment_status = 'partial'
    else:
        payment_status = 'due'

    cursor.execute("""
        UPDATE bills
        SET bill_date = ?, subtotal = ?, discount = ?, net_amount = ?, paid_amount = ?,
            due_amount = ?, payment_status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (bill_date, subtotal, discount, net_amount, paid_now, due_amount, payment_status, notes, bill_id))

    # Delete existing bill items and reinsert updated ones
    cursor.execute("DELETE FROM bill_items WHERE bill_id = ?", (bill_id,))
    for item in items:
        tot = round(item['quantity'] * item['unit_price'], 2)
        cursor.execute("""
            INSERT INTO bill_items (bill_id, product_id, item_name, unit, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (bill_id, item.get('product_id'), item['item_name'], item.get('unit', 'pcs'), item['quantity'], item['unit_price'], tot))

    # Check for payment created with this bill
    existing_pay = cursor.execute("SELECT id FROM payments WHERE bill_id = ?", (bill_id,)).fetchone()
    if paid_now > 0:
        if existing_pay:
            cursor.execute("""
                UPDATE payments
                SET payment_date = ?, amount = ?, payment_method = ?, notes = ?
                WHERE id = ?
            """, (bill_date, paid_now, payment_method, f"Paid at billing for Bill #{old_bill['bill_number']} (Updated)", existing_pay['id']))
        else:
            pay_no = f"REC-B{bill_id:04d}"
            cursor.execute("""
                INSERT INTO payments (payment_number, customer_id, bill_id, payment_date, amount, payment_method, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pay_no, old_bill['customer_id'], bill_id, bill_date, paid_now, payment_method, f"Paid at billing for Bill #{old_bill['bill_number']}"))
    else:
        if existing_pay:
            cursor.execute("DELETE FROM payments WHERE id = ?", (existing_pay['id'],))

    conn.commit()
    conn.close()
    return True

def delete_bill(bill_id):
    conn = get_db_connection()
    # Cascade will handle bill_items; also delete linked billing payment
    conn.execute("DELETE FROM payments WHERE bill_id = ?", (bill_id,))
    conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
    conn.commit()
    conn.close()

def get_bill_by_id(bill_id):
    conn = get_db_connection()
    bill_row = conn.execute("""
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone,
               c.address AS customer_address, c.salary_day AS customer_salary_day
        FROM bills b
        JOIN customers c ON b.customer_id = c.id
        WHERE b.id = ?
    """, (bill_id,)).fetchone()

    if not bill_row:
        conn.close()
        return None

    bill = dict(bill_row)
    items_rows = conn.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill_id,)).fetchall()
    bill['items'] = [dict(r) for r in items_rows]

    # Check payment method from linked payment if any
    pay_row = conn.execute("SELECT payment_method FROM payments WHERE bill_id = ?", (bill_id,)).fetchone()
    bill['payment_method'] = pay_row['payment_method'] if pay_row else 'Cash'

    # Customer current balance
    cust = get_customer_by_id(bill['customer_id'])
    bill['customer_total_balance'] = cust['current_balance'] if cust else 0.0

    conn.close()
    return bill

def get_all_bills(customer_id=None, start_date=None, end_date=None, status=None):
    conn = get_db_connection()
    query = """
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone, c.salary_day
        FROM bills b
        JOIN customers c ON b.customer_id = c.id
    """
    conditions = []
    params = []

    if customer_id:
        conditions.append("b.customer_id = ?")
        params.append(customer_id)
    if start_date:
        conditions.append("b.bill_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("b.bill_date <= ?")
        params.append(end_date)
    if status:
        conditions.append("b.payment_status = ?")
        params.append(status)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY b.bill_date DESC, b.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ----------------- PAYMENTS -----------------

def record_payment(customer_id, amount, payment_date, payment_method='Cash', bill_id=None, notes=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    pay_no = generate_payment_number()
    amount = round(float(amount), 2)

    cursor.execute("""
        INSERT INTO payments (payment_number, customer_id, bill_id, payment_date, amount, payment_method, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (pay_no, customer_id, bill_id, payment_date, amount, payment_method, notes))
    pay_id = cursor.lastrowid

    # If linked to a specific bill, update the bill's paid/due amount and status
    if bill_id:
        bill = cursor.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
        if bill:
            new_paid = round(bill['paid_amount'] + amount, 2)
            new_due = round(max(0.0, bill['net_amount'] - new_paid), 2)
            new_status = 'paid' if new_due <= 0 else 'partial'
            cursor.execute("""
                UPDATE bills SET paid_amount = ?, due_amount = ?, payment_status = ? WHERE id = ?
            """, (new_paid, new_due, new_status, bill_id))

    conn.commit()
    conn.close()
    return pay_id

def get_all_payments(customer_id=None, start_date=None, end_date=None):
    conn = get_db_connection()
    query = """
        SELECT p.*, c.name AS customer_name, c.phone AS customer_phone, b.bill_number
        FROM payments p
        JOIN customers c ON p.customer_id = c.id
        LEFT JOIN bills b ON p.bill_id = b.id
    """
    conditions = []
    params = []

    if customer_id:
        conditions.append("p.customer_id = ?")
        params.append(customer_id)
    if start_date:
        conditions.append("p.payment_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("p.payment_date <= ?")
        params.append(end_date)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY p.payment_date DESC, p.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_payment_by_id(payment_id):
    conn = get_db_connection()
    row = conn.execute("""
        SELECT p.*, c.name AS customer_name, c.phone AS customer_phone, c.address AS customer_address, b.bill_number
        FROM payments p
        JOIN customers c ON p.customer_id = c.id
        LEFT JOIN bills b ON p.bill_id = b.id
        WHERE p.id = ?
    """, (payment_id,)).fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    cust = get_customer_by_id(res['customer_id'])
    res['customer_remaining_balance'] = cust['current_balance'] if cust else 0.0
    return res

def delete_payment(payment_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()

# ----------------- PRODUCTS / GROCERY ITEMS -----------------

def get_all_products(search_query=None):
    conn = get_db_connection()
    query = "SELECT * FROM products"
    params = []
    if search_query:
        query += " WHERE name LIKE ? OR category LIKE ?"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    query += " ORDER BY name ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_product(name, category, unit, selling_price, cost_price=0.0, stock_quantity=0.0, barcode=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO products (name, category, unit, selling_price, cost_price, stock_quantity, barcode)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, category, unit, selling_price, cost_price, stock_quantity, barcode))
    prod_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return prod_id

def update_product(product_id, name, category, unit, selling_price, cost_price=0.0, stock_quantity=0.0, barcode=None):
    conn = get_db_connection()
    conn.execute("""
        UPDATE products
        SET name = ?, category = ?, unit = ?, selling_price = ?, cost_price = ?, stock_quantity = ?, barcode = ?
        WHERE id = ?
    """, (name, category, unit, selling_price, cost_price, stock_quantity, barcode, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

# ----------------- DASHBOARD & METRICS -----------------

def get_dashboard_metrics():
    customers = get_all_customers()
    total_customers = len(customers)
    
    total_market_dues = sum(c['current_balance'] for c in customers if c['current_balance'] > 0)
    customers_with_dues = [c for c in customers if c['current_balance'] > 0]
    
    today_str = date.today().isoformat()
    month_prefix = date.today().strftime('%Y-%m')

    conn = get_db_connection()
    
    # Month sales
    m_sales = conn.execute(
        "SELECT COALESCE(SUM(net_amount), 0) AS total FROM bills WHERE bill_date LIKE ?",
        (f"{month_prefix}%",)
    ).fetchone()['total']

    # Month collections
    m_collections = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE payment_date LIKE ?",
        (f"{month_prefix}%",)
    ).fetchone()['total']

    # Today sales & collections
    t_sales = conn.execute(
        "SELECT COALESCE(SUM(net_amount), 0) AS total FROM bills WHERE bill_date = ?",
        (today_str,)
    ).fetchone()['total']

    t_collections = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE payment_date = ?",
        (today_str,)
    ).fetchone()['total']

    # Recent bills
    recent_bills = conn.execute("""
        SELECT b.*, c.name AS customer_name
        FROM bills b
        JOIN customers c ON b.customer_id = c.id
        ORDER BY b.id DESC LIMIT 5
    """).fetchall()

    # Recent payments
    recent_payments = conn.execute("""
        SELECT p.*, c.name AS customer_name
        FROM payments p
        JOIN customers c ON p.customer_id = c.id
        ORDER BY p.id DESC LIMIT 5
    """).fetchall()

    conn.close()

    # Salary alerts
    overdue_customers = [c for c in customers_with_dues if c['salary_status'] == 'overdue']
    due_today_customers = [c for c in customers_with_dues if c['salary_status'] == 'due_today']
    due_soon_customers = [c for c in customers_with_dues if c['salary_status'] == 'due_soon']

    return {
        'total_customers': total_customers,
        'customers_with_dues_count': len(customers_with_dues),
        'total_market_dues': round(total_market_dues, 2),
        'month_sales': round(m_sales, 2),
        'month_collections': round(m_collections, 2),
        'today_sales': round(t_sales, 2),
        'today_collections': round(t_collections, 2),
        'recent_bills': [dict(r) for r in recent_bills],
        'recent_payments': [dict(r) for r in recent_payments],
        'overdue_count': len(overdue_customers),
        'due_today_count': len(due_today_customers),
        'due_soon_count': len(due_soon_customers),
        'overdue_customers': overdue_customers[:5],
        'due_today_customers': due_today_customers,
        'due_soon_customers': due_soon_customers[:5]
    }

