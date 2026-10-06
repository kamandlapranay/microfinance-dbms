from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = "microfinance_secret_key"

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Pranay@1195",
        database="microfinance_db"
    )

@app.route("/")
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Key Metrics
    cursor.execute("SELECT COUNT(*) AS total_clients FROM clients")
    total_clients = cursor.fetchone()["total_clients"]

    # Only count loans that are currently active ('Disbursed' or 'Approved')
    cursor.execute("SELECT COUNT(*) AS active_loans FROM loans WHERE Status IN ('Disbursed', 'Approved')")
    active_loans = cursor.fetchone()["active_loans"]

    cursor.execute("SELECT COALESCE(SUM(ApprovedAmount), 0) AS total_disbursed FROM loans WHERE Status IN ('Disbursed', 'Approved')")
    total_disbursed = cursor.fetchone()["total_disbursed"]

    cursor.execute("SELECT COALESCE(SUM(AmountPaid), 0) AS total_repaid FROM repayments")
    total_repaid = cursor.fetchone()["total_repaid"]

    # Tables & Views with fallback protection
    try:
        cursor.execute("SELECT * FROM view_overdueloans")
        overdue_loans = cursor.fetchall()
    except Exception:
        overdue_loans = []

    try:
        cursor.execute("SELECT * FROM view_savings_penalty_audit")
        savings_audit = cursor.fetchall()
    except Exception:
        savings_audit = []

    cursor.execute("SELECT * FROM clients")
    clients = cursor.fetchall()

    cursor.execute("SELECT * FROM loans")
    loans = cursor.fetchall()

    cursor.execute("SELECT * FROM repayments")
    repayments = cursor.fetchall()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        total_clients=total_clients,
        active_loans=active_loans,
        total_disbursed=total_disbursed,
        total_repaid=total_repaid,
        overdue_loans=overdue_loans,
        savings_audit=savings_audit,
        clients=clients,
        loans=loans,
        repayments=repayments,
        products=products
    )

@app.route("/apply_loan", methods=["POST"])
def apply_loan():
    client_id = request.form["client_id"]
    product_id = request.form["product_id"]
    requested_amount = float(request.form["requested_amount"])

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """INSERT INTO loans 
               (ClientID, ProductID, RequestedAmount, ApprovedAmount, Status, ApplicationDate, ApprovalDate, DisbursementDate) 
               VALUES (%s, %s, %s, %s, 'Disbursed', CURDATE(), CURDATE(), CURDATE())""",
            (client_id, product_id, requested_amount, requested_amount)
        )
        conn.commit()
        flash("Loan application created and registered successfully!", "success")
    except Exception as err:
        conn.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("index"))

@app.route("/record_repayment", methods=["POST"])
def record_repayment():
    loan_id = request.form["loan_id"]
    amount_paid = float(request.form["amount_paid"])
    payment_type = request.form["payment_type"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Insert repayment transaction record into DB
        cursor.execute(
            "INSERT INTO repayments (LoanID, AmountPaid, PaymentDate, PaymentType) VALUES (%s, %s, CURDATE(), %s)",
            (loan_id, amount_paid, payment_type)
        )

        # 2. Query total amount approved vs total cumulative repayments for this loan
        cursor.execute("SELECT ApprovedAmount FROM loans WHERE LoanID = %s", (loan_id,))
        loan = cursor.fetchone()

        cursor.execute("SELECT COALESCE(SUM(AmountPaid), 0) AS total_repaid FROM repayments WHERE LoanID = %s", (loan_id,))
        repayment_data = cursor.fetchone()

        # 3. Dynamic Auto-Closure: If total repayments equal/exceed approved amount, update status to 'Closed'
        if loan and repayment_data['total_repaid'] >= loan['ApprovedAmount']:
            cursor.execute("UPDATE loans SET Status = 'Closed' WHERE LoanID = %s", (loan_id,))

        conn.commit()
        flash("Repayment recorded successfully!", "success")
    except Exception as err:
        conn.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)