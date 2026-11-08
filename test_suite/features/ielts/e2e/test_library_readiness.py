"""A real prerequisite gate, not a mock implementation of the future IELTS UI."""

from playwright.sync_api import expect


def test_ielts_library_prerequisites(page, studio):
    """IELTS-E2E-002: fail explicitly until the designed IELTS API/UI is implemented."""
    page.goto(studio.ui_url)
    expect(page.get_by_role("heading", name="🦆 AI Content Studio", exact=True)).to_be_visible()
    response = page.request.get(studio.api_url + "/openapi.json")
    assert response.ok
    paths = response.json()["paths"]
    required = {
        "/api/ielts/topics": {"get", "post"},
        "/api/ielts/vocabulary": {"get", "post"},
        "/api/ielts/patterns": {"get", "post"},
        "/api/ielts/samples": {"get", "post"},
        "/api/ielts/exercises": {"get", "post"},
        "/api/ielts/imports/preview": {"post"},
    }
    missing = [
        f"{method.upper()} {path}"
        for path, methods in required.items()
        for method in sorted(methods)
        if method not in paths.get(path, {})
    ]
    assert not missing, (
        "IELTS feature is not implemented; full library-to-Short acceptance is BLOCKED. "
        "Missing operations: " + ", ".join(missing)
    )
    expect(page.get_by_role("tab", name="Thư viện IELTS", exact=True)).to_be_visible()
