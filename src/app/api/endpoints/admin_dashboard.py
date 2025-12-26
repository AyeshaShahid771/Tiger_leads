from datetime import datetime, timedelta
from typing import List, Dict
import base64

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, text
from sqlalchemy.orm import Session
import os
import hmac
import hashlib
import time

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


@router.get("/contractors-summary", dependencies=[Depends(require_admin_token)])
def contractors_summary(db: Session = Depends(get_db)):
    """Admin endpoint: return list of contractors with basic contact and trade info.

    Returns entries with: name, email, company, license_number, trade_categories
    """
    # join contractors -> users to get email
    rows = (
        db.query(models.user.Contractor, models.user.User.email)
        .join(models.user.User, models.user.User.id == models.user.Contractor.user_id)
        .all()
    )

    result = []
    for contractor, email in rows:
        result.append(
            {
                "id": contractor.id,
                "name": contractor.primary_contact_name,
                "email": email,
                "company": contractor.company_name,
                "license_number": contractor.state_license_number,
                "trade_categories": contractor.trade_categories,
            }
        )

    return {"contractors": result}


@router.get("/contractors/{contractor_id}", dependencies=[Depends(require_admin_token)])
def contractor_detail(contractor_id: int, include_images: bool = False, db: Session = Depends(get_db)):
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
        return {"filename": filename, "content_type": content_type, "data": base64.b64encode(blob).decode("ascii"),}

    if include_images:
        license_val = as_blob_full(c.license_picture_filename, c.license_picture_content_type, c.license_picture)
        referrals_val = as_blob_full(c.referrals_filename, c.referrals_content_type, c.referrals)
        job_photos_val = as_blob_full(c.job_photos_filename, c.job_photos_content_type, c.job_photos)
    else:
        license_val = as_blob_metadata(c.license_picture_filename, c.license_picture_content_type, c.license_picture, "license_picture")
        referrals_val = as_blob_metadata(c.referrals_filename, c.referrals_content_type, c.referrals, "referrals")
        job_photos_val = as_blob_metadata(c.job_photos_filename, c.job_photos_content_type, c.job_photos, "job_photos")

    return {
        "id": c.id,
        "name": c.primary_contact_name,
        "company_name": c.company_name,
        "phone_number": c.phone_number,
        "business_address": c.business_address,
        "business_type": c.business_type,
        "years_in_business": c.years_in_business,
        "state_license_number": c.state_license_number,
        "license_expiration_date": c.license_expiration_date.isoformat() if c.license_expiration_date else None,
        "license_status": c.license_status,
        "license_picture": license_val,
        "referrals": referrals_val,
        "job_photos": job_photos_val,
        "trade_categories": c.trade_categories,
        "trade_specialities": c.trade_specialities,
        "country_city": c.country_city,
        "state": c.state,
        "created_at": c.created_at.isoformat() if getattr(c, "created_at", None) else None,
    }


@router.get("/contractors/{contractor_id}/image/{field}", dependencies=[Depends(require_admin_token)])
def contractor_image(contractor_id: int, field: str, db: Session = Depends(get_db)):
    """Return binary content for a contractor image/document field.

    `field` must be one of: `license_picture`, `referrals`, `job_photos`.
    Responds with raw binary and proper Content-Type so frontend can display or open.
    """
    allowed = {
        "license_picture": ("license_picture", "license_picture_content_type", "license_picture_filename"),
        "referrals": ("referrals", "referrals_content_type", "referrals_filename"),
        "job_photos": ("job_photos", "job_photos_content_type", "job_photos_filename"),
    }
    if field not in allowed:
        raise HTTPException(status_code=400, detail="Invalid image field")

    c = db.query(models.user.Contractor).filter(models.user.Contractor.id == contractor_id).first()
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


@router.post("/contractors/{contractor_id}/image/{field}/signed", dependencies=[Depends(require_admin_token)])
def contractor_image_signed(contractor_id: int, field: str, ttl_seconds: int = 300):
    """Admin-only: return a temporary public URL to open the image in a browser.

    The returned URL is under `/admin/dashboard/public/contractor_image` and valid
    for `ttl_seconds` (default 300s). The signing key is read from
    `ADMIN_SIGNING_KEY` env var (fallback insecure default for local/dev).
    """
    allowed_fields = {"license_picture", "referrals", "job_photos"}
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Invalid image field")

    expires = int(time.time()) + int(ttl_seconds)
    key = os.environ.get("ADMIN_SIGNING_KEY", "dev-secret").encode()
    msg = f"{contractor_id}:{field}:{expires}".encode()
    sig = hmac.new(key, msg, hashlib.sha256).hexdigest()

    url = f"/admin/dashboard/public/contractor_image?contractor_id={contractor_id}&field={field}&expires={expires}&sig={sig}"
    return {"url": url, "expires": expires}


@router.get("/public/contractor_image")
def public_contractor_image(contractor_id: int, field: str, expires: int, sig: str, db: Session = Depends(get_db)):
    """Public endpoint that validates the signed token and serves the image.

    This endpoint does not require admin auth; the signature must match and not be expired.
    """
    # expiry
    now = int(time.time())
    if now > int(expires):
        raise HTTPException(status_code=410, detail="URL expired")

    key = os.environ.get("ADMIN_SIGNING_KEY", "dev-secret").encode()
    msg = f"{contractor_id}:{field}:{expires}".encode()
    expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    allowed = {
        "license_picture": ("license_picture", "license_picture_content_type", "license_picture_filename"),
        "referrals": ("referrals", "referrals_content_type", "referrals_filename"),
        "job_photos": ("job_photos", "job_photos_content_type", "job_photos_filename"),
    }
    if field not in allowed:
        raise HTTPException(status_code=400, detail="Invalid image field")

    c = db.query(models.user.Contractor).filter(models.user.Contractor.id == contractor_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found")

    blob_attr, content_type_attr, filename_attr = allowed[field]
    blob = getattr(c, blob_attr, None)
    if not blob:
        raise HTTPException(status_code=404, detail=f"{field} not found for contractor")
    content_type = getattr(c, content_type_attr, None) or "application/octet-stream"
    filename = getattr(c, filename_attr, None) or f"{field}-{contractor_id}"

    return Response(content=blob, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
