from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "shop.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "hardware-shop-secret-key"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception: Exception | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price REAL NOT NULL CHECK(price >= 0),
            gst REAL NOT NULL CHECK(gst >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total REAL NOT NULL CHECK(total >= 0),
            cgst REAL NOT NULL CHECK(cgst >= 0),
            sgst REAL NOT NULL CHECK(sgst >= 0),
            grand_total REAL NOT NULL CHECK(grand_total >= 0),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            price REAL NOT NULL CHECK(price >= 0),
            gst REAL NOT NULL CHECK(gst >= 0),
            subtotal REAL NOT NULL CHECK(subtotal >= 0),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )
    db.commit()
    db.close()


@app.route("/")
def index():
    db = get_db()
    product_count = db.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
    stock_value = db.execute(
        "SELECT COALESCE(SUM(price * stock), 0) AS total_value FROM products"
    ).fetchone()["total_value"]
    sales_total = db.execute(
        "SELECT COALESCE(SUM(grand_total), 0) AS total FROM invoices"
    ).fetchone()["total"]
    invoice_count = db.execute("SELECT COUNT(*) AS count FROM invoices").fetchone()["count"]
    low_stock_items = db.execute(
        "SELECT name, stock FROM products WHERE stock <= 5 ORDER BY stock ASC, name ASC LIMIT 5"
    ).fetchall()
    return render_template(
        "index.html",
        product_count=product_count,
        stock_value=stock_value,
        sales_total=sales_total,
        invoice_count=invoice_count,
        low_stock_items=low_stock_items,
    )


@app.route("/add-product", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        gst_percentage = request.form.get("gst_percentage", "").strip()
        stock = request.form.get("stock", "").strip()

        errors: list[str] = []

        if not name:
            errors.append("Product name is required.")

        try:
            price_value = float(price)
            if price_value < 0:
                errors.append("Price must be 0 or more.")
        except ValueError:
            errors.append("Enter a valid price.")
            price_value = 0.0

        try:
            gst_value = float(gst_percentage)
            if gst_value < 0:
                errors.append("GST percentage must be 0 or more.")
        except ValueError:
            errors.append("Enter a valid GST percentage.")
            gst_value = 0.0

        try:
            stock_value = int(stock)
            if stock_value < 0:
                errors.append("Stock must be 0 or more.")
        except ValueError:
            errors.append("Enter a valid stock quantity.")
            stock_value = 0

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("add_product.html")

        db = get_db()
        try:
            db.execute(
                """
                INSERT INTO products (name, price, gst, stock)
                VALUES (?, ?, ?, ?)
                """,
                (name, price_value, gst_value, stock_value),
            )
            db.commit()
            flash("Product added successfully.", "success")
            return redirect(url_for("products"))
        except sqlite3.IntegrityError:
            flash("A product with this name already exists.", "danger")

    return render_template("add_product.html")


def get_product(product_id: int) -> sqlite3.Row | None:
    db = get_db()
    return db.execute(
        "SELECT id, name, price, gst, stock FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()


@app.route("/products")
def products():
    db = get_db()
    search_query = request.args.get("search", "").strip()
    
    if search_query:
        all_products = db.execute(
            "SELECT id, name, price, gst, stock FROM products WHERE name LIKE ? ORDER BY name ASC",
            (f"%{search_query}%",)
        ).fetchall()
    else:
        all_products = db.execute(
            "SELECT id, name, price, gst, stock FROM products ORDER BY name ASC"
        ).fetchall()
    
    return render_template("products.html", products=all_products, search_query=search_query)


@app.route("/edit-product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id: int):
    product = get_product(product_id)
    if product is None:
        flash("Product not found.", "danger")
        return redirect(url_for("products"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        gst_percentage = request.form.get("gst_percentage", "").strip()
        stock = request.form.get("stock", "").strip()

        errors: list[str] = []

        if not name:
            errors.append("Product name is required.")

        try:
            price_value = float(price)
            if price_value < 0:
                errors.append("Price must be 0 or more.")
        except ValueError:
            errors.append("Enter a valid price.")
            price_value = 0.0

        try:
            gst_value = float(gst_percentage)
            if gst_value < 0:
                errors.append("GST percentage must be 0 or more.")
        except ValueError:
            errors.append("Enter a valid GST percentage.")
            gst_value = 0.0

        try:
            stock_value = int(stock)
            if stock_value < 0:
                errors.append("Stock must be 0 or more.")
        except ValueError:
            errors.append("Enter a valid stock quantity.")
            stock_value = 0

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("add_product.html", product=product, edit_mode=True)

        db = get_db()
        try:
            db.execute(
                "UPDATE products SET name = ?, price = ?, gst = ?, stock = ? WHERE id = ?",
                (name, price_value, gst_value, stock_value, product_id),
            )
            db.commit()
            flash("Product updated successfully.", "success")
            return redirect(url_for("products"))
        except sqlite3.IntegrityError:
            flash("A product with this name already exists.", "danger")
            return render_template("add_product.html", product=product, edit_mode=True)

    return render_template("add_product.html", product=product, edit_mode=True)


@app.route("/delete-product/<int:product_id>")
def delete_product(product_id: int):
    db = get_db()
    product = get_product(product_id)
    if product is None:
        flash("Product not found.", "danger")
    else:
        linked_items = db.execute(
            "SELECT COUNT(*) AS count FROM invoice_items WHERE product_id = ?",
            (product_id,),
        ).fetchone()["count"]
        if linked_items > 0:
            flash(
                "This product is linked to existing invoices and cannot be deleted.",
                "warning",
            )
        else:
            db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            db.commit()
            flash("Product deleted successfully.", "success")
    return redirect(url_for("products"))


@app.route("/invoice", methods=["GET", "POST"])
def invoice():
    db = get_db()
    all_products = db.execute(
        "SELECT id, name, price, gst, stock FROM products ORDER BY name ASC"
    ).fetchall()

    if request.method == "POST":
        selected_ids = request.form.getlist("selected_products")
        if not selected_ids:
            flash("Select at least one product to create an invoice.", "danger")
            return render_template("invoice.html", products=all_products)

        selected_product_ids: list[int] = []
        for product_id in selected_ids:
            try:
                selected_product_ids.append(int(product_id))
            except ValueError:
                flash("Invalid product selection received.", "danger")
                return render_template("invoice.html", products=all_products)

        placeholders = ",".join("?" for _ in selected_product_ids)
        selected_products = db.execute(
            f"""
            SELECT id, name, price, gst, stock
            FROM products
            WHERE id IN ({placeholders})
            ORDER BY name ASC
            """,
            selected_product_ids,
        ).fetchall()

        errors: list[str] = []
        invoice_items: list[dict[str, float | int | str]] = []

        for product in selected_products:
            product_id = str(product["id"])
            quantity_raw = request.form.get(f"quantity_{product_id}", "").strip()
            try:
                quantity = int(quantity_raw)
                if quantity <= 0:
                    errors.append(f"Quantity for {product['name']} must be greater than 0.")
                    continue
            except ValueError:
                errors.append(f"Enter a valid quantity for {product['name']}.")
                continue

            if quantity > product["stock"]:
                errors.append(
                    f"Not enough stock for {product['name']}. Available stock: {product['stock']}."
                )
                continue

            subtotal = float(product["price"]) * quantity
            gst_amount = subtotal * (float(product["gst"]) / 100)
            invoice_items.append(
                {
                    "id": product["id"],
                    "name": product["name"],
                    "price": float(product["price"]),
                    "quantity": quantity,
                    "subtotal": subtotal,
                    "gst_percentage": float(product["gst"]),
                    "gst_amount": gst_amount,
                    "cgst": gst_amount / 2,
                    "sgst": gst_amount / 2,
                }
            )

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("invoice.html", products=all_products)

        if not invoice_items:
            flash("No valid products were selected for the invoice.", "danger")
            return render_template("invoice.html", products=all_products)

        total = sum(float(item["subtotal"]) for item in invoice_items)
        total_gst = sum(float(item["gst_amount"]) for item in invoice_items)
        cgst_total = total_gst / 2
        sgst_total = total_gst / 2
        grand_total = total + total_gst
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with db:
                cursor = db.execute(
                    """
                    INSERT INTO invoices (total, cgst, sgst, grand_total, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (total, cgst_total, sgst_total, grand_total, created_at),
                )
                invoice_id = cursor.lastrowid

                for item in invoice_items:
                    db.execute(
                        """
                        INSERT INTO invoice_items (
                            invoice_id, product_id, quantity, price, gst, subtotal
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            invoice_id,
                            item["id"],
                            item["quantity"],
                            item["price"],
                            item["gst_amount"],
                            item["subtotal"],
                        ),
                    )
                    db.execute(
                        "UPDATE products SET stock = stock - ? WHERE id = ?",
                        (item["quantity"], item["id"]),
                    )
        except sqlite3.DatabaseError:
            flash("Invoice could not be saved. Please try again.", "danger")
            return render_template("invoice.html", products=all_products)

        return render_template(
            "invoice_result.html",
            invoice_items=invoice_items,
            invoice_id=invoice_id,
            total=total,
            total_gst=total_gst,
            cgst_total=cgst_total,
            sgst_total=sgst_total,
            grand_total=grand_total,
        )

    return render_template("invoice.html", products=all_products)


@app.route("/invoices")
def view_invoices():
    db = get_db()
    all_invoices = db.execute(
        "SELECT id, total, cgst, sgst, grand_total, created_at FROM invoices ORDER BY created_at DESC"
    ).fetchall()
    return render_template("invoices.html", invoices=all_invoices)


@app.route("/invoices/<int:invoice_id>")
def invoice_detail(invoice_id):
    db = get_db()
    invoice = db.execute(
        "SELECT id, total, cgst, sgst, grand_total, created_at FROM invoices WHERE id = ?",
        (invoice_id,)
    ).fetchone()
    
    if not invoice:
        flash("Invoice not found.", "danger")
        return redirect(url_for("view_invoices"))
    
    items = db.execute(
        "SELECT ii.id, ii.product_id, p.name, ii.quantity, ii.price, ii.gst, ii.subtotal FROM invoice_items ii JOIN products p ON ii.product_id = p.id WHERE ii.invoice_id = ?",
        (invoice_id,)
    ).fetchall()
    
    return render_template("invoice_detail.html", invoice=invoice, items=items)


@app.route("/delete-invoice/<int:invoice_id>")
def delete_invoice(invoice_id: int):
    db = get_db()
    invoice = db.execute(
        "SELECT id FROM invoices WHERE id = ?",
        (invoice_id,),
    ).fetchone()
    if invoice is None:
        flash("Invoice not found.", "danger")
        return redirect(url_for("view_invoices"))

    items = db.execute(
        "SELECT product_id, quantity FROM invoice_items WHERE invoice_id = ?",
        (invoice_id,),
    ).fetchall()

    try:
        with db:
            for item in items:
                db.execute(
                    "UPDATE products SET stock = stock + ? WHERE id = ?",
                    (item["quantity"], item["product_id"]),
                )
            db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        flash("Invoice deleted and stock restored.", "success")
    except sqlite3.DatabaseError:
        flash("Unable to delete invoice. Please try again.", "danger")

    return redirect(url_for("view_invoices"))


@app.route("/invoices/<int:invoice_id>/pdf")
def download_invoice_pdf(invoice_id):
    db = get_db()
    invoice = db.execute(
        "SELECT id, total, cgst, sgst, grand_total, created_at FROM invoices WHERE id = ?",
        (invoice_id,)
    ).fetchone()
    
    if not invoice:
        flash("Invoice not found.", "danger")
        return redirect(url_for("view_invoices"))
    
    items = db.execute(
        "SELECT ii.id, ii.product_id, p.name, ii.quantity, ii.price, ii.gst, ii.subtotal FROM invoice_items ii JOIN products p ON ii.product_id = p.id WHERE ii.invoice_id = ?",
        (invoice_id,)
    ).fetchall()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0066ff'),
        spaceAfter=6,
        alignment=1,
        fontName='Helvetica-Bold'
    )
    
    subheader_style = ParagraphStyle(
        'SubHeader',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#6c757d'),
        spaceAfter=20,
        alignment=1
    )
    
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6c757d'),
        fontName='Helvetica-Bold'
    )
    
    elements.append(Paragraph("QuickBill Pro", header_style))
    elements.append(Paragraph("Professional Invoice Management System", subheader_style))
    elements.append(Spacer(1, 0.2*inch))
    
    info_data = [
        [Paragraph("<b>Invoice #</b>", label_style), str(invoice['id'])],
        [Paragraph("<b>Date</b>", label_style), invoice['created_at']],
    ]
    info_table = Table(info_data, colWidths=[1.5*inch, 3.5*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e6f0ff')),
        ('BACKGROUND', (1, 0), (1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1d23')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDINGTOP', (0, 0), (-1, -1), 10),
        ('PADDINGBOTTOM', (0, 0), (-1, -1), 10),
        ('PADDINGLEFT', (1, 0), (1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f8f9fd'), colors.white])
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    item_data = [['Product Name', 'Quantity', 'Unit Price', 'GST Amount', 'Subtotal']]
    total_qty = 0
    for item in items:
        total_qty += item['quantity']
        item_data.append([
            item['name'],
            str(item['quantity']),
            f"Rs. {item['price']:.2f}",
            f"Rs. {item['gst']:.2f}",
            f"Rs. {item['subtotal']:.2f}"
        ])
    
    item_table = Table(item_data, colWidths=[2.2*inch, 1*inch, 1.1*inch, 1.1*inch, 1.1*inch])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066ff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('PADDINGTOP', (0, 1), (-1, -1), 10),
        ('PADDINGBOTTOM', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fd')]),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#0066ff')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#0066ff')),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 0.3*inch))
    
    summary_data = [
        ['Subtotal', f"Rs. {invoice['total']:.2f}"],
        ['CGST (50% of GST)', f"Rs. {invoice['cgst']:.2f}"],
        ['SGST (50% of GST)', f"Rs. {invoice['sgst']:.2f}"],
        ['Grand Total', f"Rs. {invoice['grand_total']:.2f}"]
    ]
    summary_table = Table(summary_data, colWidths=[3.5*inch, 2.5*inch])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, 2), 'Helvetica'),
        ('FONTNAME', (0, 3), (0, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 2), 10),
        ('FONTSIZE', (0, 3), (-1, 3), 12),
        ('BACKGROUND', (0, 0), (1, 2), colors.white),
        ('BACKGROUND', (0, 3), (1, 3), colors.HexColor('#0066ff')),
        ('TEXTCOLOR', (0, 3), (1, 3), colors.whitesmoke),
        ('PADDINGTOP', (0, 0), (-1, -1), 10),
        ('PADDINGBOTTOM', (0, 0), (-1, -1), 10),
        ('PADDINGRIGHT', (1, 0), (1, -1), 12),
        ('GRID', (0, 0), (-1, 2), 1, colors.HexColor('#e9ecef')),
        ('GRID', (0, 3), (-1, 3), 1, colors.HexColor('#0066ff')),
        ('LINEABOVE', (0, 3), (-1, 3), 2, colors.HexColor('#0066ff')),
        ('LINEBELOW', (0, 3), (-1, 3), 2, colors.HexColor('#0066ff')),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4*inch))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6c757d'),
        alignment=1
    )
    elements.append(Paragraph("Thank you for your business! Invoice is valid for GST purposes.", footer_style))
    generated_time = datetime.now().strftime('%d-%b-%Y %I:%M %p')
    elements.append(Paragraph(f"Generated by QuickBill Pro | {generated_time}", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'invoice_{invoice_id}.pdf')


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
else:
    init_db()
