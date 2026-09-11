"""Parse an SEC Inline XBRL instance document into structured facts (AD-4).

The second ingestion path, and the ONLY path to dimensional data: the Company
Facts API carries no segment- or member-level facts at all — not sparsely, not
by exception — verified live against a 4.6 MB fetch
(`company_facts_api_carries_no_segment_dimensions`). AD-4 declared this path in
the architecture spine on 2026-07-19; nothing built it until Story 13.2.

Pure functions — no network, no DB — so they are fully unit-testable against
committed fixtures, matching `ingestion.company_facts`. The live fetch lives in
`ingestion.edgar` (`fetch_instance_document`); persistence lives in
`raw_store.repository`.

DIMENSIONS ARE PRESERVED VERBATIM. A context's `<xbrldi:explicitMember
dimension="AXIS">MEMBER</>` pairs, whether under `entity/segment` or
`scenario`, are stored as `{axis: member}` using the filer's own qualified names
— `us-gaap:StatementBusinessSegmentsAxis` -> `cpb:MealsBeveragesMember` — never
normalized, prefixed-expanded or prettified here. Typed members are stored under
the same axis key with a deterministic XML identity because they have no QName
member. Mapping named members to canonical concepts is Story 13.3's job, and it
needs the filer's own vocabulary intact to do it: custom `cpb:`/`qsr:`/`zts:` tags
are filer-specific by construction, so per-filer mapping is the point rather than
an inconvenience (`cpb_segment_members_stable_but_tags_switch`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from xml.etree import ElementTree

from ingestion.company_facts import ParsedFact, _content_hash

# Every universe instance uses the default namespace for xbrli (verified across
# CPB, QSR, ZTS, SHOP and CP, 2026-09-10), but the prefix is the document's
# choice, so resolve by URI rather than by tag text.
XBRLI_NS = "http://www.xbrl.org/2003/instance"
XBRLDI_NS = "http://xbrl.org/2006/xbrldi"

_CONTEXT = f"{{{XBRLI_NS}}}context"
_ENTITY = f"{{{XBRLI_NS}}}entity"
_SEGMENT = f"{{{XBRLI_NS}}}segment"
_PERIOD = f"{{{XBRLI_NS}}}period"
_SCENARIO = f"{{{XBRLI_NS}}}scenario"
_START = f"{{{XBRLI_NS}}}startDate"
_END = f"{{{XBRLI_NS}}}endDate"
_INSTANT = f"{{{XBRLI_NS}}}instant"
_UNIT = f"{{{XBRLI_NS}}}unit"
_MEASURE = f"{{{XBRLI_NS}}}measure"
_EXPLICIT_MEMBER = f"{{{XBRLDI_NS}}}explicitMember"
_TYPED_MEMBER = f"{{{XBRLDI_NS}}}typedMember"


@dataclass(frozen=True)
class ParsedContext:
    """An XBRL context: a period, plus the dimensions that scope it."""

    context_id: str
    period_start: str | None
    period_end: str | None
    dimensions: dict[str, str] | None


def _qname(tag: str, nsmap: dict[str, str]) -> tuple[str, str]:
    """`{uri}local` -> (prefix, local), using the document's own prefixes.

    ElementTree discards prefixes and keeps URIs, but the raw store records the
    filer's taxonomy prefix (`us-gaap`, `cpb`) because that is what the mapping
    specs key on. Reversing the document's own nsmap preserves it exactly.
    """
    if not tag.startswith("{"):
        return "", tag
    uri, _, local = tag[1:].partition("}")
    return nsmap.get(uri, uri), local


def _typed_member_identity(node: ElementTree.Element) -> str:
    """Return a stable identity for a typed dimension's XML payload.

    Typed dimensions do not have a QName member like ``explicitMember`` does;
    their member is an XML value.  The raw store's dimensions contract is still
    a ``{axis: member}`` mapping, so encode that value as a deterministic,
    namespace-aware JSON tree rather than silently treating the context as
    undimensioned.  Story 13.3 can map named members without having to pretend
    a typed member is a QName.
    """

    def encode(element: ElementTree.Element) -> dict:
        return {
            "tag": element.tag,
            "attributes": sorted(element.attrib.items()),
            "text": element.text or "",
            "children": [encode(child) for child in element],
        }

    return "__typed_member__:" + json.dumps(
        encode(node), sort_keys=True, separators=(",", ":")
    )


def parse_contexts(root: ElementTree.Element) -> dict[str, ParsedContext]:
    """Index every `<context>` by id, with its period and dimensions."""
    contexts: dict[str, ParsedContext] = {}
    for node in root.iterfind(_CONTEXT):
        context_id = node.get("id")
        if context_id is None:
            continue

        dimensions: dict[str, str] = {}

        def add_dimension(axis: str | None, member: str | None) -> None:
            if not axis or member is None:
                return
            value = member.strip()
            if not value:
                return
            previous = dimensions.get(axis)
            if previous is not None and previous != value:
                raise ValueError(
                    f"context {context_id!r} has conflicting members for dimension {axis!r}"
                )
            dimensions[axis] = value

        entity = node.find(_ENTITY)
        segment = entity.find(_SEGMENT) if entity is not None else None
        containers = [
            container for container in (segment, node.find(_SCENARIO)) if container is not None
        ]
        for container in containers:
            for member in container.iterfind(_EXPLICIT_MEMBER):
                # Verbatim, including the filer's own prefix. A context may carry
                # SEVERAL axes at once (CPB pairs MajorCustomersAxis with two
                # concentration-risk axes), so this is a dict, not a single pair.
                add_dimension(member.get("dimension"), member.text)
            for member in container.iterfind(_TYPED_MEMBER):
                add_dimension(member.get("dimension"), _typed_member_identity(member))

        period = node.find(_PERIOD)
        start = end = None
        if period is not None:
            if (instant := period.find(_INSTANT)) is not None:
                # A point-in-time fact (balance sheet). Recorded as end only, the
                # same shape `company_facts` uses for instants.
                end = (instant.text or "").strip() or None
            else:
                s, e = period.find(_START), period.find(_END)
                start = (s.text or "").strip() or None if s is not None else None
                end = (e.text or "").strip() or None if e is not None else None

        contexts[context_id] = ParsedContext(
            context_id=context_id,
            period_start=start,
            period_end=end,
            dimensions=dimensions or None,
        )
    return contexts


def parse_units(root: ElementTree.Element, nsmap: dict[str, str]) -> dict[str, str]:
    """Index `<unit>` by id, resolved to its measure's local name (`USD`)."""
    units: dict[str, str] = {}
    for node in root.iterfind(_UNIT):
        unit_id = node.get("id")
        if unit_id is None:
            continue
        measures = [m.text.strip() for m in node.iter(_MEASURE) if m.text]
        if measures:
            # "iso4217:USD" -> "USD"; a divide unit (per-share) keeps both parts.
            units[unit_id] = "/".join(m.rpartition(":")[2] for m in measures)
    return units


def parse_instance(
    xml_text: str,
    *,
    accession_number: str,
    fiscal_year: int,
    source: str = "inline_xbrl",
) -> list[ParsedFact]:
    """Flatten an instance document into `ParsedFact`s, dimensions included.

    Returns EVERY numeric fact carrying a resolvable context and unit, both
    dimensioned and undimensioned. Undimensioned facts are deliberately not
    dropped here: AD-4 makes Company Facts the winner where the two sources
    genuinely overlap on the same identity, and that reconciliation needs both
    sides present to compare (see `raw_store.repository`). Dimensioned facts are
    never compared to their undimensioned counterparts — they are different
    facts (AD-3 rule 0).
    """
    root = ElementTree.fromstring(xml_text)
    nsmap = _nsmap(xml_text)
    contexts = parse_contexts(root)
    units = parse_units(root, nsmap)

    facts: list[ParsedFact] = []
    for node in root:
        context_ref = node.get("contextRef")
        unit_ref = node.get("unitRef")
        if not context_ref or not unit_ref:
            continue  # a context, unit, schemaRef, or a non-numeric fact
        context = contexts.get(context_ref)
        unit = units.get(unit_ref)
        if context is None or unit is None or node.text is None:
            continue
        try:
            value = float(node.text.strip())
        except ValueError:
            continue  # non-numeric despite carrying a unitRef

        taxonomy, concept = _qname(node.tag, nsmap)
        if not taxonomy:
            continue

        # NOTE: `node.get("decimals")` is available here and is NOT captured,
        # because `ParsedFact` has no decimals field and neither ingestion path
        # populates `RawFact.decimals` — it has been NULL for every row since
        # Epic 1. AD-3's rule (2) ranks candidates on "higher decimals
        # precision", so that tiebreak has never had data to work with. Real,
        # pre-existing, and deliberately out of scope for this story: adding it
        # changes Company Facts ingestion and every existing content hash.
        facts.append(
            ParsedFact(
                accession_number=accession_number,
                taxonomy=taxonomy,
                concept=concept,
                unit=unit,
                period_start=context.period_start,
                period_end=context.period_end,
                value=value,
                fiscal_year=fiscal_year,
                source=source,
                content_hash=_content_hash(
                    taxonomy,
                    concept,
                    unit,
                    context.period_start,
                    context.period_end,
                    value,
                    context.dimensions,
                ),
                dimensions=context.dimensions,
            )
        )
    return facts


def _nsmap(xml_text: str) -> dict[str, str]:
    """{uri: prefix} from the document's own declarations.

    ElementTree's public API exposes no namespace map on a parsed tree, so this
    re-scans for declarations. Only the root element's declarations matter in
    practice — SEC instance documents declare every taxonomy there.
    """
    mapping: dict[str, str] = {}
    for _, (prefix, uri) in ElementTree.iterparse(
        _StringSource(xml_text), events=["start-ns"]
    ):
        # First declaration wins: a prefix redeclared on a descendant would
        # otherwise silently re-map an already-recorded taxonomy.
        mapping.setdefault(uri, prefix)
    return mapping


class _StringSource:
    """Minimal file-like wrapper so `iterparse` can read an in-memory string."""

    def __init__(self, text: str) -> None:
        self._data = text.encode("utf-8")
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk, self._pos = self._data[self._pos :], len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk
