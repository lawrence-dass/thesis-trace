"""Add a concept's real facts to a trimmed golden fixture, from the dev store.

The golden fixtures are trimmed company-facts JSON. A new mapping that reads a
concept the fixture never carried makes the golden harness resolve it to nothing
and assert nothing (CLAUDE.md, live-data DoD rule 6). This copies the concept's
facts from the dev store's `raw_facts` (already-ingested real EDGAR company
facts), limited to the SAME filings that a sibling concept's facts in the
fixture come from, so the two operands of a derivation share provenance exactly.

    make py F=scripts/extend_fixture_concept.py \
        ARGS="backend/tests/fixtures/otex_company_facts.json SellingAndMarketingExpense GeneralAndAdministrativeExpense"

No network. Refuses to write unless re-serialising the untouched fixture
reproduces it byte for byte, so the diff is only ever the added facts.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text

from app.db import get_sessionmaker

ROOT = Path(__file__).resolve().parents[1]


def _indent_of(raw: str) -> int:
    second = raw.splitlines()[1]
    return len(second) - len(second.lstrip(" "))


async def run(fixture: Path, concept: str, sibling: str) -> None:
    raw = fixture.read_text()
    indent = _indent_of(raw)
    tail = "\n" if raw.endswith("\n") else ""
    data = json.loads(raw)

    def _dump(d: dict) -> str:
        return json.dumps(d, indent=indent, ensure_ascii=False) + tail

    if _dump(data) != raw:
        raise SystemExit(f"{fixture.name}: does not round-trip at indent {indent}; refusing to rewrite")

    gaap = data["facts"]["us-gaap"]
    if concept in gaap:
        raise SystemExit(f"{fixture.name} already carries {concept}")
    siblings = [f for unit in gaap[sibling]["units"].values() for f in unit]
    by_accn = {f["accn"]: f for f in siblings}  # fy/fp/form/filed per filing

    async with get_sessionmaker()() as session:
        rows = (
            await session.execute(
                text(
                    "select r.accession_number, r.period_start, r.period_end, r.value, r.unit "
                    "from raw_facts r where r.source = 'company_facts' and r.taxonomy = 'us-gaap' "
                    "and r.concept = :concept and r.accession_number = any(:accns) "
                    "order by r.period_end, r.accession_number"
                ),
                {"concept": concept, "accns": sorted(by_accn)},
            )
        ).all()
    if not rows:
        raise SystemExit(f"no {concept} facts in the dev store for {sorted(by_accn)}")

    units: dict[str, list[dict]] = {}
    for accn, start, end, value, unit in rows:
        meta = by_accn[accn]
        fact = {"start": start.isoformat()} if start else {}
        fact |= {
            "end": end.isoformat(),
            "val": int(value) if value == int(value) else float(value),
            "accn": accn,
            "fy": meta["fy"],
            "fp": meta["fp"],
            "form": meta["form"],
            "filed": meta["filed"],
        }
        units.setdefault(unit or "USD", []).append(fact)

    gaap[concept] = {"label": concept, "description": f"Added by Ops 5 from the dev store (filings of {sibling}).", "units": units}
    fixture.write_text(_dump(data))
    for unit, facts in units.items():
        for f in facts:
            print(f"{fixture.name} +{concept} {f.get('start', '')}..{f['end']} {f['val']:,} {unit} {f['accn']}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    asyncio.run(run(ROOT / sys.argv[1], sys.argv[2], sys.argv[3]))
