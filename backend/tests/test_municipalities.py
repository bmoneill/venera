"""Tests for the /api/municipalities autocomplete endpoint."""


class TestSuggestMunicipalities:
    """Tests for the ``/api/municipalities`` text-completion endpoint."""

    def test_returns_matches_for_prefix(self, client):
        response = client.get("/api/municipalities", params={"query": "Par"})
        assert response.status_code == 200
        data = response.json()
        assert any(item["name"] == "Paris" for item in data)

    def test_result_shape(self, client):
        response = client.get("/api/municipalities", params={"query": "Par"})
        item = response.json()[0]
        assert set(item.keys()) == {"name", "territory", "country", "label"}

    def test_blank_query_returns_empty_list(self, client):
        response = client.get("/api/municipalities", params={"query": ""})
        assert response.status_code == 200
        assert response.json() == []

    def test_missing_query_returns_empty_list(self, client):
        response = client.get("/api/municipalities")
        assert response.status_code == 200
        assert response.json() == []

    def test_limit_is_respected(self, client):
        response = client.get("/api/municipalities", params={"query": "a", "limit": 3})
        assert response.status_code == 200
        assert len(response.json()) <= 3

    def test_no_match_returns_empty_list(self, client):
        response = client.get(
            "/api/municipalities", params={"query": "Zzzzznotarealplace"}
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_limit_out_of_range_returns_422(self, client):
        response = client.get(
            "/api/municipalities", params={"query": "Paris", "limit": 0}
        )
        assert response.status_code == 422

    def test_requires_authentication(self):
        from fastapi.testclient import TestClient as PlainClient

        from backend.main import app

        with PlainClient(app) as plain_client:
            response = plain_client.get(
                "/api/municipalities", params={"query": "Paris"}
            )
        assert response.status_code == 401
