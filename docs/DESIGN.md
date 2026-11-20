# One Holiday Calendar

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

The page's "Add to calendar app" link is the `webcal://` URL with
`?format=ics`, so calendar apps get the feed whatever `Accept` header they send.

`/` shows an empty configuration page. The form submits to `/build`, which
encodes the configuration and redirects to `/c/<blob>`.

`/versionz` returns `{"version": "<version>"}`, the `version` in
`pyproject.toml` of the deployed package.

## Data source

Holidays come from [python-holidays](https://github.com/vacanza/holidays):
250 countries, 651 subdivisions and per-country holiday categories (public,
bank, optional, government, school, …). Country names are taken in English
(`en_US`) where python-holidays has a translation.

Religions (Christian, Orthodox Christian, Jewish, Islamic, Hindu) are
calendars defined in `src/one_holiday_calendar/religions.py` on top of python-holidays'
calendar mixins, which compute the dates (Easter, Hebrew, Hijri and Hindu
lunisolar calendars). Their holiday names match the countries' English names
where possible, so they merge.

## Configuration

The configuration is a protobuf message (`proto/config.proto`), carried in the
URL as a one-character format marker followed by unpadded base64url:

- `A`: the serialized protobuf as is.
- `B`: the serialized protobuf compressed with raw DEFLATE and the preset
  dictionary `src/one_holiday_calendar/config_dictionary_v1.txt` (common hide tokens,
  alias ids and category names, built by `tools/build_dictionary.py`).

`encode` picks the shorter. Measured on random realistic configs, `B` halves
the median URL and cuts the longest ones by about 70% (hidden holidays
compress best); tiny configs stay `A`. Compressing JSON instead of protobuf, or
using bzip2, LZMA, Brotli or Zstandard without a dictionary, did worse. A
dictionary is frozen once deployed (a test pins its hash): an improved one gets
a new marker, and old markers keep decoding. Decoding caps the decompressed
size at 64 KiB. It holds:

- **Sources**: each one is either a country, with optional subdivisions (or
  all of them) and categories (`public` when empty); or a religion.
- **Hidden holidays**: entries of the form `<source>[/<region>]:<merge key>`
  (e.g. `US:independence day`, `US/PR:emancipation_day`,
  `@christian:christmas_day`). Hiding is per source and region because a merge
  key can mean different holidays elsewhere, such as every country's
  "Independence Day", or Emancipation Day in Puerto Rico, DC and the Virgin
  Islands.
- **Title style**: plain (`Christmas Eve`), or with the contributing sources
  as a prefix or suffix, using codes, names or flags (`[CA, US] Christmas Eve`,
  `Christmas Eve 🇨🇦🇺🇸`). A holiday from `global_sources` (4) or more sources is
  labelled `Global` (🌍 for flags) instead, there and in descriptions and the
  preview.
- **Description options**: whether each event's description lists the
  countries (with regions, for regional holidays) and the holiday types.
- **Multi-day holidays**: one event per day (default), or one event spanning
  consecutive days that share the same name (e.g. Passover). Days whose names
  differ only by "(observed)" stay separate.

Empty and default fields cost no bytes, so a typical blob is about 40–60
characters. Field numbers are never reused; removed fields are `reserved`. The `v` field
allows a breaking change if one is ever needed. Generated code
(`src/one_holiday_calendar/config_pb2.py` and `.pyi`) is committed and refreshed with
`tools/genproto.sh`; `tools/ci.sh` fails if it is stale.

## Merging

Holidays are generated in English: each country's own variant where
python-holidays has one (`en_CA`, `en_GB`, …), US English otherwise. They are
merged on `(date, merge key)`. The merge key is the name lowercased, without
punctuation or "(observed)" / "(estimated)" markers, unless that name belongs to
a holiday in `src/one_holiday_calendar/aliases.toml`, in which case it is that holiday's
id (e.g. `labor_day` for "Labour Day", "Workers' Day" and "Labor Day").

Each holiday in `aliases.toml` lists its names as tiers in order of preference:

```toml
labor_day = [
  ["labor day", "labour day"],
  ["international workers day", "workers day"],
  ...
]
```

A merged event takes the name of the occurrence in the earliest tier; within a
tier, the top-most configured source wins. So [US, CA] gives "Labor Day" and
[CA, US] "Labour Day", while "Christmas Eve" beats "Christmas Eve (from 12pm)"
whatever the order. The aliases were curated from a scan of every country,
region and category for same-date names that look alike, and only join names of
the same holiday. Ids stay sorted and a name belongs to one holiday at most
(both are tested). A merged event remembers every source, subdivision and
category it came from.

Each event's UID is a hash of its date and merge key, so it is stable across
refreshes and across configurations.

## Feed

All-day events from ten years back to thirty years ahead
(`feed.years_before` and `feed.years_after`), with a one-day refresh hint (`REFRESH-INTERVAL`,
`X-PUBLISHED-TTL`). The calendar's description (`DESCRIPTION`, `X-WR-CALDESC`)
and `URL` link back to its config page, on the host the feed was served from.

## Development

- Environment: pyenv Python 3.13 with a `.venv` built from it
  (`pip install -e '.[dev]'`).
- `./tools/ci.sh`: format check, lint, type check, protobuf freshness, tests,
  and browser tests (`tests/browser/run.mjs`, when `node` and `google-chrome`
  are installed). The browser tests start the app and a headless Chrome on
  free local ports and drive the page over the DevTools protocol; the page
  fires `app:updated` after each in-place update so they can wait for it.
- `./tools/genproto.sh`: regenerates `config_pb2.py` after editing the proto.
- `./tools/dev.sh`: local server in debug mode, restarting whenever Python
  code, templates, static assets or `aliases.toml` change.

## Deployment

App Engine standard, `python313` runtime (`app.yaml`). App Engine installs
`requirements.txt`, which installs this package (`.`) so its dependencies stay
pinned in `pyproject.toml` alone. `.gcloudignore` keeps tests and tooling out
of the upload.

    ./tools/deploy.sh

It runs the CI gate, then `gcloud app deploy` to the `one-holiday-calendar`
project; extra flags (e.g. `--no-promote`) are passed through.

Monitoring mirrors nyc-city-bike-at-a-glance and is set up once with
`ALERT_EMAIL=… ./tools/setup_monitoring.sh`: an email channel, an uptime check
on `/versionz` every minute, and alerts when that check fails, when more than
two errors are logged in 5 minutes, or when a second instance is billed for
2×15 minutes (`min_instances: 1` keeps one running, within the free tier).

## Settings

Tunable values live in `src/one_holiday_calendar/settings.toml`, which is deployed with
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
`/build` followed by a redirect. With JavaScript, `static/app.mjs` sends the same
POST in the background, swaps in the new `#app` content, keeps open sections
and focus, and pushes the new URL as a history entry; Back and Forward fetch
that entry's URL and swap its content in the same way. Sources are submitted in page order, so
reordering (↑/↓ buttons, which also work without JavaScript, or the drag
handle) just moves them in the page before submitting.

Each preview row has an eye button (greyed out while hidden) that hides or
shows the row for every source contributing to it. Hidden holidays stay in the preview, dimmed, so they can be shown
again; a "Show all" button clears the list. When every holiday a country, one of
its regions, or one of its types contributes (over the preview's years) is hidden,
that source's card shows a notice with a button to remove the country, region or
type from the config.

The "Event format" card looks like a calendar event and doubles as the format
controls: clicking the title opens a popover (Popover API, anchored with CSS
anchor positioning where supported) listing every title style rendered for the
shown event, and each description line has its own checkbox. It shows the most
varied holiday in the preview by default (most sources, then regions and types),
or a sample Christmas Eve when nothing is selected. Hovering or focusing a
preview row shows that holiday instead, and clicking a row shows or hides it,
like its eye button. Every card line stays on one line (overflow is
cut off with an ellipsis, with the full text as a tooltip), so previewing a
holiday never changes the card's height or moves the preview below it. Each
row carries its card content (title in every style, date, description lines) as JSON, so
previews need no server round trip. Updates animate with the View Transitions
API where available.

Countries and religions are added through an autocomplete box (the ARIA
combobox pattern): focusing it lists everything, typing filters by name or code
(ignoring accents), and arrow keys, Enter and Escape work as expected. It writes
the choice into a plain `<select>`, which pages without JavaScript use directly.

A service worker (`/sw.js`, rendered from `templates/sw.js`) serves the CSS and
JS from cache and pages network-first, falling back to the last 20 cached pages
offline. Static URLs carry `?v=<APP_VERSION>`, and the worker's cache is named
after it, so any code or asset change replaces the cache.
