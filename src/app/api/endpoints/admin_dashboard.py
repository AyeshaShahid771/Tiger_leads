from datetime import datetime, timedelta
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.app.api.deps import require_admin_token
from src.app.core.database import get_db
from src.app import models

router = APIRouter(prefix="/admin/dashboard", tags=["Admin"])


from pydantic import BaseModel


class DashboardFilter(BaseModel):
    state: str
    timeRange: str


def _periods_for_range(time_range: str):
    """Return (periods, bucket) where periods is list of (label,start,end).

    bucket: 'month' or 'day'
    """
    now = datetime.utcnow()
    if time_range == "last6Months":
        # reuse _month_starts
        return _month_starts(6), "month"
    if time_range == "last12Months":
        return _month_starts(12), "month"
    if time_range == "thisYear":
        start = datetime(now.year, 1, 1)
        months = []
        for m in range(1, now.month + 1):
            s = datetime(now.year, m, 1)
            nm = m + 1
            ny = now.year
            if nm == 13:
                nm = 1
                ny += 1
            e = datetime(ny, nm, 1)
            months.append((s.strftime("%b"), s, e))
        return months, "month"
    if time_range == "lastYear":
        y = now.year - 1
        months = []
        for m in range(1, 13):
            s = datetime(y, m, 1)
            nm = m + 1
            ny = y
            if nm == 13:
                nm = 1
                ny += 1
            e = datetime(ny, nm, 1)
            months.append((s.strftime("%b"), s, e))
        return months, "month"
    if time_range == "last30Days":
        periods = []
        for i in range(29, -1, -1):
            d = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            periods.append((d.strftime("%Y-%m-%d"), d, d + timedelta(days=1)))
        return periods, "day"
    if time_range == "last90Days":
        periods = []
        for i in range(89, -1, -1):
            d = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            periods.append((d.strftime("%Y-%m-%d"), d, d + timedelta(days=1)))
        return periods, "day"
    # default
    return _month_starts(6), "month"



@router.post("/filter", dependencies=[Depends(require_admin_token)])
def admin_dashboard_filter(payload: DashboardFilter, db: Session = Depends(get_db)):
    """Return dashboard charts filtered by `state` and `timeRange`.

    - `state`: state code or name to filter (matches contractor.state or supplier.service_states or job.state)
    - `timeRange`: one of the supported range values
    """
    state = payload.state
    periods, bucket = _periods_for_range(payload.timeRange)

    # find user ids for contractors/suppliers who serve this state
    user_ids = set()
    try:
        # contractors: state is an ARRAY column; use PostgreSQL ANY
        q = text("SELECT user_id FROM contractors WHERE :st = ANY(state)")
        for row in db.execute(q, {"st": state}).fetchall():
            user_ids.add(row.user_id)

        q2 = text("SELECT user_id FROM suppliers WHERE :st = ANY(service_states)")
        for row in db.execute(q2, {"st": state}).fetchall():
            user_ids.add(row.user_id)
    except Exception:
        # if DB doesn't support ANY or arrays, skip and return empty
        user_ids = set()

    # fetch subscriber ids for these users (to filter payments)
    subscriber_ids = set()
    if user_ids:
        s_q = text("SELECT id FROM subscribers WHERE user_id = ANY(:uids)")
        # SQLAlchemy/text doesn't auto-adapt list; pass as tuple string
        for r in db.execute(s_q, {"uids": list(user_ids)}).fetchall():
            subscriber_ids.add(r.id)

    revenue_data = []
    jobs_data = []
    users_data = []

    for label, start, end in periods:
        # revenue
        if subscriber_ids and _table_exists(db, 'payments'):
            q = text("SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE payment_date >= :s AND payment_date < :e AND subscriber_id = ANY(:sids)")
            res = db.execute(q, {"s": start, "e": end, "sids": list(subscriber_ids)}).first()
            revenue = float(res.total) if res and res.total is not None else 0.0
        else:
            revenue = 0.0
        revenue_data.append({"month": label, "value": int(revenue), "label": label})

        # jobs: match job.state or uploaded_by_user_id in user_ids
        jobs_q = db.query(func.count(models.user.Job.id)).filter(models.user.Job.created_at >= start, models.user.Job.created_at < end)
        jobs_q = jobs_q.filter((models.user.Job.state == state) | (models.user.Job.uploaded_by_user_id.in_(list(user_ids)) if user_ids else False))
        jobs_count = jobs_q.scalar() or 0
        jobs_data.append({"month": label, "value": int(jobs_count), "label": label})

        # users cumulative at end
        if user_ids:
            users_cum = db.query(func.count(models.user.User.id)).filter(models.user.User.created_at < end, models.user.User.id.in_(list(user_ids))).scalar() or 0
        else:
            users_cum = 0
        users_data.append({"month": label, "value": int(users_cum), "label": label})

    revenue_values = [m["value"] for m in revenue_data]
    revenue_total = sum(revenue_values)
    revenue_latest = revenue_values[-1] if revenue_values else 0

    jobs_total = sum(j["value"] for j in jobs_data)

    users_current = users_data[-1]["value"] if users_data else 0

    resp = {
        "charts": {
            "revenue": {
                "data": revenue_data,
                "latest": {"month": periods[-1][0], "value": revenue_latest, "formatted": f"${revenue_latest:,}"},
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
                "total": int(jobs_total),
                "averagePerMonth": round(sum(j['value'] for j in jobs_data) / len(jobs_data)) if jobs_data else 0,
            },
            "userGrowth": {
                "data": users_data,
                "current": users_current,
                "formatted": f"{users_current:,} Users",
                "growthRate": 0,
            },
        }
    }

    return resp


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


def _percent_change(current: int, previous: int):
    """Return (pct, formatted_str) where pct is a float or None when undefined.

    Rules:
    - if previous > 0: pct = (current - previous) / previous * 100
    - if previous == 0 and current == 0: pct = 0.0
    - if previous == 0 and current > 0: return a numeric value (show +100%)
    """
    try:
        if previous > 0:
            pct = round((current - previous) / previous * 100.0, 1)
            return pct, f"{pct:+}%"
        # previous == 0
        if current == 0:
            return 0.0, "+0%"
        # previous == 0 and current > 0 -> represent as +100% (numeric) rather than N/A
        pct = 100.0
        return pct, f"+{pct}%"
    except Exception:
        return 0.0, "+0%"



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
    subscribers_growth_data: List[Dict] = []

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
        # cumulative active subscribers at end of month
        subs_cum = (
            db.query(func.count(models.user.Subscriber.id))
            .filter(models.user.Subscriber.subscription_start_date < end, models.user.Subscriber.is_active == True)
            .scalar() or 0
        )
        subscribers_growth_data.append({"month": label, "value": int(subs_cum), "label": label})

    # Totals and latest comparisons
    # Total users (current)
    total_users = db.query(func.count(models.user.User.id)).scalar() or 0

    # New users in latest month vs previous (derive from cumulative counts)
    latest_cum = users_growth_data[-1]["value"] if len(users_growth_data) >= 1 else 0
    prev_cum = users_growth_data[-2]["value"] if len(users_growth_data) >= 2 else 0
    prevprev_cum = users_growth_data[-3]["value"] if len(users_growth_data) >= 3 else 0
    new_users_latest = latest_cum - prev_cum
    new_users_prev = prev_cum - prevprev_cum
    # compute growth on TOTAL users (cumulative) not on new users per month
    users_pct, users_pct_str = _percent_change(latest_cum, prev_cum)

    # Total jobs (current)
    total_jobs = db.query(func.count(models.user.Job.id)).scalar() or 0
    jobs_latest = jobs_data[-1]["value"] if len(jobs_data) >= 1 else 0
    jobs_prev = jobs_data[-2]["value"] if len(jobs_data) >= 2 else 0
    jobs_change = jobs_latest - jobs_prev
    jobs_pct, jobs_pct_str = _percent_change(jobs_latest, jobs_prev)

    # Active subscriptions (current)
    active_subs = db.query(func.count(models.user.Subscriber.id)).filter(models.user.Subscriber.is_active == True).scalar() or 0
    # For growth compare active subscribers at month-end (cumulative) latest vs previous
    sub_latest = subscribers_growth_data[-1]["value"] if subscribers_growth_data else 0
    sub_prev = subscribers_growth_data[-2]["value"] if len(subscribers_growth_data) >= 2 else 0
    sub_change = sub_latest - sub_prev
    sub_pct, sub_pct_str = _percent_change(sub_latest, sub_prev)

    # Revenue totals over period and growth
    revenue_values = [m["value"] for m in revenue_data]
    revenue_total = sum(revenue_values)
    revenue_latest = revenue_values[-1] if revenue_values else 0
    revenue_prev = revenue_values[-2] if len(revenue_values) >= 2 else 0
    revenue_change = revenue_latest - revenue_prev
    revenue_pct, revenue_pct_str = _percent_change(revenue_latest, revenue_prev)

    response = {
        "stats": {
            "totalUsers": {
                "count": int(total_users),
                "growth": users_pct_str if users_pct_str is not None else "+0%",
                "growthValue": users_pct if users_pct is not None else 0,
                "changeFromLastMonth": int(new_users_latest),
            },
            "totalJobs": {
                "count": int(total_jobs),
                "growth": jobs_pct_str if jobs_pct_str is not None else "+0%",
                "growthValue": jobs_pct if jobs_pct is not None else 0,
                "changeFromLastMonth": int(jobs_change),
            },
            "activeSubscriptions": {
                "count": int(active_subs),
                "growth": sub_pct_str if sub_pct_str is not None else "+0%",
                "growthValue": sub_pct if sub_pct is not None else 0,
                "changeFromLastMonth": int(sub_change),
            },
            "totalRevenue": {
                "amount": int(revenue_total),
                "formatted": f"${int(revenue_total):,}",
                "growth": revenue_pct_str if revenue_pct_str is not None else "+0%",
                "growthValue": revenue_pct if revenue_pct is not None else 0,
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
                "growthRate": users_pct if users_pct is not None else 0,
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
