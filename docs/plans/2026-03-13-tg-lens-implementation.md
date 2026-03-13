# TG Lens Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that scrapes 50+ Telegram channels, filters noise with AI, generates digests in 5 formats, and provides semantic search across all history.

**Architecture:** Python pipeline in GitHub Actions (Telethon scraping + Claude AI analysis) stores data in Supabase (Postgres + pgvector). Next.js frontend on Vercel for viewing digests, searching, and chatting with AI about content.

**Tech Stack:** Python 3.11, Telethon, Anthropic SDK, Supabase (Postgres + pgvector), Next.js 14 (App Router), Tailwind CSS, Vercel, GitHub Actions

**Spec:** `docs/specs/2026-03-12-tg-lens-design.md`

---

## Chunk 1: Database & Python Foundation

### Task 1: Supabase Project Setup

**Files:**
- Create: `supabase/migrations/001_initial_schema.sql`
- Create: `supabase/seed.sql`

- [ ] **Step 1: Create Supabase project**

Go to https://supabase.com/dashboard, create project "tg-lens". Save the project URL and anon/service keys.

- [ ] **Step 2: Enable pgvector extension**

In Supabase SQL Editor, run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

- [ ] **Step 3: Write initial migration — channels table**

Create `supabase/migrations/001_initial_schema.sql`:
```sql
-- Channels
CREATE TABLE channels (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id     bigint UNIQUE NOT NULL,
    username        text,
    title           text NOT NULL,
    category        text,
    is_active       boolean DEFAULT true,
    last_scraped_at timestamptz,
    created_at      timestamptz DEFAULT now()
);
```

- [ ] **Step 4: Add posts table to migration**

Append to the same file:
```sql
-- Posts
CREATE TABLE posts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id      uuid NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    telegram_msg_id integer NOT NULL,
    text            text,
    date            timestamptz NOT NULL,
    views           integer,
    forwards        integer,
    reactions_json  jsonb,
    has_media       boolean DEFAULT false,
    media_type      text,
    link            text,
    embedding       vector(1024),
    created_at      timestamptz DEFAULT now(),
    UNIQUE(channel_id, telegram_msg_id)
);
```

- [ ] **Step 5: Add comments table to migration**

Append:
```sql
-- Comments
CREATE TABLE comments (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    telegram_msg_id     integer NOT NULL,
    sender_name         text,
    sender_id           bigint,
    text                text,
    date                timestamptz NOT NULL,
    is_reply            boolean DEFAULT false,
    reply_to_comment_id uuid REFERENCES comments(id),
    embedding           vector(1024),
    created_at          timestamptz DEFAULT now()
);
```

- [ ] **Step 6: Add channel_summaries table**

Append:
```sql
-- Channel summaries (hierarchical: week -> month -> half_year)
CREATE TABLE channel_summaries (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id          uuid NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    period_type         text NOT NULL CHECK (period_type IN ('week', 'month', 'quarter', 'half_year', 'year', 'custom')),
    period_start        timestamptz NOT NULL,
    period_end          timestamptz NOT NULL,
    summary             text,
    facts_json          jsonb,
    post_count          integer,
    status              text DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'error')),
    parent_summary_id   uuid REFERENCES channel_summaries(id),
    model_used          text,
    tokens_used         integer,
    created_at          timestamptz DEFAULT now()
);
```

- [ ] **Step 7: Add digests and digest_posts tables**

Append:
```sql
-- Cross-channel digests
CREATE TABLE digests (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start    timestamptz NOT NULL,
    period_end      timestamptz NOT NULL,
    digest_type     text NOT NULL CHECK (digest_type IN ('headlines', 'brief', 'deep', 'qa', 'actions')),
    summary         text,
    facts_json      jsonb,
    model_used      text,
    tokens_used     integer,
    created_at      timestamptz DEFAULT now()
);

-- Junction: which posts are included in a digest
CREATE TABLE digest_posts (
    digest_id       uuid NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    post_id         uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    PRIMARY KEY(digest_id, post_id)
);

-- Search history for caching
CREATE TABLE search_history (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query           text NOT NULL,
    results_json    jsonb,
    ai_synthesis    text,
    created_at      timestamptz DEFAULT now()
);
```

- [ ] **Step 8: Add indexes**

Append:
```sql
-- Full-text search
CREATE INDEX idx_posts_fts ON posts USING GIN(to_tsvector('russian', coalesce(text, '')));
CREATE INDEX idx_comments_fts ON comments USING GIN(to_tsvector('russian', coalesce(text, '')));

-- Vector search (pgvector HNSW)
CREATE INDEX idx_posts_embedding ON posts USING hnsw(embedding vector_cosine_ops);
CREATE INDEX idx_comments_embedding ON comments USING hnsw(embedding vector_cosine_ops);

-- Query performance
CREATE INDEX idx_posts_channel_date ON posts(channel_id, date DESC);
CREATE INDEX idx_posts_date ON posts(date DESC);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_summaries_channel_period ON channel_summaries(channel_id, period_type, period_start);
CREATE INDEX idx_digests_period ON digests(period_start DESC);
```

- [ ] **Step 9: Run migration in Supabase SQL Editor**

Copy full contents of `001_initial_schema.sql` and execute in Supabase Dashboard → SQL Editor.

- [ ] **Step 10: Commit**

```bash
git add supabase/
git commit -m "feat: add initial database schema with pgvector support"
```

---

### Task 2: Python Project Setup

**Files:**
- Create: `pipeline/pyproject.toml`
- Create: `pipeline/requirements.txt`
- Create: `pipeline/.env.example`
- Create: `pipeline/src/__init__.py`
- Create: `pipeline/src/config.py`
- Create: `pipeline/tests/__init__.py`
- Create: `pipeline/tests/test_config.py`

- [ ] **Step 1: Create project structure**

```
pipeline/
├── src/
│   ├── __init__.py
│   ├── config.py          # Environment & config loading
│   ├── db.py              # Supabase client
│   ├── scraper.py         # Telethon scraping
│   ├── filter.py          # Stage 1: noise filtering
│   ├── classifier.py      # Stage 2: AI classification
│   ├── digest.py          # Stage 3: AI digest generation
│   ├── embeddings.py      # Vector embedding generation
│   └── prompts/
│       ├── classify.txt
│       ├── digest_headlines.txt
│       ├── digest_brief.txt
│       ├── digest_deep.txt
│       ├── digest_qa.txt
│       └── digest_actions.txt
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_filter.py
│   ├── test_classifier.py
│   └── test_digest.py
├── requirements.txt
├── pyproject.toml
└── .env.example
```

- [ ] **Step 2: Write requirements.txt**

Create `pipeline/requirements.txt`:
```
telethon==1.38.1
anthropic>=0.42.0
supabase>=2.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 3: Write .env.example**

Create `pipeline/.env.example`:
```
# Telegram
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

# Claude
ANTHROPIC_API_KEY=

# Embeddings (TBD - will decide provider later)
# VOYAGE_API_KEY=
```

- [ ] **Step 4: Write failing test for config**

Create `pipeline/tests/test_config.py`:
```python
import pytest
from src.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")
    monkeypatch.setenv("TELEGRAM_PHONE", "+1234567890")
    monkeypatch.setenv("SUPABASE_URL", "https://xxx.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")

    settings = Settings()
    assert settings.telegram_api_id == 12345
    assert settings.telegram_api_hash == "abc123"
    assert settings.supabase_url == "https://xxx.supabase.co"


def test_settings_fails_without_required(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    with pytest.raises(Exception):
        Settings()
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd pipeline && python -m pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 6: Implement config**

Create `pipeline/src/config.py`:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    supabase_url: str
    supabase_service_key: str
    anthropic_api_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

Create `pipeline/src/__init__.py` and `pipeline/tests/__init__.py` as empty files.

- [ ] **Step 7: Run test to verify it passes**

```bash
cd pipeline && python -m pytest tests/test_config.py -v
```
Expected: 2 PASSED

- [ ] **Step 8: Commit**

```bash
git add pipeline/
git commit -m "feat: add Python pipeline project structure with config"
```

---

### Task 3: Supabase Client (db.py)

**Files:**
- Create: `pipeline/src/db.py`
- Create: `pipeline/tests/test_db.py`

- [ ] **Step 1: Write failing test for db client**

Create `pipeline/tests/test_db.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
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
    posts = [
        {
            "channel_id": "uuid-ch",
            "telegram_msg_id": 1,
            "text": "Hello",
            "date": "2026-03-01T00:00:00Z",
        }
    ]
    result = db.insert_posts(posts)
    assert len(result) == 1


def test_get_posts_for_period():
    mock_client = MagicMock()
    mock_data = [{"id": "uuid-1", "text": "post1"}]
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value.execute.return_value.data = mock_data

    db = SupabaseDB(client=mock_client)
    result = db.get_posts_for_period("channel-uuid", "2026-03-01", "2026-03-07")
    assert len(result) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pipeline && python -m pytest tests/test_db.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.db'`

- [ ] **Step 3: Implement db.py**

Create `pipeline/src/db.py`:
```python
from supabase import Client


class SupabaseDB:
    def __init__(self, client: Client):
        self.client = client

    # --- Channels ---

    def upsert_channel(self, telegram_id: int, username: str, title: str, category: str = None) -> dict:
        data = {
            "telegram_id": telegram_id,
            "username": username,
            "title": title,
            "category": category,
        }
        result = self.client.table("channels").upsert(data, on_conflict="telegram_id").execute()
        return result.data[0]

    def get_active_channels(self) -> list[dict]:
        result = self.client.table("channels").select("*").eq("is_active", True).execute()
        return result.data

    def update_last_scraped(self, channel_id: str, scraped_at: str):
        self.client.table("channels").update({"last_scraped_at": scraped_at}).eq("id", channel_id).execute()

    # --- Posts ---

    def insert_posts(self, posts: list[dict]) -> list[dict]:
        result = self.client.table("posts").upsert(
            posts, on_conflict="channel_id,telegram_msg_id"
        ).execute()
        return result.data

    def get_posts_for_period(self, channel_id: str, start: str, end: str) -> list[dict]:
        result = (
            self.client.table("posts")
            .select("*")
            .eq("channel_id", channel_id)
            .gte("date", start)
            .lte("date", end)
            .order("date")
            .execute()
        )
        return result.data

    # --- Comments ---

    def insert_comments(self, comments: list[dict]) -> list[dict]:
        result = self.client.table("comments").upsert(
            comments, on_conflict="post_id,telegram_msg_id"
        ).execute()
        return result.data

    def get_comments_for_post(self, post_id: str) -> list[dict]:
        result = self.client.table("comments").select("*").eq("post_id", post_id).order("date").execute()
        return result.data

    # --- Summaries ---

    def get_summary(self, channel_id: str, period_type: str, period_start: str) -> dict | None:
        result = (
            self.client.table("channel_summaries")
            .select("*")
            .eq("channel_id", channel_id)
            .eq("period_type", period_type)
            .eq("period_start", period_start)
            .execute()
        )
        return result.data[0] if result.data else None

    def upsert_summary(self, summary: dict) -> dict:
        result = self.client.table("channel_summaries").upsert(summary).execute()
        return result.data[0]

    # --- Digests ---

    def insert_digest(self, digest: dict) -> dict:
        result = self.client.table("digests").insert(digest).execute()
        return result.data[0]

    def link_digest_posts(self, digest_id: str, post_ids: list[str]):
        rows = [{"digest_id": digest_id, "post_id": pid} for pid in post_ids]
        self.client.table("digest_posts").insert(rows).execute()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd pipeline && python -m pytest tests/test_db.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/db.py pipeline/tests/test_db.py
git commit -m "feat: add Supabase database client with CRUD operations"
```

---

### Task 4: Telegram Scraper

**Files:**
- Create: `pipeline/src/scraper.py`
- Create: `pipeline/tests/test_scraper.py`

- [ ] **Step 1: Write failing test for message parsing**

Create `pipeline/tests/test_scraper.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.scraper import TelegramScraper


def test_parse_message_to_dict():
    """Test that a Telethon message object is correctly parsed to a dict."""
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pipeline && python -m pytest tests/test_scraper.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement scraper**

Create `pipeline/src/scraper.py`:
```python
import logging
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

logger = logging.getLogger(__name__)


class TelegramScraper:
    def __init__(self, api_id: int, api_hash: str, session_path: str = "tg_session"):
        self.client = TelegramClient(session_path, api_id, api_hash)

    async def connect(self, phone: str):
        await self.client.start(phone=phone)
        logger.info("Connected to Telegram")

    async def disconnect(self):
        await self.client.disconnect()

    @staticmethod
    def parse_message(msg, channel_id: str, channel_username: str) -> dict:
        """Parse a Telethon message into a dict for DB storage."""
        # Detect media type
        has_media = msg.media is not None
        media_type = None
        if has_media:
            if getattr(msg, "photo", None):
                media_type = "photo"
            elif getattr(msg, "video", None):
                media_type = "video"
            elif getattr(msg, "document", None):
                media_type = "document"
            else:
                media_type = "other"

        # Parse reactions
        reactions_json = None
        if msg.reactions and hasattr(msg.reactions, "results"):
            reactions_json = {}
            for r in msg.reactions.results:
                emoji = getattr(r.reaction, "emoticon", str(r.reaction))
                reactions_json[emoji] = r.count

        link = f"https://t.me/{channel_username}/{msg.id}" if channel_username else None

        return {
            "channel_id": channel_id,
            "telegram_msg_id": msg.id,
            "text": msg.text,
            "date": msg.date.isoformat(),
            "views": msg.views or 0,
            "forwards": msg.forwards or 0,
            "reactions_json": reactions_json,
            "has_media": has_media,
            "media_type": media_type,
            "link": link,
        }

    @staticmethod
    def parse_comment(msg, post_id: str) -> dict:
        """Parse a comment message into a dict for DB storage."""
        sender = msg.get_sender()
        sender_name = None
        sender_id = None
        if sender:
            sender_name = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            if last:
                sender_name = f"{sender_name} {last}".strip()
            if not sender_name:
                sender_name = getattr(sender, "title", None)
            sender_id = sender.id

        return {
            "post_id": post_id,
            "telegram_msg_id": msg.id,
            "sender_name": sender_name,
            "sender_id": sender_id,
            "text": msg.text,
            "date": msg.date.isoformat(),
            "is_reply": msg.is_reply,
            "reply_to_comment_id": None,  # resolved later if needed
        }

    async def scrape_channel(self, channel_id_or_username, db_channel_id: str,
                              channel_username: str, since: datetime = None) -> tuple[list, list]:
        """
        Scrape posts and comments from a channel since a given datetime.
        Returns (posts, comments) as lists of dicts.
        """
        posts = []
        comments = []

        async for msg in self.client.iter_messages(channel_id_or_username):
            if since and msg.date < since:
                break

            post_dict = self.parse_message(msg, channel_id=db_channel_id, channel_username=channel_username)
            posts.append(post_dict)

            # Scrape comments (discussion) if available
            try:
                async for reply in self.client.iter_messages(
                    channel_id_or_username, reply_to=msg.id
                ):
                    comment_dict = self.parse_comment(reply, post_id=None)  # post_id set after DB insert
                    comment_dict["_parent_telegram_msg_id"] = msg.id
                    comments.append(comment_dict)
            except Exception as e:
                # Some channels don't have comments enabled
                logger.debug(f"No comments for msg {msg.id}: {e}")

        posts.reverse()
        comments.reverse()
        logger.info(f"Scraped {len(posts)} posts and {len(comments)} comments from {channel_username}")
        return posts, comments
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd pipeline && python -m pytest tests/test_scraper.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/scraper.py pipeline/tests/test_scraper.py
git commit -m "feat: add Telegram scraper with message/comment parsing"
```

---

## Chunk 2: AI Pipeline

### Task 5: Noise Filter (Stage 1)

**Files:**
- Create: `pipeline/src/filter.py`
- Create: `pipeline/tests/test_filter.py`

- [ ] **Step 1: Write failing tests**

Create `pipeline/tests/test_filter.py`:
```python
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
    """Short post with high engagement should be kept."""
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd pipeline && python -m pytest tests/test_filter.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement filter**

Create `pipeline/src/filter.py`:
```python
import re

# Messages that are just noise
SKIP_PATTERNS = [
    r"^[\+\-\!\.]+$",                    # just +, -, !, .
    r"^(ok|ок|да|нет|ага|угу|лол|кек)$",
    r"^спасибо[!\.]*$",
    r"^привет[!\.]*( всем[!\.]*)?$",
    r"^здравствуйте[!\.]*$",
    r"^добрый (день|вечер|утро)[!\.]*$",
    r"^(👍|👎|😂|🤣|❤️|🔥|👏|😭|🎉)+$",  # just emojis
]

SKIP_COMPILED = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]

MIN_TEXT_LENGTH = 20
MIN_ENGAGEMENT_TO_KEEP_SHORT = 50  # views + forwards + reactions total


class NoiseFilter:
    @staticmethod
    def _engagement_score(post: dict) -> int:
        views = post.get("views") or 0
        forwards = post.get("forwards") or 0
        reactions = 0
        if post.get("reactions_json"):
            reactions = sum(post["reactions_json"].values())
        return views + forwards * 5 + reactions * 3

    @staticmethod
    def filter_posts(posts: list[dict]) -> list[dict]:
        """Filter out noise posts. Returns list of posts worth analyzing."""
        result = []
        for post in posts:
            text = post.get("text")

            # No text at all
            if not text:
                continue

            text_stripped = text.strip()

            # Check skip patterns
            if any(p.match(text_stripped) for p in SKIP_COMPILED):
                engagement = NoiseFilter._engagement_score(post)
                if engagement < MIN_ENGAGEMENT_TO_KEEP_SHORT:
                    continue

            # Too short (unless high engagement)
            if len(text_stripped) < MIN_TEXT_LENGTH:
                engagement = NoiseFilter._engagement_score(post)
                if engagement < MIN_ENGAGEMENT_TO_KEEP_SHORT:
                    continue

            result.append(post)
        return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd pipeline && python -m pytest tests/test_filter.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/filter.py pipeline/tests/test_filter.py
git commit -m "feat: add noise filter for stage 1 message filtering"
```

---

### Task 6: AI Classifier (Stage 2)

**Files:**
- Create: `pipeline/src/classifier.py`
- Create: `pipeline/src/prompts/classify.txt`
- Create: `pipeline/tests/test_classifier.py`

- [ ] **Step 1: Write classification prompt**

Create `pipeline/src/prompts/classify.txt`:
```
Ты анализируешь сообщения из Telegram-канала. Для каждого сообщения определи категорию:

- FACT — конкретный факт, событие, новость, объявление, важная информация
- EXPERIENCE — личный опыт, решение проблемы, полезный совет, инструкция, рекомендация
- DISCUSSION — ключевой аргумент в дискуссии, интересное мнение, экспертная оценка
- SKIP — болтовня, приветствия, мемы, оффтоп, короткие реакции без содержания

Верни ТОЛЬКО JSON-массив в формате:
[{"id": "<message_id>", "category": "FACT|EXPERIENCE|DISCUSSION|SKIP"}]

Без пояснений, только JSON.

Сообщения:
{messages}
```

- [ ] **Step 2: Write failing test**

Create `pipeline/tests/test_classifier.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd pipeline && python -m pytest tests/test_classifier.py -v
```
Expected: FAIL

- [ ] **Step 4: Implement classifier**

Create `pipeline/src/classifier.py`:
```python
import json
import re
import logging
from pathlib import Path
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "classify.txt"
BATCH_SIZE = 50
KEEP_CATEGORIES = {"FACT", "EXPERIENCE", "DISCUSSION"}


class AIClassifier:
    def __init__(self, client: AsyncAnthropic = None, model: str = "claude-sonnet-4-20250514"):
        self.client = client
        self.model = model
        self.prompt_template = PROMPT_PATH.read_text(encoding="utf-8")

    @staticmethod
    def _build_batch_prompt(posts: list[dict]) -> str:
        lines = []
        for p in posts:
            lines.append(f'[{p["id"]}] {p["text"][:500]}')
        return "\n\n".join(lines)

    @staticmethod
    def _parse_response(text: str) -> dict[str, str]:
        # Strip markdown code block if present
        cleaned = re.sub(r"^```(?:json)?\n?", "", text.strip())
        cleaned = re.sub(r"\n?```$", "", cleaned)
        items = json.loads(cleaned)
        return {item["id"]: item["category"] for item in items}

    async def classify_batch(self, posts: list[dict]) -> dict[str, str]:
        messages_text = self._build_batch_prompt(posts)
        prompt = self.prompt_template.replace("{messages}", messages_text)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_response(response.content[0].text)

    async def classify_all(self, posts: list[dict]) -> list[dict]:
        """Classify all posts in batches. Returns only posts with KEEP_CATEGORIES."""
        important = []
        for i in range(0, len(posts), BATCH_SIZE):
            batch = posts[i : i + BATCH_SIZE]
            classifications = await self.classify_batch(batch)

            for post in batch:
                category = classifications.get(post["id"], "SKIP")
                if category in KEEP_CATEGORIES:
                    post["_category"] = category
                    important.append(post)

            logger.info(f"Classified batch {i // BATCH_SIZE + 1}: {len(batch)} posts, {len([p for p in batch if classifications.get(p['id'], 'SKIP') in KEEP_CATEGORIES])} important")

        return important
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd pipeline && python -m pytest tests/test_classifier.py -v
```
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add pipeline/src/classifier.py pipeline/src/prompts/classify.txt pipeline/tests/test_classifier.py
git commit -m "feat: add AI classifier for stage 2 message categorization"
```

---

### Task 7: Digest Generator (Stage 3)

**Files:**
- Create: `pipeline/src/digest.py`
- Create: `pipeline/src/prompts/digest_headlines.txt`
- Create: `pipeline/src/prompts/digest_brief.txt`
- Create: `pipeline/src/prompts/digest_deep.txt`
- Create: `pipeline/src/prompts/digest_qa.txt`
- Create: `pipeline/src/prompts/digest_actions.txt`
- Create: `pipeline/tests/test_digest.py`

- [ ] **Step 1: Write all 5 digest prompts**

Create `pipeline/src/prompts/digest_headlines.txt`:
```
Ты создаёшь дайджест из сообщений Telegram-канала.

Формат: HEADLINES — одна строка на событие. Максимально сжато, для быстрого скана за 30 секунд.

Правила:
- Каждое событие — одна строка с "•" в начале
- Без деталей, только суть
- Группируй по темам если есть явные кластеры
- Язык: русский (или язык оригинала если канал не на русском)
- Если есть ссылка на оригинал — добавь в конце строки [ссылка](url)

Сообщения за период {period}:
{messages}
```

Create `pipeline/src/prompts/digest_brief.txt`:
```
Ты создаёшь дайджест из сообщений Telegram-канала.

Формат: BRIEF — 2-3 предложения на каждую тему. Читатель должен понять суть без обращения к оригиналу.

Правила:
- Группируй по темам с заголовком
- На каждую тему: 2-3 предложения с ключевыми деталями
- Указывай имена авторов если релевантно
- Ссылки на оригинальные посты
- Язык: русский

Сообщения за период {period}:
{messages}
```

Create `pipeline/src/prompts/digest_deep.txt`:
```
Ты создаёшь дайджест из сообщений Telegram-канала.

Формат: DEEP DIVE — полный контекст каждой важной темы.

Правила:
- Группируй по темам
- Для каждой темы: что произошло, кто участвовал, какие аргументы, цитаты, чем кончилось
- Включай прямые цитаты из сообщений (в кавычках с указанием автора)
- Описывай ход дискуссий если были
- Ссылки на все оригинальные посты
- Язык: русский

Сообщения за период {period}:
{messages}
```

Create `pipeline/src/prompts/digest_qa.txt`:
```
Ты создаёшь дайджест из сообщений Telegram-канала.

Формат: Q&A — вопросы которые задавали люди и лучшие ответы.

Правила:
- Найди все вопросы (явные и неявные) в сообщениях
- Для каждого вопроса: кто спросил, лучший ответ, кто ответил
- Если вопрос без ответа — тоже включи с пометкой "без ответа"
- Формат: "В: ... / О: ..."
- Ссылки на оригинальные треды
- Язык: русский

Сообщения за период {period}:
{messages}
```

Create `pipeline/src/prompts/digest_actions.txt`:
```
Ты создаёшь дайджест из сообщений Telegram-канала.

Формат: ACTION ITEMS — только то, что требует внимания или действий.

Правила:
- Выдели только то на что нужно реагировать: дедлайны, отзывы, предупреждения, изменения правил, важные анонсы
- Полезные советы и рекомендации тоже включай
- Используй иконки: ⚠️ (предупреждение), 📅 (дедлайн), 💡 (совет), 📢 (анонс)
- Если ничего не требует действий — так и напиши
- Ссылки на оригиналы
- Язык: русский

Сообщения за период {period}:
{messages}
```

- [ ] **Step 2: Write failing test**

Create `pipeline/tests/test_digest.py`:
```python
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd pipeline && python -m pytest tests/test_digest.py -v
```
Expected: FAIL

- [ ] **Step 4: Implement digest generator**

Create `pipeline/src/digest.py`:
```python
import logging
from pathlib import Path
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


class DigestGenerator:
    FORMATS = ["headlines", "brief", "deep", "qa", "actions"]

    def __init__(self, client: AsyncAnthropic = None, model: str = "claude-sonnet-4-20250514"):
        self.client = client
        self.model = model
        self.prompts = {}
        for fmt in self.FORMATS:
            path = PROMPTS_DIR / f"digest_{fmt}.txt"
            self.prompts[fmt] = path.read_text(encoding="utf-8")

    @staticmethod
    def available_formats() -> list[str]:
        return list(DigestGenerator.FORMATS)

    @staticmethod
    def _format_messages(posts: list[dict]) -> str:
        lines = []
        for p in posts:
            category = p.get("_category", "")
            date = p.get("date", "")[:10]
            link = p.get("link", "")
            text = (p.get("text") or "")[:1000]
            lines.append(f"[{category}] [{date}] {text}\nLink: {link}")
        return "\n\n---\n\n".join(lines)

    async def generate(self, format_name: str, posts: list[dict], period: str) -> dict:
        """Generate a digest in the specified format. Returns dict with summary and metadata."""
        if format_name not in self.FORMATS:
            raise ValueError(f"Unknown format: {format_name}. Available: {self.FORMATS}")

        messages_text = self._format_messages(posts)
        prompt = self.prompts[format_name].replace("{messages}", messages_text).replace("{period}", period)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        return {
            "summary": response.content[0].text,
            "digest_type": format_name,
            "model_used": self.model,
            "tokens_used": tokens_used,
        }

    async def generate_all_formats(self, posts: list[dict], period: str) -> list[dict]:
        """Generate digests in all 5 formats."""
        results = []
        for fmt in self.FORMATS:
            result = await self.generate(fmt, posts, period)
            results.append(result)
            logger.info(f"Generated {fmt} digest: {result['tokens_used']} tokens")
        return results
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd pipeline && python -m pytest tests/test_digest.py -v
```
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add pipeline/src/digest.py pipeline/src/prompts/ pipeline/tests/test_digest.py
git commit -m "feat: add digest generator with 5 output formats"
```

---

## Chunk 3: Orchestration & GitHub Actions

### Task 8: Main Pipeline Orchestrator

**Files:**
- Create: `pipeline/src/pipeline.py`
- Create: `pipeline/run_scrape.py`
- Create: `pipeline/run_digest.py`

- [ ] **Step 1: Create scrape orchestrator**

Create `pipeline/run_scrape.py`:
```python
"""
Entry point for scraping pipeline.
Usage: python run_scrape.py [--channel CHANNEL_USERNAME]
Scrapes all active channels (or a specific one) and saves to Supabase.
"""
import asyncio
import argparse
import logging
from datetime import datetime, timezone
from supabase import create_client
from anthropic import AsyncAnthropic

from src.config import Settings
from src.db import SupabaseDB
from src.scraper import TelegramScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def scrape_channel(scraper: TelegramScraper, db: SupabaseDB, channel: dict):
    """Scrape a single channel and save results."""
    since = None
    if channel.get("last_scraped_at"):
        since = datetime.fromisoformat(channel["last_scraped_at"])

    logger.info(f"Scraping {channel['username'] or channel['telegram_id']} since {since}")

    posts, comments = await scraper.scrape_channel(
        channel_id_or_username=channel.get("username") or channel["telegram_id"],
        db_channel_id=channel["id"],
        channel_username=channel.get("username", ""),
        since=since,
    )

    if posts:
        saved_posts = db.insert_posts(posts)
        logger.info(f"Saved {len(saved_posts)} posts")

        # Map telegram_msg_id -> db uuid for linking comments
        post_id_map = {p["telegram_msg_id"]: p["id"] for p in saved_posts}

        # Set post_id on comments
        for comment in comments:
            parent_msg_id = comment.pop("_parent_telegram_msg_id", None)
            if parent_msg_id and parent_msg_id in post_id_map:
                comment["post_id"] = post_id_map[parent_msg_id]

        comments_with_post = [c for c in comments if c.get("post_id")]
        if comments_with_post:
            saved_comments = db.insert_comments(comments_with_post)
            logger.info(f"Saved {len(saved_comments)} comments")

    db.update_last_scraped(channel["id"], datetime.now(timezone.utc).isoformat())


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", type=str, help="Scrape specific channel username")
    args = parser.parse_args()

    settings = Settings()
    supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)
    db = SupabaseDB(client=supabase_client)
    scraper = TelegramScraper(settings.telegram_api_id, settings.telegram_api_hash)

    await scraper.connect(settings.telegram_phone)

    try:
        if args.channel:
            # Scrape specific channel
            channels = db.get_active_channels()
            channel = next((c for c in channels if c["username"] == args.channel), None)
            if not channel:
                logger.error(f"Channel {args.channel} not found in DB")
                return
            await scrape_channel(scraper, db, channel)
        else:
            # Scrape all active channels
            channels = db.get_active_channels()
            logger.info(f"Scraping {len(channels)} active channels")
            for channel in channels:
                try:
                    await scrape_channel(scraper, db, channel)
                except Exception as e:
                    logger.error(f"Error scraping {channel.get('username')}: {e}")
    finally:
        await scraper.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Create digest orchestrator**

Create `pipeline/run_digest.py`:
```python
"""
Entry point for digest generation pipeline.
Usage:
  python run_digest.py --type weekly
  python run_digest.py --type monthly
  python run_digest.py --channel mychannel --start 2026-01-01 --end 2026-03-01
"""
import asyncio
import argparse
import logging
from datetime import datetime, timedelta, timezone
from supabase import create_client
from anthropic import AsyncAnthropic

from src.config import Settings
from src.db import SupabaseDB
from src.filter import NoiseFilter
from src.classifier import AIClassifier
from src.digest import DigestGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_week_range() -> tuple[str, str]:
    """Get last week's Monday-Sunday range."""
    today = datetime.now(timezone.utc)
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return last_monday.isoformat(), last_sunday.isoformat()


def get_month_range() -> tuple[str, str]:
    """Get last month's range."""
    today = datetime.now(timezone.utc)
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_of_prev_month = first_of_this_month - timedelta(seconds=1)
    first_of_prev_month = last_of_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_of_prev_month.isoformat(), last_of_prev_month.isoformat()


async def generate_channel_digest(db: SupabaseDB, classifier: AIClassifier,
                                    generator: DigestGenerator, channel: dict,
                                    start: str, end: str, period_type: str):
    """Full pipeline: filter -> classify -> generate digest for one channel."""

    # Check if summary already exists
    existing = db.get_summary(channel["id"], period_type, start)
    if existing and existing["status"] == "done":
        logger.info(f"Summary already exists for {channel['username']} ({period_type} {start})")
        return existing

    # Mark as processing
    summary_record = db.upsert_summary({
        "channel_id": channel["id"],
        "period_type": period_type,
        "period_start": start,
        "period_end": end,
        "status": "processing",
    })

    try:
        # Get raw posts
        posts = db.get_posts_for_period(channel["id"], start, end)
        logger.info(f"{channel['username']}: {len(posts)} raw posts")

        if not posts:
            db.upsert_summary({**summary_record, "status": "done", "summary": "No posts in period.", "post_count": 0})
            return

        # Stage 1: noise filter
        filtered = NoiseFilter.filter_posts(posts)
        logger.info(f"{channel['username']}: {len(filtered)} after noise filter")

        # Stage 2: AI classification
        classified = await classifier.classify_all(filtered)
        logger.info(f"{channel['username']}: {len(classified)} important posts")

        if not classified:
            db.upsert_summary({**summary_record, "status": "done", "summary": "No important posts found.", "post_count": 0})
            return

        # Stage 3: generate all formats
        period_label = f"{start[:10]} — {end[:10]}"
        digests = await generator.generate_all_formats(classified, period_label)

        # Save channel summary (use 'brief' as the main summary)
        brief = next(d for d in digests if d["digest_type"] == "brief")
        total_tokens = sum(d["tokens_used"] for d in digests)

        db.upsert_summary({
            **summary_record,
            "status": "done",
            "summary": brief["summary"],
            "facts_json": {fmt: d["summary"] for fmt, d in zip(DigestGenerator.FORMATS, digests)},
            "post_count": len(classified),
            "model_used": brief["model_used"],
            "tokens_used": total_tokens,
        })

        logger.info(f"{channel['username']}: digest done, {total_tokens} tokens total")

    except Exception as e:
        logger.error(f"Error generating digest for {channel['username']}: {e}")
        db.upsert_summary({**summary_record, "status": "error"})
        raise


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["weekly", "monthly", "custom"], required=True)
    parser.add_argument("--channel", type=str, help="Specific channel username (default: all)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD) for custom type")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD) for custom type")
    args = parser.parse_args()

    settings = Settings()
    supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)
    db = SupabaseDB(client=supabase_client)
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    classifier = AIClassifier(client=anthropic_client)
    generator = DigestGenerator(client=anthropic_client)

    # Determine period
    if args.type == "weekly":
        start, end = get_week_range()
        period_type = "week"
    elif args.type == "monthly":
        start, end = get_month_range()
        period_type = "month"
    else:
        if not args.start or not args.end:
            raise ValueError("--start and --end required for custom type")
        start = f"{args.start}T00:00:00+00:00"
        end = f"{args.end}T23:59:59+00:00"
        period_type = "custom"

    # Get channels
    channels = db.get_active_channels()
    if args.channel:
        channels = [c for c in channels if c["username"] == args.channel]

    logger.info(f"Generating {period_type} digests for {len(channels)} channels ({start[:10]} to {end[:10]})")

    for channel in channels:
        try:
            await generate_channel_digest(db, classifier, generator, channel, start, end, period_type)
        except Exception as e:
            logger.error(f"Failed for {channel.get('username')}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/run_scrape.py pipeline/run_digest.py
git commit -m "feat: add scrape and digest pipeline orchestrators"
```

---

### Task 9: GitHub Actions Workflows

**Files:**
- Create: `.github/workflows/scrape.yml`
- Create: `.github/workflows/digest-weekly.yml`
- Create: `.github/workflows/digest-monthly.yml`

- [ ] **Step 1: Create scrape workflow**

Create `.github/workflows/scrape.yml`:
```yaml
name: Scrape Telegram Channels

on:
  workflow_dispatch:
  schedule:
    - cron: '0 6 * * *'  # Daily at 06:00 UTC

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: pipeline/requirements.txt

      - name: Install dependencies
        run: pip install -r pipeline/requirements.txt

      - name: Download Telethon session
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: |
          python -c "
          from supabase import create_client
          import os
          client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
          data = client.storage.from_('sessions').download('tg_session.session')
          with open('pipeline/tg_session.session', 'wb') as f:
              f.write(data)
          print('Session downloaded')
          " || echo "No existing session found, will create new one"

      - name: Run scraper
        working-directory: pipeline
        env:
          TELEGRAM_API_ID: ${{ secrets.TELEGRAM_API_ID }}
          TELEGRAM_API_HASH: ${{ secrets.TELEGRAM_API_HASH }}
          TELEGRAM_PHONE: ${{ secrets.TELEGRAM_PHONE }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python run_scrape.py

      - name: Upload Telethon session
        if: always()
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: |
          python -c "
          from supabase import create_client
          import os
          client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
          with open('pipeline/tg_session.session', 'rb') as f:
              client.storage.from_('sessions').upload('tg_session.session', f, {'upsert': 'true'})
          print('Session uploaded')
          " || echo "No session to upload"
```

- [ ] **Step 2: Create weekly digest workflow**

Create `.github/workflows/digest-weekly.yml`:
```yaml
name: Generate Weekly Digests

on:
  workflow_dispatch:
  schedule:
    - cron: '0 7 * * 1'  # Every Monday at 07:00 UTC

jobs:
  digest:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: pipeline/requirements.txt

      - name: Install dependencies
        run: pip install -r pipeline/requirements.txt

      - name: Generate weekly digests
        working-directory: pipeline
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python run_digest.py --type weekly
```

- [ ] **Step 3: Create monthly digest workflow**

Create `.github/workflows/digest-monthly.yml`:
```yaml
name: Generate Monthly Digests

on:
  workflow_dispatch:
  schedule:
    - cron: '0 8 1 * *'  # 1st of each month at 08:00 UTC

jobs:
  digest:
    runs-on: ubuntu-latest
    timeout-minutes: 90

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: pipeline/requirements.txt

      - name: Install dependencies
        run: pip install -r pipeline/requirements.txt

      - name: Generate monthly digests
        working-directory: pipeline
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python run_digest.py --type monthly
```

- [ ] **Step 4: Commit**

```bash
git add .github/
git commit -m "feat: add GitHub Actions workflows for scraping and digest generation"
```

---

## Chunk 4: Next.js Frontend

### Task 10: Next.js Project Setup

**Files:**
- Create: `web/` (Next.js project via create-next-app)
- Create: `web/.env.example`

- [ ] **Step 1: Create Next.js app**

```bash
cd /c/Users/Dem/ai/tg-lens
npx create-next-app@latest web --typescript --tailwind --app --src-dir --no-eslint --import-alias "@/*"
```

- [ ] **Step 2: Install dependencies**

```bash
cd web
npm install @supabase/supabase-js @supabase/ssr
npm install lucide-react date-fns
```

- [ ] **Step 3: Create .env.example**

Create `web/.env.example`:
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
GITHUB_TOKEN=
GITHUB_REPO=dementy-fut/tg-lens
```

- [ ] **Step 4: Create Supabase client helper**

Create `web/src/lib/supabase.ts`:
```typescript
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

Create `web/src/lib/supabase-server.ts`:
```typescript
import { createClient } from "@supabase/supabase-js";

export function createServerClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

- [ ] **Step 5: Create types**

Create `web/src/lib/types.ts`:
```typescript
export interface Channel {
  id: string;
  telegram_id: number;
  username: string;
  title: string;
  category: string | null;
  is_active: boolean;
  last_scraped_at: string | null;
  created_at: string;
}

export interface Post {
  id: string;
  channel_id: string;
  telegram_msg_id: number;
  text: string | null;
  date: string;
  views: number;
  forwards: number;
  reactions_json: Record<string, number> | null;
  has_media: boolean;
  media_type: string | null;
  link: string | null;
}

export interface ChannelSummary {
  id: string;
  channel_id: string;
  period_type: string;
  period_start: string;
  period_end: string;
  summary: string | null;
  facts_json: Record<string, string> | null;
  post_count: number | null;
  status: string;
  created_at: string;
}

export type DigestFormat = "headlines" | "brief" | "deep" | "qa" | "actions";

export const DIGEST_FORMAT_LABELS: Record<DigestFormat, string> = {
  headlines: "Headlines",
  brief: "Brief",
  deep: "Deep Dive",
  qa: "Q&A",
  actions: "Actions",
};
```

- [ ] **Step 6: Commit**

```bash
git add web/
git commit -m "feat: scaffold Next.js frontend with Supabase client and types"
```

---

### Task 11: Dashboard Page

**Files:**
- Modify: `web/src/app/page.tsx`
- Create: `web/src/app/layout.tsx` (modify default)
- Create: `web/src/components/digest-viewer.tsx`
- Create: `web/src/components/format-switcher.tsx`
- Create: `web/src/components/channel-card.tsx`

- [ ] **Step 1: Create format switcher component**

Create `web/src/components/format-switcher.tsx`:
```tsx
"use client";

import { DigestFormat, DIGEST_FORMAT_LABELS } from "@/lib/types";

interface Props {
  current: DigestFormat;
  onChange: (format: DigestFormat) => void;
}

const FORMATS: DigestFormat[] = ["headlines", "brief", "deep", "qa", "actions"];

export function FormatSwitcher({ current, onChange }: Props) {
  return (
    <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
      {FORMATS.map((fmt) => (
        <button
          key={fmt}
          onClick={() => onChange(fmt)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            current === fmt
              ? "bg-white shadow-sm text-gray-900"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          {DIGEST_FORMAT_LABELS[fmt]}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create digest viewer component**

Create `web/src/components/digest-viewer.tsx`:
```tsx
"use client";

import { useState } from "react";
import { ChannelSummary, DigestFormat } from "@/lib/types";
import { FormatSwitcher } from "./format-switcher";

interface Props {
  summary: ChannelSummary;
}

export function DigestViewer({ summary }: Props) {
  const [format, setFormat] = useState<DigestFormat>("brief");

  const content = summary.facts_json?.[format] || summary.summary || "No digest available.";

  return (
    <div>
      <FormatSwitcher current={format} onChange={setFormat} />
      <div className="mt-4 prose prose-sm max-w-none whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create channel card component**

Create `web/src/components/channel-card.tsx`:
```tsx
import Link from "next/link";
import { Channel } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

interface Props {
  channel: Channel;
  postCount?: number;
  latestSummary?: string;
}

export function ChannelCard({ channel, postCount, latestSummary }: Props) {
  return (
    <Link href={`/channels/${channel.id}`}>
      <div className="border rounded-lg p-4 hover:border-blue-400 hover:shadow-sm transition-all">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-gray-900">{channel.title}</h3>
          {channel.category && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
              {channel.category}
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-2">
          @{channel.username}
          {channel.last_scraped_at && (
            <> &middot; обновлено {formatDistanceToNow(new Date(channel.last_scraped_at), { addSuffix: true, locale: ru })}</>
          )}
        </p>
        {latestSummary && (
          <p className="text-sm text-gray-700 line-clamp-3">{latestSummary}</p>
        )}
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Build dashboard page**

Modify `web/src/app/page.tsx`:
```tsx
import { createServerClient } from "@/lib/supabase-server";
import { ChannelCard } from "@/components/channel-card";
import { Channel, ChannelSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

async function getChannels(): Promise<Channel[]> {
  const supabase = createServerClient();
  const { data } = await supabase
    .from("channels")
    .select("*")
    .eq("is_active", true)
    .order("category")
    .order("title");
  return data || [];
}

async function getLatestDigests(): Promise<Record<string, ChannelSummary>> {
  const supabase = createServerClient();
  const { data } = await supabase
    .from("channel_summaries")
    .select("*")
    .eq("status", "done")
    .order("period_end", { ascending: false });

  const map: Record<string, ChannelSummary> = {};
  for (const s of data || []) {
    if (!map[s.channel_id]) {
      map[s.channel_id] = s;
    }
  }
  return map;
}

export default async function Dashboard() {
  const [channels, digests] = await Promise.all([getChannels(), getLatestDigests()]);

  // Group by category
  const grouped: Record<string, Channel[]> = {};
  for (const ch of channels) {
    const cat = ch.category || "other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(ch);
  }

  return (
    <main className="max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">TG Lens</h1>
        <TriggerScrapeButton />
      </div>

      {Object.entries(grouped).map(([category, chs]) => (
        <section key={category} className="mb-8">
          <h2 className="text-lg font-semibold text-gray-700 mb-3 capitalize">{category}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {chs.map((ch) => (
              <ChannelCard
                key={ch.id}
                channel={ch}
                latestSummary={digests[ch.id]?.summary?.slice(0, 200)}
              />
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}

function TriggerScrapeButton() {
  return (
    <form action="/api/trigger-scrape" method="POST">
      <button
        type="submit"
        className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
      >
        Обработать новые
      </button>
    </form>
  );
}
```

- [ ] **Step 5: Create trigger-scrape API route**

Create `web/src/app/api/trigger-scrape/route.ts`:
```typescript
import { NextResponse } from "next/server";

export async function POST() {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || "dementy-fut/tg-lens";

  if (!token) {
    return NextResponse.json({ error: "GITHUB_TOKEN not set" }, { status: 500 });
  }

  const res = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/scrape.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
      },
      body: JSON.stringify({ ref: "master" }),
    }
  );

  if (res.ok || res.status === 204) {
    return NextResponse.redirect(new URL("/", process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000"));
  }

  const error = await res.text();
  return NextResponse.json({ error }, { status: res.status });
}
```

- [ ] **Step 6: Commit**

```bash
git add web/src/
git commit -m "feat: add dashboard page with channel cards and format switcher"
```

---

### Task 12: Channel Detail Page

**Files:**
- Create: `web/src/app/channels/[id]/page.tsx`
- Create: `web/src/components/summary-timeline.tsx`

- [ ] **Step 1: Create summary timeline component**

Create `web/src/components/summary-timeline.tsx`:
```tsx
"use client";

import { useState } from "react";
import { ChannelSummary, DigestFormat } from "@/lib/types";
import { FormatSwitcher } from "./format-switcher";
import { format } from "date-fns";
import { ru } from "date-fns/locale";

interface Props {
  summaries: ChannelSummary[];
}

export function SummaryTimeline({ summaries }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(summaries[0]?.id || null);
  const [digestFormat, setDigestFormat] = useState<DigestFormat>("brief");

  const selected = summaries.find((s) => s.id === selectedId);
  const content = selected?.facts_json?.[digestFormat] || selected?.summary || "";

  return (
    <div className="grid grid-cols-4 gap-6">
      {/* Timeline sidebar */}
      <div className="col-span-1 space-y-1">
        {summaries.map((s) => (
          <button
            key={s.id}
            onClick={() => setSelectedId(s.id)}
            className={`w-full text-left px-3 py-2 rounded-md text-sm ${
              selectedId === s.id
                ? "bg-blue-50 text-blue-700 font-medium"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            <div>{s.period_type}</div>
            <div className="text-xs text-gray-400">
              {format(new Date(s.period_start), "d MMM", { locale: ru })} —{" "}
              {format(new Date(s.period_end), "d MMM yyyy", { locale: ru })}
            </div>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="col-span-3">
        {selected ? (
          <>
            <FormatSwitcher current={digestFormat} onChange={setDigestFormat} />
            <div className="mt-4 prose prose-sm max-w-none whitespace-pre-wrap">
              {content}
            </div>
            {selected.post_count && (
              <p className="mt-4 text-xs text-gray-400">
                {selected.post_count} posts analyzed
              </p>
            )}
          </>
        ) : (
          <p className="text-gray-500">No digests yet. Run the pipeline first.</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create channel detail page**

Create `web/src/app/channels/[id]/page.tsx`:
```tsx
import { createServerClient } from "@/lib/supabase-server";
import { SummaryTimeline } from "@/components/summary-timeline";
import { Channel, ChannelSummary } from "@/lib/types";
import { notFound } from "next/navigation";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface Props {
  params: { id: string };
}

async function getChannel(id: string): Promise<Channel | null> {
  const supabase = createServerClient();
  const { data } = await supabase.from("channels").select("*").eq("id", id).single();
  return data;
}

async function getSummaries(channelId: string): Promise<ChannelSummary[]> {
  const supabase = createServerClient();
  const { data } = await supabase
    .from("channel_summaries")
    .select("*")
    .eq("channel_id", channelId)
    .eq("status", "done")
    .order("period_end", { ascending: false })
    .limit(50);
  return data || [];
}

export default async function ChannelPage({ params }: Props) {
  const channel = await getChannel(params.id);
  if (!channel) notFound();

  const summaries = await getSummaries(channel.id);

  return (
    <main className="max-w-5xl mx-auto p-6">
      <Link href="/" className="text-blue-600 text-sm hover:underline mb-4 block">
        &larr; Dashboard
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold">{channel.title}</h1>
        <p className="text-gray-500">@{channel.username} &middot; {channel.category}</p>
      </div>

      <SummaryTimeline summaries={summaries} />
    </main>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/app/channels/ web/src/components/summary-timeline.tsx
git commit -m "feat: add channel detail page with summary timeline"
```

---

### Task 13: Search Page

**Files:**
- Create: `web/src/app/search/page.tsx`
- Create: `web/src/app/api/search/route.ts`
- Create: `web/src/components/search-results.tsx`

- [ ] **Step 1: Create search API route**

Create `web/src/app/api/search/route.ts`:
```typescript
import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase-server";

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.get("q");
  const channelId = req.nextUrl.searchParams.get("channel");
  const from = req.nextUrl.searchParams.get("from");
  const to = req.nextUrl.searchParams.get("to");

  if (!query) {
    return NextResponse.json({ error: "Query required" }, { status: 400 });
  }

  const supabase = createServerClient();

  // Full-text search (vector search added later when embeddings are ready)
  let postsQuery = supabase
    .from("posts")
    .select("*, channels!inner(title, username, category)")
    .textSearch("text", query, { type: "websearch", config: "russian" })
    .order("date", { ascending: false })
    .limit(100);

  if (channelId) postsQuery = postsQuery.eq("channel_id", channelId);
  if (from) postsQuery = postsQuery.gte("date", from);
  if (to) postsQuery = postsQuery.lte("date", to);

  const { data: posts, error } = await postsQuery;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // Also search comments
  let commentsQuery = supabase
    .from("comments")
    .select("*, posts!inner(id, link, channel_id, channels!inner(title, username))")
    .textSearch("text", query, { type: "websearch", config: "russian" })
    .order("date", { ascending: false })
    .limit(50);

  const { data: comments } = await commentsQuery;

  return NextResponse.json({ posts: posts || [], comments: comments || [] });
}
```

- [ ] **Step 2: Create search results component**

Create `web/src/components/search-results.tsx`:
```tsx
"use client";

import { Post } from "@/lib/types";
import { format } from "date-fns";
import { ru } from "date-fns/locale";

interface Props {
  posts: (Post & { channels: { title: string; username: string } })[];
}

export function SearchResults({ posts }: Props) {
  if (posts.length === 0) {
    return <p className="text-gray-500 text-center py-8">Nothing found.</p>;
  }

  return (
    <div className="space-y-4">
      {posts.map((post) => (
        <div key={post.id} className="border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-blue-600">
              {post.channels.title}
            </span>
            <span className="text-xs text-gray-400">
              {format(new Date(post.date), "d MMM yyyy", { locale: ru })}
            </span>
            {post.views > 0 && (
              <span className="text-xs text-gray-400">{post.views} views</span>
            )}
          </div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap line-clamp-6">
            {post.text}
          </p>
          {post.link && (
            <a
              href={post.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-500 hover:underline mt-2 inline-block"
            >
              Open in Telegram
            </a>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create search page**

Create `web/src/app/search/page.tsx`:
```tsx
"use client";

import { useState } from "react";
import { SearchResults } from "@/components/search-results";
import Link from "next/link";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ posts: any[]; comments: any[] } | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setResults(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-blue-600 text-sm hover:underline mb-4 block">
        &larr; Dashboard
      </Link>

      <h1 className="text-2xl font-bold mb-6">Search</h1>

      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Как жизнь в Черногории..."
            className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "..." : "Search"}
          </button>
        </div>
      </form>

      {results && (
        <>
          <p className="text-sm text-gray-500 mb-4">
            Found {results.posts.length} posts, {results.comments.length} comments
          </p>
          <SearchResults posts={results.posts} />
        </>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add web/src/app/search/ web/src/app/api/search/ web/src/components/search-results.tsx
git commit -m "feat: add search page with full-text search"
```

---

### Task 14: Settings Page (Channel Management)

**Files:**
- Create: `web/src/app/settings/page.tsx`
- Create: `web/src/app/api/channels/route.ts`

- [ ] **Step 1: Create channels API route**

Create `web/src/app/api/channels/route.ts`:
```typescript
import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase-server";

export async function GET() {
  const supabase = createServerClient();
  const { data } = await supabase.from("channels").select("*").order("category").order("title");
  return NextResponse.json(data || []);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const supabase = createServerClient();

  const { data, error } = await supabase
    .from("channels")
    .upsert(
      {
        telegram_id: body.telegram_id,
        username: body.username,
        title: body.title,
        category: body.category || null,
        is_active: true,
      },
      { onConflict: "telegram_id" }
    )
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function PATCH(req: NextRequest) {
  const body = await req.json();
  const supabase = createServerClient();

  const { data, error } = await supabase
    .from("channels")
    .update({ is_active: body.is_active, category: body.category })
    .eq("id", body.id)
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
```

- [ ] **Step 2: Create settings page**

Create `web/src/app/settings/page.tsx`:
```tsx
"use client";

import { useEffect, useState } from "react";
import { Channel } from "@/lib/types";
import Link from "next/link";

export default function SettingsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [newChannel, setNewChannel] = useState({ telegram_id: "", username: "", title: "", category: "" });

  useEffect(() => {
    fetch("/api/channels").then((r) => r.json()).then(setChannels);
  }, []);

  async function addChannel(e: React.FormEvent) {
    e.preventDefault();
    const res = await fetch("/api/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...newChannel, telegram_id: parseInt(newChannel.telegram_id) }),
    });
    if (res.ok) {
      const ch = await res.json();
      setChannels((prev) => [...prev, ch]);
      setNewChannel({ telegram_id: "", username: "", title: "", category: "" });
    }
  }

  async function toggleChannel(ch: Channel) {
    const res = await fetch("/api/channels", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: ch.id, is_active: !ch.is_active }),
    });
    if (res.ok) {
      setChannels((prev) => prev.map((c) => (c.id === ch.id ? { ...c, is_active: !c.is_active } : c)));
    }
  }

  return (
    <main className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-blue-600 text-sm hover:underline mb-4 block">&larr; Dashboard</Link>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      {/* Add channel form */}
      <form onSubmit={addChannel} className="border rounded-lg p-4 mb-6 space-y-3">
        <h2 className="font-semibold">Add Channel</h2>
        <div className="grid grid-cols-2 gap-3">
          <input placeholder="Telegram ID" value={newChannel.telegram_id} onChange={(e) => setNewChannel((p) => ({ ...p, telegram_id: e.target.value }))} className="border rounded px-3 py-2 text-sm" required />
          <input placeholder="@username" value={newChannel.username} onChange={(e) => setNewChannel((p) => ({ ...p, username: e.target.value }))} className="border rounded px-3 py-2 text-sm" />
          <input placeholder="Title" value={newChannel.title} onChange={(e) => setNewChannel((p) => ({ ...p, title: e.target.value }))} className="border rounded px-3 py-2 text-sm" required />
          <input placeholder="Category (tech, offroad, news...)" value={newChannel.category} onChange={(e) => setNewChannel((p) => ({ ...p, category: e.target.value }))} className="border rounded px-3 py-2 text-sm" />
        </div>
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded text-sm">Add</button>
      </form>

      {/* Channel list */}
      <div className="space-y-2">
        {channels.map((ch) => (
          <div key={ch.id} className="flex items-center justify-between border rounded-lg px-4 py-3">
            <div>
              <span className="font-medium">{ch.title}</span>
              <span className="text-gray-500 text-sm ml-2">@{ch.username}</span>
              {ch.category && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full ml-2">{ch.category}</span>}
            </div>
            <button onClick={() => toggleChannel(ch)} className={`text-sm px-3 py-1 rounded ${ch.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
              {ch.is_active ? "Active" : "Disabled"}
            </button>
          </div>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Add navigation to layout**

Modify `web/src/app/layout.tsx` — add a simple nav bar with links to Dashboard, Search, Settings.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/settings/ web/src/app/api/channels/ web/src/app/layout.tsx
git commit -m "feat: add settings page with channel management"
```

---

## Chunk 5: Integration & Deploy

### Task 15: Vercel Deployment

- [ ] **Step 1: Push to GitHub**

```bash
git push origin master
```

- [ ] **Step 2: Connect Vercel**

Go to https://vercel.com/new, import `dementy-fut/tg-lens`, set root directory to `web/`.

- [ ] **Step 3: Set environment variables in Vercel**

```
NEXT_PUBLIC_SUPABASE_URL=<from Supabase dashboard>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from Supabase dashboard>
GITHUB_TOKEN=<personal access token with repo + actions scope>
GITHUB_REPO=dementy-fut/tg-lens
```

- [ ] **Step 4: Deploy and verify**

Vercel auto-deploys on push. Verify dashboard loads at the Vercel URL.

### Task 16: GitHub Secrets Setup

- [ ] **Step 1: Set GitHub secrets**

```bash
gh secret set TELEGRAM_API_ID --body "<your_id>"
gh secret set TELEGRAM_API_HASH --body "<your_hash>"
gh secret set TELEGRAM_PHONE --body "<your_phone>"
gh secret set SUPABASE_URL --body "<url>"
gh secret set SUPABASE_SERVICE_KEY --body "<service_key>"
gh secret set ANTHROPIC_API_KEY --body "<key>"
```

- [ ] **Step 2: Create Supabase storage bucket for sessions**

In Supabase dashboard → Storage → Create bucket "sessions" (private).

- [ ] **Step 3: Initial Telethon session**

Run locally once to create the session file (requires phone OTP):
```bash
cd pipeline
python -c "
from telethon import TelegramClient
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
client = TelegramClient('tg_session', int(os.getenv('TELEGRAM_API_ID')), os.getenv('TELEGRAM_API_HASH'))
async def main():
    await client.start(phone=os.getenv('TELEGRAM_PHONE'))
    print('Session created!')
    await client.disconnect()
asyncio.run(main())
"
```

Upload session to Supabase Storage:
```bash
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
with open('tg_session.session', 'rb') as f:
    client.storage.from_('sessions').upload('tg_session.session', f)
print('Session uploaded!')
"
```

- [ ] **Step 4: Test full pipeline**

```bash
# Add a test channel via Settings UI or directly:
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
client.table('channels').insert({
    'telegram_id': 0,
    'username': 'durov',
    'title': 'Durov Channel',
    'category': 'tech'
}).execute()
print('Test channel added')
"
```

Then trigger scrape from GitHub Actions UI or from the web dashboard.

- [ ] **Step 5: Verify end-to-end**

1. Check Supabase → posts table has data
2. Run digest: `python run_digest.py --type custom --channel durov --start 2026-03-01 --end 2026-03-13`
3. Check Supabase → channel_summaries has digest
4. Open web UI → channel page shows digest with 5 formats
5. Try search

- [ ] **Step 6: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration adjustments after e2e testing"
git push origin master
```
