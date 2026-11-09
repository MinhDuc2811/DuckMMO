"""Separate local project lifecycle around the pinned upstream renderer."""

import asyncio
import json
from asyncio import to_thread
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from app.infrastructure.local_lock import LocalBusy, exclusive_lock
from app.infrastructure.media.probe import MediaFailure, inspect_audio, inspect_image
from app.infrastructure.media.storage import file_digest
from app.infrastructure.stickman import VENDOR, StickmanStore, run_cli
from app.infrastructure.stickman import director_kit as build_director_kit
from app.modules.errors import ApplicationError


@contextmanager
def workspace(settings, *, lock=True):
    try:
        store = StickmanStore(settings)
        if lock:
            with exclusive_lock(store.root / ".stickman.lock"):
                yield store
        else:
            yield store
    except LocalBusy as exc:
        raise ApplicationError(429, "Stickman Studio đang xử lý một tác vụ khác.") from exc
    except FileNotFoundError as exc:
        raise ApplicationError(404, "Không tìm thấy dự án hoặc file Stickman.") from exc
    except (MediaFailure, ValueError, TypeError, RecursionError) as exc:
        raise ApplicationError(422, str(exc)) from exc
    except TimeoutError as exc:
        raise ApplicationError(408, "Tải file quá 120 giây.") from exc
    except OSError as exc:
        raise ApplicationError(507, "Không ghi/đọc được kho Stickman local.") from exc


def doctor(settings):
    try:
        result = run_cli("doctor")
        ready = all(result["checks"].values())
        detail = "Runtime local sẵn sàng; chưa kiểm tra provider sinh ảnh/giọng."
    except MediaFailure as exc:
        result, ready, detail = {}, False, str(exc)
    return {
        "ready": ready,
        "runtime": result,
        "detail": detail,
        "upstream_commit": json.loads((VENDOR / "UPSTREAM.json").read_text())["commit"],
        "generation": "external assets required; no paid generation or TTS adapter is invoked",
        "max_voice_seconds": 120,
    }


def projects(settings):
    with workspace(settings, lock=False) as store:
        return [
            {k: v for k, v in json.loads(p.read_text()).items() if k != "project"}
            for p in sorted(
                store.root.glob("*/studio.json"), key=lambda p: p.stat().st_mtime, reverse=True
            )[:100]
        ]


def create(payload, settings):
    with workspace(settings) as store:
        store.storage.ensure_capacity(1_000_000)
        project_id = str(uuid4())
        base = store.root / project_id
        run_cli("init", base, "--style", payload.style)
        project = json.loads((base / "project.json").read_text())
        project.update(
            width=720 if payload.ratio == "9:16" else 1280,
            height=1280 if payload.ratio == "9:16" else 720,
            fps=24,
        )
        metadata = {
            "id": project_id,
            "title": payload.title,
            "version": 1,
            "state": "draft",
            "assets": [],
            "project": project,
            "preview_version": None,
            "film_version": None,
        }
        store.save(base, "studio.json", metadata)
        return metadata


def get(project_id, settings):
    with workspace(settings, lock=False) as store:
        return store.read(project_id)


def current(store, project_id, version):
    data = store.read(project_id)
    if data["version"] != version:
        raise ApplicationError(409, "Dự án đã đổi. Tải lại trước khi tiếp tục.")
    return data


def persist_edit(store, project_id, data, project):
    base = store.project(project_id)
    (base / "output" / "approval.json").unlink(missing_ok=True)
    data.update(
        project=project,
        version=data["version"] + 1,
        state="draft",
        preview_version=None,
        film_version=None,
    )
    store.save(base, "studio.json", data)
    return data


def edit(project_id, payload, settings):
    with workspace(settings) as store:
        data = current(store, project_id, payload.expected_version)
        store.check_project(project_id, payload.project)
        return persist_edit(store, project_id, data, payload.project)


async def upload(project_id, filename, rights_note, chunks, settings):
    if not rights_note.strip():
        raise ApplicationError(422, "Ghi nguồn và quyền sử dụng file trước khi tải lên.")
    extension = Path(filename).suffix.lower()
    kind = "image" if extension in (".png", ".jpg", ".jpeg") else "audio"
    if extension not in (".png", ".jpg", ".jpeg", ".wav", ".mp3", ".flac", ".ogg", ".m4a"):
        raise ApplicationError(422, "Chọn PNG/JPEG hoặc audio WAV/MP3/FLAC/OGG/M4A.")
    extension = ".jpg" if extension == ".jpeg" else extension
    with workspace(settings) as store:
        data = store.read(project_id)
        if len(data["assets"]) >= 20:
            raise ApplicationError(409, "Mỗi dự án tối đa 20 file.")
        limit = 3_000_000 if kind == "image" else 20_000_000
        store.storage.ensure_capacity(limit)
        base = store.project(project_id)
        if (base / "inputs").is_symlink():
            raise MediaFailure("Thư mục nguồn không được là symlink.")
        (base / "inputs").mkdir(exist_ok=True)
        temporary = base / "inputs" / (str(uuid4()) + ".part")
        try:
            size = 0
            async with asyncio.timeout(120):
                with temporary.open("xb") as target:
                    async for chunk in chunks:
                        size += len(chunk)
                        if size > limit:
                            raise ApplicationError(413, "File vượt giới hạn Stickman.")
                        await to_thread(target.write, chunk)
            details = (
                await to_thread(inspect_image, temporary)
                if kind == "image"
                else await to_thread(inspect_audio, temporary, store.media_settings)
            )
            if kind == "audio" and details["duration"] > 120:
                raise MediaFailure("Lời đọc/nhạc trong workspace này tối đa 120 giây.")
            if kind == "image" and details["width"] * details["height"] > 4_000_000:
                raise MediaFailure("Ảnh Stickman tối đa 4 megapixel.")
            digest = await to_thread(file_digest, temporary)
            path = f"inputs/{digest}{extension}"
            if not any(a["path"] == path for a in data["assets"]):
                temporary.replace(base / path)
                data["assets"].append(
                    {
                        "path": path,
                        "sha256": digest,
                        "kind": kind,
                        "name": filename,
                        "size": size,
                        "rights_note": rights_note,
                        **details,
                    }
                )
                store.save(base, "studio.json", data)
            return next(a for a in data["assets"] if a["path"] == path)
        finally:
            temporary.unlink(missing_ok=True)


def starter(project_id, payload, settings):
    with workspace(settings) as store:
        data = current(store, project_id, payload.expected_version)
        if data["project"]["style"] != "B1":
            raise ApplicationError(
                422, "Timeline minh họa nhanh dùng B1; style khác cần storyboard riêng."
            )
        asset = next(
            (a for a in data["assets"] if a["path"] == payload.audio_path and a["kind"] == "audio"),
            None,
        )
        if not asset:
            raise ApplicationError(422, "Chọn file lời đọc của dự án.")
        duration = asset["duration"]
        project = {
            **data["project"],
            "voice": {"path": asset["path"], "lead": 0, "tail": 0},
            "captions": [{"start": 0, "end": duration, "text": payload.caption}],
            "shots": [
                {
                    "start": 0,
                    "end": duration,
                    "layers": [
                        {
                            "type": "pose",
                            "pose": 0,
                            "x": 400,
                            "y": 160,
                            "w": 400,
                            "keys": [{"t": 0, "x": 400}, {"t": duration, "x": 460}],
                        }
                    ],
                }
            ],
        }
        store.check_project(project_id, project)
        return persist_edit(store, project_id, data, project)


def action(project_id, command, payload, settings):
    with workspace(settings) as store:
        data = current(store, project_id, payload.expected_version)
        store.check_project(project_id, data["project"])
        base = store.project(project_id)
        store.save(base, "project.json", data["project"])
        store.storage.ensure_capacity(300_000_000 if command in ("preview", "render") else 0)
        args = [base / "project.json"]
        if command in ("preview", "validate"):
            args += ["--seconds", payload.seconds]
        if command in ("preview", "render"):
            args += ["--replace"]
        if command == "approve":
            if not payload.note or data.get("preview_version") != data["version"]:
                raise ApplicationError(
                    409, "Cần xem preview hiện hành và ghi nhận xét trước khi duyệt."
                )
            preview = base / "output" / "preview.mp4"
            if payload.preview_sha256 != file_digest(preview):
                raise ApplicationError(409, "Preview đã đổi; tải lại trước khi duyệt.")
            args += ["--note", payload.note]
        if command == "render" and data["state"] != "approved":
            raise ApplicationError(409, "Duyệt preview hiện tại trước khi render đầy đủ.")
        report = run_cli(command, *args, directory=base)
        if command == "preview":
            data.update(
                state="previewed",
                preview_version=data["version"],
                film_version=None,
                preview_sha256=report["output_sha256"],
            )
        elif command == "approve":
            data.update(state="approved", approval_note=payload.note)
        elif command == "render":
            data.update(
                state="rendered", film_version=data["version"], film_sha256=report["output_sha256"]
            )
        store.save(base, "studio.json", data)
        return {"project": data, "report": report}


def artifact(project_id, kind, settings):
    with workspace(settings, lock=False) as store:
        data = store.read(project_id)
        stage = "film" if kind.startswith("film") else "preview"
        if data.get(stage + "_version") != data["version"]:
            raise ApplicationError(409, "Đầu ra chưa có hoặc không còn khớp phiên bản dự án.")
        names = {
            "preview": "preview.mp4",
            "film": "film.mp4",
            "preview-srt": "preview.srt",
            "film-srt": "film.srt",
            "contact": "preview-contact-sheet.png",
        }
        path = store.project(project_id) / "output" / names[kind]
        if not path.is_file():
            raise ApplicationError(404, "Chưa có file đầu ra.")
        if kind in ("preview", "film") and file_digest(path) != data.get(kind + "_sha256"):
            raise ApplicationError(409, "File video đã đổi; cần dựng và duyệt lại.")
        return path


def director_kit(payload):
    return build_director_kit(payload)
