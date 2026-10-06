PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS field_officer(officer_id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, zone TEXT);
CREATE TABLE IF NOT EXISTS grp(group_id INTEGER PRIMARY KEY, officer_id INT NOT NULL REFERENCES field_officer, group_name TEXT NOT NULL, meeting_day TEXT);
CREATE TABLE IF NOT EXISTS client(client_id INTEGER PRIMARY KEY, group_id INT NOT NULL REFERENCES grp, full_name TEXT NOT NULL, national_id TEXT UNIQUE, kyc_status TEXT DEFAULT 'PENDING');
CREATE TABLE IF NOT EXISTS loan_product(product_id INTEGER PRIMARY KEY, name TEXT NOT NULL, interest_rate REAL NOT NULL, max_amount REAL NOT NULL CHECK(max_amount>0), months INT NOT NULL);
CREATE TABLE IF NOT EXISTS savings(client_id INT PRIMARY KEY REFERENCES client, balance REAL NOT NULL DEFAULT 0 CHECK(balance>=0));
CREATE TABLE IF NOT EXISTS loan(loan_id INTEGER PRIMARY KEY, client_id INT NOT NULL REFERENCES client, product_id INT NOT NULL REFERENCES loan_product,
  amount REAL NOT NULL CHECK(amount>0), approval_date TEXT NOT NULL, disbursement_date TEXT, outstanding REAL NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('APPROVED','DISBURSED','CLOSED')),
  CHECK(disbursement_date IS NULL OR disbursement_date>=approval_date));
CREATE TABLE IF NOT EXISTS schedule(schedule_id INTEGER PRIMARY KEY, loan_id INT NOT NULL REFERENCES loan, due_date TEXT NOT NULL, due REAL NOT NULL, paid REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'PENDING');
CREATE TABLE IF NOT EXISTS repayment(repayment_id INTEGER PRIMARY KEY, loan_id INT NOT NULL REFERENCES loan, amount REAL NOT NULL CHECK(amount>0), pay_date TEXT NOT NULL);

CREATE TRIGGER IF NOT EXISTS trg_loan_rules BEFORE INSERT ON loan BEGIN
  SELECT RAISE(ABORT,'Approved amount exceeds product limit') WHERE NEW.amount>(SELECT max_amount FROM loan_product WHERE product_id=NEW.product_id);
  SELECT RAISE(ABORT,'Savings below 20% mandatory collateral') WHERE COALESCE((SELECT balance FROM savings WHERE client_id=NEW.client_id),0)<NEW.amount*0.2;
END;
CREATE TRIGGER IF NOT EXISTS trg_repay_check BEFORE INSERT ON repayment BEGIN
  SELECT RAISE(ABORT,'Repayment exceeds outstanding balance') WHERE NEW.amount>(SELECT outstanding FROM loan WHERE loan_id=NEW.loan_id)+0.005;
END;
CREATE TRIGGER IF NOT EXISTS trg_repay_post AFTER INSERT ON repayment BEGIN
  UPDATE loan SET outstanding=MAX(0,outstanding-NEW.amount),
    status=CASE WHEN outstanding-NEW.amount<=0.005 THEN 'CLOSED' ELSE status END WHERE loan_id=NEW.loan_id;
END;

CREATE VIEW IF NOT EXISTS vw_overdue AS
SELECT l.loan_id, c.full_name AS client, g.group_name, s.due_date, ROUND(s.due-s.paid,2) AS overdue_amount,
  CAST(julianday('now')-julianday(s.due_date) AS INT) AS days,
  CASE WHEN julianday('now')-julianday(s.due_date)>90 THEN 'PAR 90 (NPL)'
       WHEN julianday('now')-julianday(s.due_date)>30 THEN 'PAR 30 (Watchlist)' ELSE 'PAR 1-30' END AS risk
FROM schedule s JOIN loan l USING(loan_id) JOIN client c USING(client_id) JOIN grp g USING(group_id)
WHERE s.due_date<date('now') AND s.paid<s.due-0.005 AND l.status='DISBURSED';
