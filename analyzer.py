"""
Supply Chain Performance & Inventory Risk Analyzer
Author: Kendra M. Adams
Description: Connects to a SQL database, analyzes supply chain performance,
             flags inventory risks, scores vendors, and generates a weekly
             exception report with actionable recommendations.
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ── CONFIG ───────────────────────────────────────────────────────────────────
DB_PATH = '/home/claude/supply_chain_project/supply_chain.db'
OUTPUT_DIR = '/home/claude/supply_chain_project/'
REPORT_DATE = datetime(2026, 4, 16)
STOCKOUT_THRESHOLD_DAYS = 14   # Flag if < 14 days of supply
LOW_STOCK_THRESHOLD_DAYS = 21  # Warn if < 21 days of supply
LATE_DELIVERY_THRESHOLD = 3    # Days late before flagging
ON_TIME_TARGET = 85.0          # Vendor on-time % target

# ── DATABASE CONNECTION ──────────────────────────────────────────────────────
def get_connection():
    return sqlite3.connect(DB_PATH)

# ── SQL QUERIES ──────────────────────────────────────────────────────────────
def query_inventory_risk():
    """SQL: Pull inventory levels and calculate stockout risk."""
    sql = """
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        p.safety_stock,
        p.reorder_point,
        i.current_stock,
        i.weekly_demand_avg,
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
    """
    conn = get_connection()
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df

def query_vendor_performance():
    """SQL: Pull vendor scorecard from view."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM vendor_performance ORDER BY on_time_rate_pct ASC", conn)
    conn.close()
    return df

def query_late_orders():
    """SQL: Pull currently open or recently late purchase orders."""
    sql = """
    SELECT 
        po.po_id,
        p.product_name,
        v.vendor_name,
        po.order_date,
        po.expected_delivery,
        po.actual_delivery,
        po.days_late,
        po.quantity_ordered,
        po.status,
        ROUND(po.quantity_ordered * po.unit_cost, 2) as order_value
    FROM purchase_orders po
    JOIN products p ON po.product_id = p.product_id
    JOIN vendors v ON po.vendor_id = v.vendor_id
    WHERE (po.days_late > 3 AND po.status = 'Delivered')
       OR po.status = 'In Transit'
    ORDER BY po.days_late DESC
    """
    conn = get_connection()
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df

def query_fulfillment_rate():
    """SQL: Calculate customer order fulfillment rate by product."""
    sql = """
    SELECT 
        p.product_name,
        p.category,
        COUNT(co.order_id) as total_orders,
        SUM(co.quantity_requested) as total_requested,
        SUM(co.quantity_fulfilled) as total_fulfilled,
        ROUND(100.0 * SUM(co.quantity_fulfilled) / NULLIF(SUM(co.quantity_requested), 0), 1) as fill_rate_pct,
        SUM(CASE WHEN co.fulfillment_status LIKE '%Backorder%' THEN 1 ELSE 0 END) as backorder_count
    FROM customer_orders co
    JOIN products p ON co.product_id = p.product_id
    GROUP BY p.product_id
    ORDER BY fill_rate_pct ASC
    """
    conn = get_connection()
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df

# ── ANALYSIS & RECOMMENDATIONS ───────────────────────────────────────────────
def generate_recommendations(inventory_df, vendor_df, late_df, fulfillment_df):
    recommendations = []
    priority_actions = []

    # Inventory recommendations
    critical = inventory_df[inventory_df['risk_level'] == 'CRITICAL']
    stockout = inventory_df[inventory_df['risk_level'] == 'STOCKOUT RISK']
    low = inventory_df[inventory_df['risk_level'] == 'LOW STOCK']
    reorder = inventory_df[inventory_df['risk_level'] == 'REORDER NOW']

    for _, row in critical.iterrows():
        priority_actions.append({
            'priority': '🔴 URGENT',
            'action': f"EMERGENCY REORDER: {row['product_name']} — only {row['current_stock']} units left ({row['days_of_supply']} days of supply). Below safety stock of {row['safety_stock']}. Place order immediately."
        })

    for _, row in stockout.iterrows():
        priority_actions.append({
            'priority': '🔴 HIGH',
            'action': f"REORDER NOW: {row['product_name']} — {row['days_of_supply']} days of supply remaining. At current demand of {row['weekly_demand_avg']} units/week, stockout expected within 2 weeks."
        })

    for _, row in low.iterrows():
        priority_actions.append({
            'priority': '🟡 MEDIUM',
            'action': f"PLAN REORDER: {row['product_name']} — {row['days_of_supply']} days of supply. Review lead times and place order within 5 days."
        })

    for _, row in reorder.iterrows():
        priority_actions.append({
            'priority': '🟡 MEDIUM',
            'action': f"REORDER POINT REACHED: {row['product_name']} — stock at {row['current_stock']} units, below reorder point of {row['reorder_point']}."
        })

    # Vendor recommendations
    underperforming = vendor_df[vendor_df['on_time_rate_pct'] < ON_TIME_TARGET]
    for _, row in underperforming.iterrows():
        gap = ON_TIME_TARGET - row['on_time_rate_pct']
        priority_actions.append({
            'priority': '🟠 VENDOR',
            'action': f"EVALUATE VENDOR: {row['vendor_name']} ({row['country']}) — on-time rate {row['on_time_rate_pct']}%, which is {gap:.1f}% below the {ON_TIME_TARGET}% target. {row['late_deliveries']} late deliveries in period. Schedule performance review or identify backup supplier."
        })

    # Fulfillment recommendations
    low_fill = fulfillment_df[fulfillment_df['fill_rate_pct'] < 90]
    for _, row in low_fill.iterrows():
        priority_actions.append({
            'priority': '🟡 MEDIUM',
            'action': f"IMPROVE FILL RATE: {row['product_name']} — fill rate at {row['fill_rate_pct']}% with {row['backorder_count']} backorders. Investigate root cause: vendor delays or insufficient safety stock."
        })

    return priority_actions

# ── VISUALIZATIONS ────────────────────────────────────────────────────────────
def create_charts(inventory_df, vendor_df, fulfillment_df):
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Supply Chain Performance Dashboard\nWeek of April 16, 2026',
                 fontsize=16, fontweight='bold', y=0.98)

    colors_risk = {'CRITICAL': '#d32f2f', 'STOCKOUT RISK': '#f44336',
                   'LOW STOCK': '#ff9800', 'REORDER NOW': '#ffc107', 'OK': '#4caf50'}

    # Chart 1: Inventory Days of Supply
    ax1 = axes[0, 0]
    bar_colors = [colors_risk.get(r, '#4caf50') for r in inventory_df['risk_level']]
    bars = ax1.barh(inventory_df['product_name'], inventory_df['days_of_supply'], color=bar_colors)
    ax1.axvline(x=14, color='red', linestyle='--', alpha=0.7, label='Stockout Risk (14 days)')
    ax1.axvline(x=21, color='orange', linestyle='--', alpha=0.7, label='Low Stock (21 days)')
    ax1.set_xlabel('Days of Supply Remaining')
    ax1.set_title('Inventory Health — Days of Supply', fontweight='bold')
    ax1.legend(fontsize=8)
    for bar, val in zip(bars, inventory_df['days_of_supply']):
        ax1.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                f'{val}d', va='center', fontsize=8)

    # Chart 2: Vendor On-Time Rate
    ax2 = axes[0, 1]
    bar_colors2 = ['#4caf50' if x >= ON_TIME_TARGET else '#f44336' for x in vendor_df['on_time_rate_pct']]
    bars2 = ax2.bar(vendor_df['vendor_name'], vendor_df['on_time_rate_pct'], color=bar_colors2)
    ax2.axhline(y=ON_TIME_TARGET, color='navy', linestyle='--', label=f'Target ({ON_TIME_TARGET}%)')
    ax2.set_ylabel('On-Time Delivery Rate (%)')
    ax2.set_title('Vendor Scorecard — On-Time Delivery', fontweight='bold')
    ax2.set_ylim(0, 105)
    ax2.tick_params(axis='x', rotation=20)
    ax2.legend()
    for bar, val in zip(bars2, vendor_df['on_time_rate_pct']):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{val}%', ha='center', fontsize=9, fontweight='bold')

    # Chart 3: Customer Fill Rate
    ax3 = axes[1, 0]
    fill_colors = ['#4caf50' if x >= 90 else '#f44336' for x in fulfillment_df['fill_rate_pct']]
    ax3.barh(fulfillment_df['product_name'], fulfillment_df['fill_rate_pct'], color=fill_colors)
    ax3.axvline(x=90, color='red', linestyle='--', alpha=0.7, label='90% Target')
    ax3.set_xlabel('Fill Rate (%)')
    ax3.set_title('Customer Order Fill Rate by Product', fontweight='bold')
    ax3.set_xlim(0, 110)
    ax3.legend()

    # Chart 4: Risk Summary Donut
    ax4 = axes[1, 1]
    risk_counts = inventory_df['risk_level'].value_counts()
    risk_colors_list = [colors_risk.get(r, '#4caf50') for r in risk_counts.index]
    wedges, texts, autotexts = ax4.pie(
        risk_counts.values, labels=risk_counts.index,
        colors=risk_colors_list, autopct='%1.0f%%',
        startangle=90, pctdistance=0.75
    )
    centre_circle = plt.Circle((0, 0), 0.55, fc='white')
    ax4.add_patch(centre_circle)
    ax4.set_title('Inventory Risk Distribution', fontweight='bold')
    ax4.text(0, 0, f'{len(inventory_df)}\nProducts', ha='center', va='center',
             fontsize=12, fontweight='bold')

    plt.tight_layout()
    chart_path = f'{OUTPUT_DIR}dashboard.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Dashboard saved: {chart_path}")
    return chart_path

# ── EXCEPTION REPORT ──────────────────────────────────────────────────────────
def generate_report(inventory_df, vendor_df, late_df, fulfillment_df, recommendations):
    report_lines = []
    sep = "=" * 70

    report_lines.append(sep)
    report_lines.append("  WEEKLY SUPPLY CHAIN EXCEPTION REPORT")
    report_lines.append(f"  Generated: {REPORT_DATE.strftime('%B %d, %Y')} | Analyst: Kendra M. Adams")
    report_lines.append(sep)

    # Executive Summary
    critical_count = len(inventory_df[inventory_df['risk_level'].isin(['CRITICAL', 'STOCKOUT RISK'])])
    low_count = len(inventory_df[inventory_df['risk_level'].isin(['LOW STOCK', 'REORDER NOW'])])
    vendor_flags = len(vendor_df[vendor_df['on_time_rate_pct'] < ON_TIME_TARGET])
    avg_fill = fulfillment_df['fill_rate_pct'].mean()

    report_lines.append("\n📊 EXECUTIVE SUMMARY")
    report_lines.append("-" * 40)
    report_lines.append(f"  🔴 Critical/Stockout Risk Products : {critical_count}")
    report_lines.append(f"  🟡 Low Stock / Reorder Required    : {low_count}")
    report_lines.append(f"  🟠 Vendors Below On-Time Target    : {vendor_flags}")
    report_lines.append(f"  📦 Avg Customer Fill Rate          : {avg_fill:.1f}%")
    report_lines.append(f"  📋 Total Action Items This Week    : {len(recommendations)}")

    # Inventory Risk
    report_lines.append(f"\n\n🏭 INVENTORY RISK ANALYSIS")
    report_lines.append("-" * 40)
    flagged = inventory_df[inventory_df['risk_level'] != 'OK']
    if flagged.empty:
        report_lines.append("  ✅ All inventory levels are healthy.")
    else:
        for _, row in flagged.iterrows():
            report_lines.append(f"\n  [{row['risk_level']}] {row['product_name']}")
            report_lines.append(f"    Current Stock : {row['current_stock']} units")
            report_lines.append(f"    Days of Supply: {row['days_of_supply']} days")
            report_lines.append(f"    Weekly Demand : {row['weekly_demand_avg']} units/week")
            report_lines.append(f"    Safety Stock  : {row['safety_stock']} units")

    # Vendor Scorecard
    report_lines.append(f"\n\n🚚 VENDOR PERFORMANCE SCORECARD")
    report_lines.append("-" * 40)
    for _, row in vendor_df.iterrows():
        status = "✅" if row['on_time_rate_pct'] >= ON_TIME_TARGET else "❌"
        report_lines.append(f"\n  {status} {row['vendor_name']} ({row['country']})")
        report_lines.append(f"    On-Time Rate  : {row['on_time_rate_pct']}% (Target: {ON_TIME_TARGET}%)")
        report_lines.append(f"    Avg Days Late : {row['avg_days_late']} days")
        report_lines.append(f"    Late Deliveries: {row['late_deliveries']} of {row['delivered_orders']}")

    # Late Orders
    report_lines.append(f"\n\n⚠️  LATE & AT-RISK PURCHASE ORDERS")
    report_lines.append("-" * 40)
    if late_df.empty:
        report_lines.append("  ✅ No significantly late orders.")
    else:
        for _, row in late_df.head(8).iterrows():
            report_lines.append(f"\n  PO: {row['po_id']} | {row['product_name']}")
            report_lines.append(f"    Vendor   : {row['vendor_name']}")
            report_lines.append(f"    Status   : {row['status']}")
            report_lines.append(f"    Days Late: {row['days_late'] if row['days_late'] else 'In Transit'}")
            report_lines.append(f"    Value    : ${row['order_value']:,.2f}")

    # Fulfillment
    report_lines.append(f"\n\n📦 CUSTOMER ORDER FULFILLMENT")
    report_lines.append("-" * 40)
    low_fill = fulfillment_df[fulfillment_df['fill_rate_pct'] < 90]
    if low_fill.empty:
        report_lines.append("  ✅ All products meeting 90% fill rate target.")
    else:
        for _, row in low_fill.iterrows():
            report_lines.append(f"\n  ❌ {row['product_name']}")
            report_lines.append(f"    Fill Rate  : {row['fill_rate_pct']}%")
            report_lines.append(f"    Backorders : {row['backorder_count']}")

    # Actionable Recommendations
    report_lines.append(f"\n\n✅ ACTIONABLE RECOMMENDATIONS — PRIORITY ORDER")
    report_lines.append("-" * 40)
    for i, rec in enumerate(recommendations, 1):
        report_lines.append(f"\n  {i}. {rec['priority']}")
        report_lines.append(f"     {rec['action']}")

    report_lines.append(f"\n\n{sep}")
    report_lines.append("  END OF REPORT")
    report_lines.append(sep)

    report_text = "\n".join(report_lines)
    report_path = f'{OUTPUT_DIR}weekly_exception_report.txt'
    with open(report_path, 'w') as f:
        f.write(report_text)

    print(report_text)
    print(f"\n✅ Report saved: {report_path}")
    return report_path

# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔄 Running Supply Chain Performance Analyzer...\n")

    # Pull data via SQL queries
    inventory_df    = query_inventory_risk()
    vendor_df       = query_vendor_performance()
    late_df         = query_late_orders()
    fulfillment_df  = query_fulfillment_rate()

    # Generate recommendations
    recommendations = generate_recommendations(inventory_df, vendor_df, late_df, fulfillment_df)

    # Create visualizations
    create_charts(inventory_df, vendor_df, fulfillment_df)

    # Generate exception report
    generate_report(inventory_df, vendor_df, late_df, fulfillment_df, recommendations)
