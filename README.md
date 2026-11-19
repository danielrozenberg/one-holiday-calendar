# One Holiday Calendar

One subscribable calendar of holidays from any mix of countries, regions and
religions. Pick your sources, hide the holidays you don't want, choose how event
titles look, and add the result to Google Calendar, Apple Calendar or Outlook.
Holidays shared between sources, like Christmas Day, show up once.

There are no accounts: the whole configuration lives in the calendar's URL.
The same URL shows the configuration page in a browser and serves the
`webcal://` feed to calendar apps.

> [![Made primarily by AI](docs/made-primarily-by-ai.svg)](https://ailabels.org/#made-primarily-by-ai)

## How it works

- Holiday data comes from
  [python-holidays](https://github.com/vacanza/holidays): 250 countries, their
  regions and holiday types, plus Christian, Orthodox, Jewish, Islamic and Hindu
  calendars.
- Holidays with different names in different places ("Labour Day" and "Labor
  Day", "Pesach" and "Passover") are merged through a curated alias list.
- The configuration is a protobuf message, compressed with DEFLATE and a preset
  dictionary, and encoded as base64url in the URL path.
- It runs on Google App Engine (Python, Flask). The page needs no JavaScript
  build step.

See [docs/DESIGN.md](docs/DESIGN.md) for the details.

## Development

Needs Python 3.13 (via pyenv) and, for the browser tests, Node and Google
Chrome.

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
./tools/dev.sh          # local server that reloads on changes
./tools/ci.sh           # format, lint, type check and all tests
./tools/deploy.sh       # CI, then deploy to App Engine
```

## License

[ISC](LICENSE)
