import pytest
from unittest.mock import MagicMock
from src.db import SupabaseDB


def test_upsert_channel():
    mock_client = MagicMock()
    mock_client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "uuid-1", "telegram_id": 123, "title": "Test Channel"}
    ]
    db = SupabaseDB(client=mock_client)
    result = db.upsert_channel(telegram_id=123, username="test", title="Test Channel", category="tech")
    mock_client.table.assert_called_with("channels")
    assert result["telegram_id"] == 123


def test_insert_posts_batch():
    mock_client = MagicMock()
    mock_client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "uuid-1", "telegram_msg_id": 1}
    ]
    db = SupabaseDB(client=mock_client)
    posts = [{"channel_id": "uuid-ch", "telegram_msg_id": 1, "text": "Hello", "date": "2026-03-01T00:00:00Z"}]
    result = db.insert_posts(posts)
    assert len(result) == 1


def test_get_posts_for_period():
    mock_client = MagicMock()
    mock_data = [{"id": "uuid-1", "text": "post1"}]
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value.execute.return_value.data = mock_data
    db = SupabaseDB(client=mock_client)
    result = db.get_posts_for_period("channel-uuid", "2026-03-01", "2026-03-07")
    assert len(result) == 1


def test_get_summary_returns_none():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    db = SupabaseDB(client=mock_client)
    result = db.get_summary("ch-id", "week", "2026-03-01")
    assert result is None


def test_get_summary_returns_data():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "s1", "summary": "test"}]
    db = SupabaseDB(client=mock_client)
    result = db.get_summary("ch-id", "week", "2026-03-01")
    assert result["summary"] == "test"
