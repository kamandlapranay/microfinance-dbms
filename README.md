# Microfinance Loan & Repayment Management System

Flask + SQLite implementation of the 3NF microfinance DBMS from the project reviews, with a live analytics dashboard.

## Run
    pip install -r requirements.txt
    python app.py        # http://127.0.0.1:5000 (auto-creates and seeds microfinance.db)

## What maps to the review slides
- `schema.sql` – 3NF tables, CHECK constraints, triggers (product limit, 20% savings collateral, repayment within balance), `vw_overdue` PAR view
- `app.py` – REST API, schedule generation, repayment allocation to oldest installments, officer portfolio aggregation
- `templates/index.html` – dashboard: KPIs, collections trend, PAR risk chart, overdue table, officer portfolio, loan and repayment forms

## Demo for the final review
Try disbursing 15000 on product 1, or repaying more than the outstanding balance: the DB triggers reject it and the error shows in the UI.
