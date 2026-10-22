from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.db import LearningConfig, make_engine, make_sessions


def learned_style(branch, session=None):
    if session is not None:
        active = session.scalar(
            select(LearningConfig).where(
                LearningConfig.branch == branch,
                LearningConfig.family == "style",
                LearningConfig.state.in_(("active", "canary")),
            )
        )
        if active:
            return {
                **active.config,
                "learning_config_id": active.id,
                "selection_reason": "Style đã qua benchmark và được duyệt áp dụng",
            }
        return None
    # Compatibility for standalone callers; app requests inject their session.
    engine = make_engine(Settings().database_url)
    try:
        with make_sessions(engine)() as owned_session:
            return learned_style(branch, owned_session)
    except OperationalError:
        return None  # Allows catalog tools to run before migrations.
    finally:
        engine.dispose()
