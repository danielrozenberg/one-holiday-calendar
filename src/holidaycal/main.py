"""Web app serving the config page and the calendar feed from one URL."""

import datetime
import functools
import hashlib
import os

import flask
import holidays
from werkzeug import wrappers
from werkzeug.middleware import proxy_fix

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import form
from holidaycal import ics
from holidaycal import merge
from holidaycal import sources

PREVIEW_DAYS = 365
# shortcut: per-instance LRU caches; use a shared cache if instances multiply.
CACHE_SIZE = 32
# Changes whenever the holiday data or this app is redeployed.
DATA_VERSION = f"{holidays.__version__}/{os.environ.get('GAE_VERSION', 'dev')}"

app = flask.Flask(__name__)
app.wsgi_app = proxy_fix.ProxyFix(app.wsgi_app, x_proto=1)


@app.get("/")
def index() -> str:
    """Shows an empty config page."""
    return _page(blob="")


@app.post("/build")
def build() -> wrappers.Response:
    """Encodes the submitted form and redirects to its calendar URL."""
    try:
        parsed = form.parse(flask.request.form)
    except config.InvalidConfigError as e:
        flask.abort(400, str(e))
    if not parsed.sources:
        return flask.redirect(flask.url_for("index"), code=303)
    blob = config.encode(parsed)
    return flask.redirect(flask.url_for("calendar", blob=blob), code=303)


@app.get("/c/<blob>")
def calendar(blob: str) -> wrappers.Response | str:
    """Serves the config page to browsers and the feed to calendar apps."""
    try:
        config.decode(blob)
    except config.InvalidConfigError as e:
        flask.abort(400, str(e))
    match _wanted_format(flask.request):
        case "ics":
            years = ics.years(datetime.datetime.now(datetime.UTC).date())
            response = flask.Response(
                _feed(blob, years), mimetype="text/calendar"
            )
            etag = f"{DATA_VERSION}|{blob}|{years.start}-{years.stop}"
            response.set_etag(hashlib.sha256(etag.encode()).hexdigest())
            return response.make_conditional(flask.request)
        case _:
            return _page(blob)


def _wanted_format(request: flask.Request) -> str:
    match request.args.get("format"):
        case "ics" | "html" as forced:
            return forced
    accepted = (mimetype for mimetype, _ in request.accept_mimetypes)
    return "html" if "text/html" in accepted else "ics"


@functools.lru_cache(maxsize=CACHE_SIZE)
def _feed(blob: str, years: range) -> bytes:
    parsed = config.decode(blob)
    now = datetime.datetime.now(datetime.UTC)
    return ics.render(merge.build(parsed, years), parsed, now)


@functools.lru_cache(maxsize=CACHE_SIZE)
def _page_data(
    blob: str, years: range
) -> tuple[config_pb2.Config, list[merge.Event], list[form.SourceView]]:
    parsed = config.decode(blob)
    return parsed, merge.build(parsed, years), form.views(parsed, years)


def _page(blob: str) -> str:
    today = datetime.datetime.now(datetime.UTC).date()
    parsed, all_events, views = _page_data(blob, ics.years(today))
    end = today + datetime.timedelta(days=PREVIEW_DAYS)
    events = [e for e in all_events if today <= e.date < end]
    path = flask.url_for("calendar", blob=blob) if blob else ""
    return flask.render_template(
        "index.html",
        events=events,
        config=parsed,
        title=ics.title,
        title_styles=config_pb2.TitleStyle,
        sources=views,
        countries=sources.country_names(),
        religions=form.religion_names(),
        https_url=flask.request.host_url.rstrip("/") + path if path else "",
        webcal_url=f"webcal://{flask.request.host}{path}" if path else "",
    )
