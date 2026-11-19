import datetime
import hashlib
import importlib.metadata
import re
from unittest import mock

import icalendar
import pytest
from werkzeug.datastructures import MultiDict

from one_holiday_calendar import config
from one_holiday_calendar import config_pb2
from one_holiday_calendar import main
from one_holiday_calendar import merge

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
    assert f"webcal://localhost/c/{BLOB}?format=ics".encode() in response.data


def test_page_has_remove_buttons_after_default_submit(client):
    response = client.get(f"/c/{BLOB}", headers={"Accept": BROWSER_ACCEPT})

    buttons = re.findall(r"<button [^>]*>", response.get_data(as_text=True))
    assert 'name="remove"' not in buttons[0]
    assert any('aria-label="Remove Canada"' in b for b in buttons)


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


def test_build_redirects_to_calendar(client):
    response = client.post("/build", data={"add": "CA"})

    assert response.status_code == 303
    assert response.location == f"/c/{BLOB}"


def test_build_without_sources_redirects_home(client):
    response = client.post("/build", data={"s0.kind": "CA", "remove": "0"})

    assert response.location == "/"


def test_invalid_blob(client):
    response = client.get("/c/not-a-config!")

    assert response.status_code == 400


def test_https_behind_proxy(client):
    response = client.get(
        f"/c/{BLOB}",
        headers={"Accept": BROWSER_ACCEPT, "X-Forwarded-Proto": "https"},
    )

    assert f"https://localhost/c/{BLOB}".encode() in response.data


@pytest.fixture
def cold_cache():
    main.RESPONSES.clear()


@pytest.mark.usefixtures("cold_cache")
@pytest.mark.parametrize("accept", ["*/*", BROWSER_ACCEPT])
def test_repeat_requests_are_cached(client, accept):
    with mock.patch.object(merge, "build", wraps=merge.build) as build:
        first = client.get(f"/c/{BLOB}", headers={"Accept": accept})
        second = client.get(f"/c/{BLOB}", headers={"Accept": accept})

    assert build.call_count == 1
    assert first.data == second.data


def test_feed_etag(client):
    first = client.get(f"/c/{BLOB}")
    second = client.get(
        f"/c/{BLOB}", headers={"If-None-Match": first.headers["ETag"]}
    )

    assert first.headers["ETag"]
    assert second.status_code == 304
    assert not second.data


def test_feed_etag_changes_with_data_version(client):
    first = client.get(f"/c/{BLOB}")
    with mock.patch.object(main, "DATA_VERSION", "other"):
        second = client.get(
            f"/c/{BLOB}", headers={"If-None-Match": first.headers["ETag"]}
        )

    assert second.status_code == 200
    assert second.headers["ETag"] != first.headers["ETag"]


def test_service_worker(client):
    response = client.get("/sw.js")

    assert response.mimetype == "text/javascript"
    assert response.headers["Cache-Control"] == "no-cache"
    body = response.get_data(as_text=True)
    assert f'const VERSION = "{main.APP_VERSION}"' in body
    assert f"/static/app.css?v={main.APP_VERSION}" in body


def test_page_uses_versioned_assets(client):
    response = client.get("/", headers={"Accept": BROWSER_ACCEPT})

    assert f"/static/app.mjs?v={main.APP_VERSION}".encode() in response.data


def test_all_regions_disables_region_boxes(client):
    blob = config.encode(
        config_pb2.Config(
            sources=[config_pb2.Source(country="CA", all_subdivisions=True)]
        )
    )

    page = client.get(f"/c/{blob}", headers={"Accept": BROWSER_ACCEPT})

    boxes = re.findall(r"<input [^>]*data-region=[^>]*>", page.text)
    assert boxes
    assert all("disabled" in box and "checked" not in box for box in boxes)


def test_add_offers_a_select_and_an_autocomplete(client):
    page = client.get("/", headers={"Accept": BROWSER_ACCEPT}).text

    assert '<option value="CA">Canada</option>' in page
    assert 'role="combobox"' in page
    assert 'data-value="CA" data-search="Canada CA"' in page
    assert 'data-value="@jewish"' in page


def test_add_leaves_out_sources_already_added(client):
    blob = config.encode(
        config_pb2.Config(
            sources=[
                config_pb2.Source(country="CA"),
                config_pb2.Source(religion="jewish"),
            ]
        )
    )

    page = client.get(f"/c/{blob}", headers={"Accept": BROWSER_ACCEPT}).text

    assert '<option value="CA">' not in page
    assert 'data-value="CA"' not in page
    assert 'data-value="@jewish"' not in page
    assert 'data-value="US"' in page


def test_build_rejects_configs_too_long_for_a_url(client):
    data = MultiDict(
        [("s0.kind", "US"), ("s0.all_subdivisions", "1")]
        # Random names don't compress, so the URL stays long.
        + [
            ("hidden", "US:" + hashlib.sha256(str(i).encode()).hexdigest())
            for i in range(400)
        ]
    )

    response = client.post("/build", data=data)

    assert response.status_code == 400
    assert "too many hidden holidays" in response.text


def test_build_rejects_regions_on_religions(client):
    data = MultiDict(
        [
            ("s0.kind", "@jewish"),
            ("s0.all_subdivisions", "1"),
            ("drop_region", "0:XX"),
        ]
    )

    assert client.post("/build", data=data).status_code == 400


def _twenty_countries() -> config_pb2.Config:
    codes = "CA US DE FR GB IT ES MX BR AR JP KR IN AU NZ ZA EG IL TR SE"
    return config_pb2.Config(
        sources=[config_pb2.Source(country=c) for c in codes.split()]
    )


def test_build_rejections_are_plain_text(client):
    data = MultiDict(
        [
            (f"s{i}.kind", s.country)
            for i, s in enumerate(_twenty_countries().sources)
        ]
        + [("add", "NO")]
    )

    response = client.post("/build", data=data)

    assert response.status_code == 400
    assert response.mimetype == "text/plain"
    assert response.text == "More than 20 sources"


def test_add_box_is_replaced_at_the_source_limit(client):
    blob = config.encode(_twenty_countries())

    page = client.get(f"/c/{blob}", headers={"Accept": BROWSER_ACCEPT}).text

    assert 'role="combobox"' not in page
    assert "up to 20 countries and religions" in page


def test_preview_keeps_today_for_visitors_behind_utc(client):
    blob = config.encode(
        config_pb2.Config(sources=[config_pb2.Source(country="US")])
    )
    # 01:00 UTC on Nov 27 is still Thanksgiving evening in California.
    now = datetime.datetime(2026, 11, 27, 1, tzinfo=datetime.UTC)

    with mock.patch.object(
        main.datetime, "datetime", wraps=datetime.datetime
    ) as clock:
        clock.now.return_value = now
        page = client.get(f"/c/{blob}?format=html").text

    assert "Thanksgiving Day" in page


def test_versionz(client):
    response = client.get("/versionz")

    assert response.json == {
        "version": importlib.metadata.version("one-holiday-calendar")
    }


def test_favicon(client):
    page = client.get("/", headers={"Accept": BROWSER_ACCEPT})
    icon = client.get("/static/favicon.svg")

    assert b'rel="icon"' in page.data
    assert icon.mimetype == "image/svg+xml"


def test_subscribe_box_offers_webcal_and_https_feed_urls(client):
    page = client.get(f"/c/{BLOB}", headers={"Accept": BROWSER_ACCEPT}).text

    webcal = f"webcal://localhost/c/{BLOB}?format=ics"
    https = f"http://localhost/c/{BLOB}?format=ics"
    assert f'value="{webcal}" aria-label="Calendar URL"' in page
    assert f'data-url="{https}"' in page
    assert "delete it and add this new one" in page


def test_feed_links_to_the_page_it_was_served_from(client):
    response = client.get(f"/c/{BLOB}", headers={"X-Forwarded-Proto": "https"})

    calendar = icalendar.Calendar.from_ical(response.data)
    assert calendar["url"] == f"https://localhost/c/{BLOB}"
