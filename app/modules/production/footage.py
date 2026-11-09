"""Prepare external footage without replacing content, narration, cards or review."""

import asyncio
from asyncio import to_thread

from app.contracts.content import content_hash
from app.infrastructure.local_lock import LocalBusy, exclusive_lock
from app.infrastructure.media import moneyprinter
from app.infrastructure.media.probe import MediaFailure
from app.modules.errors import ApplicationError
from app.modules.jobs.lookup import load_job
from app.modules.production.assets import upload_asset


def runtime_status(settings):
    keys = {
        p: bool(getattr(settings, f"{p}_api_key").get_secret_value())
        for p in ("pexels", "pixabay", "coverr")
    }
    try:
        return {"ready": True, "providers": keys, "runtime": moneyprinter.doctor(settings)}
    except MediaFailure as exc:
        return {"ready": False, "providers": keys, "detail": str(exc)}


async def prepare_footage(job_id, payload, *, settings, session):
    job = load_job(session, job_id)
    if content_hash(job.package) != payload.expected_content_hash:
        raise ApplicationError(409, "Kịch bản đã đổi; tải lại trước khi tìm footage.")
    key = getattr(settings, f"{payload.provider}_api_key").get_secret_value()
    if not key:
        raise ApplicationError(
            409, f"Cần STUDIO_{payload.provider.upper()}_API_KEY để lấy footage."
        )
    session.commit()  # End the read transaction before provider/network work.
    settings.mpt_dir.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_lock(settings.mpt_dir / ".prepare.lock"):
            context = moneyprinter.prepare(
                settings,
                {
                    **payload.model_dump(exclude={"expected_content_hash", "rights_note"}),
                    "api_key": key,
                },
            )
            # The media subprocess is owned/cleaned by the existing command runner.
            preparing = asyncio.create_task(to_thread(context.__enter__))
            try:
                path, report = await asyncio.shield(preparing)
            except asyncio.CancelledError:
                try:
                    await preparing
                finally:
                    await to_thread(context.__exit__, None, None, None)
                raise
            try:
                session.expire_all()
                job = load_job(session, job_id)
                if content_hash(job.package) != payload.expected_content_hash:
                    raise ApplicationError(
                        409, "Kịch bản đổi khi đang chuẩn bị clip; hãy chạy lại."
                    )

                async def chunks():
                    with path.open("rb") as source:
                        while chunk := await to_thread(source.read, 1024 * 1024):
                            yield chunk

                provenance = {
                    "engine": "MoneyPrinterTurbo",
                    "version": report["version"],
                    "provider": payload.provider,
                    "terms": payload.terms,
                    "sources": report["sources"],
                    "rights_note": payload.rights_note,
                    "content_hash": payload.expected_content_hash,
                }
                return await upload_asset(
                    job_id,
                    "video",
                    chunks(),
                    str(path.stat().st_size),
                    settings=settings,
                    session=session,
                    provenance=provenance,
                )
            finally:
                await to_thread(context.__exit__, None, None, None)
    except LocalBusy as exc:
        raise ApplicationError(429, "Một lượt chuẩn bị MPT khác đang chạy.") from exc
    except MediaFailure as exc:
        raise ApplicationError(502, str(exc)) from exc
