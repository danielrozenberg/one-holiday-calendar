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

Empty and default fields cost no bytes, so a typical blob is about 40–60
characters. Field numbers are never reused; removed fields are `reserved`. The `v` field
allows a breaking change if one is ever needed. Generated code
(`src/holidaycal/config_pb2.py` and `.pyi`) is committed and refreshed with
`tools/genproto.sh`; `tools/ci.sh` fails if it is stale.

## Merging

Holidays are generated with English names and merged on
`(date, normalized name)`. Normalization lowercases, strips punctuation and
"(observed)" and "(estimated)" markers, and maps known spelling variants through
`src/holidaycal/aliases.toml` (e.g. "Labour Day" and "Labor Day"). A merged
event remembers every source, subdivision and category it came from.

Each event's UID is a hash of its merge key, so it is stable across refreshes
and across configurations. Excluding a holiday uses its normalized name, which
is stable across years.

## Feed

All-day events from the start of the previous year to the end of the year
after next, with a one-day refresh hint (`REFRESH-INTERVAL`,
`X-PUBLISHED-TTL`).

## Development

- Environment: pyenv Python 3.13 with a `.venv` built from it
  (`pip install -e '.[dev]'`).
- `./tools/ci.sh`: format check, lint, type check, protobuf freshness, tests.
- `./tools/genproto.sh`: regenerates `config_pb2.py` after editing the proto.
- `flask --app holidaycal.main run`: local server.

## Deployment

App Engine standard, `python313` runtime (`app.yaml`). App Engine installs
`requirements.txt`, which installs this package (`.`) so its dependencies stay
pinned in `pyproject.toml` alone. `.gcloudignore` keeps tests and tooling out
of the upload.

    gcloud app deploy

## Caching

Each instance keeps the last 32 built feeds and page data in memory, keyed by
the blob and the covered years. Feeds also carry an `ETag` derived from the
python-holidays version, the App Engine deployment (`GAE_VERSION`), the blob
and the covered years, so calendar apps that revalidate get `304 Not Modified`
until the data or the year window changes. Responses are not marked publicly
cacheable, because the same URL serves HTML or ICS depending on `Accept`.
