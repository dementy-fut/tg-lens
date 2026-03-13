import pytest
from unittest.mock import AsyncMock, MagicMock
from src.digest import DigestGenerator


def test_format_messages_for_prompt():
    posts = [
        {"text": "Post 1", "link": "https://t.me/ch/1", "date": "2026-03-01T12:00:00", "_category": "FACT"},
        {"text": "Post 2", "link": "https://t.me/ch/2", "date": "2026-03-02T12:00:00", "_category": "EXPERIENCE"},
    ]
    result = DigestGenerator._format_messages(posts)
    assert "Post 1" in result
    assert "https://t.me/ch/1" in result
    assert "FACT" in result


@pytest.mark.asyncio
async def test_generate_single_format():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="• Toyota отзывает Prado 150")]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    generator = DigestGenerator(client=mock_client)
    result = await generator.generate("headlines", [], "1-7 марта 2026")
    assert "Toyota" in result["summary"]
    assert result["tokens_used"] == 150


def test_available_formats():
    formats = DigestGenerator.available_formats()
    assert "headlines" in formats
    assert "brief" in formats
    assert "deep" in formats
    assert "qa" in formats
    assert "actions" in formats
    assert len(formats) == 5


@pytest.mark.asyncio
async def test_generate_unknown_format_raises():
    mock_client = AsyncMock()
    generator = DigestGenerator(client=mock_client)
    with pytest.raises(ValueError, match="Unknown format"):
        await generator.generate("nonexistent", [], "period")
