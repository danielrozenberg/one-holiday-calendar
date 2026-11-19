# Holiday Calendar

A no-login web app that builds a single subscribable calendar of holidays from
any mix of countries, subdivisions and religions. The whole configuration lives
in the URL, so there are no accounts and no server-side storage.

## One URL, two faces

`https://<host>/c/<blob>` and `webcal://<host>/c/<blob>` are the same URL.
Calendar apps rewrite `webcal://` to `https://` before fetching, so the server
never sees the scheme. Instead it negotiates on the request:

- `?format=html` or `?format=ics` forces a face.
- Otherwise, an `Accept` header containing `text/html` (any browser) gets the
  configuration and preview page.
- Everything else (Apple Calendar, Google Calendar, Outlook, Thunderbird) gets
  the `text/calendar` feed.

`/` shows an empty configuration page. The form submits to `/build`, which
encodes the configuration and redirects to `/c/<blob>`.

## Data source

Holidays come from [python-holidays](https://github.com/vacanza/holidays):
250 countries, 651 subdivisions and per-country holiday categories (public,
bank, optional, government, school, …). Country names are taken in English
(`en_US`) where python-holidays has a translation.

Religions (Christian, Orthodox Christian, Jewish, Islamic, Hindu) are
calendars defined in `src/holidaycal/religions.py` on top of python-holidays'
calendar mixins, which compute the dates (Easter, Hebrew, Hijri and Hindu
lunisolar calendars). Their holiday names match the countries' English names
where possible, so they merge.

## Configuration

The configuration is a protobuf message (`proto/config.proto`), serialized and
encoded as unpadded base64url. It holds:

- **Sources**: each one is either a country, with optional subdivisions (or
  all of them), categories (`public` when empty) and excluded holidays; or a
  religion, with excluded holidays.
- **Title style**: plain (`Christmas Eve`) or prefixed with the contributing
  sources (`[CA, US] Christmas Eve`), using codes or names.
- **Description options**: whether each event's description lists the
  countries (with regions, for regional holidays) and the holiday types.
- **Multi-day holidays**: one event per day (default), or one event spanning
  consecutive days that share the same name (e.g. Passover). Days whose names
  differ only by "(observed)" stay separate.

Empty and default fields cost no bytes, so a typical blob is about 40–60
characters. Field numbers are never reused; removed fields are `reserved`. The `v` field
allows a breaking change if one is ever needed. Generated code
(`src/holidaycal/config_pb2.py` and `.pyi`) is committed and refreshed with
`tools/genproto.sh`; `tools/ci.sh` fails if it is stale.

## Merging

Holidays are generated in English: each country's own variant where
python-holidays has one (`en_CA`, `en_GB`, …), US English otherwise. They are
merged on `(date, normalized name)`. Normalization lowercases, strips
punctuation and "(observed)" / "(estimated)" markers, and maps names of the same
holiday through `src/holidaycal/aliases.toml` (e.g. "Labour Day" and "Labor
Day", "Pesach" and "Passover", regional variants of Martin Luther King Jr. Day).
The aliases were curated from a scan of every country, region and category for
same-date names that look alike; an alias is added only when both names are the
same holiday. Aliases never chain, and keys stay sorted (both are tested).

A merged event is named after its first occurrence, so the name comes from the
top-most configured source: [US, CA] gives "Labor Day", [CA, US] "Labour Day".
It remembers every source, subdivision and category it came from.

Each event's UID is a hash of its date and merge key, so it is stable across
refreshes and across configurations. Hiding a holiday stores its merge key; a
holiday also stays hidden when its unaliased key matches, so adding an alias
does not unhide holidays in existing URLs.

## Feed

All-day events from the start of the previous year to the end of the year
after next, with a one-day refresh hint (`REFRESH-INTERVAL`,
`X-PUBLISHED-TTL`).

## Development

- Environment: pyenv Python 3.13 with a `.venv` built from it
  (`pip install -e '.[dev]'`).
- `./tools/ci.sh`: format check, lint, type check, protobuf freshness, tests.
- `./tools/genproto.sh`: regenerates `config_pb2.py` after editing the proto.
- `./tools/dev.sh`: local server in debug mode, restarting whenever Python
  code, templates, static assets or `aliases.toml` change.

## Deployment

App Engine standard, `python313` runtime (`app.yaml`). App Engine installs
`requirements.txt`, which installs this package (`.`) so its dependencies stay
pinned in `pyproject.toml` alone. `.gcloudignore` keeps tests and tooling out
of the upload.

    gcloud app deploy

## Settings

Tunable values live in `src/holidaycal/settings.toml`, which is deployed with
the code and validated at startup by `settings.py` (pydantic models; unknown
keys are rejected). They cover URL limits, the feed's name, refresh interval
and year window, the preview length, the offline page count and the cache
budget. Values that change what existing URLs mean (such as the default
`public` category) stay in code.

## Caching

Each instance keeps rendered feeds and pages in a byte-budgeted LRU cache
(`cache.ByteCache`, budget `cache.budget_mb` in `settings.toml`). Feeds are
keyed by the blob and the covered years; pages by the blob, the day and the
host. Values are the response bytes, so the budget is the real memory used:
200 MB holds about 100 of the heaviest allowed configs, or thousands of
typical ones, within an F1 instance's 384 MB. A response larger than the whole
budget is served but not kept.

Feeds also carry an `ETag` derived from the python-holidays version, a hash of
this package's files (`APP_VERSION`), the blob and the covered years, so
calendar apps that revalidate get `304 Not Modified` until the data or the
year window changes. Responses are not marked publicly cacheable, because the
same URL serves HTML or ICS depending on `Accept`.

## Page behaviour

The config page works without JavaScript: every change is a form POST to
`/build` followed by a redirect. With JavaScript, `static/app.js` sends the same
POST in the background, swaps in the new `#app` content, keeps open sections
and focus, and updates the address bar. Sources are submitted in page order, so
reordering (↑/↓ buttons, which also work without JavaScript, or the drag
handle) just moves them in the page before submitting.

The "Event format" card looks like a calendar event and doubles as the format
controls: clicking the title opens a popover (Popover API, anchored with CSS
anchor positioning where supported) listing every title style rendered for the
shown event, and each description line has its own checkbox. It shows the most
varied holiday in the preview by default (most sources, then regions and types),
or a sample Christmas Eve when nothing is selected. Hovering or focusing a
preview row shows that holiday instead; clicking a row pins it for the browser
tab's session (`sessionStorage`), and clicking again unpins it. Every card line stays on one line (overflow is
cut off with an ellipsis, with the full text as a tooltip), so previewing a
holiday never changes the card's height or moves the preview below it. Each
row carries its card content (title in every style, date, description lines) as JSON, so
previews need no server round trip. Updates animate with the View Transitions
API where available.

A service worker (`/sw.js`, rendered from `templates/sw.js`) serves the CSS and
JS from cache and pages network-first, falling back to the last 20 cached pages
offline. Static URLs carry `?v=<APP_VERSION>`, and the worker's cache is named
after it, so any code or asset change replaces the cache.
