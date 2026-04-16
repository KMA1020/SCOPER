# SCOPER — Supply Chain Performance & Exception Reporter

**Author:** Kendra M. Adams  
**Tools Used:** Python, SQL, HTML
**Industry:** Consumer Goods / E-Commerce Supply Chain  

---

## What This Project Does

This project simulates a real-world supply chain monitoring system for a consumer goods importer/supplier. It automatically analyzes inventory levels, vendor performance, purchase order delays, and customer fulfillment rates — then generates a prioritized weekly exception report with actionable recommendations.

The goal: replace manual weekly Excel reporting with an automated system that surfaces the right problems at the right time so operations teams can act before a stockout or vendor failure becomes a customer issue.

---

## What SQL Is Doing

SQL is the foundation of this project. All data lives in a relational SQLite database with five tables:

| Table | What It Stores |
|---|---|
| `products` | Product catalog with safety stock and reorder points |
| `vendors` | Vendor profiles including lead times and reliability scores |
| `purchase_orders` | Every PO with order dates, expected vs actual delivery, and delay data |
| `inventory` | Current stock levels and weekly demand averages |
| `customer_orders` | Customer demand and fulfillment status |

**Key SQL operations used:**
- `JOIN` — connects purchase orders to products and vendors in a single query
- `CASE WHEN` — classifies inventory into risk tiers (CRITICAL, STOCKOUT RISK, LOW STOCK, OK)
- `GROUP BY` + `AVG` / `SUM` / `COUNT` — aggregates vendor performance metrics
- `CREATE VIEW` — builds a reusable vendor scorecard that Python can query anytime
- `WHERE` filters — isolates late or at-risk purchase orders

**Example SQL query — inventory risk classification:**
```sql
SELECT 
    p.product_name,
    i.current_stock,
    i.days_of_supply,
    CASE 
        WHEN i.current_stock <= p.safety_stock THEN 'CRITICAL'
        WHEN i.days_of_supply <= 14             THEN 'STOCKOUT RISK'
        WHEN i.days_of_supply <= 21             THEN 'LOW STOCK'
        WHEN i.current_stock <= p.reorder_point THEN 'REORDER NOW'
        ELSE 'OK'
    END AS risk_level
FROM products p
JOIN inventory i ON p.product_id = i.product_id
ORDER BY i.days_of_supply ASC
```

---

## What Python Is Doing

Python connects to the SQL database, pulls the query results into Pandas DataFrames, runs the analysis logic, generates visualizations, and writes the final report.

**Key Python operations:**

| Task | How Python Does It |
|---|---|
| Database connection | `sqlite3` library — connects, queries, returns results |
| Data manipulation | `pandas` — DataFrames for filtering, sorting, calculating |
| Visualization | `matplotlib` + `seaborn` — 4-panel dashboard |
| Recommendation engine | Custom logic that flags exceptions and writes plain-English action items |
| Report generation | Writes formatted text report automatically — no manual work |

**The analysis Python runs:**
1. Pulls inventory data → calculates days of supply → classifies risk level
2. Pulls vendor scorecard → compares on-time rate to 85% target → flags underperformers
3. Pulls late purchase orders → surfaces high-value at-risk shipments
4. Pulls customer orders → calculates fill rate by product → flags below 90%
5. Combines all findings → generates prioritized recommendations in urgency order

---

## What the Output Looks Like

**Dashboard (dashboard.png):** 4-panel visual showing inventory health, vendor scorecard, customer fill rates, and risk distribution

**Weekly Exception Report (weekly_exception_report.txt):** Auto-generated report with:
- Executive summary (counts of critical items, vendor flags, fill rate)
- Detailed inventory risk breakdown
- Vendor performance scorecard
- Late and at-risk purchase orders
- Prioritized action items ranked by urgency

**Sample recommendation output:**
```
1. 🔴 URGENT
   EMERGENCY REORDER: Stainless Steel Water Bottle — only 94 units left 
   (4.1 days of supply). Below safety stock of 400. Place order immediately.

8. 🟠 VENDOR
   EVALUATE VENDOR: SunTech Suppliers (China) — on-time rate 36.8%, 
   which is 48.2% below the 85.0% target. 12 late deliveries in period. 
   Schedule performance review or identify backup supplier.
```

---

## How to Run It

```bash
# 1. Generate the dataset
python3 generate_data.py

# 2. Load data into SQL database
python3 setup_database.py

# 3. Run the analyzer — generates dashboard and report
python3 analyzer.py
```

---

## Real-World Application

This type of tool directly addresses problems I encountered in supply chain operations:

- **At Rhee Bros** — manually reconciling inventory across multiple warehouse locations. This automates that process and adds risk scoring.
- **In AOG logistics** — identifying exception patterns across high-volume shipment data. The same exception-monitoring logic applies at any scale.
- **For any operations team** — the weekly report replaces hours of manual Excel work with a single script run, giving analysts time to act on insights instead of building them by hand.

---

## Skills Demonstrated

`Python` `SQL` `Pandas` `Matplotlib` `SQLite` `Data Analysis` `KPI Tracking` `Exception Monitoring` `Inventory Management` `Vendor Scorecard` `Supply Chain Analytics` `Automated Reporting`
