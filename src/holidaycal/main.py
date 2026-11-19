"""Web app serving the config page and the calendar feed from one URL."""

import datetime
import hashlib
import pathlib

import flask
import holidays
from werkzeug import wrappers
from werkzeug.middleware import proxy_fix

from holidaycal import cache
from holidaycal import config
from holidaycal import config_pb2
from holidaycal import form
from holidaycal import ics
from holidaycal import merge
from holidaycal import settings
from holidaycal import sources

STATIC_ASSETS = ("app.css", "app.js")


def _app_version() -> str:
    digest = hashlib.sha256()
    package = pathlib.Path(__file__).parent
    for path in sorted(package.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            digest.update(path.relative_to(package).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


APP_VERSION = _app_version()
# Changes whenever the holiday data or this app's code or assets change.
DATA_VERSION = f"{holidays.__version__}/{APP_VERSION}"

# shortcut: per-instance cache; use a shared cache if instances multiply.
RESPONSES = cache.ByteCache(settings.CURRENT.cache.budget_mb * 2**20)

app = flask.Flask(__name__)
app.wsgi_app = proxy_fix.ProxyFix(app.wsgi_app, x_proto=1)


@app.context_processor
def _versioned_static() -> dict[str, str]:
    return {"version": APP_VERSION}


@app.get("/sw.js")
def service_worker() -> flask.Response:
    """Serves the service worker from the root so it controls every page."""
    assets = [
        flask.url_for("static", filename=name, v=APP_VERSION)
        for name in STATIC_ASSETS
    ]
    response = flask.Response(
        flask.render_template(
            "sw.js",
            assets=assets,
            max_pages=settings.CURRENT.page.offline_pages,
        ),
        mimetype="text/javascript",
    )
    response.cache_control.no_cache = True
    return response


@app.get("/")
def index() -> bytes:
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
def calendar(blob: str) -> wrappers.Response | bytes:
    """Serves the config page to browsers and the feed to calendar apps."""
    try:
        config.decode(blob)
    except config.InvalidConfigError as e:
        flask.abort(400, str(e))
    match _wanted_format(flask.request):
        case "ics":
            years = ics.years(datetime.datetime.now(datetime.UTC).date())
            body = RESPONSES.get(
                ("feed", blob, years), lambda: _render_feed(blob, years)
            )
            response = flask.Response(body, mimetype="text/calendar")
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


def _render_feed(blob: str, years: range) -> bytes:
    parsed = config.decode(blob)
    now = datetime.datetime.now(datetime.UTC)
    return ics.render(merge.build(parsed, years), parsed, now)


def _page(blob: str) -> bytes:
    today = datetime.datetime.now(datetime.UTC).date()
    key = ("page", blob, today, flask.request.host_url)
    return RESPONSES.get(key, lambda: _render_page(blob, today))


def _render_page(blob: str, today: datetime.date) -> bytes:
    parsed = config.decode(blob)
    years = ics.years(today)
    end = today + datetime.timedelta(days=settings.CURRENT.page.preview_days)
    events = [e for e in merge.build(parsed, years) if today <= e.date < end]
    path = flask.url_for("calendar", blob=blob) if blob else ""
    return flask.render_template(
        "index.html",
        events=events,
        config=parsed,
        title=ics.title,
        title_styles=config_pb2.TitleStyle,
        sources=form.views(parsed, years),
        countries=sources.country_names(),
        religions=form.religion_names(),
        https_url=flask.request.host_url.rstrip("/") + path if path else "",
        webcal_url=f"webcal://{flask.request.host}{path}" if path else "",
    ).encode()
