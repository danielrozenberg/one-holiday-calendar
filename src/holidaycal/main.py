"""Web app serving the config page and the calendar feed from one URL."""

import datetime

import flask
from werkzeug import wrappers
from werkzeug.middleware import proxy_fix

from holidaycal import config
from holidaycal import config_pb2
from holidaycal import form
from holidaycal import ics
from holidaycal import merge
from holidaycal import sources

PREVIEW_DAYS = 365

app = flask.Flask(__name__)
app.wsgi_app = proxy_fix.ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


@app.get("/")
def index() -> str:
    """Shows an empty config page."""
    return _page(config_pb2.Config(), blob="")


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
def calendar(blob: str) -> flask.Response | str:
    """Serves the config page to browsers and the feed to calendar apps."""
    try:
        parsed = config.decode(blob)
    except config.InvalidConfigError as e:
        flask.abort(400, str(e))
    match _wanted_format(flask.request):
        case "ics":
            now = datetime.datetime.now(datetime.UTC)
            events = merge.build(parsed, ics.years(now.date()))
            return flask.Response(
                ics.render(events, parsed, now), mimetype="text/calendar"
            )
        case _:
            return _page(parsed, blob)


def _wanted_format(request: flask.Request) -> str:
    match request.args.get("format"):
        case "ics" | "html" as forced:
            return forced
    accepted = (mimetype for mimetype, _ in request.accept_mimetypes)
    return "html" if "text/html" in accepted else "ics"


def _page(parsed: config_pb2.Config, blob: str) -> str:
    today = datetime.datetime.now(datetime.UTC).date()
    years = ics.years(today)
    end = today + datetime.timedelta(days=PREVIEW_DAYS)
    events = [
        event
        for event in merge.build(parsed, years)
        if today <= event.date < end
    ]
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
    )
