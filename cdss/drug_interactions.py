"""Drug interaction checking using RxNorm API + local fallback database.

NLM RxNorm API (free, no key required):
- https://rxnav.nlm.nih.gov/REST/rxcui.json?name=aspirin
- https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis=...

NOTE: The /REST/interaction/list.json endpoint was deprecated by NLM in Jan 2024
and may return non-200 status. When that happens we fall back to the local
KNOWN_INTERACTIONS table and set api_status="offline" so callers/UI can tell the
user "local-only check".
"""
import logging

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DrugInteraction(BaseModel):
    drug_pair: list[str]
    severity: str  # "contraindicated" | "major" | "moderate" | "minor"
    description: str
    source: str


class DrugInteractionResult(BaseModel):
    interactions: list[DrugInteraction] = Field(default_factory=list)
    severity_summary: str = "No known interactions found"
    contraindicated: bool = False
    clinical_notes: list[str] = Field(default_factory=list)
    api_status: str = Field(
        default="ok",
        description="RxNorm API status: ok | offline | unreachable | parse_error | skipped | not_called",
    )


# Normalisation map: concrete brand/generic/salt names → the class key used
# in KNOWN_INTERACTIONS. Lets local rules fire when a patient med list uses a
# specific drug name (e.g. "potassium chloride" matches the "potassium" rule;
# "lisinopril" matches the generic "ace inhibitor" rule — we already have an
# explicit lisinopril+potassium entry below, the alias just catches the rest).
DRUG_ALIASES = {
    # Potassium supplements (common salts)
    "potassium chloride": "potassium",
    "potassium citrate": "potassium",
    "kcl": "potassium",
    "slow-k": "potassium",
    "klor-con": "potassium",
    # ACE inhibitors (class-level rule)
    "lisinopril": "ace inhibitor",
    "enalapril": "ace inhibitor",
    "ramipril": "ace inhibitor",
    "benazepril": "ace inhibitor",
    "captopril": "ace inhibitor",
    "perindopril": "ace inhibitor",
    # SSRIs (class-level rule)
    "fluoxetine": "ssri",
    "sertraline": "ssri",
    "paroxetine": "ssri",
    "citalopram": "ssri",
    "escitalopram": "ssri",
    # MAOIs (class-level rule)
    "phenelzine": "maoi",
    "tranylcypromine": "maoi",
    "isocarboxazid": "maoi",
    "selegiline": "maoi",
    # Iodinated contrast variants
    "iodinated contrast": "contrast dye",
    "iohexol": "contrast dye",
    "iopamidol": "contrast dye",
    "iodixanol": "contrast dye",
    # Common NSAIDs → bucket to ibuprofen so the warfarin+NSAID rule fires
    "naproxen": "ibuprofen",
    "diclofenac": "ibuprofen",
    "ketorolac": "ibuprofen",
    "celecoxib": "ibuprofen",
}


def _normalize_drug(name: str) -> str:
    """Map a drug name to the canonical key used in KNOWN_INTERACTIONS, if any."""
    n = name.lower().strip()
    return DRUG_ALIASES.get(n, n)


# Local fallback for common high-risk interactions (when API unavailable)
KNOWN_INTERACTIONS = {
    frozenset(["warfarin", "aspirin"]): DrugInteraction(
        drug_pair=["warfarin", "aspirin"], severity="major",
        description="Increased risk of bleeding. Combined antiplatelet and anticoagulant effect.",
        source="NLM DailyMed"),
    frozenset(["metformin", "contrast dye"]): DrugInteraction(
        drug_pair=["metformin", "contrast dye"], severity="major",
        description="Risk of lactic acidosis. Hold metformin before and after contrast.",
        source="FDA Drug Safety Communication"),
    frozenset(["ssri", "maoi"]): DrugInteraction(
        drug_pair=["SSRI", "MAOI"], severity="contraindicated",
        description="Risk of serotonin syndrome. Absolutely contraindicated.",
        source="FDA Black Box Warning"),
    frozenset(["ace inhibitor", "potassium"]): DrugInteraction(
        drug_pair=["ACE inhibitor", "potassium"], severity="major",
        description="Risk of hyperkalemia. Monitor potassium levels closely.",
        source="Clinical Pharmacology"),
    frozenset(["lisinopril", "potassium"]): DrugInteraction(
        drug_pair=["lisinopril", "potassium"], severity="major",
        description="Risk of hyperkalemia. Monitor potassium levels closely.",
        source="Clinical Pharmacology"),
    frozenset(["warfarin", "ibuprofen"]): DrugInteraction(
        drug_pair=["warfarin", "ibuprofen"], severity="major",
        description="NSAIDs increase bleeding risk with anticoagulants.",
        source="NLM DailyMed"),
}


async def _resolve_rxcui(drug_name: str) -> str | None:
    """Resolve drug name to RxCUI via NLM API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://rxnav.nlm.nih.gov/REST/rxcui.json",
                params={"name": drug_name, "search": 1},
            )
            if resp.status_code == 200:
                data = resp.json()
                ids = data.get("idGroup", {}).get("rxnormId", [])
                return ids[0] if ids else None
    except (httpx.HTTPError, KeyError):
        return None


async def _check_rxnorm_interactions(rxcuis: list[str]) -> tuple[list[dict], str]:
    """Check pairwise interactions via NLM Interaction API.

    Returns (results, status) where status is one of:
      ok | offline_<status_code> | unreachable | parse_error | skipped
    Each result dict contains: drug_pair (list[str]), description, severity.
    """
    if len(rxcuis) < 2:
        return [], "skipped"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://rxnav.nlm.nih.gov/REST/interaction/list.json",
                params={"rxcuis": "+".join(rxcuis)},
            )
            if resp.status_code != 200:
                # NLM deprecated this endpoint in Jan 2024 — expect 410/404.
                logger.warning(
                    "RxNorm Interaction API returned %s — endpoint may be deprecated; "
                    "using local fallback only.",
                    resp.status_code,
                )
                return [], f"offline_{resp.status_code}"
            data = resp.json()
            pairs = data.get("fullInteractionTypeGroup", [])
            results: list[dict] = []
            for group in pairs:
                for itype in group.get("fullInteractionType", []):
                    for pair in itype.get("interactionPair", []):
                        # Extract the actual two drug names from interactionConcept
                        # rather than hard-coding all_drugs[:2] at the call site.
                        concepts = pair.get("interactionConcept", [])
                        names = [
                            (c.get("minConceptItem") or {}).get("name", "")
                            for c in concepts
                        ]
                        names = [n for n in names if n]
                        if len(names) < 2:
                            continue
                        results.append({
                            "drug_pair": names[:2],
                            "description": pair.get("description", ""),
                            "severity": pair.get("severity", "N/A"),
                        })
            return results, "ok"
    except httpx.HTTPError as e:
        logger.warning("RxNorm Interaction API unreachable (%s) — using local fallback only.", e)
        return [], "unreachable"
    except (KeyError, ValueError) as e:
        logger.warning("RxNorm Interaction API response parse error (%s).", e)
        return [], "parse_error"


async def check_interactions(
    current_medications: list[str],
    proposed_medications: list[str] | None = None,
) -> DrugInteractionResult:
    """Check drug interactions using RxNorm API with local fallback."""
    all_drugs = [d.lower().strip() for d in current_medications]
    if proposed_medications:
        all_drugs.extend(d.lower().strip() for d in proposed_medications)

    if len(all_drugs) < 2:
        return DrugInteractionResult(api_status="skipped")

    interactions: list[DrugInteraction] = []

    # Step 1: Check local known interactions (fast, always works).
    # Normalise each pair through DRUG_ALIASES so e.g. "potassium chloride"
    # resolves to the class-level "potassium" rule below. When we record the
    # match we keep the patient's actual drug names in `drug_pair`, not the
    # canonical class names — clinicians need to see "lisinopril + potassium
    # chloride" not "ACE inhibitor + potassium".
    for i, d1 in enumerate(all_drugs):
        for d2 in all_drugs[i+1:]:
            n1, n2 = _normalize_drug(d1), _normalize_drug(d2)
            key = frozenset([n1, n2])
            if key in KNOWN_INTERACTIONS:
                rule = KNOWN_INTERACTIONS[key]
                interactions.append(rule.model_copy(update={"drug_pair": [d1, d2]}))

    # Step 2: Try RxNorm API for comprehensive check
    rxcuis = []
    for drug in all_drugs:
        rxcui = await _resolve_rxcui(drug)
        if rxcui:
            rxcuis.append(rxcui)

    api_status = "not_called"
    if len(rxcuis) >= 2:
        api_results, api_status = await _check_rxnorm_interactions(rxcuis)
        for r in api_results:
            severity = r.get("severity", "moderate").lower()
            if severity not in ("contraindicated", "major", "moderate", "minor"):
                severity = "moderate"
            pair = r.get("drug_pair") or all_drugs[:2]
            interactions.append(DrugInteraction(
                drug_pair=pair,
                severity=severity,
                description=r["description"][:300],
                source="NLM RxNorm Interaction API",
            ))

    # Deduplicate by (drug pair, severity) — keying on description prefix
    # collapsed genuinely-different interactions whose descriptions started
    # with the same boilerplate (e.g. "Concurrent use may increase risk of
    # bleeding…"). Pair+severity is the natural identity for a clinical
    # interaction.
    seen: set[tuple] = set()
    unique = []
    for inter in interactions:
        dedup_key = (frozenset(d.lower().strip() for d in inter.drug_pair), inter.severity)
        if dedup_key not in seen:
            seen.add(dedup_key)
            unique.append(inter)
    interactions = unique

    # Build summary
    contraindicated = any(i.severity == "contraindicated" for i in interactions)
    severity_counts = {}
    for i in interactions:
        severity_counts[i.severity] = severity_counts.get(i.severity, 0) + 1

    if not interactions:
        summary = "No known interactions found"
    else:
        parts = [f"{v} {k}" for k, v in severity_counts.items()]
        summary = ", ".join(parts)

    notes = []
    if contraindicated:
        notes.append("CONTRAINDICATED combination detected. Do NOT co-administer.")
    if severity_counts.get("major", 0) > 0:
        notes.append("Major interaction(s) found. Close monitoring required.")
    if api_status.startswith("offline") or api_status in ("unreachable", "parse_error"):
        notes.append(
            "Note: RxNorm Interaction API unavailable — only local high-risk pairs "
            "were checked. Review the full medication list manually."
        )

    return DrugInteractionResult(
        interactions=interactions,
        severity_summary=summary,
        contraindicated=contraindicated,
        clinical_notes=notes,
        api_status=api_status,
    )
