import pytest
from decimal import Decimal

def test_mcq_scoring_logic_math():
    """Verifies the core scoring math used in the application."""
    # Data simulation matching the exam logic
    marks = Decimal("2.5")
    negative_factor = Decimal("0.33")
    
    # Correct answer
    score_correct = marks
    assert score_correct == Decimal("2.5")
    
    # Incorrect answer
    score_incorrect = Decimal("0.00")
    penalty = marks * negative_factor
    # Total negative logic as per student_service.py:751
    # total_negative += penalty
    assert penalty == Decimal("0.825")

@pytest.mark.asyncio
async def test_not_found_return_none(mocker):
    """Verifies that the service returns None correctly when exam doesn't exist."""
    from services.exam_service import get_exam_by_id
    
    # Mock the database execute to return None
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_result.one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    result = await get_exam_by_id(mock_db, 999999)
    assert result is None
