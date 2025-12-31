
import base64
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, Body
import asyncio
from sqlalchemy import func, text
from sqlalchemy.orm import Session
import logging

from src.app import models
from src.app.api.deps import (
    require_admin_token,
    require_admin_or_editor,
    require_admin_only,
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
            d = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            periods.append((d.strftime("%Y-%m-%d"), d, d + timedelta(days=1)))
        return periods, "day"
    if time_range == "last90Days":
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
        jobs_q = jobs_q.filter(
            (models.user.Job.state == state)
            | (
                models.user.Job.uploaded_by_user_id.in_(list(user_ids))
                if user_ids
                else False
            )
        )
        jobs_count = jobs_q.scalar() or 0
        jobs_data.append({"month": label, "value": int(jobs_count), "label": label})

        # users cumulative at end
        if user_ids:
            users_cum = (
                db.query(func.count(models.user.User.id))
                .filter(
                    models.user.User.created_at < end,
                    models.user.User.id.in_(list(user_ids)),
                )
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

    # Total jobs (current)
    total_jobs = db.query(func.count(models.user.Job.id)).scalar() or 0
    jobs_latest = jobs_data[-1]["value"] if len(jobs_data) >= 1 else 0
    jobs_prev = jobs_data[-2]["value"] if len(jobs_data) >= 2 else 0
    jobs_change = jobs_latest - jobs_prev
    jobs_pct, jobs_pct_str = _percent_change(jobs_latest, jobs_prev)

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
    """Admin endpoint: return list of contractors with basic contact and trade info.

    Returns entries with: name, email, company, license_number, trade_categories
    """
    # join contractors -> users to get email and active flag
    rows = (
        db.query(models.user.Contractor, models.user.User.email, models.user.User.is_active)
        .join(models.user.User, models.user.User.id == models.user.Contractor.user_id)
        .all()
    )

    result = []
    for contractor, email, is_active in rows:
        action = "disable" if is_active else "enable"
        result.append(
            {
                "id": contractor.id,
                "name": contractor.primary_contact_name,
                "email": email,
                "company": contractor.company_name,
                "license_number": contractor.state_license_number,
                "trade_categories": contractor.trade_categories,
                "action": action,
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
                "address_code": j.permit_record_number,
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
    """Admin-only: mark an ingested job as posted.

    Sets `job_review_status` to `posted` for the given job id.
    """
    j = db.query(models.user.Job).filter(models.user.Job.id == job_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    j.job_review_status = "posted"
    db.add(j)
    db.commit()

    return {"job_id": j.id, "job_review_status": j.job_review_status, "message": "Job marked as posted."}


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

    Returns entries with: id, permit_type, permit_value, address, permit_status
    for jobs where `uploaded_by_contractor == False`.
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
                "id": j.id,
                "permit_type": j.permit_type,
                "permit_value": j.job_cost,
                "address": j.job_address,
                "permit_status": j.permit_status,
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
    """Admin endpoint: return list of suppliers with basic contact and trade info.

    Returns entries with: id, name, email, company, service_states, product_categories, action
    """
    # join suppliers -> users to get email and active flag
    rows = (
        db.query(models.user.Supplier, models.user.User.email, models.user.User.is_active)
        .join(models.user.User, models.user.User.id == models.user.Supplier.user_id)
        .all()
    )

    result = []
    for supplier, email, is_active in rows:
        action = "disable" if is_active else "enable"
        result.append(
            {
                "id": supplier.id,
                "name": supplier.primary_contact_name,
                "email": email,
                "company": supplier.company_name,
                "service_states": supplier.service_states,
                "product_categories": supplier.product_categories,
                "action": action,
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
    contractor_id: int, include_images: bool = False, db: Session = Depends(get_db)
):
    """Admin endpoint: return full contractor profile.

    Set include_images=true to get base64 image data (heavy).
    By default, only metadata is returned with a URL to fetch the image.
    """
    c = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.id == contractor_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found")

    user = db.query(models.user.User).filter(models.user.User.id == c.user_id).first()

    def as_blob_metadata(filename, content_type, blob, field_name):
        """Return metadata only, with URL to fetch actual image"""
        if not blob:
            return None
        return {
            "filename": filename,
            "content_type": content_type,
            "has_image": True,
            "url": f"/admin/dashboard/contractors/{contractor_id}/image/{field_name}",
        }

    def as_blob_full(filename, content_type, blob):
        """Return full base64 data (only when requested)"""
        if not blob:
            return None
        return {
            "filename": filename,
            "content_type": content_type,
            "data": base64.b64encode(blob).decode("ascii"),
        }

    if include_images:
        license_val = as_blob_full(
            c.license_picture_filename,
            c.license_picture_content_type,
            c.license_picture,
        )
        referrals_val = as_blob_full(
            c.referrals_filename, c.referrals_content_type, c.referrals
        )
        job_photos_val = as_blob_full(
            c.job_photos_filename, c.job_photos_content_type, c.job_photos
        )
    else:
        license_val = as_blob_metadata(
            c.license_picture_filename,
            c.license_picture_content_type,
            c.license_picture,
            "license_picture",
        )
        referrals_val = as_blob_metadata(
            c.referrals_filename, c.referrals_content_type, c.referrals, "referrals"
        )
        job_photos_val = as_blob_metadata(
            c.job_photos_filename, c.job_photos_content_type, c.job_photos, "job_photos"
        )

    return {
        "id": c.id,
        "name": c.primary_contact_name,
        "company_name": c.company_name,
        "phone_number": c.phone_number,
        "business_address": c.business_address,
        "business_type": c.business_type,
        "years_in_business": c.years_in_business,
        "state_license_number": c.state_license_number,
        "license_expiration_date": (
            c.license_expiration_date.isoformat() if c.license_expiration_date else None
        ),
        "license_status": c.license_status,
        "license_picture": license_val,
        "referrals": referrals_val,
        "job_photos": job_photos_val,
        "trade_categories": c.trade_categories,
        "trade_specialities": c.trade_specialities,
        "country_city": c.country_city,
        "state": c.state,
        "created_at": (
            c.created_at.isoformat() if getattr(c, "created_at", None) else None
        ),
    }


@router.get("/suppliers/{supplier_id}", dependencies=[Depends(require_admin_token)])
def supplier_detail(supplier_id: int, db: Session = Depends(get_db)):
    """Admin endpoint: return full supplier profile.

    Returns a comprehensive supplier record for admin review.
    """
    s = (
        db.query(models.user.Supplier)
        .filter(models.user.Supplier.id == supplier_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")

    user = db.query(models.user.User).filter(models.user.User.id == s.user_id).first()

    # Some supplier fields mirror contractor naming; use getattr for compatibility
    return {
        "id": s.id,
        "name": s.primary_contact_name,
        "company_name": s.company_name,
        "email": user.email if user else None,
        "phone_number": s.phone_number,
        "business_address": getattr(s, "business_address", None),
        "business_type": s.business_type,
        "years_in_business": s.years_in_business,
        "delivery_lead_time": s.delivery_lead_time,
        "onsite_delivery": s.onsite_delivery,
        "service_states": s.service_states,
        "country": s.country_city,
        "trade_categories": getattr(s, "trade_categories", None),
        "carries_inventory": s.carries_inventory,
        "minimum_order_amount": s.minimum_order_amount,
        "offers_credit_accounts": s.offers_credit_accounts,
        "offers_custom_orders": s.offers_custom_orders,
        "product_categories": s.product_categories,
        "project_type": s.product_types,
        "created_at": (s.created_at.isoformat() if getattr(s, "created_at", None) else None),
    }


@router.get(
    "/contractors/{contractor_id}/image/{field}",
    dependencies=[Depends(require_admin_token)],
)
def contractor_image(contractor_id: int, field: str, db: Session = Depends(get_db)):
    """Return binary content for a contractor image/document field.

    `field` must be one of: `license_picture`, `referrals`, `job_photos`.
    Responds with raw binary and proper Content-Type so frontend can display or open.
    """
    allowed = {
        "license_picture": (
            "license_picture",
            "license_picture_content_type",
            "license_picture_filename",
        ),
        "referrals": ("referrals", "referrals_content_type", "referrals_filename"),
        "job_photos": ("job_photos", "job_photos_content_type", "job_photos_filename"),
    }
    if field not in allowed:
        raise HTTPException(status_code=400, detail="Invalid image field")

    c = (
        db.query(models.user.Contractor)
        .filter(models.user.Contractor.id == contractor_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found")

    blob_attr, content_type_attr, filename_attr = allowed[field]
    blob = getattr(c, blob_attr, None)
    if not blob:
        raise HTTPException(status_code=404, detail=f"{field} not found for contractor")
    content_type = getattr(c, content_type_attr, None) or "application/octet-stream"
    filename = getattr(c, filename_attr, None) or f"{field}-{contractor_id}"

    # Stream raw bytes with correct Content-Type so browsers can render via <img src="...">.
    return Response(content=blob, media_type=content_type)


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
