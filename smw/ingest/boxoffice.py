"""Box Office Mojo yearly-chart ingest (spec §4). The system's only network dependency."""
from dataclasses import dataclass
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from smw.config.season import Season


class IngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChartRow:
    title: str
    gross: float
    release_date: date
    is_rerelease: bool


def fetch_chart(year: int) -> str:
    resp = requests.get(
        f"https://www.boxofficemojo.com/year/{year}/",
        timeout=30,
        headers={"User-Agent": "smw-tracker (personal box-office pool)"},
    )
    resp.raise_for_status()
    return resp.text


def parse_chart(html: str, year: int) -> list[ChartRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[ChartRow] = []
    for tr in soup.find_all("tr"):
        title_cell = tr.select_one("td.mojo-field-type-release")
        # Rule 1: in-year gross is the FIRST cell carrying BOTH the money class and the
        # estimatable marker. Money-without-estimatable is the budget column; a later
        # money+estimatable cell is the stale "Total Gross".
        money_cell = tr.select_one("td.mojo-field-type-money.mojo-estimatable")
        date_cell = tr.select_one("td.mojo-field-type-date")
        if title_cell is None or money_cell is None or date_cell is None:
            continue  # Rule 4: header/footer rows partially match; skip, don't raise
        link = title_cell.find("a")
        if link is None:
            continue
        title = link.get_text(strip=True)  # Rule 2: anchor text only
        try:
            gross = float(money_cell.get_text(strip=True).replace("$", "").replace(",", ""))
            release = datetime.strptime(
                f"{date_cell.get_text(strip=True)} {year}", "%b %d %Y"
            ).date()
        except ValueError:
            continue
        # Rule 3: a note element nested in the title cell marks a re-release.
        is_rerelease = title_cell.find("span") is not None
        rows.append(ChartRow(title=title, gross=gross, release_date=release,
                             is_rerelease=is_rerelease))
    return rows


def chart_floor(rows: list[ChartRow]) -> float:
    return min(r.gross for r in rows)


def windowed(rows: list[ChartRow], season: Season) -> list[ChartRow]:
    if not rows:
        raise IngestError(
            "Guard A: chart parse yielded zero rows — the fetch failed or the markup changed."
        )
    kept = [
        r for r in rows
        if season.window_start <= r.release_date <= season.window_end and not r.is_rerelease
    ]
    if not kept:
        raise IngestError(
            "Guard B: the chart parsed but the window filter kept zero rows. "
            "First check Rule 3 (re-release detection): a markup change that nests a new "
            "element inside every title cell flags every film as a re-release and filters "
            "everything away."
        )
    return kept
