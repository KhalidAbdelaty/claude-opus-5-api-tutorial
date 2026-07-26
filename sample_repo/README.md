# billing

Subscription trials and mid-cycle invoice credits.

- `billing/timeutils.py` shared date helpers
- `billing/subscriptions.py` trial state and access levels
- `billing/invoices.py` proration for mid-cycle plan changes
- `billing/plans.py` plan catalog

Run the suite with `python -m pytest tests -q` from this directory.
