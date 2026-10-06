import sqlite3, random, os
from datetime import date, timedelta
from flask import Flask, g, jsonify, request, render_template

DB = os.environ.get("DB", "microfinance.db")
app = Flask(__name__)

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, a=()): return [dict(r) for r in db().execute(sql, a)]

def make_schedule(c, loan_id, total, months, start):
    for i in range(1, months + 1):
        c.execute("INSERT INTO schedule(loan_id,due_date,due) VALUES(?,?,?)",
                  (loan_id, (start + timedelta(days=30 * i)).isoformat(), round(total / months, 2)))

def repay(c, loan_id, amt, day):
    c.execute("INSERT INTO repayment(loan_id,amount,pay_date) VALUES(?,?,?)", (loan_id, amt, day))  # trigger enforces balance
    left = amt
    for s in c.execute("SELECT schedule_id, due-paid AS r FROM schedule WHERE loan_id=? AND paid<due-0.005 ORDER BY due_date", (loan_id,)).fetchall():
        if left <= 0: break
        p = min(left, s["r"]); left -= p
        c.execute("UPDATE schedule SET paid=paid+?, status=CASE WHEN paid+?>=due-0.005 THEN 'PAID' ELSE 'PARTIAL' END WHERE schedule_id=?", (p, p, s["schedule_id"]))

def init():
    c = sqlite3.connect(DB); c.executescript(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())
    if c.execute("SELECT COUNT(*) FROM client").fetchone()[0]: return
    random.seed(7)
    c.executemany("INSERT INTO field_officer VALUES(?,?,?)", [(1, "Asha Reddy", "North"), (2, "Ravi Kumar", "South"), (3, "Meena Iyer", "East")])
    c.executemany("INSERT INTO loan_product VALUES(?,?,?,?,?)", [(1, "Micro Starter", 0.18, 10000, 12), (2, "Group Growth", 0.22, 25000, 12)])
    gid = cid = 0
    for o in (1, 2, 3):
        for _ in range(2):
            gid += 1; c.execute("INSERT INTO grp VALUES(?,?,?,?)", (gid, o, f"Group {gid}", random.choice(["Mon", "Wed", "Fri"])))
            for _ in range(5):
                cid += 1; amt = random.choice([3000, 5000, 8000, 10000])
                c.execute("INSERT INTO client VALUES(?,?,?,?,?)", (cid, gid, f"Client {cid}", f"NID{1000+cid}", "VERIFIED"))
                c.execute("INSERT INTO savings VALUES(?,?)", (cid, amt * 0.25))
                start = date.today() - timedelta(days=random.randint(60, 200)); total = round(amt * 1.18, 2)
                c.execute("INSERT INTO loan VALUES(?,?,?,?,?,?,?,?)", (cid, cid, 1, amt, start.isoformat(), start.isoformat(), total, "DISBURSED"))
                make_schedule(c, cid, total, 12, start)
                due_n = min(12, (date.today() - start).days // 30)
                for i in range(max(0, due_n - random.choice([0, 0, 1, 2, 4]))):
                    repay(c, cid, round(total / 12, 2), (start + timedelta(days=30 * (i + 1))).isoformat())
    c.commit(); c.close()

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/summary")
def summary():
    r = q("""SELECT COUNT(*) active, COALESCE(SUM(outstanding),0) outstanding FROM loan WHERE status='DISBURSED'""")[0]
    r["collected"] = q("SELECT COALESCE(SUM(amount),0) t FROM repayment")[0]["t"]
    r["overdue"] = q("SELECT COALESCE(SUM(overdue_amount),0) t FROM vw_overdue")[0]["t"]
    risk = q("SELECT COALESCE(SUM(outstanding),0) t FROM loan WHERE status='DISBURSED' AND loan_id IN (SELECT loan_id FROM vw_overdue WHERE days>30)")[0]["t"]
    r["par30"] = round(100 * risk / r["outstanding"], 1) if r["outstanding"] else 0
    return jsonify(r)

@app.route("/api/collections")
def collections(): return jsonify(q("SELECT substr(pay_date,1,7) m, ROUND(SUM(amount)) t FROM repayment GROUP BY m ORDER BY m"))

@app.route("/api/overdue")
def overdue(): return jsonify(q("SELECT * FROM vw_overdue ORDER BY days DESC"))

@app.route("/api/officers")
def officers(): return jsonify(q("""SELECT o.full_name officer_name, COUNT(DISTINCT g.group_id) n_groups, COUNT(l.loan_id) loans,
    ROUND(SUM(l.amount)) portfolio, ROUND(SUM(l.outstanding)) outstanding FROM field_officer o JOIN grp g USING(officer_id)
    JOIN client c USING(group_id) JOIN loan l USING(client_id) GROUP BY o.officer_id"""))

@app.route("/api/loans", methods=["POST"])
def new_loan():
    d = request.get_json(); c = db()
    try:
        p = c.execute("SELECT * FROM loan_product WHERE product_id=?", (d["product_id"],)).fetchone()
        if not p: return jsonify(error="Unknown product"), 400
        total = round(d["amount"] * (1 + p["interest_rate"]), 2); today = date.today()
        cur = c.execute("INSERT INTO loan(client_id,product_id,amount,approval_date,disbursement_date,outstanding,status) VALUES(?,?,?,?,?,?,'DISBURSED')",
                        (d["client_id"], d["product_id"], d["amount"], today.isoformat(), today.isoformat(), total))
        make_schedule(c, cur.lastrowid, total, p["months"], today); c.commit()
        return jsonify(message=f"Loan #{cur.lastrowid} disbursed, {p['months']} installments created")
    except sqlite3.DatabaseError as e:
        c.rollback(); return jsonify(error=str(e)), 400

@app.route("/api/repay", methods=["POST"])
def post_repay():
    d = request.get_json(); c = db()
    try:
        repay(c, d["loan_id"], d["amount"], date.today().isoformat()); c.commit()
        return jsonify(message="Repayment posted and schedule updated")
    except sqlite3.DatabaseError as e:
        c.rollback(); return jsonify(error=str(e)), 400

init()
if __name__ == "__main__": app.run(debug=True)
