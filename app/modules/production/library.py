"""Read-only library downloads through the media owner."""

from app.contracts.artifacts import ArtifactDownload
from app.infrastructure.media.probe import MediaFailure
from app.infrastructure.media.study_pack import bundled_asset
from app.modules.errors import ApplicationError


def library_asset(kind, asset_id):
    try:
        path = bundled_asset(kind, asset_id)
    except MediaFailure as exc:
        raise ApplicationError(404, str(exc)) from exc
    return ArtifactDownload(path, "image/png" if kind == "background" else "audio/wav", path.name)


def stock_search(provider, kind, query, page, settings):
    from app.infrastructure.media.stock import search_stock

    if (provider == "pexels" and kind == "audio") or (provider == "openverse" and kind == "video"):
        raise ApplicationError(422, "Nguồn stock không hỗ trợ loại nội dung này.")
    if provider == "pexels" and not settings.pexels_api_key.get_secret_value():
        raise ApplicationError(409, "Cần STUDIO_PEXELS_API_KEY để tìm ảnh/video trên Pexels.")
    try:
        return search_stock(provider, kind, query, page, settings)
    except MediaFailure as exc:
        raise ApplicationError(502, str(exc)) from exc
