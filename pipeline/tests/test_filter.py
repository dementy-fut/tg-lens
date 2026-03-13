from src.filter import NoiseFilter


def test_filters_short_messages():
    posts = [
        {"text": "ok", "views": 0, "forwards": 0, "reactions_json": None},
        {"text": "This is a meaningful post about something important", "views": 10, "forwards": 0, "reactions_json": None},
    ]
    result = NoiseFilter.filter_posts(posts)
    assert len(result) == 1
    assert "meaningful" in result[0]["text"]


def test_filters_greeting_spam():
    posts = [
        {"text": "Привет всем!", "views": 0, "forwards": 0, "reactions_json": None},
        {"text": "+", "views": 0, "forwards": 0, "reactions_json": None},
        {"text": "спасибо", "views": 0, "forwards": 0, "reactions_json": None},
        {"text": "Серьёзный пост про технологии и разработку новых систем", "views": 5, "forwards": 0, "reactions_json": None},
    ]
    result = NoiseFilter.filter_posts(posts)
    assert len(result) == 1


def test_keeps_high_engagement_short():
    posts = [
        {"text": "Wow!", "views": 500, "forwards": 10, "reactions_json": {"👍": 50}},
    ]
    result = NoiseFilter.filter_posts(posts)
    assert len(result) == 1


def test_filters_none_text():
    posts = [
        {"text": None, "views": 0, "forwards": 0, "reactions_json": None},
    ]
    result = NoiseFilter.filter_posts(posts)
    assert len(result) == 0


def test_filters_emoji_only():
    posts = [
        {"text": "🔥🔥🔥", "views": 0, "forwards": 0, "reactions_json": None},
        {"text": "Real content here about important things happening", "views": 0, "forwards": 0, "reactions_json": None},
    ]
    result = NoiseFilter.filter_posts(posts)
    assert len(result) == 1
