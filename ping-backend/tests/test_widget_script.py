"""GET /widget.js: the embeddable widget served by the API itself. No database."""

from fastapi.testclient import TestClient

from app import main


def test_widget_script_is_served_as_javascript():
    r = TestClient(main.app).get("/widget.js", headers={"Origin": "https://help.acme.com"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/javascript")
    assert r.headers["cache-control"] == "public, max-age=300"
    assert "Pingie" in r.text


def test_missing_build_is_a_clear_404(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "WIDGET_SCRIPT", tmp_path / "widget.js")
    r = TestClient(main.app).get("/widget.js")
    assert r.status_code == 404
    assert "build:backend" in r.json()["detail"]
