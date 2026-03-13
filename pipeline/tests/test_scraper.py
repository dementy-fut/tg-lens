import pytest
from unittest.mock import MagicMock
from src.scraper import TelegramScraper


def test_parse_message_to_dict():
    msg = MagicMock()
    msg.id = 42
    msg.text = "Hello world"
    msg.date.isoformat.return_value = "2026-03-01T12:00:00+00:00"
    msg.views = 150
    msg.forwards = 5
    msg.reactions = None
    msg.media = None

    result = TelegramScraper.parse_message(msg, channel_id="ch-uuid", channel_username="testchan")

    assert result["telegram_msg_id"] == 42
    assert result["text"] == "Hello world"
    assert result["channel_id"] == "ch-uuid"
    assert result["link"] == "https://t.me/testchan/42"
    assert result["has_media"] is False


def test_parse_message_with_media():
    msg = MagicMock()
    msg.id = 43
    msg.text = "Photo post"
    msg.date.isoformat.return_value = "2026-03-01T12:00:00+00:00"
    msg.views = 10
    msg.forwards = 0
    msg.reactions = None
    msg.media = MagicMock()
    msg.photo = True
    msg.video = None
    msg.document = None

    result = TelegramScraper.parse_message(msg, channel_id="ch-uuid", channel_username="testchan")
    assert result["has_media"] is True
    assert result["media_type"] == "photo"


def test_parse_message_without_text():
    msg = MagicMock()
    msg.id = 44
    msg.text = None
    msg.date.isoformat.return_value = "2026-03-01T12:00:00+00:00"
    msg.views = 0
    msg.forwards = 0
    msg.reactions = None
    msg.media = None

    result = TelegramScraper.parse_message(msg, channel_id="ch-uuid", channel_username="testchan")
    assert result["text"] is None


def test_parse_message_with_reactions():
    msg = MagicMock()
    msg.id = 45
    msg.text = "Popular post"
    msg.date.isoformat.return_value = "2026-03-01T12:00:00+00:00"
    msg.views = 500
    msg.forwards = 10
    msg.media = None

    reaction1 = MagicMock()
    reaction1.reaction.emoticon = "👍"
    reaction1.count = 25
    reaction2 = MagicMock()
    reaction2.reaction.emoticon = "🔥"
    reaction2.count = 10
    msg.reactions.results = [reaction1, reaction2]

    result = TelegramScraper.parse_message(msg, channel_id="ch-uuid", channel_username="testchan")
    assert result["reactions_json"] == {"👍": 25, "🔥": 10}
