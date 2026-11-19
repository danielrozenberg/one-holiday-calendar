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
250 countries, 651 subdivisions, per-country holiday categories (public, bank,
optional, government, school, …) and religious calendars.

## Configuration

The configuration is a protobuf message (`proto/config.proto`), serialized and
encoded as unpadded base64url. It holds:

- **Sources**: each one is a country with optional subdivisions, a set of
  categories, and a list of excluded holidays; or a religion.
- **Title style**: plain (`Christmas Eve`) or prefixed with the contributing
  sources (`[CA, US] Christmas Eve`), using codes or names.
- **Description options**: which details (sources, categories, local names)
  to list in each event's description.

Field numbers are never reused; removed fields are `reserved`. The `v` field
allows a breaking change if one is ever needed. Generated code
(`src/holidaycal/config_pb2.py` and `.pyi`) is committed and refreshed with
`tools/genproto.sh`; `tools/ci.sh` fails if it is stale.

## Merging

Holidays are generated with English names and merged on
`(date, normalized name)`. Normalization lowercases, strips punctuation and
"(observed)" markers, and maps known spelling variants through
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

- `./tools/ci.sh`: format check, lint, type check, tests.
- `flask --app holidaycal.main run`: local server.
