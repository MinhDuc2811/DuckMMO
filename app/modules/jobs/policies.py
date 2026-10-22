"""Shared lifecycle decisions, independent of HTTP and persistence."""

ACTIVE_STATUSES = ("queued", "running", "cancelling")
VIDEO_REVIEW_STATUSES = ("awaiting_video_review", "video_approved", "video_rejected")
EDITABLE_STATUSES = ("awaiting_review", "approved", "rejected", *VIDEO_REVIEW_STATUSES)


def can_render(status, render_config):
    return status in ("approved", *VIDEO_REVIEW_STATUSES) or (
        status in ("failed", "cancelled") and bool(render_config)
    )


def cancellation_state(status):
    if status in ("cancelled", "cancelling"):
        return status
    return {"queued": "cancelled", "running": "cancelling"}.get(status)
