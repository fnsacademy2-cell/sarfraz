import os
import csv
import io
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, make_response, send_file, send_from_directory
)
from config import Config
from db import init_db
import models

app = Flask(__name__)
app.config.from_object(Config)

# Context processor to make shop settings and current year available to all templates
@app.context_processor
def inject_global_data():
    settings = models.get_settings()
    return {
        'settings': settings,
        'currency': settings.get('currency_symbol', 'Rs.'),
        'today': date.today().isoformat(),
        'current_year': date.today().year
    }

# ----------------- HOME / DASHBOARD -----------------
@app.route('/')
def dashboard():
    # If the user prefers the standalone single HTML app in the root folder:
    return send_file(os.path.join(Config.BASE_DIR, 'index.html'))

@app.route('/index.html')
def index_file():
    return send_file(os.path.join(Config.BASE_DIR, 'index.html'))

@app.route('/dashboard-server')
def server_dashboard():
    metrics = models.get_dashboard_metrics()
    return render_template('dashboard.html', metrics=metrics)

# ----------------- CUSTOMER MIS -----------------
@app.route('/customers')
def customers_list():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('filter', '').strip() # 'has_dues', 'overdue', 'due_soon'
    customers = models.get_all_customers(search_query=search or None, filter_status=status_filter or None)
    
    total_dues = sum(c['current_balance'] for c in customers if c['current_balance'] > 0)
    overdue_count = sum(1 for c in customers if c['salary_status'] == 'overdue')
    
    return render_template(
        'customers.html',
        customers=customers,
        search=search,
        status_filter=status_filter,
        total_dues=round(total_dues, 2),
        overdue_count=overdue_count
    )

@app.route('/customers/new', methods=['POST'])
def customer_create():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    alternate_phone = request.form.get('alternate_phone', '').strip()
    address = request.form.get('address', '').strip()
    salary_day = int(request.form.get('salary_day') or 1)
    credit_limit = float(request.form.get('credit_limit') or 0.0)
    opening_balance = float(request.form.get('opening_balance') or 0.0)
    notes = request.form.get('notes', '').strip()

    if not name:
        flash('Customer name is required!', 'danger')
        return redirect(url_for('customers_list'))

    cust_id = models.create_customer(
        name=name,
        phone=phone,
        alternate_phone=alternate_phone,
        address=address,
        salary_day=salary_day,
        credit_limit=credit_limit,
        opening_balance=opening_balance,
        notes=notes
    )
    flash(f'Customer "{name}" added successfully with salary day on {salary_day}th!', 'success')
    return redirect(url_for('customer_detail', customer_id=cust_id))

@app.route('/customers/<int:customer_id>')
def customer_detail(customer_id):
    customer = models.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found!', 'danger')
        return redirect(url_for('customers_list'))

    ledger = models.get_customer_ledger(customer_id)
    bills = models.get_all_bills(customer_id=customer_id)
    payments = models.get_all_payments(customer_id=customer_id)

    # Prepare pre-formatted WhatsApp message
    settings = models.get_settings()
    shop_name = settings.get('shop_name', 'Grocery Store')
    currency = settings.get('currency_symbol', 'Rs.')
    clean_phone = ''.join(filter(str.isdigit, customer['phone'] or ''))
    if clean_phone.startswith('0'):
        clean_phone = '92' + clean_phone[1:] # Pakistani phone format default, or generic
    
    wa_msg = (
        f"Assalam-o-Alaikum / Hello {customer['name']},\n\n"
        f"This is a gentle monthly account summary from *{shop_name}*.\n"
        f"Total Purchases: {currency} {customer['total_billed']}\n"
        f"Total Paid: {currency} {customer['total_paid']}\n"
        f"*Current Pending Dues: {currency} {customer['current_balance']}*\n"
        f"Your scheduled salary payment date is the *{customer['salary_day']}th* of every month.\n\n"
        f"Kindly clear your dues at your earliest convenience. Thank you for your patronage!"
    )
    from urllib.parse import quote
    wa_link = f"https://wa.me/{clean_phone}?text={quote(wa_msg)}" if clean_phone else None

    return render_template(
        'customer_detail.html',
        customer=customer,
        ledger=ledger,
        bills=bills,
        payments=payments,
        wa_link=wa_link
    )

@app.route('/customers/<int:customer_id>/edit', methods=['POST'])
def customer_update(customer_id):
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    alternate_phone = request.form.get('alternate_phone', '').strip()
    address = request.form.get('address', '').strip()
    salary_day = int(request.form.get('salary_day') or 1)
    credit_limit = float(request.form.get('credit_limit') or 0.0)
    opening_balance = float(request.form.get('opening_balance') or 0.0)
    notes = request.form.get('notes', '').strip()

    models.update_customer(
        customer_id=customer_id,
        name=name,
        phone=phone,
        alternate_phone=alternate_phone,
        address=address,
        salary_day=salary_day,
        credit_limit=credit_limit,
        opening_balance=opening_balance,
        notes=notes
    )
    flash('Customer details updated successfully!', 'success')
    return redirect(url_for('customer_detail', customer_id=customer_id))

@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
def customer_delete(customer_id):
    models.delete_customer(customer_id)
    flash('Customer and associated account history deleted successfully.', 'info')
    return redirect(url_for('customers_list'))

@app.route('/customers/<int:customer_id>/statement')
def customer_statement(customer_id):
    customer = models.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found!', 'danger')
        return redirect(url_for('customers_list'))

    ledger = models.get_customer_ledger(customer_id)
    return render_template('customer_statement.html', customer=customer, ledger=ledger)

# ----------------- BILLS & EDITABLE BILLS -----------------
@app.route('/bills')
def bills_list():
    customer_id = request.args.get('customer_id', type=int)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    status = request.args.get('status', '')

    bills = models.get_all_bills(customer_id=customer_id, start_date=start_date or None, end_date=end_date or None, status=status or None)
    customers = models.get_all_customers()

    return render_template(
        'bills.html',
        bills=bills,
        customers=customers,
        selected_customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        status=status
    )

@app.route('/bills/new')
def bill_new():
    preselected_customer_id = request.args.get('customer_id', type=int)
    customers = models.get_all_customers()
    products = models.get_all_products()
    return render_template(
        'bill_new.html',
        customers=customers,
        products=products,
        preselected_customer_id=preselected_customer_id
    )

@app.route('/bills/new', methods=['POST'])
def bill_create():
    customer_id = int(request.form.get('customer_id'))
    bill_date = request.form.get('bill_date') or date.today().isoformat()
    discount = float(request.form.get('discount') or 0.0)
    paid_now = float(request.form.get('paid_now') or 0.0)
    payment_method = request.form.get('payment_method', 'Cash')
    notes = request.form.get('notes', '').strip()

    # Extract dynamic item rows
    item_names = request.form.getlist('item_name[]')
    quantities = request.form.getlist('quantity[]')
    units = request.form.getlist('unit[]')
    unit_prices = request.form.getlist('unit_price[]')
    product_ids = request.form.getlist('product_id[]')

    items = []
    for i in range(len(item_names)):
        name = item_names[i].strip()
        if not name:
            continue
        qty = float(quantities[i]) if i < len(quantities) and quantities[i] else 1.0
        unit = units[i] if i < len(units) and units[i] else 'pcs'
        price = float(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else 0.0
        pid = int(product_ids[i]) if i < len(product_ids) and product_ids[i] else None
        items.append({
            'product_id': pid,
            'item_name': name,
            'unit': unit,
            'quantity': qty,
            'unit_price': price
        })

    if not items:
        flash('Please add at least one item to the bill!', 'danger')
        return redirect(url_for('bill_new', customer_id=customer_id))

    bill_id = models.create_bill(
        customer_id=customer_id,
        bill_date=bill_date,
        items=items,
        discount=discount,
        paid_now=paid_now,
        payment_method=payment_method,
        notes=notes
    )

    flash('Bill created successfully!', 'success')
    return redirect(url_for('bill_view', bill_id=bill_id))

@app.route('/bills/<int:bill_id>')
def bill_view(bill_id):
    bill = models.get_bill_by_id(bill_id)
    if not bill:
        flash('Bill not found!', 'danger')
        return redirect(url_for('bills_list'))

    # Build WhatsApp receipt share link
    settings = models.get_settings()
    shop_name = settings.get('shop_name', 'Grocery Store')
    currency = settings.get('currency_symbol', 'Rs.')
    clean_phone = ''.join(filter(str.isdigit, bill['customer_phone'] or ''))
    if clean_phone.startswith('0'):
        clean_phone = '92' + clean_phone[1:]
    
    items_summary = "\n".join([f"- {it['item_name']}: {it['quantity']} {it['unit']} x {it['unit_price']} = {currency} {it['total_price']}" for it in bill['items']])
    wa_msg = (
        f"*{shop_name} - Bill Receipt*\n"
        f"Bill No: *{bill['bill_number']}*\n"
        f"Date: {bill['bill_date']}\n"
        f"Customer: {bill['customer_name']}\n\n"
        f"Items:\n{items_summary}\n\n"
        f"Subtotal: {currency} {bill['subtotal']}\n"
        f"Discount: {currency} {bill['discount']}\n"
        f"*Net Bill: {currency} {bill['net_amount']}*\n"
        f"Paid Now: {currency} {bill['paid_amount']}\n"
        f"Due on this Bill: {currency} {bill['due_amount']}\n"
        f"*Total Customer Remaining Dues: {currency} {bill['customer_total_balance']}*\n\n"
        f"Salary Day: {bill['customer_salary_day']}th of month\n"
        f"Thank you!"
    )
    from urllib.parse import quote
    wa_link = f"https://wa.me/{clean_phone}?text={quote(wa_msg)}" if clean_phone else None

    return render_template('bill_view.html', bill=bill, wa_link=wa_link)

@app.route('/bills/<int:bill_id>/edit')
def bill_edit(bill_id):
    bill = models.get_bill_by_id(bill_id)
    if not bill:
        flash('Bill not found!', 'danger')
        return redirect(url_for('bills_list'))

    products = models.get_all_products()
    return render_template('bill_edit.html', bill=bill, products=products)

@app.route('/bills/<int:bill_id>/edit', methods=['POST'])
def bill_update(bill_id):
    bill_date = request.form.get('bill_date') or date.today().isoformat()
    discount = float(request.form.get('discount') or 0.0)
    paid_now = float(request.form.get('paid_now') or 0.0)
    payment_method = request.form.get('payment_method', 'Cash')
    notes = request.form.get('notes', '').strip()

    item_names = request.form.getlist('item_name[]')
    quantities = request.form.getlist('quantity[]')
    units = request.form.getlist('unit[]')
    unit_prices = request.form.getlist('unit_price[]')
    product_ids = request.form.getlist('product_id[]')

    items = []
    for i in range(len(item_names)):
        name = item_names[i].strip()
        if not name:
            continue
        qty = float(quantities[i]) if i < len(quantities) and quantities[i] else 1.0
        unit = units[i] if i < len(units) and units[i] else 'pcs'
        price = float(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else 0.0
        pid = int(product_ids[i]) if i < len(product_ids) and product_ids[i] else None
        items.append({
            'product_id': pid,
            'item_name': name,
            'unit': unit,
            'quantity': qty,
            'unit_price': price
        })

    if not items:
        flash('Please keep at least one item in the bill!', 'danger')
        return redirect(url_for('bill_edit', bill_id=bill_id))

    success = models.update_bill(
        bill_id=bill_id,
        bill_date=bill_date,
        items=items,
        discount=discount,
        paid_now=paid_now,
        payment_method=payment_method,
        notes=notes
    )

    if success:
        flash('Bill updated successfully! Ledger & Customer dues recalculated.', 'success')
    else:
        flash('Failed to update bill.', 'danger')

    return redirect(url_for('bill_view', bill_id=bill_id))

@app.route('/bills/<int:bill_id>/delete', methods=['POST'])
def bill_delete(bill_id):
    bill = models.get_bill_by_id(bill_id)
    cust_id = bill['customer_id'] if bill else None
    models.delete_bill(bill_id)
    flash('Bill deleted and customer ledger adjusted.', 'info')
    if cust_id:
        return redirect(url_for('customer_detail', customer_id=cust_id))
    return redirect(url_for('bills_list'))

# ----------------- PAYMENTS -----------------
@app.route('/payments')
def payments_list():
    customer_id = request.args.get('customer_id', type=int)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    payments = models.get_all_payments(customer_id=customer_id, start_date=start_date or None, end_date=end_date or None)
    customers = models.get_all_customers()
    total_received = sum(p['amount'] for p in payments)

    return render_template(
        'payments.html',
        payments=payments,
        customers=customers,
        selected_customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        total_received=round(total_received, 2)
    )

@app.route('/payments/new', methods=['POST'])
def payment_create():
    customer_id = int(request.form.get('customer_id'))
    amount = float(request.form.get('amount') or 0.0)
    payment_date = request.form.get('payment_date') or date.today().isoformat()
    payment_method = request.form.get('payment_method', 'Cash')
    bill_id = request.form.get('bill_id', type=int) or None
    notes = request.form.get('notes', '').strip()

    if amount <= 0:
        flash('Payment amount must be greater than zero!', 'danger')
        return redirect(request.referrer or url_for('payments_list'))

    pay_id = models.record_payment(
        customer_id=customer_id,
        amount=amount,
        payment_date=payment_date,
        payment_method=payment_method,
        bill_id=bill_id,
        notes=notes
    )

    flash(f'Payment of {models.get_settings().get("currency_symbol", "Rs.")} {amount} recorded successfully!', 'success')
    return redirect(url_for('payment_receipt', payment_id=pay_id))

@app.route('/payments/<int:payment_id>/receipt')
def payment_receipt(payment_id):
    payment = models.get_payment_by_id(payment_id)
    if not payment:
        flash('Payment receipt not found!', 'danger')
        return redirect(url_for('payments_list'))
    return render_template('payment_receipt.html', payment=payment)

@app.route('/payments/<int:payment_id>/delete', methods=['POST'])
def payment_delete(payment_id):
    payment = models.get_payment_by_id(payment_id)
    cust_id = payment['customer_id'] if payment else None
    models.delete_payment(payment_id)
    flash('Payment entry deleted and customer ledger updated.', 'info')
    if cust_id:
        return redirect(url_for('customer_detail', customer_id=cust_id))
    return redirect(url_for('payments_list'))

# ----------------- SALARY DUES TRACKER -----------------
@app.route('/salary-dues')
def salary_dues_tracker():
    customers = models.get_all_customers()
    customers_with_dues = [c for c in customers if c['current_balance'] > 0]

    overdue = [c for c in customers_with_dues if c['salary_status'] == 'overdue']
    due_today = [c for c in customers_with_dues if c['salary_status'] == 'due_today']
    due_soon = [c for c in customers_with_dues if c['salary_status'] == 'due_soon']
    upcoming = [c for c in customers_with_dues if c['salary_status'] == 'upcoming']

    total_overdue_dues = sum(c['current_balance'] for c in overdue)
    total_due_today_dues = sum(c['current_balance'] for c in due_today)
    total_due_soon_dues = sum(c['current_balance'] for c in due_soon)
    total_upcoming_dues = sum(c['current_balance'] for c in upcoming)

    return render_template(
        'salary_dues.html',
        overdue=overdue,
        due_today=due_today,
        due_soon=due_soon,
        upcoming=upcoming,
        total_overdue_dues=round(total_overdue_dues, 2),
        total_due_today_dues=round(total_due_today_dues, 2),
        total_due_soon_dues=round(total_due_soon_dues, 2),
        total_upcoming_dues=round(total_upcoming_dues, 2)
    )

# ----------------- PRODUCTS / GROCERY ITEMS -----------------
@app.route('/products')
def products_list():
    search = request.args.get('search', '').strip()
    products = models.get_all_products(search_query=search or None)
    return render_template('products.html', products=products, search=search)

@app.route('/products/new', methods=['POST'])
def product_create():
    name = request.form.get('name', '').strip()
    category = request.form.get('category', 'General Grocery').strip()
    unit = request.form.get('unit', 'kg').strip()
    selling_price = float(request.form.get('selling_price') or 0.0)
    cost_price = float(request.form.get('cost_price') or 0.0)
    stock_quantity = float(request.form.get('stock_quantity') or 0.0)
    barcode = request.form.get('barcode', '').strip()

    if not name:
        flash('Product name is required!', 'danger')
        return redirect(url_for('products_list'))

    models.create_product(name, category, unit, selling_price, cost_price, stock_quantity, barcode)
    flash(f'Product "{name}" added to catalog!', 'success')
    return redirect(url_for('products_list'))

@app.route('/products/<int:product_id>/edit', methods=['POST'])
def product_update(product_id):
    name = request.form.get('name', '').strip()
    category = request.form.get('category', 'General Grocery').strip()
    unit = request.form.get('unit', 'kg').strip()
    selling_price = float(request.form.get('selling_price') or 0.0)
    cost_price = float(request.form.get('cost_price') or 0.0)
    stock_quantity = float(request.form.get('stock_quantity') or 0.0)
    barcode = request.form.get('barcode', '').strip()

    models.update_product(product_id, name, category, unit, selling_price, cost_price, stock_quantity, barcode)
    flash('Product updated successfully!', 'success')
    return redirect(url_for('products_list'))

@app.route('/products/<int:product_id>/delete', methods=['POST'])
def product_delete(product_id):
    models.delete_product(product_id)
    flash('Product removed from catalog.', 'info')
    return redirect(url_for('products_list'))

# ----------------- JSON APIS FOR SPEED / INTERACTIVE BILLING -----------------
@app.route('/api/products')
def api_products():
    search = request.args.get('q', '').strip()
    products = models.get_all_products(search_query=search or None)
    return jsonify(products)

@app.route('/api/customers')
def api_customers():
    search = request.args.get('q', '').strip()
    customers = models.get_all_customers(search_query=search or None)
    return jsonify(customers)

# ----------------- REPORTS & EXPORTS -----------------
@app.route('/reports')
def reports():
    start_date = request.args.get('start_date', date.today().replace(day=1).isoformat())
    end_date = request.args.get('end_date', date.today().isoformat())

    bills = models.get_all_bills(start_date=start_date, end_date=end_date)
    payments = models.get_all_payments(start_date=start_date, end_date=end_date)
    customers = models.get_all_customers()

    period_sales = sum(b['net_amount'] for b in bills)
    period_collections = sum(p['amount'] for p in payments)
    total_market_dues = sum(c['current_balance'] for c in customers if c['current_balance'] > 0)

    return render_template(
        'reports.html',
        start_date=start_date,
        end_date=end_date,
        bills=bills,
        payments=payments,
        period_sales=round(period_sales, 2),
        period_collections=round(period_collections, 2),
        total_market_dues=round(total_market_dues, 2)
    )

@app.route('/reports/export/dues-csv')
def export_dues_csv():
    customers = models.get_all_customers(filter_status='has_dues')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Customer ID', 'Name', 'Phone', 'Address', 'Salary Day', 'Total Purchases', 'Total Paid', 'Current Outstanding Due', 'Salary Status'])

    for c in customers:
        writer.writerow([
            c['id'], c['name'], c['phone'], c['address'], c['salary_day'],
            c['total_billed'], c['total_paid'], c['current_balance'], c['salary_status_text']
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=Customer_Salary_Dues_{date.today().isoformat()}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

@app.route('/customers/<int:customer_id>/export-csv')
def export_customer_ledger_csv(customer_id):
    customer = models.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found!', 'danger')
        return redirect(url_for('customers_list'))

    ledger = models.get_customer_ledger(customer_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Reference #', 'Transaction Description', 'Debit (+Bill)', 'Credit (-Payment)', 'Running Balance', 'Notes'])

    for e in ledger:
        writer.writerow([
            e['date'],
            e['ref_no'],
            e['description'],
            e['debit'],
            e['credit'],
            e['balance'],
            e.get('notes', '')
        ])

    clean_name = "".join(c for c in customer['name'] if c.isalnum() or c in (' ', '_', '-')).strip()
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=Ledger_{clean_name}_{date.today().isoformat()}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

@app.route('/backup/download')
def backup_database():
    db_path = Config.DATABASE_PATH
    if os.path.exists(db_path):
        return send_file(
            db_path,
            as_attachment=True,
            download_name=f"grocery_store_backup_{date.today().isoformat()}.db"
        )
    else:
        flash('Database file not found for backup!', 'danger')
        return redirect(url_for('settings_page'))

# ----------------- SETTINGS -----------------
@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        new_settings = {
            'shop_name': request.form.get('shop_name', '').strip(),
            'shop_tagline': request.form.get('shop_tagline', '').strip(),
            'shop_phone': request.form.get('shop_phone', '').strip(),
            'shop_address': request.form.get('shop_address', '').strip(),
            'currency_symbol': request.form.get('currency_symbol', 'Rs.').strip(),
            'footer_note': request.form.get('footer_note', '').strip(),
        }
        models.update_settings(new_settings)
        flash('Shop settings updated successfully!', 'success')
        return redirect(url_for('settings_page'))

    settings = models.get_settings()
    return render_template('settings.html', settings=settings)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)

