"""
Hutt City Council / open-data-huttcity.hub.arcgis.com
Source for hacs_waste_collection_schedule

Queries the HCC Open Data ArcGIS service to determine recycling and green
waste collection zones, then calculates future collection dates.

Public holidays are fetched dynamically from date.nager.at (free, no key).
Only Good Friday, Christmas Day, and New Year's Day shift collection to the
following Saturday — all other NZ public holidays collect as normal (HCC policy).

Data sources:
  Recycling/Glass zones:
    https://open-data-huttcity.hub.arcgis.com/datasets/64e6414e56ce4d379ce532960fe592b3_0
  Green Waste zones:
    (same ArcGIS service, separate layer — not yet in open data; schedule
     derived from toogoodtowaste.co.nz/bin-enquiries/collection-zones-and-calendars)
"""

import datetime
import logging

import requests

from waste_collection_schedule import Collection
from waste_collection_schedule.exceptions import (
    SourceArgumentNotFound,
    SourceArgumentNotFoundWithSuggestions,
)

_LOGGER = logging.getLogger(__name__)

TITLE = "Hutt City Council / open-data-huttcity.hub.arcgis.com"
DESCRIPTION = "Source for Hutt City Council, Lower Hutt, New Zealand"
URL = "open-data-huttcity.hub.arcgis.com"
COUNTRY = "nz"

TEST_CASES = {
    "Petone Tue Zone 1 (lat/lon)": {
        "lat": -41.22744517583203,
        "lon": 174.87867480938988,
    },
    "Petone (address)": {
        "address": "20 Buick Street, Petone, Lower Hutt",
    },
    "Naenae (address)": {
        "address": "100 Oxford Terrace, Naenae, Lower Hutt",
    },
    "Eastbourne (address)": {
        "address": "45 Marine Parade, Eastbourne, Lower Hutt",
    },
}

ICON_MAP = {
    "Rubbish":     "mdi:trash-can",
    "Recycling":   "mdi:recycle",
    "Glass":       "mdi:bottle-soda",
    "Green Waste": "mdi:leaf",
}

HOW_TO_GET_ARGUMENTS_DESCRIPTION = {
    "en": (
        "Enter your street address within Lower Hutt / Te Awa Kairangi ki Tai, "
        "for example '20 Buick Street, Petone, Lower Hutt'. "
        "Alternatively, provide your property's latitude and longitude directly "
        "(right-click your address in Google Maps → 'What's here?')."
    ),
}

PARAM_DESCRIPTIONS = {
    "en": {
        "address": (
            "Your full street address within Lower Hutt. "
            "Not required if lat and lon are provided."
        ),
        "lat": "Latitude of your property (optional, alternative to address).",
        "lon": "Longitude of your property (optional, must be used with lat).",
    }
}

# ---------------------------------------------------------------------------
# External API endpoints
# ---------------------------------------------------------------------------

ARCGIS_QUERY_URL = (
    "https://services1.arcgis.com/DlsnLEhGfXazS5Er/arcgis/rest/services"
    "/Rubbish_and_recycling_collection_days/FeatureServer/0/query"
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "hacs_waste_collection_schedule toogoodtowaste_co_nz"}
NAGER_DATE_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/NZ"

# HCC only shifts collection for these three holidays (all others collect as normal)
HCC_SHIFTED_HOLIDAYS = {"Good Friday", "Christmas Day", "New Year's Day"}

# ---------------------------------------------------------------------------
# Anchor dates — recycling / glass
#
# The ArcGIS data returns Collection_Zone (1 or 2) and Collection_Day
# (Monday–Friday). These are independent:
#   Zone  → which FORTNIGHT recycling/glass falls on
#   Day   → which DAY OF THE WEEK within that fortnight's week
#
# Reference: Zone 1 glass confirmed on the week of 2026-04-07 (Tuesday).
# The Monday of that week = 2026-04-06.
# Zone 2 is the opposite fortnight, so its glass week Monday = 2026-04-13.
#
# To get the anchor for any property:
#   anchor = zone_week_monday + weekday_offset(Collection_Day)
# ---------------------------------------------------------------------------

WEEKDAY_OFFSET = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4,
}

# Monday of the reference week for recycling zone/type combinations
_RECYCLING_ZONE_WEEK_MONDAYS = {
    (1, "glass"):       datetime.date(2026, 4, 6),
    (1, "recycling"):   datetime.date(2026, 4, 13),
    (2, "glass"):       datetime.date(2026, 4, 13),
    (2, "recycling"):   datetime.date(2026, 4, 6),
}

# ---------------------------------------------------------------------------
# Anchor dates — green waste
#
# Green waste has 4 independent zones per day, completely separate from the
# recycling zones. The ArcGIS recycling layer does NOT contain green waste
# zone data, so we cannot look it up programmatically.
#
# Instead we derive it from the published toogoodtowaste.co.nz zone maps.
# Green waste is collected every 4 weeks.
#
# The anchor is the Monday of the reference week for each green waste zone,
# derived from the 2026 calendar. Zone 1 green waste for Tuesday was confirmed
# as aligning with recycling Zone 1 (week of 2026-04-13).
#
# NOTE: Green waste zone numbers are NOT the same as recycling zone numbers.
# A property in recycling Zone 1 may be in green waste Zone 2, 3, or 4.
# Since the ArcGIS data doesn't expose green waste zones, we cannot determine
# the correct green waste zone programmatically.
#
# We therefore generate green waste entries for ALL 4 zones and label them
# clearly so users can identify which one matches their bin by checking
# toogoodtowaste.co.nz/bin-enquiries/collection-zones-and-calendars, then
# use the `types` filter in configuration to show only their correct zone.
#
# Confirmed anchor week Mondays (from 2026 calendar, all zones cycle 4-weekly):
#   Green Zone 1: week of 2026-04-06 (confirmed offset from recycling anchors)
#   Green Zone 2: week of 2026-04-13
#   Green Zone 3: week of 2026-04-20
#   Green Zone 4: week of 2026-04-27
# ---------------------------------------------------------------------------

_GREEN_ZONE_WEEK_MONDAYS = {
    1: datetime.date(2026, 4, 6),
    2: datetime.date(2026, 4, 13),
    3: datetime.date(2026, 4, 20),
    4: datetime.date(2026, 4, 27),
}

_LOOKAHEAD_WEEKS = 52


# ---------------------------------------------------------------------------
# Source class
# ---------------------------------------------------------------------------

class Source:
    def __init__(self, address: str = None, lat: float = None, lon: float = None):
        if address is None and (lat is None or lon is None):
            raise ValueError("Provide either 'address' or both 'lat' and 'lon'.")
        self._address = address
        self._lat = float(lat) if lat is not None else None
        self._lon = float(lon) if lon is not None else None

    def fetch(self) -> list[Collection]:
        lat, lon = self._resolve_coordinates()
        recycling_zone, collection_day = self._query_arcgis(lat, lon)
        _LOGGER.debug(
            "HCC bin collection: recycling_zone=%s day=%s for (%.5f, %.5f)",
            recycling_zone, collection_day, lat, lon,
        )
        public_holidays = self._fetch_public_holidays()
        return self._build_entries(recycling_zone, collection_day, public_holidays)

    # ------------------------------------------------------------------
    # Coordinate resolution
    # ------------------------------------------------------------------

    def _resolve_coordinates(self) -> tuple[float, float]:
        if self._lat is not None and self._lon is not None:
            return self._lat, self._lon
        return self._geocode(self._address)

    def _geocode(self, address: str) -> tuple[float, float]:
        query = address
        if not any(s in address.lower() for s in ("new zealand", "lower hutt", "nz")):
            query = f"{address}, Lower Hutt, New Zealand"
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "nz"},
            headers=NOMINATIM_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            raise SourceArgumentNotFound("address", address)
        return float(results[0]["lat"]), float(results[0]["lon"])

    # ------------------------------------------------------------------
    # ArcGIS query
    # ------------------------------------------------------------------

    def _query_arcgis(self, lat: float, lon: float) -> tuple[int, str]:
        resp = requests.get(
            ARCGIS_QUERY_URL,
            params={
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "Collection_Zone,Collection_Day",
                "returnGeometry": "false",
                "f": "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            raise SourceArgumentNotFoundWithSuggestions(
                "address",
                f"coordinates ({lat:.5f}, {lon:.5f})",
                suggestions=[
                    "Ensure the address is within Lower Hutt / Te Awa Kairangi ki Tai.",
                    "Try providing lat/lon coordinates directly instead of an address.",
                ],
            )
        attrs = features[0]["attributes"]
        return int(attrs["Collection_Zone"]), str(attrs["Collection_Day"])

    # ------------------------------------------------------------------
    # Public holidays — dynamic via Nager.Date
    # ------------------------------------------------------------------

    def _fetch_public_holidays(self) -> set[datetime.date]:
        """
        Fetch NZ public holidays for the current and next year from Nager.Date,
        filtered to only the three holidays that HCC shifts collection for:
        Good Friday, Christmas Day, New Year's Day.
        Falls back to an empty set if the API is unreachable, so collection
        dates are still returned (just without holiday shifting).
        """
        today = datetime.date.today()
        years = {today.year, today.year + 1}
        holidays: set[datetime.date] = set()

        for year in years:
            try:
                resp = requests.get(
                    NAGER_DATE_URL.format(year=year),
                    timeout=10,
                )
                resp.raise_for_status()
                for h in resp.json():
                    if h.get("name") in HCC_SHIFTED_HOLIDAYS:
                        holidays.add(datetime.date.fromisoformat(h["date"]))
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not fetch NZ public holidays for %s from Nager.Date: %s. "
                    "Collection dates will be generated without holiday shifting.",
                    year, exc,
                )

        return holidays

    # ------------------------------------------------------------------
    # Date calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _get_recycling_anchor(
        zone: int, collection_day: str, waste_type: str
    ) -> datetime.date:
        """Return the anchor date for a recycling/glass zone + day + type."""
        key = (zone, waste_type)
        if key not in _RECYCLING_ZONE_WEEK_MONDAYS:
            _LOGGER.warning(
                "Unknown HCC recycling zone %s — defaulting to zone 1. "
                "Please report at https://github.com/mampfes/hacs_waste_collection_schedule",
                zone,
            )
            key = (1, waste_type)
        week_monday = _RECYCLING_ZONE_WEEK_MONDAYS[key]
        return week_monday + datetime.timedelta(days=WEEKDAY_OFFSET.get(collection_day, 0))

    @staticmethod
    def _get_green_anchor(green_zone: int, collection_day: str) -> datetime.date:
        """Return the anchor date for a green waste zone + day."""
        week_monday = _GREEN_ZONE_WEEK_MONDAYS.get(
            green_zone, _GREEN_ZONE_WEEK_MONDAYS[1]
        )
        return week_monday + datetime.timedelta(days=WEEKDAY_OFFSET.get(collection_day, 0))

    @staticmethod
    def _shift_holiday(d: datetime.date, holidays: set[datetime.date]) -> datetime.date:
        """Shift to following Saturday if collection falls on a shifted public holiday."""
        if d in holidays:
            days_to_sat = (5 - d.weekday()) % 7 or 7
            return d + datetime.timedelta(days=days_to_sat)
        return d

    @staticmethod
    def _advance_to(
        anchor: datetime.date, step_weeks: int, target: datetime.date
    ) -> datetime.date:
        """Return first date in anchor + N*step_weeks sequence >= target."""
        if anchor >= target:
            return anchor
        delta = (target - anchor).days
        steps = delta // (step_weeks * 7)
        candidate = anchor + datetime.timedelta(weeks=steps * step_weeks)
        if candidate < target:
            candidate += datetime.timedelta(weeks=step_weeks)
        return candidate

    def _generate(
        self,
        anchor: datetime.date,
        step_weeks: int,
        count: int,
        holidays: set[datetime.date],
    ) -> list[datetime.date]:
        results, d = [], anchor
        while len(results) < count:
            results.append(self._shift_holiday(d, holidays))
            d += datetime.timedelta(weeks=step_weeks)
        return results

    def _build_entries(
        self,
        recycling_zone: int,
        collection_day: str,
        public_holidays: set[datetime.date],
    ) -> list[Collection]:
        today = datetime.date.today()
        entries = []

        # --- Rubbish: every week ---
        # Use the glass anchor as weekly reference (earliest confirmed collection date)
        rubbish_anchor = self._get_recycling_anchor(recycling_zone, collection_day, "glass")
        rubbish_start = self._advance_to(rubbish_anchor, 1, today)
        for d in self._generate(rubbish_start, 1, _LOOKAHEAD_WEEKS, public_holidays):
            entries.append(Collection(d, "Rubbish", icon=ICON_MAP["Rubbish"]))

        # --- Glass: every 2 weeks ---
        glass_anchor = self._get_recycling_anchor(recycling_zone, collection_day, "glass")
        glass_start = self._advance_to(glass_anchor, 2, today)
        for d in self._generate(glass_start, 2, _LOOKAHEAD_WEEKS // 2, public_holidays):
            entries.append(Collection(d, "Glass", icon=ICON_MAP["Glass"]))

        # --- Recycling: every 2 weeks, opposite week to glass ---
        recycling_anchor = self._get_recycling_anchor(recycling_zone, collection_day, "recycling")
        recycling_start = self._advance_to(recycling_anchor, 2, today)
        for d in self._generate(recycling_start, 2, _LOOKAHEAD_WEEKS // 2, public_holidays):
            entries.append(Collection(d, "Recycling", icon=ICON_MAP["Recycling"]))

        # --- Green waste: every 4 weeks, all 4 zones ---
        # The ArcGIS recycling layer doesn't expose green waste zones, so we
        # generate all 4 zones and label them. Users should keep only the one
        # matching their bin using `types:` in the sensor configuration.
        for gz in range(1, 5):
            green_anchor = self._get_green_anchor(gz, collection_day)
            green_start = self._advance_to(green_anchor, 4, today)
            label = f"Green Waste Zone {gz}"
            for d in self._generate(green_start, 4, _LOOKAHEAD_WEEKS // 4, public_holidays):
                entries.append(Collection(d, label, icon=ICON_MAP["Green Waste"]))

        return entries
