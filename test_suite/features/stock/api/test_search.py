from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_stock_search_auth_validation_and_unconfigured_pexels(client):
    # Missing configured key is reported; no external call or fabricated result.
    response = client.get(
        "/api/production/stock/search", params={"provider": "pexels", "q": "library"}
    )
    assert response.status_code == 409 and "PEXELS_API_KEY" in response.json()["detail"]
    assert (
        client.get("/api/production/stock/search?provider=openverse&kind=video&q=city").status_code
        == 422
    )
    assert client.get("/api/production/stock/search?provider=unknown&q=city").status_code == 422
    assert client.get("/api/production/stock/search?provider=openverse&q=x").status_code == 422
    assert (
        client.get("/api/production/stock/search?provider=openverse&q=city&page=21").status_code
        == 422
    )
    with TestClient(
        create_app(Settings(database_url=str(client.app.state.engine.url), api_key="fixture-only"))
    ) as protected:
        assert (
            protected.get("/api/production/stock/search?provider=openverse&q=city").status_code
            == 401
        )
