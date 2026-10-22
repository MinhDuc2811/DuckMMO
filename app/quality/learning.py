"""Reproducible style experiments; no invented model training or platform metrics."""

from sqlalchemy import select

from app.db import Experiment, Job, LearningConfig, ReviewFeedback
from app.quality.evaluators import subtitle_checks
from app.quality.recorder import digest

TEXTS = [
    "Bình minh lên trên dãy núi. Người lữ khách chuẩn bị hành trình qua miền đất mới.",
    "Báo cáo ghi nhận nhiều thay đổi. Cần kiểm tra nguồn trước khi đưa ra kết luận cuối cùng.",
    "Nhân vật dừng lại trước cánh cửa. Một cuộc trò chuyện bất ngờ đã thay đổi kế hoạch.",
    "Ảnh minh họa cần phù hợp với nội dung đang kể và không che mất phần phụ đề trên màn hình.",
    "Thông tin mới cần được đối chiếu. Không biến suy đoán thành lời khẳng định chắc chắn.",
    "Đây là tình huống có tên riêng Nguyễn Thị Minh và số liệu 1.250 người tham gia khảo sát.",
    "Người kể chậm lại để giải thích sự kiện. Khán giả cần đủ thời gian đọc hết câu chữ.",
    "Một bức ảnh ngang xuất hiện trong khung hình dọc, cần kiểm tra vùng chữ và khoảng cách.",
    "Điều gì đã xảy ra sau cuộc gặp? Câu chuyện tiếp tục khi người bạn trở lại ngôi làng.",
    "Ngày 21 tháng 10, nhóm hoàn thành kiểm tra dữ liệu và lưu phiên bản kết quả để đối chiếu.",
]


def benchmark(style):
    from app.services.video import split_captions

    cases = []
    for i, text in enumerate(TEXTS):
        chunks = split_captions(text, style["caption_chars"])
        cues, cursor = [], 0.0
        for chunk in chunks:
            duration = max(1, len(chunk) / 18)
            cues.append((cursor, cursor + duration, chunk))
            cursor += duration
        evaluations = subtitle_checks(cues, cursor, style, 720, 1280)
        layout = next(e for e in evaluations if e["dimension"] == "subtitle_layout")
        failures = sum(e["outcome"] == "fail" for e in evaluations)
        # Reward two-line captions without rewarding one-word flashing captions.
        small = sum(len(c[2].split()) < 3 for c in cues)
        score = max(0, 100 - 25 * len(layout["evidence"]["overflow"]) - 5 * small)
        cases.append(
            {"id": f"vi-{i}", "score": score, "blockers": failures, "evaluations": evaluations}
        )
    return {
        "score": sum(c["score"] for c in cases) / len(cases),
        "blockers": sum(c["blockers"] for c in cases),
        "cases": cases,
    }


def create_experiment(session, candidate):
    from app.services.styles import choose_style

    baseline = choose_style({"branch": candidate.branch}, use_learned=False)
    # Compare against the actual current active config, not a convenient weaker baseline.
    active = session.scalar(
        select(LearningConfig).where(
            LearningConfig.branch == candidate.branch,
            LearningConfig.family == "style",
            LearningConfig.state.in_(("active", "canary")),
        )
    )
    if active:
        baseline = active.config
    before, after = benchmark(baseline), benchmark(candidate.config)
    rows = list(
        session.scalars(
            select(ReviewFeedback)
            .join(Job)
            .where(
                Job.package.is_not(None),
                ReviewFeedback.scope == "video",
                ReviewFeedback.decision == "reject",
            )
        )
    )
    supporting_jobs = {
        r.job_id
        for r in rows
        if "subtitle_overflow" in r.labels
        and session.get(Job, r.job_id).package["branch"] == candidate.branch
    }
    regressions = [
        a["id"]
        for a, b in zip(after["cases"], before["cases"], strict=True)
        if a["score"] < b["score"] or a["blockers"] > b["blockers"]
    ]
    eligible = (
        after["score"] > before["score"]
        and not regressions
        and after["blockers"] == 0
        and len(supporting_jobs) >= 3
    )
    report = {
        "baseline": before,
        "candidate": after,
        "regressions": regressions,
        "supporting_jobs": len(supporting_jobs),
        "required_jobs": 3,
        "eligible": eligible,
        "limitations": [
            "Offline subtitle layout benchmark only",
            "No factual, voice, visual preference or platform uplift claims",
        ],
        "reason": "Eligible for human-approved canary"
        if eligible
        else (
            "Need measured improvement, no regression, zero blockers "
            "and 3 independent reviewed jobs"
        ),
    }
    row = Experiment(
        candidate_id=candidate.id,
        baseline=baseline,
        dataset={
            "version": "vi-layout-v1",
            "sha256": digest(TEXTS),
            "case_count": len(TEXTS),
            "branch": candidate.branch,
        },
        report=report,
        state="eligible" if eligible else "blocked",
    )
    session.add(row)
    session.flush()
    return row


def learn_from_feedback(session, job, labels):
    if "subtitle_overflow" not in labels or not job.video or not job.video.get("style"):
        return None
    base = job.video["style"]
    config = {
        **base,
        "font_size": max(32, base["font_size"] - 4),
        "caption_chars": max(24, base["caption_chars"] - 8),
    }
    row = LearningConfig(
        family="style",
        branch=job.package["branch"],
        config=config,
        provenance={
            "job_id": job.id,
            "video_hash": job.video["sha256"],
            "baseline_hash": digest(base),
            "reason": "subtitle_overflow",
        },
    )
    session.add(row)
    session.flush()
    create_experiment(session, row)
    return row


def promote(session, experiment):
    if experiment.state != "eligible" or not experiment.report.get("eligible"):
        raise ValueError("Candidate chưa đạt benchmark và số mẫu tối thiểu.")
    candidate = session.get(LearningConfig, experiment.candidate_id)
    current = session.scalar(
        select(LearningConfig).where(
            LearningConfig.branch == candidate.branch,
            LearningConfig.family == candidate.family,
            LearningConfig.state.in_(("active", "canary")),
        )
    )
    from app.services.styles import choose_style

    actual_baseline = (
        current.config if current else choose_style({"branch": candidate.branch}, use_learned=False)
    )
    if digest(actual_baseline) != digest(experiment.baseline):
        raise ValueError("Baseline đã đổi. Chạy benchmark lại trước khi áp dụng.")
    if current:
        current.state = "retired"
    candidate.state = "canary"
    experiment.state = "canary"
    return candidate
