from __future__ import annotations

SIZE_BAND_TITLES: dict[str, list[str]] = {
    "50-200": [
        "Head of Talent",
        "Head of People",
        "Head of HR",
        "Director Regulatory Affairs",
        "Director Clinical Operations",
    ],
    "201-1000": [
        "VP People",
        "VP Talent Acquisition",
        "Senior Director Regulatory Affairs",
        "Senior Director Clinical Operations",
        "Director Talent Acquisition Europe",
    ],
    "1001-2000": [
        "Global Head of Talent",
        "EU Head of Talent Acquisition",
        "VP Regulatory Affairs EU",
        "VP Clinical Operations EU",
        "Senior Director Talent Acquisition",
    ],
}


def employee_count_to_band(count: int | None) -> str:
    if count is None:
        return "unknown"
    if count < 50:
        return "out_of_band"
    if count <= 200:
        return "50-200"
    if count <= 1000:
        return "201-1000"
    if count <= 2000:
        return "1001-2000"
    return "out_of_band"


def titles_for_band(band: str) -> list[str]:
    return SIZE_BAND_TITLES.get(band, [])
