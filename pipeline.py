"""
RiverWatch - Stage 2: load river readings into PostgreSQL.

Fetches the last 24 h of readings for each gauge and "upserts" them:
new readings are inserted, readings we already have are updated only if
their values changed, and nothing is ever duplicated. That makes the
script safe to run as many times as you like.
"""

from datetime import datetime

import requests

from db import get_connection
from fetch_levels import STATIONS, fetch_station

UPSERT_STATION_SQL = """
    insert into stations (station_number, station_name, province)
    values (%s, %s, %s)
    on conflict (station_number) do update
        set station_name = excluded.station_name,
            province     = excluded.province
"""

# If (station_number, observed_at) already exists, update it instead of
# inserting a duplicate - but only when a value actually changed, so
# last_updated_at reflects real revisions. RETURNING tells us which happened:
# (xmax = 0) is true for a fresh insert and false for an update.
UPSERT_READING_SQL = """
    insert into readings (station_number, observed_at, level_m, discharge_m3s,
                          level_symbol, discharge_symbol)
    values (%s, %s, %s, %s, %s, %s)
    on conflict (station_number, observed_at) do update
        set level_m          = excluded.level_m,
            discharge_m3s    = excluded.discharge_m3s,
            level_symbol     = excluded.level_symbol,
            discharge_symbol = excluded.discharge_symbol,
            last_updated_at  = now()
        where (readings.level_m, readings.discharge_m3s,
               readings.level_symbol, readings.discharge_symbol)
              is distinct from
              (excluded.level_m, excluded.discharge_m3s,
               excluded.level_symbol, excluded.discharge_symbol)
    returning (xmax = 0) as inserted
"""


def to_row(reading: dict) -> tuple:
    """Turn one API reading into a row for the readings table."""
    return (
        reading["STATION_NUMBER"],
        datetime.fromisoformat(reading["DATETIME"]),  # "2026-10-21T14:35:00Z" -> datetime
        reading.get("LEVEL"),
        reading.get("DISCHARGE"),
        reading.get("LEVEL_SYMBOL_EN"),
        reading.get("DISCHARGE_SYMBOL_EN"),
    )


def upsert_readings(cur, rows: list[tuple]) -> tuple[int, int]:
    """Upsert all rows in one batch. Returns (inserted, revised) counts."""
    if not rows:
        return 0, 0

    cur.executemany(UPSERT_READING_SQL, rows, returning=True)

    inserted = revised = 0
    while True:  # one result per row; unchanged rows return nothing
        result = cur.fetchone()
        if result is not None:
            if result[0]:
                inserted += 1
            else:
                revised += 1
        if not cur.nextset():
            break
    return inserted, revised


def main() -> None:
    total_fetched = total_inserted = total_revised = 0

    # Everything happens in one transaction: if anything crashes,
    # the database rolls back to how it was before the run.
    with get_connection() as conn, conn.cursor() as cur:
        for station_number, fallback_name in STATIONS.items():
            try:
                readings = fetch_station(station_number)
            except requests.RequestException as err:
                print(f"{station_number}: fetch failed, skipping ({err})")
                continue

            if not readings:
                print(f"{station_number}: no readings returned, skipping")
                continue

            first = readings[0]
            cur.execute(UPSERT_STATION_SQL, (
                station_number,
                first.get("STATION_NAME") or fallback_name,
                first.get("PROV_TERR_STATE_LOC") or "ON",
            ))

            rows = [to_row(r) for r in readings]
            inserted, revised = upsert_readings(cur, rows)
            unchanged = len(rows) - inserted - revised
            print(f"{station_number}: fetched {len(rows)} | "
                  f"new {inserted} | revised {revised} | unchanged {unchanged}")

            total_fetched += len(rows)
            total_inserted += inserted
            total_revised += revised

    print(f"\nDone. Fetched {total_fetched}, new {total_inserted}, revised {total_revised}.")


if __name__ == "__main__":
    main()