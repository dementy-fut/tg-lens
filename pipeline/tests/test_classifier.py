import pytest
from unittest.mock import AsyncMock, MagicMock
from src.classifier import AIClassifier


def test_build_batch_prompt():
    posts = [
        {"id": "uuid-1", "text": "Toyota отзывает Prado 150"},
        {"id": "uuid-2", "text": "Классный пост!"},
    ]
    prompt = AIClassifier._build_batch_prompt(posts)
    assert "uuid-1" in prompt
    assert "Toyota" in prompt


def test_parse_classification_response():
    response_text = '[{"id": "uuid-1", "category": "FACT"}, {"id": "uuid-2", "category": "SKIP"}]'
    result = AIClassifier._parse_response(response_text)
    assert result["uuid-1"] == "FACT"
    assert result["uuid-2"] == "SKIP"


def test_parse_response_with_markdown_wrapper():
    response_text = '```json\n[{"id": "uuid-1", "category": "FACT"}]\n```'
    result = AIClassifier._parse_response(response_text)
    assert result["uuid-1"] == "FACT"


@pytest.mark.asyncio
async def test_classify_batch():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='[{"id": "uuid-1", "category": "FACT"}, {"id": "uuid-2", "category": "SKIP"}]')]
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    classifier = AIClassifier(client=mock_client)
    posts = [
        {"id": "uuid-1", "text": "Important news about something"},
        {"id": "uuid-2", "text": "Lol nice"},
    ]
    result = await classifier.classify_batch(posts)
    assert result["uuid-1"] == "FACT"
    assert result["uuid-2"] == "SKIP"
