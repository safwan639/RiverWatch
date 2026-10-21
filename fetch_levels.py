"""
RiverWatch - Stage 1: fetch live water levels for Ottawa-area river gauges.

Data source: Environment and Climate Change Canada (Water Survey of Canada)
real-time hydrometric data, via the MSC GeoMet OGC API. No API key needed.
Contains information licensed under the Open Government Licence - Canada.
"""

from datetime import datetime, timedelta, timezone

import requests

API_URL = "https://api.weather.gc.ca/collections/hydrometric-realtime/items"

# Water Survey of Canada station numbers -> readable names.
STATIONS = {
    "02KF005": "Ottawa River at Britannia",
    "02LA015": "Ottawa River at Hull",
    "02LA004": "Rideau River at Ottawa",
}

# Readings can be published up to ~6 hours after they're recorded,
# so we look back a full day to be sure we catch the latest ones.
LOOKBACK_HOURS = 24


def fetch_station(station_number: str, hours: int = LOOKBACK_HOURS) -> list[dict]:
    """Return the last `hours` of readings for one station, oldest first."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    params = {
        "STATION_NUMBER": station_number,  # filter on the server, not in Python
        "datetime": f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}",
        "limit": 1000,  # 24 h of 5-minute readings is ~288, so this is plenty
        "f": "json",
    }

    response = requests.get(API_URL, params=params, timeout=30)
    response.raise_for_status()  # turn HTTP errors (404, 500, ...) into exceptions

    features = response.json().get("features", [])
    readings = [feature["properties"] for feature in features]
    readings.sort(key=lambda r: r.get("DATETIME") or "")
    return readings


def main() -> None:
    sample = None  # one reading we keep so we can list every field the API returns

    for station_number, name in STATIONS.items():
        print(f"\n=== {name} ({station_number}) ===")

        try:
            readings = fetch_station(station_number)
        except requests.RequestException as err:
            print(f"  Request failed: {err}")
            continue

        if not readings:
            print(f"  No readings in the last {LOOKBACK_HOURS} h (gauge may be offline).")
            continue

        latest = readings[-1]
        sample = sample or latest

        print(f"  Readings in last {LOOKBACK_HOURS} h: {len(readings)}")
        print(f"  Latest reading at:  {latest.get('DATETIME')} (UTC)")
        print(f"  Water level:        {latest.get('LEVEL')} m")
        print(f"  Discharge (flow):   {latest.get('DISCHARGE')} m3/s")

    if sample:
        print("\nFields available in each reading:")
        for field in sorted(sample):
            print(f"  - {field}")


if __name__ == "__main__":
    main()