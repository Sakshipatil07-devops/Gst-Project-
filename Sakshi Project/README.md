# QuickBill Pro

QuickBill Pro is a lightweight Flask invoicing application built with SQLite. It helps manage products, create invoices, download PDF invoices, and track sales totals.

## Features

- Add, edit, and delete products
- Create invoices with product quantities and GST calculation
- View past invoices and invoice details
- Download invoices as styled PDF files
- Search products and see sales/dashboard metrics

## Setup

1. Create a Python virtual environment:
   ```bash
   python -m venv venv
   ```
2. Activate the environment:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   python app.py
   ```
5. Open the browser at:
   ```text
   http://127.0.0.1:5000
   ```

## Notes

- The database file is created automatically as `shop.db`.
- If you want to use a remote Git repository, add a remote and push after initial commit.
