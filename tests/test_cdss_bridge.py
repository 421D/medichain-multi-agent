from cdss.bridge import get_cdss_tools


def test_bridge_returns_tools():
    tools = get_cdss_tools()
    assert len(tools) >= 6
    names = [t.name for t in tools]
    assert "wells_score" in names
    assert "curb65" in names
    assert "heart_score" in names
    assert "qsofa" in names
    assert "phq9" in names


def test_wells_tool_callable():
    tools = get_cdss_tools()
    wells = next(t for t in tools if t.name == "wells_score")
    result = wells.invoke({
        "clinical_signs_dvt": True, "pe_most_likely": False,
        "heart_rate_over_100": False, "immobilization_or_surgery": False,
        "previous_dvt_pe": False, "hemoptysis": False, "malignancy": False,
    })
    assert "score" in result
    assert "risk_level" in result
