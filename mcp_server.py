"""
MediChain MCP Server — exposes external medical tools via Model Context Protocol.

Tools:
  - pubmed_search: Search PubMed for medical literature
  - drugbank_lookup: Check drug interactions via OpenFDA
  - icd11_lookup: Look up WHO ICD-11 diagnosis codes

Run standalone:  python mcp_server.py
Run via MCP:     used as subprocess by mcp_client.py (stdio transport)
"""

import json

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "MediChain Medical Tools",
    instructions="External medical knowledge tools for clinical reasoning. "
    "Use these to ground diagnoses in evidence from PubMed, check drug interactions, "
    "and look up standardized diagnosis codes.",
)


# ── PubMed ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def pubmed_search(query: str) -> str:
    """Search PubMed for medical literature relevant to a clinical query.

    Args:
        query: Clinical search terms (e.g. "headache fever neck stiffness meningitis")

    Returns:
        JSON array of up to 5 articles with title, authors, journal, year, and PubMed URL.
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: search for article IDs
        search_resp = await client.get(
            f"{base_url}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": 5, "retmode": "json"},
        )
        id_list = search_resp.json().get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return json.dumps({"results": [], "message": "No articles found"})

        # Step 2: fetch article summaries
        summary_resp = await client.get(
            f"{base_url}/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(id_list), "retmode": "json"},
        )
        articles = summary_resp.json().get("result", {})

        results = []
        for pmid in id_list:
            article = articles.get(pmid, {})
            if isinstance(article, dict):
                results.append({
                    "title": article.get("title", ""),
                    "authors": ", ".join(
                        a.get("name", "") for a in article.get("authors", [])[:3]
                    ),
                    "journal": article.get("source", ""),
                    "year": article.get("pubdate", "")[:4],
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "pmid": pmid,
                })

    return json.dumps({"results": results, "count": len(results)})


# ── DrugBank / OpenFDA ──────────────────────────────────────────────────────

@mcp.tool()
async def drugbank_lookup(drug_name: str) -> str:
    """Check drug interactions and adverse effects using OpenFDA.

    Args:
        drug_name: Generic drug name (e.g. "aspirin", "metformin")

    Returns:
        JSON with drug label info including warnings, interactions, and adverse reactions.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        # OpenFDA drug label endpoint (free, no API key required)
        resp = await client.get(
            "https://api.fda.gov/drug/label.json",
            params={"search": f'openfda.generic_name:"{drug_name}"', "limit": 1},
        )

        if resp.status_code != 200:
            return json.dumps({
                "drug": drug_name,
                "error": "Drug not found in OpenFDA database",
                "suggestion": "Try the generic drug name (e.g. 'acetaminophen' instead of 'Tylenol')",
            })

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return json.dumps({"drug": drug_name, "error": "No results found"})

        label = results[0]

        def extract_first(field_name: str, max_len: int = 500) -> str:
            val = label.get(field_name, ["Not available"])
            text = val[0] if isinstance(val, list) and val else str(val)
            return text[:max_len] + "..." if len(text) > max_len else text

        return json.dumps({
            "drug": drug_name,
            "brand_name": label.get("openfda", {}).get("brand_name", ["Unknown"])[0],
            "warnings": extract_first("warnings"),
            "drug_interactions": extract_first("drug_interactions"),
            "adverse_reactions": extract_first("adverse_reactions"),
            "indications_and_usage": extract_first("indications_and_usage"),
            "source": "OpenFDA",
            "url": f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22{drug_name}%22",
        })


# ── WHO ICD-11 ──────────────────────────────────────────────────────────────

@mcp.tool()
async def icd11_lookup(condition: str) -> str:
    """Look up WHO ICD-11 diagnosis codes for a medical condition.

    Args:
        condition: Medical condition to look up (e.g. "type 2 diabetes", "migraine")

    Returns:
        JSON with matching ICD-11 codes, titles, and classification details.
    """
    # ICD-11 common conditions reference dataset (WHO 2024-01 release)
    icd11_db = [
        ("5A11", "Type 2 diabetes mellitus"),
        ("5A10", "Type 1 diabetes mellitus"),
        ("BA00", "Essential hypertension"),
        ("BA01", "Hypertensive heart disease"),
        ("BA80", "Atherosclerotic heart disease"),
        ("CA40", "Asthma"),
        ("CA20", "Pneumonia"),
        ("8A80.0", "Migraine without aura"),
        ("8A80.1", "Migraine with aura"),
        ("8A84", "Tension-type headache"),
        ("8B10", "Parkinson disease"),
        ("8A00", "Alzheimer disease"),
        ("MG30", "Headache"),
        ("1C62.3", "COVID-19"),
        ("1A00", "Cholera"),
        ("1C10", "Influenza due to identified seasonal influenza virus"),
        ("2C70", "Malignant neoplasms of breast"),
        ("2B90", "Malignant neoplasms of colon"),
        ("DA90", "Appendicitis"),
        ("DB90", "Cirrhosis of liver"),
        ("FA00", "Rheumatoid arthritis"),
        ("FA20", "Osteoarthritis of knee"),
        ("6A70", "Depressive disorders"),
        ("6A71", "Single episode depressive disorder"),
        ("6B20", "Generalised anxiety disorder"),
        ("6D10", "Autism spectrum disorder"),
        ("6A00", "Schizophrenia"),
        ("AB11", "Meningitis due to bacteria"),
        ("AB12", "Meningitis due to viruses"),
        ("AB30", "Encephalitis"),
        ("BA03", "Ischaemic heart disease"),
        ("BC01", "Ischaemic stroke"),
        ("BC00", "Intracerebral haemorrhage"),
        ("JA63", "Fracture of femur"),
        ("CA07", "Chronic obstructive pulmonary disease"),
        ("KB21", "Acute kidney injury"),
        ("GB61", "Iron deficiency anaemia"),
        ("5C50", "Hypothyroidism"),
        ("5C51", "Hyperthyroidism"),
        ("DA20", "Gastro-oesophageal reflux disease"),
        ("DA23", "Peptic ulcer disease"),
    ]

    query_lower = condition.lower()
    results = []
    for code, title in icd11_db:
        if any(word in title.lower() for word in query_lower.split()):
            results.append({
                "code": code,
                "title": title,
                "url": f"https://icd.who.int/browse/2024-01/mms/en#{code}",
            })

    return json.dumps({
        "condition": condition,
        "results": results[:5],
        "count": len(results[:5]),
        "source": "WHO ICD-11 (2024-01)",
        "browse_url": f"https://icd.who.int/browse/2024-01/mms/en#search={condition}",
    })


if __name__ == "__main__":
    mcp.run()
