import json
import pytest
from cdss.drug_interactions import check_interactions, DrugInteractionResult


@pytest.mark.asyncio(loop_scope="function")
async def test_known_interaction_warfarin_aspirin():
    result = await check_interactions(
        current_medications=["warfarin"],
        proposed_medications=["aspirin"],
    )
    assert isinstance(result, DrugInteractionResult)
    assert len(result.interactions) > 0
    assert result.severity_summary != "No known interactions found"


@pytest.mark.asyncio(loop_scope="function")
async def test_no_interaction():
    result = await check_interactions(
        current_medications=["metformin"],
        proposed_medications=[],
    )
    assert isinstance(result, DrugInteractionResult)


@pytest.mark.asyncio(loop_scope="function")
async def test_empty_input():
    result = await check_interactions(
        current_medications=[],
        proposed_medications=[],
    )
    assert result.contraindicated is False
    assert len(result.interactions) == 0
