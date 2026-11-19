"""Builds a preset compression dictionary for config blobs.

A dictionary is frozen once its format is deployed: changing it breaks every
existing calendar URL. To improve it, write a new file, give it a new format
marker in `config.py`, and keep decoding the old one.

Usage:  python tools/build_dictionary.py OUT_FILE
"""

import datetime
import sys

from holidaycal import config_pb2
from holidaycal import ics
from holidaycal import merge

# Countries most likely to be picked; their hide tokens dominate long configs.
COUNTRIES = [
    "US",
    "CA",
    "GB",
    "DE",
    "FR",
    "IN",
    "AU",
    "IL",
    "MX",
    "BR",
    "ES",
    "IT",
    "NL",
    "JP",
    "PH",
    "IE",
    "NZ",
    "ZA",
    "SG",
    "CH",
    "AT",
    "BE",
    "SE",
    "PL",
]
CATEGORIES = (
    "public",
    "optional",
    "government",
    "unofficial",
    "bank",
    "school",
)
# zlib only looks back 32 KiB, so anything earlier would be wasted.
MAX_BYTES = 32 * 1024


def build() -> bytes:
    """Returns the dictionary: common strings, the most common ones last."""
    years = ics.years(datetime.date(2026, 1, 1))
    tokens: set[str] = set()
    for code in COUNTRIES:
        parsed = config_pb2.Config(
            sources=[config_pb2.Source(country=code, all_subdivisions=True)]
        )
        events = merge.build(parsed, years, include_hidden=True)
        tokens |= {token for e in events for token in merge.hide_tokens(e)}
    regional = sorted(t for t in tokens if "/" in t)
    national = sorted(t for t in tokens if "/" not in t)
    # zlib finds closer matches more cheaply, so the likeliest strings go last.
    strings = [*regional, *sorted(merge.alias_groups()), *national, *CATEGORIES]
    data = "\n".join(strings).encode()
    return data[-MAX_BYTES:]


if __name__ == "__main__":
    with open(sys.argv[1], "wb") as out:
        out.write(build())
