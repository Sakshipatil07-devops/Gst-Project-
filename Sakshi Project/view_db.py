import sqlite3
from pathlib import Path
from tabulate import tabulate

BASE_DIR=Path(__file__).resolve().parent
DATABASE=BASE_DIR/"shop.db"

def view_products():
    db=sqlite3.connect(DATABASE)
    db.row_factory=sqlite3.Row
    cursor=db.execute("SELECT id, name, price, gst, stock FROM products ORDER BY name ASC")
    rows=cursor.fetchall()
    if rows:
        data=[list(row) for row in rows]
        print("\n🏢 PRODUCTS TABLE")
        print(tabulate(data,headers=['ID','Name','Price','GST','Stock'],tablefmt='grid'))
    else:
        print("No products found")
    db.close()

def view_invoices():
    db=sqlite3.connect(DATABASE)
    db.row_factory=sqlite3.Row
    cursor=db.execute("SELECT id, total, cgst, sgst, grand_total, created_at FROM invoices ORDER BY created_at DESC")
    rows=cursor.fetchall()
    if rows:
        data=[list(row) for row in rows]
        print("\n📄 INVOICES TABLE")
        print(tabulate(data,headers=['ID','Total','CGST','SGST','Grand Total','Created At'],tablefmt='grid'))
    else:
        print("No invoices found")
    db.close()

def view_invoice_items():
    db=sqlite3.connect(DATABASE)
    db.row_factory=sqlite3.Row
    cursor=db.execute("SELECT id, invoice_id, product_id, quantity, price, gst, subtotal FROM invoice_items ORDER BY invoice_id DESC")
    rows=cursor.fetchall()
    if rows:
        data=[list(row) for row in rows]
        print("\n📋 INVOICE ITEMS TABLE")
        print(tabulate(data,headers=['ID','Invoice ID','Product ID','Qty','Price','GST','Subtotal'],tablefmt='grid'))
    else:
        print("No invoice items found")
    db.close()

def view_all():
    view_products()
    view_invoices()
    view_invoice_items()

def main():
    print("="*60)
    print("DATABASE VIEWER - Hardware Shop")
    print("="*60)
    print("\n1. View Products")
    print("2. View Invoices")
    print("3. View Invoice Items")
    print("4. View All Tables")
    print("5. Exit")
    choice=input("\nSelect option: ").strip()
    
    if choice=='1':
        view_products()
    elif choice=='2':
        view_invoices()
    elif choice=='3':
        view_invoice_items()
    elif choice=='4':
        view_all()
    else:
        print("Exiting...")

if __name__=="__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
