from datetime import datetime, timedelta
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.app.api.deps import require_admin_token
from src.app.core.database import get_db
from src.app import models

router = APIRouter(prefix="/admin/dashboard", tags=["Admin"])


def _month_starts(last_n: int = 6):
    """Return list of (month_label, start_dt, end_dt) for last_n months (ascending)."""
    now = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = []
    for i in range(last_n - 1, -1, -1):
        # month i months ago
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        start = datetime(year, month, 1)
        # compute next month
        nm = month + 1
        ny = year
        if nm == 13:
            nm = 1
            ny += 1
        end = datetime(ny, nm, 1)
        label = start.strftime("%b")
        months.append((label, start, end))
    return months


def _table_exists(db: Session, table_name: str) -> bool:
    r = db.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = :t LIMIT 1"), {"t": table_name}).first()
    return bool(r)


@router.get("", dependencies=[Depends(require_admin_token)])
def admin_dashboard(db: Session = Depends(get_db)):
    """Admin dashboard summary for last 6 months.

    Returns stats (total users, jobs, active subscriptions, revenue) and charts per month.
    """
    months = _month_starts(6)

    # Charts data
    revenue_data: List[Dict] = []
    jobs_data: List[Dict] = []
    users_growth_data: List[Dict] = []

    # Prepare monthly values
    payments_table = _table_exists(db, 'payments')

    for label, start, end in months:
        # revenue
        if payments_table:
            q = text("SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE payment_date >= :s AND payment_date < :e")
            res = db.execute(q, {"s": start, "e": end}).first()
            revenue = float(res.total) if res and res.total is not None else 0.0
        else:
            revenue = 0.0

        revenue_data.append({"month": label, "value": int(revenue), "label": label})

        # jobs count
        jobs_count = (
            db.query(func.count(models.user.Job.id))
            .filter(models.user.Job.created_at >= start, models.user.Job.created_at < end)
            .scalar()
            or 0
        )
        jobs_data.append({"month": label, "value": int(jobs_count), "label": label})

        # cumulative users at end of month
        users_cum = (
            db.query(func.count(models.user.User.id)).filter(models.user.User.created_at < end).scalar() or 0
        )
        users_growth_data.append({"month": label, "value": int(users_cum), "label": label})

    # Totals and latest comparisons
    # Total users (current)
    total_users = db.query(func.count(models.user.User.id)).scalar() or 0

    # New users in latest month vs previous
    latest_users = users_growth_data[-1]["value"] if len(users_growth_data) >= 1 else 0
    prev_users = users_growth_data[-2]["value"] if len(users_growth_data) >= 2 else 0
    new_users_latest = latest_users - prev_users
    new_users_prev = prev_users - (users_growth_data[-3]["value"] if len(users_growth_data) >= 3 else 0)
    users_growth_pct = 0
    if new_users_prev != 0:
        try:
            users_growth_pct = round((new_users_latest - new_users_prev) / abs(new_users_prev) * 100, 1)
        except Exception:
            users_growth_pct = 0

    # Total jobs (current)
    total_jobs = db.query(func.count(models.user.Job.id)).scalar() or 0
    jobs_latest = jobs_data[-1]["value"] if len(jobs_data) >= 1 else 0
    jobs_prev = jobs_data[-2]["value"] if len(jobs_data) >= 2 else 0
    jobs_change = jobs_latest - jobs_prev
    jobs_growth_pct = round(((jobs_latest - jobs_prev) / jobs_prev * 100), 1) if jobs_prev != 0 else 0

    # Active subscriptions
    active_subs = db.query(func.count(models.user.Subscriber.id)).filter(models.user.Subscriber.is_active == True).scalar() or 0
    # For growth compare active in latest month vs previous month using subscribers table creation/renew dates
    # Approximation: count subscribers with subscription_renew_date in month range
    sub_latest = (
        db.query(func.count(models.user.Subscriber.id))
        .filter(models.user.Subscriber.subscription_renew_date >= months[-1][1], models.user.Subscriber.subscription_renew_date < months[-1][2])
        .scalar() or 0
    )
    sub_prev = (
        db.query(func.count(models.user.Subscriber.id))
        .filter(models.user.Subscriber.subscription_renew_date >= months[-2][1], models.user.Subscriber.subscription_renew_date < months[-2][2])
        .scalar() or 0
    )
    sub_change = sub_latest - sub_prev
    sub_growth_pct = round(((sub_latest - sub_prev) / sub_prev * 100), 1) if sub_prev != 0 else 0

    # Revenue totals over period and growth
    revenue_values = [m["value"] for m in revenue_data]
    revenue_total = sum(revenue_values)
    revenue_latest = revenue_values[-1] if revenue_values else 0
    revenue_prev = revenue_values[-2] if len(revenue_values) >= 2 else 0
    revenue_change = revenue_latest - revenue_prev
    revenue_growth_pct = round(((revenue_latest - revenue_prev) / revenue_prev * 100), 1) if revenue_prev != 0 else 0

    response = {
        "stats": {
            "totalUsers": {
                "count": int(total_users),
                "growth": f"{users_growth_pct:+}%",
                "growthValue": users_growth_pct,
                "changeFromLastMonth": int(new_users_latest),
            },
            "totalJobs": {
                "count": int(total_jobs),
                "growth": f"{jobs_growth_pct:+}%",
                "growthValue": jobs_growth_pct,
                "changeFromLastMonth": int(jobs_change),
            },
            "activeSubscriptions": {
                "count": int(active_subs),
                "growth": f"{sub_growth_pct:+}%",
                "growthValue": sub_growth_pct,
                "changeFromLastMonth": int(sub_change),
            },
            "totalRevenue": {
                "amount": int(revenue_total),
                "formatted": f"${int(revenue_total):,}",
                "growth": f"{revenue_growth_pct:+}%",
                "growthValue": revenue_growth_pct,
                "changeFromLastMonth": int(revenue_change),
            },
        },
        "charts": {
            "revenue": {
                "data": revenue_data,
                "latest": {"month": months[-1][0], "value": revenue_latest, "formatted": f"${revenue_latest:,}"},
                "total": int(revenue_total),
                "currency": "USD",
            },
            "jobs": {
                "data": jobs_data,
                "peak": {
                    "month": max(jobs_data, key=lambda x: x['value'])['month'] if jobs_data else None,
                    "value": max(jobs_data, key=lambda x: x['value'])['value'] if jobs_data else 0,
                    "formatted": f"{max(jobs_data, key=lambda x: x['value'])['value']} Jobs" if jobs_data else "0 Jobs",
                },
                "total": sum(j['value'] for j in jobs_data),
                "averagePerMonth": round(sum(j['value'] for j in jobs_data) / len(jobs_data)) if jobs_data else 0,
            },
            "userGrowth": {
                "data": users_growth_data,
                "current": users_growth_data[-1]['value'] if users_growth_data else 0,
                "formatted": f"{users_growth_data[-1]['value']:,} Users" if users_growth_data else "0 Users",
                "growthRate": users_growth_pct,
            },
        },
        "filters": {
            "timeRange": "last6Months",
            "state": "allStates",
            "appliedFilters": {"dateFrom": months[0][1].strftime("%Y-%m-%d"), "dateTo": (months[-1][2] - timedelta(seconds=1)).strftime("%Y-%m-%d")},
        },
        "metadata": {"lastUpdated": datetime.utcnow().isoformat() + "Z", "timezone": "UTC", "dataSource": "primary_db", "cacheKey": "dashboard_6m_all_states"},
    }

    return response
