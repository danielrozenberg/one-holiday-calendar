import pytest

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import main

BLOB = config.encode(
    config_pb2.Config(sources=[config_pb2.Source(country="CA")])
)
BROWSER_ACCEPT = "text/html,application/xhtml+xml,*/*;q=0.8"


@pytest.fixture
def client():
    return main.app.test_client()


def test_index(client):
    response = client.get("/", headers={"Accept": BROWSER_ACCEPT})

    assert response.status_code == 200
    assert b"No holidays selected yet" in response.data


def test_browser_gets_page(client):
    response = client.get(f"/c/{BLOB}", headers={"Accept": BROWSER_ACCEPT})

    assert response.mimetype == "text/html"
    assert b"Canada Day" in response.data
    assert f"webcal://localhost/c/{BLOB}".encode() in response.data


@pytest.mark.parametrize("accept", ["*/*", "text/calendar", ""])
def test_calendar_app_gets_feed(client, accept):
    response = client.get(f"/c/{BLOB}", headers={"Accept": accept})

    assert response.mimetype == "text/calendar"
    assert b"SUMMARY:Canada Day" in response.data


@pytest.mark.parametrize(
    ("accept", "fmt", "mimetype"),
    [
        (BROWSER_ACCEPT, "ics", "text/calendar"),
        ("*/*", "html", "text/html"),
    ],
)
def test_format_override(client, accept, fmt, mimetype):
    response = client.get(f"/c/{BLOB}?format={fmt}", headers={"Accept": accept})

    assert response.mimetype == mimetype


def test_invalid_blob(client):
    response = client.get("/c/not-a-config!")

    assert response.status_code == 400


def test_https_behind_proxy(client):
    response = client.get(
        f"/c/{BLOB}",
        headers={"Accept": BROWSER_ACCEPT, "X-Forwarded-Proto": "https"},
    )

    assert f"https://localhost/c/{BLOB}".encode() in response.data
