"""Upload adapters shared by image and clip forms; no base64 media payloads."""


def file_chunks(upload, chunk_size=256 * 1024):
    upload.seek(0)
    while chunk := upload.read(chunk_size):
        yield chunk


def upload_media(request, job_id, uploads, kind):
    ids = []
    for upload in uploads:
        result = request(
            "POST",
            f"/api/jobs/{job_id}/assets?kind={kind}",
            extra_headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(upload.size),
            },
            content=file_chunks(upload),
            timeout=120,
        )
        if result is None:
            return None
        ids.append(result["id"])
    return ids
