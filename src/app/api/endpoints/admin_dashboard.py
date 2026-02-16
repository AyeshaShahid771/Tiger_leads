
import base64
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, Body, Query
import asyncio
from sqlalchemy import func, text
from sqlalchemy.orm import Session
import logging

from src.app import models
from src.app.api.deps import (
    require_admin_token,
    require_admin_or_editor,
    require_admin_only,
    require_viewer_or_editor,
)
from src.app.core.database import get_db

router = APIRouter(prefix="/admin/dashboard", tags=["Admin"])

logger = logging.getLogger("uvicorn.error")


@router.get(
    "/jobs/{job_id}",
    dependencies=[Depends(require_admin_token)],
    summary="Get Job Details (Admin)",
)
def get_job_details(job_id: int, db: Session = Depends(get_db)):
    """Admin endpoint: get job details by job id.

    Returns: permit_type, job_cost, job_address, email, phone_number, country_city, state, project_description.
    """
    job = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "permit_type": job.permit_type,
        "cost": job.job_cost,
        "address": job.job_address,
        "email": job.email,
        "phone_number": job.phone_number,
        "country_city": job.country_city,
        "state": job.state,
        "job_description": job.project_description,
    }


from pydantic import BaseModel
import uuid
from datetime import datetime, timedelta
from src.app.utils.email import send_admin_invitation_email


class DashboardFilter(BaseModel):
    state: str
    timeRange: str


class UserApprovalUpdate(BaseModel):
    user_id: int
    status: str  # "approved" or "rejected"


class SubscriptionEdit(BaseModel):
    name: str
    price: Optional[str] = None
    credits: Optional[int] = None
    max_seats: Optional[int] = None
    credit_price: Optional[str] = None
    seat_price: Optional[str] = None



class SubscriptionsUpdate(BaseModel):
    plans: List[SubscriptionEdit]


class AdminInvite(BaseModel):
    email: str
    name: Optional[str] = None
    role: str


class ContractorApprovalUpdate(BaseModel):
    status: str  # "approved" or "rejected"
    note: Optional[str] = None  # Optional admin note


def _periods_for_range(time_range: str):
    """Return (periods, bucket) where periods is list of (label,start,end).

    bucket: 'month' or 'day'
    """
    now = datetime.utcnow()
    # Normalize the time_range to lowercase and remove spaces
    time_range_normalized = time_range.lower().replace(" ", "")
    
    if time_range_normalized in ["last6months", "last6month"]:
        # reuse _month_starts
        return _month_starts(6), "month"
    if time_range_normalized in ["last3months", "last3month"]:
        return _month_starts(3), "month"
    if time_range_normalized in ["last12months", "last12month"]:
        return _month_starts(12), "month"
    if time_range_normalized in ["thisyear"]:
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
    if time_range_normalized in ["lastyear"]:
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
    if time_range_normalized in ["last30days", "last30day"]:
        periods = []
        for i in range(29, -1, -1):
            d = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            periods.append((d.strftime("%Y-%m-%d"), d, d + timedelta(days=1)))
        return periods, "day"
    if time_range_normalized in ["last90days", "last90day"]:
        periods = []
        for i in range(89, -1, -1):
            d = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
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

    # Check if "All States" is selected - if so, don't filter by state
    filter_by_state = state and state.lower() not in ["all", "all states"]

    # find user ids for contractors/suppliers who serve this state
    user_ids = set()
    if filter_by_state:
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
    else:
        # "All States" - get all users
        try:
            all_users_q = text("SELECT DISTINCT user_id FROM contractors UNION SELECT DISTINCT user_id FROM suppliers")
            for row in db.execute(all_users_q).fetchall():
                user_ids.add(row.user_id)
        except Exception:
            pass

    # fetch subscriber ids for these users (to filter payments)
    subscriber_ids = set()
    if user_ids:
        s_q = text("SELECT id FROM subscribers WHERE user_id = ANY(:uids)")
        # SQLAlchemy/text doesn't auto-adapt list; pass as tuple string
        for r in db.execute(s_q, {"uids": list(user_ids)}).fetchall():
            subscriber_ids.add(r.id)
    elif not filter_by_state:
        # "All States" and no user filter - get all subscribers
        try:
            all_subs_q = text("SELECT id FROM subscribers")
            for r in db.execute(all_subs_q).fetchall():
                subscriber_ids.add(r.id)
        except Exception:
            pass

    revenue_data = []
    jobs_data = []
    users_data = []

    for label, start, end in periods:
        # revenue
        if subscriber_ids and _table_exists(db, "payments"):
            q = text(
                "SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE payment_date >= :s AND payment_date < :e AND subscriber_id = ANY(:sids)"
            )
            res = db.execute(
                q, {"s": start, "e": end, "sids": list(subscriber_ids)}
            ).first()
            revenue = float(res.total) if res and res.total is not None else 0.0
        else:
            revenue = 0.0
        revenue_data.append({"month": label, "value": int(revenue), "label": label})

        # jobs: match job.state or uploaded_by_user_id in user_ids
        jobs_q = db.query(func.count(models.user.Job.id)).filter(
            models.user.Job.created_at >= start, models.user.Job.created_at < end
        )
        
        if filter_by_state:
            # Filter by specific state
            jobs_q = jobs_q.filter(
                (models.user.Job.state == state)
                | (
                    models.user.Job.uploaded_by_user_id.in_(list(user_ids))
                    if user_ids
                    else False
                )
            )
        # else: "All States" - no state filter, count all jobs
        
        jobs_count = jobs_q.scalar() or 0
        jobs_data.append({"month": label, "value": int(jobs_count), "label": label})

        # users cumulative at end
        if filter_by_state and user_ids:
            users_cum = (
                db.query(func.count(models.user.User.id))
                .filter(
                    models.user.User.created_at < end,
                    models.user.User.id.in_(list(user_ids)),
                )
                .scalar()
                or 0
            )
        elif not filter_by_state:
            # "All States" - count all users
            users_cum = (
                db.query(func.count(models.user.User.id))
                .filter(models.user.User.created_at < end)
                .scalar()
                or 0
            )
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
                "latest": {
                    "month": periods[-1][0],
                    "value": revenue_latest,
                    "formatted": f"${revenue_latest:,}",
                },
                "total": int(revenue_total),
                "currency": "USD",
            },
            "jobs": {
                "data": jobs_data,
                "peak": {
                    "month": (
                        max(jobs_data, key=lambda x: x["value"])["month"]
                        if jobs_data
                        else None
                    ),
                    "value": (
                        max(jobs_data, key=lambda x: x["value"])["value"]
                        if jobs_data
                        else 0
                    ),
                    "formatted": (
                        f"{max(jobs_data, key=lambda x: x['value'])['value']} Jobs"
                        if jobs_data
                        else "0 Jobs"
                    ),
                },
                "total": int(jobs_total),
                "averagePerMonth": (
                    round(sum(j["value"] for j in jobs_data) / len(jobs_data))
                    if jobs_data
                    else 0
                ),
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
    r = db.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name = :t LIMIT 1"),
        {"t": table_name},
    ).first()
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
    payments_table = _table_exists(db, "payments")

    for label, start, end in months:
        # revenue
        if payments_table:
            q = text(
                "SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE payment_date >= :s AND payment_date < :e"
            )
            res = db.execute(q, {"s": start, "e": end}).first()
            revenue = float(res.total) if res and res.total is not None else 0.0
        else:
            revenue = 0.0

        revenue_data.append({"month": label, "value": int(revenue), "label": label})

        # jobs count
        jobs_count = (
            db.query(func.count(models.user.Job.id))
            .filter(
                models.user.Job.created_at >= start, models.user.Job.created_at < end
            )
            .scalar()
            or 0
        )
        jobs_data.append({"month": label, "value": int(jobs_count), "label": label})

        # cumulative users at end of month
        users_cum = (
            db.query(func.count(models.user.User.id))
            .filter(models.user.User.created_at < end)
            .scalar()
            or 0
        )
        users_growth_data.append(
            {"month": label, "value": int(users_cum), "label": label}
        )
        # cumulative active subscribers at end of month
        subs_cum = (
            db.query(func.count(models.user.Subscriber.id))
            .filter(
                models.user.Subscriber.subscription_start_date < end,
                models.user.Subscriber.is_active == True,
            )
            .scalar()
            or 0
        )
        subscribers_growth_data.append(
            {"month": label, "value": int(subs_cum), "label": label}
        )

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

    # Total jobs (current) - use cumulative count for growth comparison
    total_jobs = db.query(func.count(models.user.Job.id)).scalar() or 0
    
    # Calculate cumulative jobs for proper growth comparison
    jobs_cum_data = []
    for i, (label, start, end) in enumerate(months):
        jobs_cum = (
            db.query(func.count(models.user.Job.id))
            .filter(models.user.Job.created_at < end)
            .scalar()
            or 0
        )
        jobs_cum_data.append(jobs_cum)
    
    jobs_cum_latest = jobs_cum_data[-1] if jobs_cum_data else 0
    jobs_cum_prev = jobs_cum_data[-2] if len(jobs_cum_data) >= 2 else 0
    jobs_change = jobs_cum_latest - jobs_cum_prev
    jobs_pct, jobs_pct_str = _percent_change(jobs_cum_latest, jobs_cum_prev)

    # Active subscriptions (current)
    active_subs = (
        db.query(func.count(models.user.Subscriber.id))
        .filter(models.user.Subscriber.is_active == True)
        .scalar()
        or 0
    )
    # For growth compare active subscribers at month-end (cumulative) latest vs previous
    sub_latest = subscribers_growth_data[-1]["value"] if subscribers_growth_data else 0
    sub_prev = (
        subscribers_growth_data[-2]["value"] if len(subscribers_growth_data) >= 2 else 0
    )
    sub_change = sub_latest - sub_prev
    sub_pct, sub_pct_str = _percent_change(sub_latest, sub_prev)

    # Revenue totals over period and growth - use cumulative revenue
    revenue_values = [m["value"] for m in revenue_data]
    revenue_total = sum(revenue_values)
    
    # Calculate cumulative revenue for proper growth comparison
    revenue_cum_data = []
    cumulative = 0
    for val in revenue_values:
        cumulative += val
        revenue_cum_data.append(cumulative)
    
    revenue_cum_latest = revenue_cum_data[-1] if revenue_cum_data else 0
    revenue_cum_prev = revenue_cum_data[-2] if len(revenue_cum_data) >= 2 else 0
    revenue_change = revenue_cum_latest - revenue_cum_prev
    revenue_pct, revenue_pct_str = _percent_change(revenue_cum_latest, revenue_cum_prev)
    
    # For latest month display
    revenue_latest = revenue_values[-1] if revenue_values else 0

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
                "latest": {
                    "month": months[-1][0],
                    "value": revenue_latest,
                    "formatted": f"${revenue_latest:,}",
                },
                "total": int(revenue_total),
                "currency": "USD",
            },
            "jobs": {
                "data": jobs_data,
                "peak": {
                    "month": (
                        max(jobs_data, key=lambda x: x["value"])["month"]
                        if jobs_data
                        else None
                    ),
                    "value": (
                        max(jobs_data, key=lambda x: x["value"])["value"]
                        if jobs_data
                        else 0
                    ),
                    "formatted": (
                        f"{max(jobs_data, key=lambda x: x['value'])['value']} Jobs"
                        if jobs_data
                        else "0 Jobs"
                    ),
                },
                "total": sum(j["value"] for j in jobs_data),
                "averagePerMonth": (
                    round(sum(j["value"] for j in jobs_data) / len(jobs_data))
                    if jobs_data
                    else 0
                ),
            },
            "userGrowth": {
                "data": users_growth_data,
                "current": users_growth_data[-1]["value"] if users_growth_data else 0,
                "formatted": (
                    f"{users_growth_data[-1]['value']:,} Users"
                    if users_growth_data
                    else "0 Users"
                ),
                "growthRate": users_pct if users_pct is not None else 0,
            },
        },
        "filters": {
            "timeRange": "last6Months",
            "state": "allStates",
            "appliedFilters": {
                "dateFrom": months[0][1].strftime("%Y-%m-%d"),
                "dateTo": (months[-1][2] - timedelta(seconds=1)).strftime("%Y-%m-%d"),
            },
        },
        "metadata": {
            "lastUpdated": datetime.utcnow().isoformat() + "Z",
            "timezone": "UTC",
            "dataSource": "primary_db",
            "cacheKey": "dashboard_6m_all_states",
        },
    }

    return response


@router.get("/contractors-summary", dependencies=[Depends(require_admin_token)])
def contractors_summary(db: Session = Depends(get_db)):
    """Admin endpoint: return list of approved contractors with basic contact and trade info.

    Returns only approved contractors (approved_by_admin = 'approved').
    Returns entries with: phone_number, email, company, license_number, user_type
    """
    # join contractors -> users to get email and active flag, filter approved only
    rows = (
        db.query(models.user.Contractor, models.user.User.email, models.user.User.is_active)
        .join(models.user.User, models.user.User.id == models.user.Contractor.user_id)
        .filter(models.user.User.approved_by_admin == "approved")
        .all()
    )

    result = []
    for contractor, email, is_active in rows:
        action = "disable" if is_active else "enable"
        result.append(
            {
                "id": contractor.id,
                "phone_number": contractor.phone_number,
                "email": email,
                "company": contractor.company_name,
                "license_number": contractor.state_license_number,
                "user_type": contractor.user_type,
                "action": action,
            }
        )

    return {"contractors": result}


@router.get("/contractors-pending", dependencies=[Depends(require_admin_token)])
def contractors_pending(db: Session = Depends(get_db)):
    """Admin endpoint: return list of contractors pending admin approval.

    Returns only contractors where approved_by_admin = 'pending'.
    Returns entries with: phone_number, email, company, license_number, user_type, created_at
    """
    # join contractors -> users to get email and approval status
    rows = (
        db.query(
            models.user.Contractor, 
            models.user.User.email, 
            models.user.User.is_active,
            models.user.User.approved_by_admin,
            models.user.User.created_at
        )
        .join(models.user.User, models.user.User.id == models.user.Contractor.user_id)
        .filter(models.user.User.approved_by_admin == "pending")
        .all()
    )

    result = []
    for contractor, email, is_active, approved_status, created_at in rows:
        action = "disable" if is_active else "enable"
        result.append(
            {
                "id": contractor.id,
                "phone_number": contractor.phone_number,
                "email": email,
                "company": contractor.company_name,
                "license_number": contractor.state_license_number,
                "user_type": contractor.user_type,
                "action": action,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )

    return {"contractors": result}


@router.get("/contractors/search", dependencies=[Depends(require_admin_token)])
def search_contractors(q: str, db: Session = Depends(get_db)):
    """Admin endpoint: search contractors across all columns.

    Query param: `q` - search string to match against any contractor field.
    Returns matching contractors with full details.
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=400, detail="Search query must be at least 2 characters"
        )

    search_term = f"%{q.lower()}%"

    # Build comprehensive search query across all text columns
    # Using raw SQL for flexible ILIKE search across all columns
    query = text("""
        SELECT 
            c.id,
            c.company_name,
            c.primary_contact_name,
            c.phone_number,
            c.state_license_number,
            c.user_type,
            u.email,
            u.is_active
        FROM contractors c
        JOIN users u ON u.id = c.user_id
        WHERE 
            LOWER(COALESCE(c.company_name, '')) LIKE :search
            OR LOWER(COALESCE(c.primary_contact_name, '')) LIKE :search
            OR LOWER(COALESCE(c.phone_number, '')) LIKE :search
            OR LOWER(COALESCE(c.website_url, '')) LIKE :search
            OR LOWER(COALESCE(c.business_address, '')) LIKE :search
            OR LOWER(COALESCE(c.business_website_url, '')) LIKE :search
            OR EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(COALESCE(c.state_license_number::jsonb, '[]'::jsonb)) AS license
                WHERE LOWER(license) LIKE :search
            )
            OR EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(COALESCE(c.license_status::jsonb, '[]'::jsonb)) AS status
                WHERE LOWER(status) LIKE :search
            )
            OR LOWER(COALESCE(u.email, '')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(c.user_type, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(c.state, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(c.country_city, ',')) LIKE :search
        AND u.approved_by_admin = 'approved'
        ORDER BY c.id DESC
        LIMIT 100
    """)

    rows = db.execute(query, {"search": search_term}).fetchall()

    result = []
    for row in rows:
        action = "disable" if row.is_active else "enable"
        result.append(
            {
                "id": row.id,
                "phone_number": row.phone_number,
                "email": row.email,
                "company": row.company_name,
                "license_number": row.state_license_number,
                "user_type": row.user_type,
                "action": action,
            }
        )

    return {"contractors": result}


@router.get("/contractors/search-pending", dependencies=[Depends(require_admin_token)])
def search_contractors_pending(q: str, db: Session = Depends(get_db)):
    """Admin endpoint: search pending contractors across all columns.

    Query param: `q` - search string to match against any contractor field.
    Returns only contractors with approved_by_admin = 'pending'.
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=400, detail="Search query must be at least 2 characters"
        )

    search_term = f"%{q.lower()}%"

    # Build comprehensive search query across all text columns
    # Using raw SQL for flexible ILIKE search across all columns
    query = text("""
        SELECT 
            c.id,
            c.company_name,
            c.primary_contact_name,
            c.phone_number,
            c.state_license_number,
            c.user_type,
            u.email,
            u.is_active,
            u.created_at
        FROM contractors c
        JOIN users u ON u.id = c.user_id
        WHERE 
            LOWER(COALESCE(c.company_name, '')) LIKE :search
            OR LOWER(COALESCE(c.primary_contact_name, '')) LIKE :search
            OR LOWER(COALESCE(c.phone_number, '')) LIKE :search
            OR LOWER(COALESCE(c.website_url, '')) LIKE :search
            OR LOWER(COALESCE(c.business_address, '')) LIKE :search
            OR LOWER(COALESCE(c.business_website_url, '')) LIKE :search
            OR EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(COALESCE(c.state_license_number::jsonb, '[]'::jsonb)) AS license
                WHERE LOWER(license) LIKE :search
            )
            OR EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(COALESCE(c.license_status::jsonb, '[]'::jsonb)) AS status
                WHERE LOWER(status) LIKE :search
            )
            OR LOWER(COALESCE(u.email, '')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(c.user_type, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(c.state, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(c.country_city, ',')) LIKE :search
        AND u.approved_by_admin = 'pending'
        ORDER BY c.id DESC
        LIMIT 100
    """)

    rows = db.execute(query, {"search": search_term}).fetchall()

    result = []
    for row in rows:
        action = "disable" if row.is_active else "enable"
        result.append(
            {
                "id": row.id,
                "phone_number": row.phone_number,
                "email": row.email,
                "company": row.company_name,
                "license_number": row.state_license_number,
                "user_type": row.user_type,
                "action": action,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    return {"contractors": result}

    
@router.get(
    "/ingested-jobs",
    dependencies=[Depends(require_admin_token)],
    summary="Job Posted Requested",
)
def ingested_jobs(db: Session = Depends(get_db)):
    """Admin endpoint: list contractor-uploaded jobs requested for posting.

    Returns entries with: id, permit_type, permit_value, job_review_status,
    address_code, job_address. Jobs where `job_review_status` is `pending` or
    `declined` and `uploaded_by_contractor == True` are returned.
    """
    rows = (
        db.query(models.user.Job)
        .filter(
            models.user.Job.uploaded_by_contractor == True,
            models.user.Job.job_review_status.in_(["pending", "declined"]),
        )
        .all()
    )

    result = []
    for j in rows:
        result.append(
            {
                "id": j.id,
                "permit_type": j.permit_type,
                "permit_value": j.job_cost,
                "job_review_status": j.job_review_status,
                "address_code": j.permit_number,  # Fixed: was permit_record_number
                "job_address": j.job_address,
                "uploaded_by_user_id": j.uploaded_by_user_id,
                "created_at": (j.created_at.isoformat() if getattr(j, "created_at", None) else None),
            }
        )

    return {"ingested_jobs": result}


@router.patch(
    "/ingested-jobs/{job_id}/post",
    dependencies=[Depends(require_admin_or_editor)],
)
def post_ingested_job(job_id: int, db: Session = Depends(get_db)):
    """Admin-only: approve an ingested job for posting.

    Sets `uploaded_by_contractor = False` and `review_posted_at = now()` in EST.
    Status remains 'pending' until scheduler script posts it based on offset_days.
    """
    j = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get current time in EST, store in EST
    est_tz = ZoneInfo("America/New_York")
    now_est = datetime.now(est_tz).replace(tzinfo=None)
    
    j.uploaded_by_contractor = False
    j.review_posted_at = now_est
    # Keep job_review_status as 'pending' - script will change to 'posted' based on offset
    db.add(j)
    db.commit()

    return {
        "job_id": j.id, 
        "job_review_status": j.job_review_status,
        "uploaded_by_contractor": j.uploaded_by_contractor,
        "review_posted_at": now_est.isoformat(),
        "message": "Job approved. Will be posted according to offset_days schedule."
    }


@router.patch(
    "/ingested-jobs/{job_id}/decline",
    dependencies=[Depends(require_admin_or_editor)],
)
def decline_ingested_job(job_id: int, db: Session = Depends(get_db)):
    """Admin/Editor: mark an ingested job as declined.

    Sets `job_review_status` to `declined` for the given job id.
    """
    j = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    j.job_review_status = "declined"
    db.add(j)
    db.commit()

    return {"job_id": j.id, "job_review_status": j.job_review_status, "message": "Job marked as declined."}


@router.get(
    "/ingested-jobs/system",
    dependencies=[Depends(require_admin_token)],
    summary="System-ingested Jobs",
)
def system_ingested_jobs(db: Session = Depends(get_db)):
    """Admin/Editor endpoint: list jobs NOT uploaded by contractors.

    Returns all fields from system-ingested jobs (uploaded via /jobs/upload-leads-json).
    """
    rows = (
        db.query(models.user.Job)
        .filter(models.user.Job.uploaded_by_contractor == False)
        .order_by(models.user.Job.created_at.desc())
        .all()
    )

    result = []
    for j in rows:
        result.append(
            {
                # Basic job info
                "id": j.id,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "updated_at": j.updated_at.isoformat() if j.updated_at else None,
                
                # Queue and routing info
                "queue_id": j.queue_id,
                "rule_id": j.rule_id,
                "recipient_group": j.recipient_group,
                "recipient_group_id": j.recipient_group_id,
                "day_offset": j.day_offset,
                "anchor_event": j.anchor_event,
                "anchor_at": j.anchor_at.isoformat() if j.anchor_at else None,
                "due_at": j.due_at.isoformat() if j.due_at else None,
                "routing_anchor_at": j.routing_anchor_at.isoformat() if j.routing_anchor_at else None,
                
                # Permit info
                "permit_id": j.permit_id,
                "permit_number": j.permit_number,
                "permit_status": j.permit_status,
                "permit_type_norm": j.audience_type_names,  # Use audience_type_names for human-readable format
                "permit_raw": j.permit_raw,
                
                # Project info
                "project_number": j.project_number,
                "project_description": j.project_description,
                "project_type": j.project_type,
                "project_sub_type": j.project_sub_type,
                "project_status": j.project_status,
                "project_cost_total": j.project_cost_total,
                "project_cost": j.project_cost,
                "project_cost_source": j.project_cost_source,
                "property_type": j.property_type,
                
                # Address info
                "job_address": j.job_address,
                "project_address": j.project_address,
                "state": j.state,
                
                # Source info
                "source_county": j.source_county,
                "source_system": j.source_system,
                "first_seen_at": j.first_seen_at.isoformat() if j.first_seen_at else None,
                "last_seen_at": j.last_seen_at.isoformat() if j.last_seen_at else None,
                
                # Contractor info
                "contractor_name": j.contractor_name,
                "contractor_company": j.contractor_company,
                "contractor_email": j.contractor_email,
                "contractor_phone": j.contractor_phone,
                "contractor_company_and_address": j.contractor_company_and_address,
                
                # Owner/Applicant info
                "owner_name": j.owner_name,
                "applicant_name": j.applicant_name,
                "applicant_email": j.applicant_email,
                "applicant_phone": j.applicant_phone,
                
                # Audience info
                "audience_type_slugs": j.audience_type_slugs,
                "audience_type_names": j.audience_type_names,
                
                # Additional info
                "querystring": j.querystring,
                "trs_score": j.trs_score,
                "uploaded_by_contractor": j.uploaded_by_contractor,
                "uploaded_by_user_id": j.uploaded_by_user_id,
                "job_review_status": j.job_review_status,
                "review_posted_at": j.review_posted_at.isoformat() if j.review_posted_at else None,
                "job_group_id": j.job_group_id,
                "job_documents": j.job_documents,
                "contact_name": j.contact_name,
            }
        )

    return {"system_ingested_jobs": result}


@router.delete(
    "/ingested-jobs/{job_id}",
    dependencies=[Depends(require_admin_or_editor)],
)
def delete_ingested_job(job_id: int, db: Session = Depends(get_db)):
    """Admin-only: permanently delete an ingested job by id."""
    j = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    db.delete(j)
    db.commit()

    return {"job_id": job_id, "deleted": True, "message": "Job deleted."}


@router.patch("/subscriptions", dependencies=[Depends(require_admin_or_editor)])
def update_subscriptions(
    payload: SubscriptionsUpdate = Body(
        ...,
        example={
            "plans": [
                {"name": "Starter", "price": "9.99", "credits": 10, "max_seats": 1},
                {"name": "Professional", "price": "29.99", "credits": 50, "max_seats": 3},
                {"name": "Enterprise", "price": "99.99", "credits": 200, "max_seats": 10},
                {"name": "Custom", "credit_price": "0.10", "seat_price": "9.99"},
            ]
        },
    ),
    db: Session = Depends(get_db),
):
    """Admin endpoint: update subscription plan fields in bulk.

    Accepts JSON `{ "plans": [ {"name":"Starter", "price":"9.99", "credits":10, "max_seats":1}, ... ] }`.
    For `Custom` plan, pass `credit_price` and/or `seat_price` to update those fields.
    """
    updated = []
    for p in payload.plans:
        sub = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.name == p.name)
            .first()
        )
        if not sub:
            # skip unknown plan names
            continue
        if p.price is not None:
            sub.price = p.price
        if p.credits is not None:
            sub.credits = p.credits
        if p.max_seats is not None:
            sub.max_seats = p.max_seats
        if p.credit_price is not None:
            sub.credit_price = p.credit_price
        if p.seat_price is not None:
            sub.seat_price = p.seat_price
        db.add(sub)
        updated.append(
            {
                "name": sub.name,
                "price": sub.price,
                "credits": sub.credits,
                "max_seats": sub.max_seats,
                "credit_price": getattr(sub, "credit_price", None),
                "seat_price": getattr(sub, "seat_price", None),
            }
        )

    db.commit()
    return {"updated": updated}


@router.get("/suppliers-summary", dependencies=[Depends(require_admin_token)])
def suppliers_summary(db: Session = Depends(get_db)):
    """Admin endpoint: return list of approved suppliers with basic contact and trade info.

    Returns only approved suppliers (approved_by_admin = 'approved').
    Returns entries with: phone_number, email, company, license_number, service_states, user_type, action
    """
    # join suppliers -> users to get email and active flag, filter approved only
    rows = (
        db.query(models.user.Supplier, models.user.User.email, models.user.User.is_active)
        .join(models.user.User, models.user.User.id == models.user.Supplier.user_id)
        .filter(models.user.User.approved_by_admin == "approved")
        .all()
    )

    result = []
    for supplier, email, is_active in rows:
        action = "disable" if is_active else "enable"
        result.append(
            {
                "id": supplier.id,
                "phone_number": supplier.phone_number,
                "email": email,
                "company": supplier.company_name,
                "license_number": supplier.state_license_number,
                "service_states": supplier.service_states,
                "user_type": supplier.user_type,
                "action": action,
            }
        )

    return {"suppliers": result}


@router.get("/suppliers-pending", dependencies=[Depends(require_admin_token)])
def suppliers_pending(db: Session = Depends(get_db)):
    """Admin endpoint: return list of suppliers pending admin approval.

    Returns only suppliers where approved_by_admin = 'pending'.
    Returns entries with: phone_number, email, company, license_number, service_states, user_type, created_at
    """
    # join suppliers -> users to get email and approval status
    rows = (
        db.query(
            models.user.Supplier, 
            models.user.User.email, 
            models.user.User.is_active,
            models.user.User.approved_by_admin,
            models.user.User.created_at
        )
        .join(models.user.User, models.user.User.id == models.user.Supplier.user_id)
        .filter(models.user.User.approved_by_admin == "pending")
        .all()
    )

    result = []
    for supplier, email, is_active, approved_status, created_at in rows:
        action = "disable" if is_active else "enable"
        result.append(
            {
                "id": supplier.id,
                "phone_number": supplier.phone_number,
                "email": email,
                "company": supplier.company_name,
                "license_number": supplier.state_license_number,
                "service_states": supplier.service_states,
                "user_type": supplier.user_type,
                "action": action,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )

    return {"suppliers": result}


@router.get("/suppliers/search", dependencies=[Depends(require_admin_token)])
def search_suppliers(q: str, db: Session = Depends(get_db)):
    """Admin endpoint: search suppliers across all columns.

    Query param: `q` - search string to match against any supplier field.
    Returns matching suppliers with basic info matching suppliers-summary format.
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=400, detail="Search query must be at least 2 characters"
        )

    search_term = f"%{q.lower()}%"

    # Build comprehensive search query across all text columns
    query = text("""
        SELECT 
            s.id,
            s.company_name,
            s.primary_contact_name,
            s.phone_number,
            s.state_license_number,
            s.service_states,
            s.user_type,
            u.email,
            u.is_active
        FROM suppliers s
        JOIN users u ON u.id = s.user_id
        WHERE 
            LOWER(COALESCE(s.company_name, '')) LIKE :search
            OR LOWER(COALESCE(s.primary_contact_name, '')) LIKE :search
            OR LOWER(COALESCE(s.phone_number, '')) LIKE :search
            OR LOWER(COALESCE(s.website_url, '')) LIKE :search
            OR LOWER(COALESCE(s.state_license_number, '')) LIKE :search
            OR LOWER(COALESCE(s.business_address, '')) LIKE :search
            OR LOWER(COALESCE(u.email, '')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(s.service_states, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(s.country_city, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(s.user_type, ',')) LIKE :search
        AND u.approved_by_admin = 'approved'
        ORDER BY s.id DESC
        LIMIT 100
    """)

    rows = db.execute(query, {"search": search_term}).fetchall()

    result = []
    for row in rows:
        action = "disable" if row.is_active else "enable"
        result.append(
            {
                "id": row.id,
                "phone_number": row.phone_number,
                "email": row.email,
                "company": row.company_name,
                "license_number": row.state_license_number,
                "service_states": row.service_states,
                "user_type": row.user_type,
                "action": action,
            }
        )

    return {"suppliers": result}


@router.get("/suppliers/search-pending", dependencies=[Depends(require_admin_token)])
def search_suppliers_pending(q: str, db: Session = Depends(get_db)):
    """Admin endpoint: search pending suppliers across all columns.

    Query param: `q` - search string to match against any supplier field.
    Returns only suppliers with approved_by_admin = 'pending'.
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=400, detail="Search query must be at least 2 characters"
        )

    search_term = f"%{q.lower()}%"

    # Build comprehensive search query across all text columns
    query = text("""
        SELECT 
            s.id,
            s.company_name,
            s.primary_contact_name,
            s.phone_number,
            s.state_license_number,
            s.service_states,
            s.user_type,
            u.email,
            u.is_active,
            u.created_at
        FROM suppliers s
        JOIN users u ON u.id = s.user_id
        WHERE 
            LOWER(COALESCE(s.company_name, '')) LIKE :search
            OR LOWER(COALESCE(s.primary_contact_name, '')) LIKE :search
            OR LOWER(COALESCE(s.phone_number, '')) LIKE :search
            OR LOWER(COALESCE(s.website_url, '')) LIKE :search
            OR EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(COALESCE(s.state_license_number::jsonb, '[]'::jsonb)) AS license
                WHERE LOWER(license) LIKE :search
            )
            OR LOWER(COALESCE(s.business_address, '')) LIKE :search
            OR LOWER(COALESCE(u.email, '')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(s.service_states, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(s.country_city, ',')) LIKE :search
            OR LOWER(ARRAY_TO_STRING(s.user_type, ',')) LIKE :search
        AND u.approved_by_admin = 'pending'
        ORDER BY s.id DESC
        LIMIT 100
    """)

    rows = db.execute(query, {"search": search_term}).fetchall()

    result = []
    for row in rows:
        action = "disable" if row.is_active else "enable"
        result.append(
            {
                "id": row.id,
                "phone_number": row.phone_number,
                "email": row.email,
                "company": row.company_name,
                "license_number": row.state_license_number,
                "service_states": row.service_states,
                "user_type": row.user_type,
                "action": action,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    return {"suppliers": result}





@router.get(
    "/admin-users/recipients",
    dependencies=[Depends(require_admin_or_editor)],
)
def admin_users_recipients(db: Session = Depends(get_db)):
    """Return non-admin admin_users suitable for sending invites/notifications.

    Each entry contains: id, name, email, role, status
    - status is 'active' when is_active is true
    - status is 'invited' when is_active is false
    """
    q = text(
        "SELECT id, COALESCE(name, '') AS name, email, role, is_active FROM admin_users "
        "WHERE LOWER(COALESCE(role, '')) != 'admin' ORDER BY id"
    )
    rows = db.execute(q).fetchall()

    recipients = []
    for r in rows:
        mapping = getattr(r, "_mapping", None)
        if mapping is None:
            try:
                rid = r[0]
                name = r[1]
                email = r[2]
                role = r[3]
                is_active = r[4]
            except Exception:
                continue
        else:
            rid = mapping.get("id")
            name = mapping.get("name")
            email = mapping.get("email")
            role = mapping.get("role")
            is_active = mapping.get("is_active")

        status = "active" if is_active else "invited"
        recipients.append({"id": rid, "name": name, "email": email, "role": role, "status": status})

    return {"recipients": recipients}


@router.get(
    "/admin-users/by-role",
    dependencies=[Depends(require_admin_or_editor)],
)
def admin_users_by_role(role: str, db: Session = Depends(get_db)):
    """Return admin users matching the given `role` (excluding 'admin').

    Query param: `role` (string). Returns same shape as `admin_users_list`.
    """
    if not role:
        raise HTTPException(status_code=400, detail="Missing role parameter")
    if role.lower() == "admin":
        # Explicitly disallow listing real admin role via this filtered endpoint
        raise HTTPException(status_code=400, detail="Filtering for role 'admin' is not allowed")

    q = text(
        "SELECT id, COALESCE(name, '') AS name, email, role, is_active FROM admin_users "
        "WHERE lower(role) = lower(:role) AND LOWER(COALESCE(role, '')) != 'admin' ORDER BY id"
    )
    rows = db.execute(q, {"role": role}).fetchall()

    result = []
    for r in rows:
        mapping = getattr(r, "_mapping", None)
        if mapping is None:
            try:
                rid = r[0]
                name = r[1]
                email = r[2]
                role_val = r[3]
                is_active = r[4]
            except Exception:
                continue
        else:
            rid = mapping.get("id")
            name = mapping.get("name")
            email = mapping.get("email")
            role_val = mapping.get("role")
            is_active = mapping.get("is_active")
        status = "active" if is_active else "inactive"
        result.append({"id": rid, "name": name, "email": email, "role": role_val, "status": status})

    return {"admin_users": result}


@router.get(
    "/admin-users/search",
    dependencies=[Depends(require_admin_or_editor)],
)
def admin_users_search(q: str, db: Session = Depends(get_db)):
    """Search admin_users by name or email (case-insensitive), excluding role 'admin'.

    Query param: `q` - substring to match against name/email (case-insensitive).
    Returns list of {id, name, email, role, status} where status is 'active'|'inactive'.
    """
    if not q:
        raise HTTPException(status_code=400, detail="Missing query parameter 'q'")

    like = f"%{q.lower()}%"
    # Use raw SQL for compatibility with optional columns
    q_text = text(
        "SELECT id, COALESCE(name, '') AS name, email, role, is_active FROM admin_users "
        "WHERE LOWER(COALESCE(role, '')) != 'admin' AND (LOWER(COALESCE(name, '')) LIKE :like OR LOWER(COALESCE(email, '')) LIKE :like) ORDER BY id"
    )
    rows = db.execute(q_text, {"like": like}).fetchall()

    result = []
    for r in rows:
        mapping = getattr(r, "_mapping", None)
        if mapping is None:
            try:
                rid = r[0]
                name = r[1]
                email = r[2]
                role_val = r[3]
                is_active = r[4]
            except Exception:
                continue
        else:
            rid = mapping.get("id")
            name = mapping.get("name")
            email = mapping.get("email")
            role_val = mapping.get("role")
            is_active = mapping.get("is_active")
        status = "active" if is_active else "inactive"
        result.append({"id": rid, "name": name, "email": email, "role": role_val, "status": status})

    return {"admin_users": result}


@router.patch(
    "/admin-users/{admin_id}/role",
    dependencies=[Depends(require_admin_or_editor)],
)
def update_admin_user_role(
    admin_id: int,
    role: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Update the role of an admin_user.

    Only callers with role 'admin' or 'editor' may perform this action.
    
    Request body: { "role": "editor" }
    """
    if not role or not role.strip():
        raise HTTPException(status_code=400, detail="Role cannot be empty")

    # Verify admin_user exists
    q = text("SELECT id, role FROM admin_users WHERE id = :id")
    row = db.execute(q, {"id": admin_id}).first()
    if not row:
        raise HTTPException(status_code=404, detail="Admin user not found")

    # Update the role
    try:
        update_q = text("UPDATE admin_users SET role = :role WHERE id = :id")
        db.execute(update_q, {"role": role.strip(), "id": admin_id})
        db.commit()
    except Exception as e:
        logger.exception("Failed to update admin user role: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to update admin user role: {e}"
        )

    return {
        "admin_id": admin_id,
        "role": role.strip(),
        "message": f"Admin user role updated to '{role.strip()}'",
    }


@router.delete(
    "/admin-users/{admin_id}",
    dependencies=[Depends(require_admin_only)],
)
def delete_admin_user(admin_id: int, db: Session = Depends(get_db)):
    """Admin-only: delete an admin_user by id.

    Only callers with role 'admin' may perform this action. Returns 404 if the
    admin_user id does not exist.
    """
    # Verify existence
    q = text("SELECT id FROM admin_users WHERE id = :id")
    row = db.execute(q, {"id": admin_id}).first()
    if not row:
        raise HTTPException(status_code=404, detail="Admin user not found")

    # Perform delete
    try:
        db.execute(text("DELETE FROM admin_users WHERE id = :id"), {"id": admin_id})
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete admin user: {e}")

    return {"admin_id": admin_id, "deleted": True, "message": "Admin user deleted."}


@router.post(
    "/admin-users/invite",
    summary="Invite Admin User",
)
async def invite_admin_user(
    payload: AdminInvite,
    db: Session = Depends(get_db),
    inviter: object = Depends(require_admin_or_editor),
):
    """Invite a new admin user. Only callers with role 'admin' or 'editor'.

    Stores a pending admin_users row (is_active=false) and sends an email invite
    with a signup link to `https://tigerleads.vercel.app/admin/signup?invite_token=...`.
    """
    # Generate invitation token and expiry
    # Trim token to fit existing DB column (VARCHAR(10)) to avoid insertion errors
    raw_token = uuid.uuid4().hex
    token = raw_token[:10]
    expires = datetime.utcnow() + timedelta(days=7)

    logger.info("Admin invite requested: email=%s role=%s by_inviter=%s", payload.email, payload.role, getattr(inviter, "email", None))
    # Insert into admin_users (idempotent: skip if email exists)
    try:
        existing = db.execute(
            text("SELECT id FROM admin_users WHERE lower(email)=lower(:email)"),
            {"email": payload.email},
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Admin user with this email already exists")

        insert_q = text(
            "INSERT INTO admin_users (email, name, role, is_active, verification_code, code_expires_at, created_by, created_at) "
            "VALUES (:email, :name, :role, :is_active, :code, :expires, :created_by, :created_at)"
        )
        # Resolve `created_by` to a users.id if possible (admin.inviter may be an admin_users id)
        inviter_email = getattr(inviter, "email", None)
        created_by_user_id = None
        if inviter_email:
            row = db.execute(
                text("SELECT id FROM users WHERE lower(email)=lower(:email)"),
                {"email": inviter_email},
            ).first()
            if row:
                created_by_user_id = row.id
        logger.debug("Resolved created_by_user_id=%s for inviter_email=%s", created_by_user_id, inviter_email)

        params = {
            "email": payload.email,
            "name": payload.name,
            "role": payload.role,
            "is_active": False,
            "code": token,
            "expires": expires,
            "created_by": created_by_user_id,
            "created_at": datetime.utcnow(),
        }
        logger.debug("Inserting admin_users row with params: %s", params)
        db.execute(insert_q, params)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create admin invite for email=%s; params=%s", payload.email, {
            "email": payload.email,
            "name": payload.name,
            "role": payload.role,
            "created_by": created_by_user_id,
        })
        raise HTTPException(status_code=500, detail=f"Failed to create admin invite: {e}")

    # Schedule sending the invitation email (fire-and-forget)
    signup_url = "https://tigerleads.vercel.app/admin/signup"
    inviter_name = getattr(inviter, "email", "Administrator")
    try:
        asyncio.create_task(
            send_admin_invitation_email(
                payload.email, inviter_name, payload.role, signup_url, token
            )
        )
    except Exception:
        # If task scheduling fails, don't block invite creation; log and continue
        pass

    return {"email": payload.email, "invited": True}


@router.get("/contractors/{contractor_id}", dependencies=[Depends(require_admin_token)])
def contractor_detail(
    contractor_id: int, db: Session = Depends(get_db)
):
    """Admin endpoint: return full contractor profile with file metadata.

    Returns file metadata with URLs to fetch actual files via the image endpoint.
    Use GET /contractors/{id}/image/{field}?file_index=0 to get actual files.
    """
    c = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.id == contractor_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found")

    user = db.query(models.user.User).filter(models.user.User.id == c.user_id).first()

    def as_json_metadata(json_array, field_name):
        """Return metadata for JSON file array with URLs to fetch actual files"""
        if not json_array or not isinstance(json_array, list):
            return []
        
        result = []
        for idx, file_obj in enumerate(json_array):
            result.append({
                "filename": file_obj.get("filename"),
                "content_type": file_obj.get("content_type"),
                "file_index": idx,
                "url": f"/admin/dashboard/contractors/{contractor_id}/image/{field_name}?file_index={idx}",
            })
        return result

    # Always return metadata only (use separate image endpoint to get actual files)
    license_val = as_json_metadata(c.license_picture, "license_picture")
    referrals_val = as_json_metadata(c.referrals, "referrals")
    job_photos_val = as_json_metadata(c.job_photos, "job_photos")

    return {
        "id": c.id,
        "name": c.primary_contact_name,
        "company_name": c.company_name,
        "phone_number": c.phone_number,
        "business_address": c.business_address,
        "business_website_url": c.business_website_url,
        "state_license_number": c.state_license_number,  # JSON array
        "license_expiration_date": c.license_expiration_date,  # JSON array
        "license_status": c.license_status,  # JSON array
        "license_picture": license_val,
        "referrals": referrals_val,
        "job_photos": job_photos_val,
        "user_type": c.user_type,
        "country_city": c.country_city,
        "state": c.state,
        "created_at": (
            c.created_at.isoformat() if getattr(c, "created_at", None) else None
        ),
    }


@router.get("/suppliers/{supplier_id}", dependencies=[Depends(require_admin_token)])
def supplier_detail(supplier_id: int, db: Session = Depends(get_db)):
    """Admin endpoint: return full supplier profile with file metadata.

    Returns file metadata with URLs to fetch actual files via the image endpoint.
    Use GET /suppliers/{id}/image/{field}?file_index=0 to get actual files.
    """
    s = (
        db.query(models.user.Supplier)
        .filter(models.user.Supplier.id == supplier_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")

    user = db.query(models.user.User).filter(models.user.User.id == s.user_id).first()

    def as_json_metadata(json_array, field_name):
        """Return metadata for JSON file array with URLs to fetch actual files"""
        if not json_array or not isinstance(json_array, list):
            return []
        
        result = []
        for idx, file_obj in enumerate(json_array):
            result.append({
                "filename": file_obj.get("filename"),
                "content_type": file_obj.get("content_type"),
                "file_index": idx,
                "url": f"/admin/dashboard/suppliers/{supplier_id}/image/{field_name}?file_index={idx}",
            })
        return result

    # Get file metadata
    license_val = as_json_metadata(s.license_picture, "license_picture")
    referrals_val = as_json_metadata(s.referrals, "referrals")
    job_photos_val = as_json_metadata(s.job_photos, "job_photos")

    return {
        "id": s.id,
        "name": s.primary_contact_name,
        "company_name": s.company_name,
        "phone_number": s.phone_number,
        "business_address": s.business_address,
        "website_url": s.website_url,
        "state_license_number": s.state_license_number,  # JSON array
        "license_expiration_date": s.license_expiration_date,  # JSON array
        "license_status": s.license_status,  # JSON array
        "license_picture": license_val,
        "referrals": referrals_val,
        "job_photos": job_photos_val,
        "user_type": s.user_type,
        "service_states": s.service_states,
        "country_city": s.country_city,
        "created_at": (
            s.created_at.isoformat() if getattr(s, "created_at", None) else None
        ),
    }


@router.get(
    "/suppliers/{supplier_id}/image/{field}",
    dependencies=[Depends(require_admin_token)],
)
def supplier_image(
    supplier_id: int, 
    field: str, 
    file_index: int = Query(0, ge=0, description="Index of file in the array (0-based)"),
    db: Session = Depends(get_db)
):
    """Return binary content for a supplier image/document field.

    `field` must be one of: `license_picture`, `referrals`, `job_photos`.
    `file_index` specifies which file to retrieve from the JSON array (default: 0).
    
    Files are stored as JSON arrays with base64-encoded data.
    Responds with raw binary and proper Content-Type so frontend can display or open.
    """
    import base64
    import json
    
    allowed_fields = ["license_picture", "referrals", "job_photos"]
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Invalid image field")

    s = (
        db.query(models.user.Supplier)
        .filter(models.user.Supplier.id == supplier_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Get the JSON array for the field
    files_json = getattr(s, field, None)
    if not files_json:
        raise HTTPException(status_code=404, detail=f"{field} not found for supplier")
    
    # Parse JSON array
    try:
        if isinstance(files_json, str):
            files_array = json.loads(files_json)
        else:
            files_array = files_json
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail=f"Invalid file data format for {field}")
    
    # Check if file_index exists
    if not isinstance(files_array, list) or len(files_array) == 0:
        raise HTTPException(status_code=404, detail=f"No files found for {field}")
    
    if file_index >= len(files_array):
        raise HTTPException(
            status_code=404, 
            detail=f"File index {file_index} not found. Only {len(files_array)} file(s) available."
        )
    
    # Get the specific file
    file_data = files_array[file_index]
    
    # Decode base64 data
    try:
        blob = base64.b64decode(file_data.get("data", ""))
        content_type = file_data.get("content_type", "application/octet-stream")
        filename = file_data.get("filename", f"{field}-{supplier_id}-{file_index}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error decoding file: {str(e)}")
    
    # Stream raw bytes with correct Content-Type so browsers can render via <img src="...">.
    return Response(
        content=blob, 
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )


@router.patch(
    "/suppliers/{supplier_id}/approval",
    dependencies=[Depends(require_admin_or_editor)],
)
def update_supplier_approval(
    supplier_id: int,
    data: ContractorApprovalUpdate,
    db: Session = Depends(get_db)
):
    """Admin/Editor: Approve or reject a supplier account.
    
    Updates the `approved_by_admin` field in the users table to "approved" or "rejected".
    Optionally adds a note to the `note` field for admin reference.
    
    Request body: {"status": "approved" or "rejected", "note": "Optional admin note"}
    """
    # Validate status
    if data.status not in ["approved", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail="Status must be either 'approved' or 'rejected'"
        )
    
    # Get the supplier
    supplier = db.query(models.user.Supplier).filter(
        models.user.Supplier.id == supplier_id
    ).first()
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Get the associated user
    user = db.query(models.user.User).filter(
        models.user.User.id == supplier.user_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Associated user not found")
    
    try:
        # Update approval status and note
        old_status = user.approved_by_admin
        user.approved_by_admin = data.status
        
        # Update note if provided
        if data.note:
            user.note = data.note
        
        db.commit()
        db.refresh(user)
        
        logger.info(
            f"Supplier {supplier.company_name} (ID: {supplier.id}, User ID: {user.id}) "
            f"approval status changed from '{old_status}' to '{data.status}'"
        )
        
        # Create notification for supplier
        notification = models.user.Notification(
            user_id=user.id,
            type="account_approval",
            message=f"Your supplier account has been {data.status} by an administrator."
        )
        db.add(notification)
        db.commit()
        
        return {
            "success": True,
            "supplier_id": supplier.id,
            "user_id": user.id,
            "email": user.email,
            "approved_by_admin": data.status,
            "note": user.note,
            "message": f"Supplier account has been {data.status} successfully."
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update supplier approval status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update approval status: {str(e)}"
        )


@router.get(
    "/contractors/{contractor_id}/image/{field}",
    dependencies=[Depends(require_admin_token)],
)
def contractor_image(
    contractor_id: int, 
    field: str, 
    file_index: int = Query(0, ge=0, description="Index of file in the array (0-based)"),
    db: Session = Depends(get_db)
):
    """Return binary content for a contractor image/document field.

    `field` must be one of: `license_picture`, `referrals`, `job_photos`.
    `file_index` specifies which file to retrieve from the JSON array (default: 0).
    
    Files are now stored as JSON arrays with base64-encoded data.
    Responds with raw binary and proper Content-Type so frontend can display or open.
    """
    import base64
    import json
    
    allowed_fields = ["license_picture", "referrals", "job_photos"]
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Invalid image field")

    c = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.id == contractor_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found")

    # Get the JSON array for the field
    files_json = getattr(c, field, None)
    if not files_json:
        raise HTTPException(status_code=404, detail=f"{field} not found for contractor")
    
    # Parse JSON array
    try:
        if isinstance(files_json, str):
            files_array = json.loads(files_json)
        else:
            files_array = files_json
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail=f"Invalid file data format for {field}")
    
    # Check if file_index exists
    if not isinstance(files_array, list) or len(files_array) == 0:
        raise HTTPException(status_code=404, detail=f"No files found for {field}")
    
    if file_index >= len(files_array):
        raise HTTPException(
            status_code=404, 
            detail=f"File index {file_index} not found. Only {len(files_array)} file(s) available."
        )
    
    # Get the specific file
    file_data = files_array[file_index]
    
    # Decode base64 data
    try:
        blob = base64.b64decode(file_data.get("data", ""))
        content_type = file_data.get("content_type", "application/octet-stream")
        filename = file_data.get("filename", f"{field}-{contractor_id}-{file_index}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error decoding file: {str(e)}")
    
    # Stream raw bytes with correct Content-Type so browsers can render via <img src="...">.
    return Response(
        content=blob, 
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )


# NOTE: The signed public image endpoints were removed. If you need temporary
# public URLs for contractor images, consider implementing cloud storage
# presigned URLs or a revocable token mechanism.


@router.patch(
    "/contractors/{contractor_id}/active",
    dependencies=[Depends(require_admin_or_editor)],
)
def set_contractor_active(contractor_id: int, db: Session = Depends(get_db)):
    """Admin-only: toggle the contractor's user `is_active` flag.

    The endpoint requires only the `contractor_id` path parameter. It will
    fetch the associated `users.is_active` value and flip it (true -> false,
    false -> true), commit the change, and return the new state.
    """
    c = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.id == contractor_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found")

    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == c.user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Associated user not found")

    # Flip the active flag
    user.is_active = not bool(user.is_active)
    db.add(user)
    db.commit()

    message = (
        "Contractor account has been enabled." if user.is_active else "Contractor account has been disabled by an administrator."
    )

    return {"user_id": user.id, "is_active": user.is_active, "message": message}


@router.patch(
    "/contractors/{contractor_id}/approval",
    dependencies=[Depends(require_admin_or_editor)],
)
def update_contractor_approval(
    contractor_id: int,
    data: ContractorApprovalUpdate,
    db: Session = Depends(get_db)
):
    """Admin/Editor: Approve or reject a contractor account.
    
    Updates the `approved_by_admin` field in the users table to "approved" or "rejected".
    Optionally adds a note to the `note` field for admin reference.
    
    Request body:
    {
        "status": "approved",  // or "rejected"
        "note": "Verified license and credentials"  // optional
    }
    """
    # Validate status
    if data.status not in ["approved", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail="Status must be either 'approved' or 'rejected'"
        )
    
    # Find contractor
    c = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.id == contractor_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found")
    
    # Find associated user
    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == c.user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Associated user not found")
    
    try:
        # Update approval status
        old_status = user.approved_by_admin
        user.approved_by_admin = data.status
        
        # Update note if provided
        if data.note is not None:
            user.note = data.note
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(
            f"Contractor {contractor_id} (user {user.id}) approval status changed from "
            f"'{old_status}' to '{data.status}'"
        )
        
        # Create notification for contractor
        notification = models.user.Notification(
            user_id=user.id,
            type="account_approval",
            message=f"Your contractor account has been {data.status} by an administrator."
        )
        db.add(notification)
        db.commit()
        
        return {
            "success": True,
            "contractor_id": contractor_id,
            "user_id": user.id,
            "email": user.email,
            "approved_by_admin": data.status,
            "note": user.note,
            "message": f"Contractor account has been {data.status} successfully."
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update contractor approval status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update approval status: {str(e)}"
        )


@router.patch(
    "/suppliers/{supplier_id}/active",
    dependencies=[Depends(require_admin_or_editor)],
)
def set_supplier_active(supplier_id: int, db: Session = Depends(get_db)):
    """Admin-only: toggle the supplier's user `is_active` flag.

    The endpoint requires only the `supplier_id` path parameter. It will
    fetch the associated `users.is_active` value and flip it (true -> false,
    false -> true), commit the change, and return the new state.
    """
    s = (
        db.query(models.user.Supplier)
        .filter(models.user.Supplier.id == supplier_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")

    user = (
        db.query(models.user.User)
        .filter(models.user.User.id == s.user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Associated user not found")

    # Flip the active flag
    user.is_active = not bool(user.is_active)
    db.add(user)
    db.commit()

    message = (
        "Supplier account has been enabled." if user.is_active else "Supplier account has been disabled by an administrator."
    )

    return {"user_id": user.id, "is_active": user.is_active, "message": message}


@router.delete(
    "/account",
    summary="Delete Own Account (Viewer/Editor)",
)
def delete_user_account(
    admin_user = Depends(require_viewer_or_editor),
    db: Session = Depends(get_db),
):
    """Delete the authenticated user's account. Only accessible by admin users with 'viewer' or 'editor' role.

    This endpoint will:
    - Delete the authenticated user's account from the database
    - Automatically determined from the authentication token
    - Cascade delete all related data (jobs, subscriptions, etc.)
    - Prevent deletion of actual admin users

    Returns:
        Success message with deleted user information

    Raises:
        HTTPException 401: If unable to identify user
        HTTPException 404: If user not found
        HTTPException 500: If deletion fails
    """
    # Get the authenticated admin user's email
    admin_email = getattr(admin_user, "email", None)
    if not admin_email:
        raise HTTPException(status_code=401, detail="Unable to identify authenticated user")

    # Find the user by email
    user = db.query(models.user.User).filter(models.user.User.email == admin_email).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User account not found")

    # Check if the user is an actual admin user - admin accounts cannot be deleted
    admin_check = db.execute(
        text("SELECT id FROM admin_users WHERE email = :email"),
        {"email": user.email}
    ).first()
    
    if admin_check:
        return {
            "success": False,
            "deleted": False,
            "message": "Admin accounts cannot be deleted through this endpoint.",
            "detail": "Please use the appropriate admin management system or contact your system administrator for assistance.",
            "user_email": user.email
        }

    try:
        # Store email and ID for response message
        user_email = user.email
        user_id = user.id

        # Delete the user (cascade will handle related records)
        db.delete(user)
        db.commit()

        logger.info(f"User account deleted: {user_email} (ID: {user_id})")

        return {
            "success": True,
            "user_id": user_id,
            "email": user_email,
            "deleted": True,
            "message": f"Your account '{user_email}' has been successfully deleted."
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete user account: {str(e)}"
        )


@router.put(
    "/users/approve",
    dependencies=[Depends(require_admin_only)],
    summary="Approve or Reject User"
)
def update_user_approval(
    data: UserApprovalUpdate,
    admin: models.user.AdminUser = Depends(require_admin_only),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to approve or reject a user account.
    
    Status options:
    - "approved": User can access the platform
    - "rejected": User is denied access
    
    Restrictions:
    - Only users with 'admin' role can use this endpoint
    - Cannot approve/reject admin accounts
    """
    # Validate status
    if data.status not in ["approved", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail="Status must be either 'approved' or 'rejected'"
        )
    
    # Get the user
    user = db.query(models.user.User).filter(
        models.user.User.id == data.user_id
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if target user is an admin (prevent approving/rejecting admin accounts)
    try:
        admin_check = db.execute(
            text("SELECT id FROM admin_users WHERE lower(email) = lower(:email) LIMIT 1"),
            {"email": user.email}
        ).first()
        
        if admin_check:
            raise HTTPException(
                status_code=403,
                detail="Cannot approve or reject admin accounts through this endpoint."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking admin status: {str(e)}")
    
    try:
        # Update approval status
        old_status = user.approved_by_admin
        user.approved_by_admin = data.status
        db.commit()
        db.refresh(user)
        
        logger.info(
            f"Admin {admin.email} changed user {user.email} (ID: {user.id}) approval status from "
            f"'{old_status}' to '{data.status}'"
        )
        
        # Create notification for user
        notification = models.user.Notification(
            user_id=user.id,
            type="account_approval",
            message=f"Your account has been {data.status} by an administrator."
        )
        db.add(notification)
        db.commit()
        
        return {
            "success": True,
            "user_id": user.id,
            "email": user.email,
            "status": data.status,
            "message": f"User account has been {data.status} successfully.",
            "updated_by": admin.email
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update approval status for user {data.user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update approval status: {str(e)}"
        )
from typing import Optional
import json


# ============================================================================
# Helper Functions for Analytics
# ============================================================================

def _get_date_range_from_filter(time_range: str, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """
    Convert time_range filter to (start_date, end_date, periods, bucket).
    
    Returns:
        tuple: (start_date, end_date, periods_list, bucket_type)
        - periods_list: [(label, start, end), ...]
        - bucket_type: 'day', 'week', or 'month'
    """
    now = datetime.utcnow()
    
    if time_range == "custom" and date_from and date_to:
        start = datetime.fromisoformat(date_from.replace('Z', ''))
        end = datetime.fromisoformat(date_to.replace('Z', ''))
        # For custom range, use monthly buckets
        periods, bucket = _periods_for_range("last6months")
        # Filter periods to custom range
        periods = [(label, s, e) for label, s, e in periods if s >= start and e <= end]
        return start, end, periods, bucket
    
    # Map time_range to periods
    if time_range == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
        periods = [(start.strftime("%H:00"), start + timedelta(hours=i), start + timedelta(hours=i+1)) for i in range(24)]
        return start, end, periods, "hour"
    
    elif time_range == "7days":
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
        periods = []
        for i in range(7):
            d = start + timedelta(days=i)
            periods.append((d.strftime("%a"), d, d + timedelta(days=1)))
        return start, end, periods, "day"
    
    elif time_range == "30days":
        periods, bucket = _periods_for_range("last30days")
        start = periods[0][1]
        end = periods[-1][2]
        return start, end, periods, bucket
    
    elif time_range == "1year":
        periods, bucket = _periods_for_range("last12months")
        start = periods[0][1]
        end = periods[-1][2]
        return start, end, periods, bucket
    
    else:  # Default: 6months
        periods, bucket = _periods_for_range("last6months")
        start = periods[0][1]
        end = periods[-1][2]
        return start, end, periods, bucket


def _apply_global_filters(query, model, filters: dict, db: Session):
    """
    Apply global filters (state, user_type, subscription_tier) to a query.
    
    Args:
        query: SQLAlchemy query object
        model: The main model being queried (Job, User, etc.)
        filters: Dict with keys: state, user_type, subscription_tier
        db: Database session
    
    Returns:
        Modified query with filters applied
    """
    # State filter
    if filters.get("state") and filters["state"] not in ["All", "all"]:
        state = filters["state"]
        if hasattr(model, 'state'):
            query = query.filter(model.state == state)
    
    # User type filter (Contractors vs Suppliers)
    if filters.get("user_type") and filters["user_type"] not in ["All", "all"]:
        user_type = filters["user_type"]
        if user_type == "Contractors":
            # Join with contractors table
            query = query.join(models.user.Contractor, models.user.Contractor.user_id == models.user.User.id)
        elif user_type == "Suppliers":
            # Join with suppliers table
            query = query.join(models.user.Supplier, models.user.Supplier.user_id == models.user.User.id)
    
    # Subscription tier filter
    if filters.get("subscription_tier") and filters["subscription_tier"] not in ["All", "all"]:
        tier = filters["subscription_tier"]
        # Join with subscribers and subscriptions
        query = query.join(models.user.Subscriber, models.user.Subscriber.user_id == models.user.User.id)
        query = query.join(models.user.Subscription, models.user.Subscription.id == models.user.Subscriber.subscription_id)
        query = query.filter(models.user.Subscription.name == tier)
    
    return query


def _calculate_credits_flow(db: Session, period_start, period_end, filters: dict):
    """
    Calculate credits flow for a period: granted, purchased, spent, frozen.
    
    Returns:
        dict: {"granted": int, "purchased": int, "spent": int, "frozen": int}
    """
    # 1. Credits Granted (trial credits given to new users in this period)
    granted_query = db.query(func.coalesce(func.sum(models.user.Subscriber.trial_credits), 0)).filter(
        models.user.Subscriber.subscription_start_date >= period_start,
        models.user.Subscriber.subscription_start_date < period_end,
        models.user.Subscriber.trial_credits_used == True
    )
    granted = granted_query.scalar() or 0
    
    # 2. Credits Purchased (from subscription purchases in this period)
    purchased_query = db.query(
        func.coalesce(func.sum(models.user.Subscription.credits), 0)
    ).join(
        models.user.Subscriber, models.user.Subscriber.subscription_id == models.user.Subscription.id
    ).filter(
        models.user.Subscriber.subscription_start_date >= period_start,
        models.user.Subscriber.subscription_start_date < period_end
    )
    purchased = purchased_query.scalar() or 0
    
    # 3. Credits Spent (from unlocked leads in this period)
    spent_query = db.query(func.coalesce(func.sum(models.user.UnlockedLead.credits_spent), 0)).filter(
        models.user.UnlockedLead.unlocked_at >= period_start,
        models.user.UnlockedLead.unlocked_at < period_end
    )
    spent = spent_query.scalar() or 0
    
    # 4. Credits Frozen (subscriptions that lapsed in this period)
    frozen_query = db.query(func.coalesce(func.sum(models.user.Subscriber.frozen_credits), 0)).filter(
        models.user.Subscriber.frozen_at >= period_start,
        models.user.Subscriber.frozen_at < period_end
    )
    frozen = frozen_query.scalar() or 0
    
    return {
        "granted": int(granted),
        "purchased": int(purchased),
        "spent": int(spent),
        "frozen": int(frozen)
    }


# ============================================================================
# Main Analytics Endpoint
# ============================================================================

@router.get("/analytics", dependencies=[Depends(require_admin_token)])
def get_admin_analytics(
    time_range: str = Query("6months", description="Time range: today, 7days, 30days, 6months, 1year, custom"),
    state: str = Query("All", description="State filter or 'All'"),
    user_type: str = Query("All", description="User type: All, Contractors, Suppliers"),
    subscription_tier: str = Query("All", description="Subscription tier: All, Starter, Professional, Enterprise, Custom"),
    date_from: Optional[str] = Query(None, description="Custom range start (ISO format)"),
    date_to: Optional[str] = Query(None, description="Custom range end (ISO format)"),
    credits_view: str = Query("monthly", description="Credits flow view: daily, weekly, monthly"),
    funnel_view: str = Query("credits", description="Funnel metric: count, credits, category"),
    page: int = Query(1, ge=1, description="Page number for tables"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Comprehensive admin analytics dashboard.
    
    Returns:
        - 4 KPIs with growth metrics
        - 8 Charts (revenue, jobs, users, credits flow, funnel, subscriptions, categories, geography)
        - 2 Data tables (top categories, top jurisdictions) with pagination
        - Applied filters metadata
    """
    
    # Get date range and periods
    start_date, end_date, periods, bucket = _get_date_range_from_filter(time_range, date_from, date_to)
    
    # Filters dict for reuse
    filters = {
        "state": state,
        "user_type": user_type,
        "subscription_tier": subscription_tier
    }
    
    # ========================================================================
    # KPIs Calculation
    # ========================================================================
    
    # Total Users (cumulative at end of period)
    total_users_query = db.query(func.count(models.user.User.id)).filter(
        models.user.User.created_at < end_date
    )
    total_users = total_users_query.scalar() or 0
    
    # Previous period users (for growth %)
    period_length = end_date - start_date
    prev_period_end = start_date
    prev_period_start = start_date - period_length
    prev_users = db.query(func.count(models.user.User.id)).filter(
        models.user.User.created_at < prev_period_end
    ).scalar() or 0
    
    users_change = total_users - prev_users
    users_growth_pct = ((users_change / prev_users * 100) if prev_users > 0 else 100.0) if users_change != 0 else 0.0
    
    # Total Revenue (from payments table if exists, else from subscriber.total_spending)
    if _table_exists(db, "payments"):
        revenue_query = text("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date >= :start AND payment_date < :end")
        total_revenue = db.execute(revenue_query, {"start": start_date, "end": end_date}).scalar() or 0
        prev_revenue = db.execute(revenue_query, {"start": prev_period_start, "end": prev_period_end}).scalar() or 0
    else:
        # Fallback: use total_spending from subscribers
        total_revenue = db.query(func.coalesce(func.sum(models.user.Subscriber.total_spending), 0)).scalar() or 0
        prev_revenue = 0  # Can't calculate previous without timestamps
    
    revenue_change = total_revenue - prev_revenue
    revenue_growth_pct = ((revenue_change / prev_revenue * 100) if prev_revenue > 0 else 100.0) if revenue_change != 0 else 0.0
    
    # Active Subscriptions
    active_subs = db.query(func.count(models.user.Subscriber.id)).filter(
        models.user.Subscriber.is_active == True
    ).scalar() or 0
    
    # Previous active subs (approximate - count those active before period start)
    prev_active_subs = db.query(func.count(models.user.Subscriber.id)).filter(
        models.user.Subscriber.is_active == True,
        models.user.Subscriber.subscription_start_date < prev_period_end
    ).scalar() or 0
    
    subs_change = active_subs - prev_active_subs
    subs_growth_pct = ((subs_change / prev_active_subs * 100) if prev_active_subs > 0 else 100.0) if subs_change != 0 else 0.0
    
    # ========================================================================
    # Charts Data
    # ========================================================================
    
    # Chart 1: Revenue Timeline
    revenue_data = []
    for label, p_start, p_end in periods:
        if _table_exists(db, "payments"):
            rev_q = text("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date >= :s AND payment_date < :e")
            rev = db.execute(rev_q, {"s": p_start, "e": p_end}).scalar() or 0
        else:
            rev = 0
        revenue_data.append({"month": label, "value": int(rev)})
    
    revenue_total = sum(r["value"] for r in revenue_data)
    revenue_peak = max(revenue_data, key=lambda x: x["value"]) if revenue_data else {"month": None, "value": 0}
    
    # Chart 2: Jobs Growth
    jobs_data = []
    for label, p_start, p_end in periods:
        jobs_count = db.query(func.count(models.user.Job.id)).filter(
            models.user.Job.created_at >= p_start,
            models.user.Job.created_at < p_end
        ).scalar() or 0
        jobs_data.append({"month": label, "value": int(jobs_count)})
    
    jobs_total = sum(j["value"] for j in jobs_data)
    
    # Chart 3: User Growth (Cumulative)
    users_growth_data = []
    for label, p_start, p_end in periods:
        users_cum = db.query(func.count(models.user.User.id)).filter(
            models.user.User.created_at < p_end
        ).scalar() or 0
        users_growth_data.append({"month": label, "value": int(users_cum)})
    
    # Chart 4: Credits Flow (with daily/weekly/monthly toggle)
    credits_flow_data = []
    
    # Adjust periods based on credits_view
    if credits_view == "daily":
        # Use daily periods for last 30 days
        flow_periods, _ = _periods_for_range("last30days")
    elif credits_view == "weekly":
        # Create weekly periods for last 12 weeks
        flow_periods = []
        for i in range(11, -1, -1):
            week_start = (now - timedelta(weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(weeks=1)
            flow_periods.append((f"W{12-i}", week_start, week_end))
    else:  # monthly
        flow_periods = periods
    
    for label, p_start, p_end in flow_periods:
        flow = _calculate_credits_flow(db, p_start, p_end, filters)
        credits_flow_data.append({
            "period": label,
            "granted": flow["granted"],
            "purchased": flow["purchased"],
            "spent": flow["spent"],
            "frozen": flow["frozen"]
        })
    
    credits_totals = {
        "granted": sum(c["granted"] for c in credits_flow_data),
        "purchased": sum(c["purchased"] for c in credits_flow_data),
        "spent": sum(c["spent"] for c in credits_flow_data),
        "frozen": sum(c["frozen"] for c in credits_flow_data)
    }
    
    # Chart 5: Marketplace Funnel
    # Stage 1: Delivered (all posted jobs)
    delivered_count = db.query(func.count(models.user.Job.id)).filter(
        models.user.Job.job_review_status == "posted"
    ).scalar() or 0
    
    # Stage 2: Unlocked (all unlocked leads - includes deleted jobs!)
    unlocked_count = db.query(func.count(models.user.UnlockedLead.id)).scalar() or 0
    unlocked_credits = db.query(func.coalesce(func.sum(models.user.UnlockedLead.credits_spent), 0)).scalar() or 0
    
    # Stage 3: Saved
    saved_count = db.query(func.count(models.user.SavedJob.id)).scalar() or 0
    
    # Stage 4: Not Interested
    not_interested_count = db.query(func.count(models.user.NotInterestedJob.id)).scalar() or 0
    
    conversion_rate = (unlocked_count / delivered_count * 100) if delivered_count > 0 else 0.0
    
    # Chart 6: Subscription Distribution (Donut)
    subscription_dist = db.query(
        models.user.Subscription.name,
        func.count(models.user.Subscriber.id).label("count")
    ).join(
        models.user.Subscriber, models.user.Subscriber.subscription_id == models.user.Subscription.id
    ).filter(
        models.user.Subscriber.is_active == True
    ).group_by(models.user.Subscription.name).all()
    
    subscription_data = []
    for sub in subscription_dist:
        # Calculate revenue (count * price)
        sub_obj = db.query(models.user.Subscription).filter(models.user.Subscription.name == sub.name).first()
        price = float(sub_obj.price.replace('$', '').replace(',', '')) if sub_obj and sub_obj.price else 0
        revenue = sub.count * price
        subscription_data.append({
            "tier": sub.name,
            "count": sub.count,
            "revenue": int(revenue)
        })
    
    # Chart 7: Category Performance (by user types)
    # Group by audience_type_names
    category_query = db.query(
        models.user.Job.audience_type_names.label("category"),
        func.count(models.user.Job.id).label("delivered"),
        func.count(models.user.UnlockedLead.id).label("unlocked")
    ).outerjoin(
        models.user.UnlockedLead, models.user.Job.id == models.user.UnlockedLead.job_id
    ).filter(
        models.user.Job.audience_type_names.isnot(None)
    ).group_by(models.user.Job.audience_type_names).all()
    
    category_data = []
    for cat in category_query:
        conv_pct = (cat.unlocked / cat.delivered * 100) if cat.delivered > 0 else 0.0
        category_data.append({
            "category": cat.category or "Unknown",
            "delivered": cat.delivered,
            "unlocked": cat.unlocked,
            "conversionPct": round(conv_pct, 1)
        })
    
    # Sort by unlocked count (descending)
    category_data.sort(key=lambda x: x["unlocked"], reverse=True)
    
    # Chart 8: Geographic Distribution
    geo_query = db.query(
        models.user.Job.state.label("state"),
        func.count(models.user.Job.id).label("jobs")
    ).filter(
        models.user.Job.state.isnot(None)
    ).group_by(models.user.Job.state).all()
    
    geographic_data = []
    for geo in geo_query:
        # Count contractors and suppliers in this state
        contractors = db.query(func.count(func.distinct(models.user.Contractor.user_id))).filter(
            models.user.Contractor.state.contains([geo.state])
        ).scalar() or 0
        
        suppliers = db.query(func.count(func.distinct(models.user.Supplier.user_id))).filter(
            models.user.Supplier.service_states.contains([geo.state])
        ).scalar() or 0
        
        geographic_data.append({
            "state": geo.state,
            "jobs": geo.jobs,
            "contractors": contractors,
            "suppliers": suppliers
        })
    
    # Sort by jobs count (descending)
    geographic_data.sort(key=lambda x: x["jobs"], reverse=True)
    
    # ========================================================================
    # Data Tables
    # ========================================================================
    
    # Table 1: Top Categories Performance
    categories_table_query = db.query(
        models.user.Job.audience_type_names.label("category"),
        func.count(models.user.Job.id).label("delivered"),
        func.count(models.user.UnlockedLead.id).label("unlocked"),
        func.avg(models.user.UnlockedLead.credits_spent).label("avg_credits"),
        func.sum(models.user.UnlockedLead.credits_spent).label("total_revenue")
    ).outerjoin(
        models.user.UnlockedLead, models.user.Job.id == models.user.UnlockedLead.job_id
    ).filter(
        models.user.Job.audience_type_names.isnot(None)
    ).group_by(models.user.Job.audience_type_names)
    
    # Get total count for pagination
    categories_total = categories_table_query.count()
    
    # Apply pagination and sorting
    categories_table = categories_table_query.order_by(
        func.count(models.user.UnlockedLead.id).desc()
    ).offset((page - 1) * per_page).limit(per_page).all()
    
    categories_table_data = []
    for cat in categories_table:
        conv_pct = (cat.unlocked / cat.delivered * 100) if cat.delivered > 0 else 0.0
        categories_table_data.append({
            "category": cat.category or "Unknown",
            "delivered": cat.delivered,
            "unlocked": cat.unlocked,
            "conversionPct": round(conv_pct, 1),
            "avgCredits": round(float(cat.avg_credits or 0), 1),
            "totalRevenue": int(cat.total_revenue or 0)
        })
    
    # Table 2: Top Jurisdictions
    jurisdictions_query = db.query(
        models.user.Job.state.label("location"),
        func.count(models.user.Job.id).label("jobs_delivered"),
        func.count(models.user.UnlockedLead.id).label("unlocks")
    ).outerjoin(
        models.user.UnlockedLead, models.user.Job.id == models.user.UnlockedLead.job_id
    ).filter(
        models.user.Job.state.isnot(None)
    ).group_by(models.user.Job.state)
    
    jurisdictions_total = jurisdictions_query.count()
    
    jurisdictions_table = jurisdictions_query.order_by(
        func.count(models.user.UnlockedLead.id).desc()
    ).offset((page - 1) * per_page).limit(per_page).all()
    
    jurisdictions_table_data = []
    for jur in jurisdictions_table:
        # Get contractors and suppliers count
        contractors = db.query(func.count(func.distinct(models.user.Contractor.user_id))).filter(
            models.user.Contractor.state.contains([jur.location])
        ).scalar() or 0
        
        suppliers = db.query(func.count(func.distinct(models.user.Supplier.user_id))).filter(
            models.user.Supplier.service_states.contains([jur.location])
        ).scalar() or 0
        
        conv_pct = (jur.unlocks / jur.jobs_delivered * 100) if jur.jobs_delivered > 0 else 0.0
        
        jurisdictions_table_data.append({
            "location": jur.location,
            "jobsDelivered": jur.jobs_delivered,
            "contractors": contractors,
            "suppliers": suppliers,
            "unlocks": jur.unlocks,
            "conversionPct": round(conv_pct, 1)
        })
    
    # ========================================================================
    # Build Response
    # ========================================================================
    
    response = {
        "kpis": {
            "totalUsers": {
                "count": total_users,
                "growth": f"{users_growth_pct:+.1f}%",
                "changeValue": users_change
            },
            "totalRevenue": {
                "amount": int(total_revenue),
                "growth": f"{revenue_growth_pct:+.1f}%",
                "changeValue": int(revenue_change)
            },
            "activeSubscriptions": {
                "count": active_subs,
                "growth": f"{subs_growth_pct:+.1f}%",
                "changeValue": subs_change
            },
            "totalRevenue2": {  # Duplicate for 4th KPI slot
                "amount": int(total_revenue),
                "growth": f"{revenue_growth_pct:+.1f}%",
                "changeValue": int(revenue_change)
            }
        },
        
        "charts": {
            "revenueTimeline": {
                "data": revenue_data,
                "peakMonth": revenue_peak["month"],
                "total": revenue_total
            },
            "jobsGrowth": {
                "data": jobs_data,
                "total": jobs_total
            },
            "userGrowth": {
                "data": users_growth_data,
                "growthRate": round(users_growth_pct, 1)
            },
            "creditsFlow": {
                "data": credits_flow_data,
                "totals": credits_totals,
                "view": credits_view
            },
            "marketplaceFunnel": {
                "delivered": {"count": delivered_count, "credits": 0},
                "unlocked": {"count": unlocked_count, "credits": int(unlocked_credits)},
                "saved": {"count": saved_count, "credits": 0},
                "notInterested": {"count": not_interested_count, "credits": 0},
                "conversionRate": round(conversion_rate, 1)
            },
            "subscriptionDistribution": {
                "data": subscription_data
            },
            "categoryPerformance": {
                "data": category_data[:10]  # Top 10 for chart
            },
            "geographicDistribution": {
                "data": geographic_data[:15]  # Top 15 states
            }
        },
        
        "tables": {
            "topCategories": {
                "data": categories_table_data,
                "pagination": {
                    "total": categories_total,
                    "page": page,
                    "perPage": per_page,
                    "totalPages": (categories_total + per_page - 1) // per_page
                }
            },
            "topJurisdictions": {
                "data": jurisdictions_table_data,
                "pagination": {
                    "total": jurisdictions_total,
                    "page": page,
                    "perPage": per_page,
                    "totalPages": (jurisdictions_total + per_page - 1) // per_page
                }
            }
        },
        
        "filters": {
            "applied": {
                "timeRange": time_range,
                "state": state,
                "userType": user_type,
                "subscriptionTier": subscription_tier
            },
            "dateRange": {
                "from": start_date.isoformat() + "Z",
                "to": end_date.isoformat() + "Z"
            }
        },
        
        "metadata": {
            "lastUpdated": datetime.utcnow().isoformat() + "Z",
            "timezone": "UTC",
            "cacheKey": f"analytics_{time_range}_{state}_{user_type}_{subscription_tier}",
            "cacheDuration": 300  # 5 minutes
        }
    }
    
    return response



# ============================================================================
# Dedicated Chart Endpoints (with Toggle Parameters)
# ============================================================================

@router.get("/charts/credits-flow", dependencies=[Depends(require_admin_token)])
def get_credits_flow_chart(
    view: str = Query(..., description="View type: daily, weekly, monthly"),
    time_range: str = Query("6months", description="Time range filter"),
    state: str = Query("All", description="State filter"),
    user_type: str = Query("All", description="User type filter"),
    subscription_tier: str = Query("All", description="Subscription tier filter"),
    date_from: Optional[str] = Query(None, description="Custom range start (ISO format)"),
    date_to: Optional[str] = Query(None, description="Custom range end (ISO format)"),
    db: Session = Depends(get_db)
):
    """
    Get credits flow chart data with configurable view.
    
    View options:
    - daily: Last 30 days, daily buckets
    - weekly: Last 12 weeks, weekly buckets
    - monthly: Last 6 months, monthly buckets
    
    Returns:
        - data: Array of period data with granted, purchased, spent, frozen, net credits
        - totals: Aggregated totals across all periods
        - metadata: View info, filters, and cache settings
    """
    # Validate view parameter
    if view not in ["daily", "weekly", "monthly"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid view. Must be one of: daily, weekly, monthly"
        )
    
    # Get date range
    start_date, end_date, _, _ = _get_date_range_from_filter(time_range, date_from, date_to)
    now = datetime.utcnow()
    
    # Build filters
    filters = {
        "state": state,
        "user_type": user_type,
        "subscription_tier": subscription_tier
    }
    
    # Determine periods based on view
    if view == "daily":
        # Last 30 days, daily buckets
        periods = []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            periods.append((day.strftime("%Y-%m-%d"), day, day + timedelta(days=1)))
    
    elif view == "weekly":
        # Last 12 weeks, weekly buckets
        periods = []
        for i in range(11, -1, -1):
            week_start = (now - timedelta(weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(weeks=1)
            periods.append((f"Week {12-i}", week_start, week_end))
    
    else:  # monthly
        # Last 6 months, monthly buckets
        periods = _month_starts(6)
    
    # Calculate credits flow for each period
    flow_data = []
    for label, p_start, p_end in periods:
        flow = _calculate_credits_flow(db, p_start, p_end, filters)
        net = flow["granted"] + flow["purchased"] - flow["spent"] - flow["frozen"]
        
        flow_data.append({
            "period": label,
            "granted": flow["granted"],
            "purchased": flow["purchased"],
            "spent": flow["spent"],
            "frozen": flow["frozen"],
            "net": net
        })
    
    # Calculate totals
    totals = {
        "granted": sum(d["granted"] for d in flow_data),
        "purchased": sum(d["purchased"] for d in flow_data),
        "spent": sum(d["spent"] for d in flow_data),
        "frozen": sum(d["frozen"] for d in flow_data),
        "net": sum(d["net"] for d in flow_data)
    }
    
    return {
        "data": flow_data,
        "totals": totals,
        "metadata": {
            "view": view,
            "bucketSize": "1 day" if view == "daily" else ("7 days" if view == "weekly" else "1 month"),
            "periodCount": len(flow_data),
            "filters": {
                "timeRange": time_range,
                "state": state,
                "userType": user_type,
                "subscriptionTier": subscription_tier
            },
            "lastUpdated": datetime.utcnow().isoformat() + "Z",
            "cacheDuration": 300
        }
    }


@router.get("/charts/marketplace-funnel", dependencies=[Depends(require_admin_token)])
def get_marketplace_funnel_chart(
    view: str = Query(..., description="View type: count, credits, category"),
    time_range: str = Query("6months", description="Time range filter"),
    state: str = Query("All", description="State filter"),
    user_type: str = Query("All", description="User type filter"),
    subscription_tier: str = Query("All", description="Subscription tier filter"),
    date_from: Optional[str] = Query(None, description="Custom range start (ISO format)"),
    date_to: Optional[str] = Query(None, description="Custom range end (ISO format)"),
    db: Session = Depends(get_db)
):
    """
    Get marketplace funnel chart data with configurable view.
    
    View options:
    - count: Job counts at each funnel stage
    - credits: Credits spent at each stage
    - category: Breakdown by user category
    
    Funnel stages:
    1. Delivered - All jobs visible to users
    2. Unlocked - Jobs purchased/unlocked
    3. Saved - Jobs bookmarked for later
    4. Not Interested - Jobs rejected
    
    Returns:
        - data: Funnel data (format varies by view)
        - conversionRates: Conversion percentages (count view only)
        - averages: Average metrics (credits view only)
        - conversionByCategory: Per-category conversion (category view only)
        - metadata: View info, filters, and cache settings
    """
    # Validate view parameter
    if view not in ["count", "credits", "category"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid view. Must be one of: count, credits, category"
        )
    
    # Get date range
    start_date, end_date, _, _ = _get_date_range_from_filter(time_range, date_from, date_to)
    
    # Build filters
    filters = {
        "state": state,
        "user_type": user_type,
        "subscription_tier": subscription_tier
    }
    
    # Base response structure
    response = {
        "metadata": {
            "view": view,
            "metric": "Job Count" if view == "count" else ("Credits Spent" if view == "credits" else "Jobs by Category"),
            "filters": {
                "timeRange": time_range,
                "state": state,
                "userType": user_type,
                "subscriptionTier": subscription_tier
            },
            "lastUpdated": datetime.utcnow().isoformat() + "Z",
            "cacheDuration": 300
        }
    }
    
    # ========================================================================
    # VIEW: COUNT - Job counts at each stage
    # ========================================================================
    if view == "count":
        # Stage 1: Delivered (all posted jobs)
        delivered_query = db.query(func.count(models.user.Job.id)).filter(
            models.user.Job.job_review_status == "posted",
            models.user.Job.created_at >= start_date,
            models.user.Job.created_at < end_date
        )
        
        # Apply state filter
        if state and state not in ["All", "all"]:
            delivered_query = delivered_query.filter(models.user.Job.state == state)
        
        delivered_count = delivered_query.scalar() or 0
        
        # Stage 2: Unlocked (all unlocked leads)
        unlocked_query = db.query(func.count(models.user.UnlockedLead.id)).filter(
            models.user.UnlockedLead.unlocked_at >= start_date,
            models.user.UnlockedLead.unlocked_at < end_date
        )
        unlocked_count = unlocked_query.scalar() or 0
        
        # Stage 3: Saved (bookmarked jobs)
        saved_query = db.query(func.count(models.user.SavedLead.id)).filter(
            models.user.SavedLead.saved_at >= start_date,
            models.user.SavedLead.saved_at < end_date
        )
        saved_count = saved_query.scalar() or 0
        
        # Stage 4: Not Interested (rejected jobs)
        not_interested_query = db.query(func.count(models.user.NotInterestedLead.id)).filter(
            models.user.NotInterestedLead.marked_at >= start_date,
            models.user.NotInterestedLead.marked_at < end_date
        )
        not_interested_count = not_interested_query.scalar() or 0
        
        response["data"] = {
            "delivered": delivered_count,
            "unlocked": unlocked_count,
            "saved": saved_count,
            "notInterested": not_interested_count
        }
        
        # Calculate conversion rates
        response["conversionRates"] = {
            "deliveredToUnlocked": round((unlocked_count / delivered_count * 100) if delivered_count > 0 else 0, 1),
            "unlockedToSaved": round((saved_count / unlocked_count * 100) if unlocked_count > 0 else 0, 1),
            "deliveredToNotInterested": round((not_interested_count / delivered_count * 100) if delivered_count > 0 else 0, 1)
        }
    
    # ========================================================================
    # VIEW: CREDITS - Credits spent at each stage
    # ========================================================================
    elif view == "credits":
        # Only unlocked stage has credits
        unlocked_credits_query = db.query(
            func.coalesce(func.sum(models.user.UnlockedLead.credits_spent), 0)
        ).filter(
            models.user.UnlockedLead.unlocked_at >= start_date,
            models.user.UnlockedLead.unlocked_at < end_date
        )
        unlocked_credits = unlocked_credits_query.scalar() or 0
        
        # Count of unlocks for average calculation
        unlocked_count = db.query(func.count(models.user.UnlockedLead.id)).filter(
            models.user.UnlockedLead.unlocked_at >= start_date,
            models.user.UnlockedLead.unlocked_at < end_date
        ).scalar() or 0
        
        response["data"] = {
            "delivered": 0,  # No credits for delivery
            "unlocked": int(unlocked_credits),
            "saved": 0,  # No credits for saving
            "notInterested": 0  # No credits for rejection
        }
        
        response["averages"] = {
            "creditsPerUnlock": round(unlocked_credits / unlocked_count, 2) if unlocked_count > 0 else 0
        }
    
    # ========================================================================
    # VIEW: CATEGORY - Breakdown by user category
    # ========================================================================
    elif view == "category":
        # Get all categories from audience_type_names
        categories_query = db.query(
            models.user.Job.audience_type_names,
            func.count(models.user.Job.id).label("delivered")
        ).filter(
            models.user.Job.job_review_status == "posted",
            models.user.Job.created_at >= start_date,
            models.user.Job.created_at < end_date,
            models.user.Job.audience_type_names.isnot(None)
        ).group_by(models.user.Job.audience_type_names).all()
        
        # Initialize data structures
        delivered_by_cat = {}
        unlocked_by_cat = {}
        saved_by_cat = {}
        not_interested_by_cat = {}
        
        for cat_row in categories_query:
            category = cat_row.audience_type_names or "Unknown"
            delivered_by_cat[category] = cat_row.delivered
            
            # Get unlocked count for this category
            unlocked = db.query(func.count(models.user.UnlockedLead.id)).join(
                models.user.Job, models.user.Job.id == models.user.UnlockedLead.job_id
            ).filter(
                models.user.Job.audience_type_names == category,
                models.user.UnlockedLead.unlocked_at >= start_date,
                models.user.UnlockedLead.unlocked_at < end_date
            ).scalar() or 0
            unlocked_by_cat[category] = unlocked
            
            # Get saved count for this category
            saved = db.query(func.count(models.user.SavedLead.id)).join(
                models.user.Job, models.user.Job.id == models.user.SavedLead.job_id
            ).filter(
                models.user.Job.audience_type_names == category,
                models.user.SavedLead.saved_at >= start_date,
                models.user.SavedLead.saved_at < end_date
            ).scalar() or 0
            saved_by_cat[category] = saved
            
            # Get not interested count for this category
            not_interested = db.query(func.count(models.user.NotInterestedLead.id)).join(
                models.user.Job, models.user.Job.id == models.user.NotInterestedLead.job_id
            ).filter(
                models.user.Job.audience_type_names == category,
                models.user.NotInterestedLead.marked_at >= start_date,
                models.user.NotInterestedLead.marked_at < end_date
            ).scalar() or 0
            not_interested_by_cat[category] = not_interested
        
        response["data"] = {
            "delivered": delivered_by_cat,
            "unlocked": unlocked_by_cat,
            "saved": saved_by_cat,
            "notInterested": not_interested_by_cat
        }
        
        # Calculate conversion rates by category
        response["conversionByCategory"] = {
            cat: round((unlocked_by_cat.get(cat, 0) / delivered_by_cat.get(cat, 1) * 100), 1)
            for cat in delivered_by_cat.keys()
        }
        
        response["metadata"]["categoryCount"] = len(delivered_by_cat)
    
    return response
