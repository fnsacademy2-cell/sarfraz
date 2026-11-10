# 🛒 SARFRAZ General and Grossary Store Newjatoi
### Customer MIS, Khata Ledger & Monthly Salary Udhar Billing System

A complete retail point-of-sale (POS) and Customer Management Information System (MIS) built specifically for **SARFRAZ General and Grossary Store Newjatoi**. Designed for general and grocery shop owners who sell to salary-class customers on monthly credit (*Udhar / Khata*) and collect payments on their monthly salary date.

---

## 🌟 Key Features

### 1. 📱 Two Ways to Run
- **Zero-Setup Standalone Web App (`index.html`)**:
  - Run directly in any mobile or desktop browser by double-clicking `index.html`.
  - Android native app look-and-feel with bottom navigation bar, quick touch actions, and responsive layout.
  - Offline-ready with browser LocalStorage, automatic data backup, and JSON restore.
- **Full-Stack Multi-Device Server (`app.py`)**:
  - Powered by Python & Flask with SQLite database.
  - Accessible across the shop Wi-Fi network from any smartphone, tablet, or counter PC.

### 2. 💳 Monthly Salary Credit Tracking (*Salary Khata*)
- Configure each customer's **Salary Day** (e.g. 1st, 5th, or 10th of every month).
- **Automated Salary Cycle Alerts**:
  - **Overdue**: Customers whose salary date has passed this month and still have outstanding dues.
  - **Due Today**: Customers receiving their salary today.
  - **Upcoming (Next 5 Days)**: Approaching salary payment cycles.
- **1-Click WhatsApp Reminder**: Sends polite, pre-formatted Urdu/English WhatsApp billing notices with total purchases, paid amounts, and remaining dues.

### 3. 🧾 Editable Grocery Bills & Real-Time Dues Calculation
- **Partial & Split Payment Handling**:
  - *Example*: If a customer purchases groceries for **Rs. 600** and pays **Rs. 500** cash at the counter:
    - **Total Bill**: Rs. 600
    - **Paid Now**: Rs. 500
    - **Due on Bill**: Rs. 100
    - **Customer Khata Balance**: Automatically adds Rs. 100 to outstanding ledger dues!
- **100% Fully Editable Bills**:
  - Shopkeeper can easily edit any past bill: add/remove items, adjust quantities, change prices, or correct payment amounts.
  - Ledger and customer balances auto-recalculate immediately.

### 4. 📖 Complete Customer Khata Ledger
- Chronological ledger tracking every debit (purchase) and credit (payment).
- Running balance calculations with debit/credit indicators.
- Printable official **Customer Statement / Hisab Kitab** report.

### 5. 💰 Cash Collections & Payment Receipts
- Instant "Receive Payment" modal from counter, customer profiles, or salary alert tabs.
- Supports Cash, EasyPaisa, JazzCash, and Bank Transfer.
- Printable thermal receipt vouchers for payments received.

### 6. 📦 Built-In Grocery Catalog
- Quick-pick items: Rice, Wheat Flour (Atta), Cooking Oil, Ghee, Sugar, Tea, Daal, Spices, Detergents, Soaps, Milk, etc.
- Custom item entry with custom units (kg, liter, packet, piece, bottle).

---

## 🚀 How to Launch the Application

### Method 1: Standalone Mobile Web App (Easiest & Fastest)
Double-click `index.html` in your file explorer to open it in Chrome, Edge, Brave, or any mobile browser. No server or Python installation required!

### Method 2: Multi-Device Wi-Fi Server (Flask Backend)

1. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Initialize demo data (optional):**
   ```powershell
   python seed_data.py
   ```

3. **Start the server:**
   - On Windows: Double-click `start.bat` **OR** run:
     ```powershell
     python run.py
     ```

4. **Access the application:**
   - **Counter PC / Laptop:** Open `http://localhost:5000`
   - **Mobile Phone / Tablet on Shop Wi-Fi:** Open `http://<your-pc-ip>:5000`

---

## 📁 Repository Structure

```
sarfraz/
├── index.html            # Standalone mobile & desktop POS web app (Zero setup)
├── app.py                # Main Flask backend application with REST routes
├── config.py             # System configuration and application settings
├── db.py                 # SQLite database schema, migrations & helpers
├── models.py             # Business logic: ledger balance, salary alerts, billing
├── seed_data.py          # Starter grocery inventory and demo salary accounts
├── test_app.py           # Automated unit test suite
├── run.py                # Local and Wi-Fi network launcher script
├── start.bat             # 1-click Windows batch launcher
├── requirements.txt      # Python dependencies
├── .gitignore            # Git ignore rules for caches, databases and OS files
├── templates/            # Flask Jinja2 templates (Bootstrap 5 + FontAwesome)
│   ├── base.html
│   ├── dashboard.html
│   ├── customers.html
│   ├── customer_detail.html
│   ├── customer_statement.html
│   ├── bills.html
│   ├── bill_new.html
│   ├── bill_edit.html
│   ├── bill_view.html
│   ├── payments.html
│   ├── payment_receipt.html
│   ├── salary_dues.html
│   ├── products.html
│   ├── reports.html
│   └── settings.html
└── static/               # Static assets
    ├── css/custom.css    # Responsive styles and thermal print formatting
    └── js/app.js         # Interactive UI scripts
```

---

## 🧪 Testing

Run backend automated tests anytime:
```powershell
python test_app.py
```

---

## 🏬 Store Information
- **Store Name**: SARFRAN General and Grossary Store Newjatoi
- **Location**: Newjatoi, Sindh
- **System**: Customer MIS & Khata Udhar Management System
