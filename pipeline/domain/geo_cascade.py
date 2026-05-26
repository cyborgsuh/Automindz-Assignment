from __future__ import annotations

from pipeline.config import COUNTRY_TO_REGION, EU_REGIONS


def build_cascade(
    cities: list[str],
    countries: list[str],
    locations_derived: list[str],
    employee_count: int | None,
) -> list[tuple[str, str]]:
    """Return ordered (cascade_level, location_query) pairs."""
    levels: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(level: str, query: str) -> None:
        key = (level, query)
        if query and key not in seen:
            seen.add(key)
            levels.append(key)

    for city, country in zip(cities, countries):
        add("city", f"{city}, {country}")

    if cities and countries:
        add("city", f"{cities[0]}, {countries[0]}")
    elif locations_derived:
        add("city", locations_derived[0])

    for country in countries:
        add("country", country)

    regions_added: set[str] = set()
    for country in countries:
        region = COUNTRY_TO_REGION.get(country)
        if region and region not in regions_added:
            regions_added.add(region)
            add("region", region)

    if employee_count is not None and employee_count <= 200:
        add("worldwide", "worldwide")

    return levels


def region_countries(region: str) -> list[str]:
    return EU_REGIONS.get(region, [])
