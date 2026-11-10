"""Persist reviewed lesson snapshots and explicit activation bound to one YouTube channel."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.contracts.ielts import BriefInput
from app.infrastructure.persistence.database import AutomationPlan, AutomationRun
from app.modules.errors import ApplicationError
from app.modules.ielts.library import prepare_brief
from app.modules.publishing.oauth import verify
from app.publishing.connection import status


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def list_plans(*, session):
    plans = session.scalars(
        select(AutomationPlan).order_by(AutomationPlan.created_at.desc()).limit(50)
    ).all()
    runs = session.scalars(
        select(AutomationRun)
        .where(AutomationRun.plan_id.in_([p.id for p in plans]))
        .order_by(AutomationRun.publish_at)
    ).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "enabled": p.enabled,
            "channel_id": p.channel_id,
            "options": p.options,
            "runs": [
                {
                    "id": r.id,
                    "position": r.position,
                    "publish_at": utc(r.publish_at),
                    "state": r.state,
                    "job_id": r.job_id,
                    "publish_id": r.publish_id,
                    "error": r.error,
                    "failures": r.failures,
                }
                for r in runs
                if r.plan_id == p.id
            ],
        }
        for p in plans
    ]


def create_plan(payload, *, settings, session):
    if payload.first_publish_at < datetime.now(UTC) + timedelta(minutes=35):
        raise ApplicationError(
            422, "Chọn lần đăng đầu cách hiện tại ít nhất 35 phút để chuẩn bị video."
        )
    snapshots = []
    for episode in payload.episodes:
        brief = prepare_brief(
            episode.item_id,
            BriefInput(expected_version=episode.expected_version, focus_text=episode.focus_text),
            session=session,
        )
        snapshots.append(brief)
    plan = AutomationPlan(
        id=str(uuid4()),
        name=payload.name,
        enabled=False,
        channel_id="",
        options={
            "voice": "en-GB-SoniaNeural",
            "background_id": payload.background_id,
            "made_for_kids": payload.made_for_kids,
            "allow_quality_warnings": payload.allow_quality_warnings,
            "interval_hours": payload.interval_hours,
        },
    )
    session.add(plan)
    session.add_all(
        [
            AutomationRun(
                plan_id=plan.id,
                position=i,
                snapshot=snapshot,
                publish_at=payload.first_publish_at.astimezone(UTC)
                + timedelta(hours=i * payload.interval_hours),
            )
            for i, snapshot in enumerate(snapshots)
        ]
    )
    session.commit()
    return {"id": plan.id, "enabled": False, "count": len(snapshots)}


def toggle(plan_id, payload, *, settings, session):
    plan = session.get(AutomationPlan, str(plan_id))
    if plan is None:
        raise ApplicationError(404, "Không tìm thấy lịch.")
    if payload.enabled:
        if not payload.authorize_auto_publish:
            raise ApplicationError(
                422, "Xác nhận cho phép tự tạo, tự duyệt kỹ thuật và đăng các video trong lịch."
            )
        session.commit()
        connection = verify(settings)
        channel_id = connection["channel"]["id"]
        session.refresh(plan)
        if plan.channel_id and plan.channel_id != channel_id:
            raise ApplicationError(409, "Lịch thuộc kênh khác; không tự chuyển kênh đích.")
        plan.channel_id = channel_id
    plan.enabled = payload.enabled
    session.commit()
    return {
        "id": plan.id,
        "enabled": plan.enabled,
        "channel_id": plan.channel_id,
        "connection": status(settings),
    }
