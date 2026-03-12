# TG Lens — Design Specification

**Date:** 2026-03-12
**Status:** Draft
**Author:** dementy-fut + Claude

---

## 1. Overview

TG Lens — веб-приложение для обработки 50+ Telegram-каналов через AI. Решает проблему: "у меня 20000 непрочитанных сообщений в разных каналах, хочу быть в курсе не читая всё".

### Что делает
- Скрапит посты и комментарии из Telegram-каналов
- AI отделяет важные факты от пустого трёпа
- Автоматически генерирует дайджесты по расписанию (неделя/месяц/полгода)
- Даёт семантический поиск по всей истории ("как жизнь в Черногории")
- 5 форматов дайджестов на выбор
- Чат с AI для уточняющих вопросов

### Целевой пользователь
Один пользователь (автор). Подписан на 50+ разнотематических каналов: технологии, офроуд, сообщества, информационные.

---

## 2. Architecture

### Стек
- **Frontend**: Next.js на Vercel
- **БД**: Supabase (Postgres + pgvector + FTS + Storage)
- **Backend/Pipeline**: Python в GitHub Actions
- **AI**: Claude API (анализ + синтез) + Voyage/Claude embeddings (vector search)
- **Telegram**: Telethon (user API)

### Схема

```
┌─────────────────┐   workflow_dispatch    ┌──────────────────────┐
│  Vercel          │ ────────────────────► │  GitHub Actions       │
│  (Next.js)       │                       │  (Python)             │
│                  │                       │                       │
│  - Dashboard     │                       │  - Scraper (Telethon) │
│  - Channel pages │                       │  - Analyzer (Claude)  │
│  - Search        │                       │  - Embeddings         │
│  - AI Chat       │                       │  - Digest generator   │
│  - Settings      │                       │                       │
└────────┬─────────┘                       └───────────┬───────────┘
         │                                             │
         │              ┌──────────────┐               │
         └─────────────►│  Supabase    │◄──────────────┘
                        │              │
                        │  - Postgres  │
                        │  - pgvector  │
                        │  - FTS index │
                        │  - Storage   │
                        │   (session)  │
                        └──────────────┘
```

### Потоки данных

**Скрапинг (по кнопке или cron):**
1. Vercel UI → GitHub Actions API (`workflow_dispatch`)
2. Actions: Python скрипт загружает Telethon session из Supabase Storage
3. Для каждого активного канала: `last_scraped_at` → тянет новые посты + комментарии
4. Сохраняет в Supabase Postgres
5. Генерирует embeddings для каждого поста/комментария → сохраняет в pgvector

**Автодайджесты (cron):**
1. Каждый понедельник → недельный дайджест по каждому каналу
2. 1-го числа месяца → месячный дайджест (синтез из 4 недельных)
3. 1 января / 1 июля → полугодовой (синтез из 6 месячных)
4. Результаты кэшируются в `channel_summaries`

**Поиск:**
1. Пользователь вводит запрос ("как жизнь в Черногории")
2. Запрос → embedding → vector search по всем постам и комментариям
3. Топ-N результатов → Claude для синтеза ответа
4. Результат с группировкой по подтемам + ссылки на оригиналы

**AI Chat:**
1. Пользователь задаёт вопрос по конкретному посту/теме/каналу
2. Система подтягивает контекст из БД (vector search + прямые связи)
3. Claude отвечает с цитатами и ссылками

---

## 3. Data Model

### channels
```sql
channels
├── id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
├── telegram_id     bigint UNIQUE NOT NULL
├── username        text                    -- @channel_name
├── title           text NOT NULL
├── category        text                    -- 'offroad', 'tech', 'news', 'life', etc.
├── is_active       boolean DEFAULT true
├── last_scraped_at timestamptz
└── created_at      timestamptz DEFAULT now()
```

### posts
```sql
posts
├── id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
├── channel_id      uuid REFERENCES channels(id)
├── telegram_msg_id integer NOT NULL
├── text            text
├── date            timestamptz NOT NULL
├── views           integer
├── forwards        integer
├── reactions_json  jsonb                   -- {👍: 12, 🔥: 5, ...}
├── has_media       boolean DEFAULT false
├── media_type      text                    -- 'photo', 'video', 'document', null
├── link            text                    -- https://t.me/channel/123
├── embedding       vector(1024)
├── created_at      timestamptz DEFAULT now()
├── UNIQUE(channel_id, telegram_msg_id)
```

### comments
```sql
comments
├── id                  uuid PRIMARY KEY DEFAULT gen_random_uuid()
├── post_id             uuid REFERENCES posts(id)
├── telegram_msg_id     integer NOT NULL
├── sender_name         text
├── sender_id           bigint
├── text                text
├── date                timestamptz NOT NULL
├── is_reply            boolean DEFAULT false
├── reply_to_comment_id uuid REFERENCES comments(id)
├── embedding           vector(1024)
└── created_at          timestamptz DEFAULT now()
```

### channel_summaries
```sql
channel_summaries
├── id                  uuid PRIMARY KEY DEFAULT gen_random_uuid()
├── channel_id          uuid REFERENCES channels(id)
├── period_type         text NOT NULL          -- 'week', 'month', 'quarter', 'half_year', 'year', 'custom'
├── period_start        timestamptz NOT NULL
├── period_end          timestamptz NOT NULL
├── summary             text                   -- AI-сгенерированный текст
├── facts_json          jsonb                  -- структурированные факты
├── post_count          integer
├── status              text DEFAULT 'pending' -- 'pending', 'processing', 'done', 'error'
├── parent_summary_id   uuid REFERENCES channel_summaries(id)
├── model_used          text
├── tokens_used         integer
└── created_at          timestamptz DEFAULT now()
```

### digests (кросс-канальные)
```sql
digests
├── id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
├── period_start    timestamptz NOT NULL
├── period_end      timestamptz NOT NULL
├── digest_type     text NOT NULL           -- 'headlines', 'brief', 'deep', 'qa', 'actions'
├── summary         text
├── facts_json      jsonb
├── model_used      text
├── tokens_used     integer
└── created_at      timestamptz DEFAULT now()
```

### digest_posts
```sql
digest_posts
├── digest_id       uuid REFERENCES digests(id)
├── post_id         uuid REFERENCES posts(id)
├── PRIMARY KEY(digest_id, post_id)
```

### search_history
```sql
search_history
├── id              uuid PRIMARY KEY DEFAULT gen_random_uuid()
├── query           text NOT NULL
├── results_json    jsonb                   -- кэш результатов
├── ai_synthesis    text                    -- AI-ответ
└── created_at      timestamptz DEFAULT now()
```

### Indexes
```sql
-- FTS
CREATE INDEX idx_posts_fts ON posts USING GIN(to_tsvector('russian', text));
CREATE INDEX idx_comments_fts ON comments USING GIN(to_tsvector('russian', text));

-- Vector search (pgvector)
CREATE INDEX idx_posts_embedding ON posts USING hnsw(embedding vector_cosine_ops);
CREATE INDEX idx_comments_embedding ON comments USING hnsw(embedding vector_cosine_ops);

-- Query performance
CREATE INDEX idx_posts_channel_date ON posts(channel_id, date DESC);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_summaries_channel_period ON channel_summaries(channel_id, period_type, period_start);
```

---

## 4. AI Pipeline

### 4.1 Scraping

Telethon (user API) для каждого активного канала:
- Посты: `client.iter_messages(channel)` с фильтром по `last_scraped_at`
- Комментарии: `client.iter_messages(channel, reply_to=msg_id)` для каждого поста
- Метаданные: views, forwards, reactions
- Ограничение: Telegram rate limits (~30 запросов/сек)

### 4.2 Embedding Generation

При сохранении каждого поста/комментария:
- Текст → Voyage AI (или Claude embeddings) → vector(1024)
- Batch processing для эффективности
- Хранение в pgvector колонке

### 4.3 Digest Generation — 3 этапа

**Этап 1: Грубая фильтрация (код, без AI)**
- Отсечение: < 20 символов, стикеры, "ок/спасибо/+", спам-шаблоны, дубли пересылок
- Сортировка по engagement (reactions + comments + views)
- ~20K → ~3-5K сообщений

**Этап 2: AI-классификация (Claude, батчами по 50-100)**
Промпт:
```
Для каждого сообщения определи категорию:
- FACT — конкретный факт, событие, новость
- EXPERIENCE — личный опыт, решение проблемы, полезный совет
- DISCUSSION — ключевой аргумент в важной дискуссии
- SKIP — болтовня, приветствия, мемы, оффтоп

Верни JSON: [{"id": "...", "category": "FACT|EXPERIENCE|DISCUSSION|SKIP"}]
```
- ~3-5K → ~200-500 важных сообщений

**Этап 3: AI-синтез (Claude, основные токены)**
Важные сообщения → Claude генерирует дайджест во всех 5 форматах:

### 4.4 Форматы дайджестов

**1. Headlines** — одна строка на событие, для скана за 30 сек
**2. Brief** — 2-3 предложения на тему, понятно без оригинала
**3. Deep dive** — полный контекст: кто, что, аргументы, цитаты, чем кончилось
**4. Q&A** — вопросы людей + лучшие ответы из обсуждений
**5. Action items** — только то, что требует реагирования: дедлайны, предупреждения, советы

### 4.5 Иерархическая суммаризация (длительные периоды)

```
Посты за 2 года
    ↓ разбивка по неделям
Недельные дайджесты (автоматически по cron)
    ↓ синтез по месяцам
Месячные дайджесты (автоматически 1-го числа)
    ↓ синтез по полугодиям
Полугодовые дайджесты (автоматически)
    ↓ синтез на лету
Произвольный период — склеивается из готовых чанков
```

Все промежуточные результаты кэшируются в `channel_summaries`. Повторный запрос за тот же период — мгновенный.

### 4.6 Semantic Search

1. Запрос пользователя → embedding
2. `pgvector` cosine similarity search по всем постам + комментариям
3. Фильтры: период, каналы, категории
4. Топ-100 результатов → Claude для группировки и синтеза
5. Ответ с подтемами, цитатами, ссылками на оригиналы

### 4.7 AI Chat

- Контекст: релевантные посты/комментарии из vector search + прямые связи (пост ↔ комментарии)
- Claude с conversation memory (в рамках сессии)
- Ответы со ссылками на оригинальные сообщения в Telegram

---

## 5. Web UI (Next.js / Vercel)

### Страницы

```
/                       — Dashboard
/channels               — Список каналов с категориями
/channels/:id           — Страница канала: дайджесты + сводка за период
/channels/:id/summary   — Генерация сводки за произвольный период
/topics                 — Кросс-канальные темы
/search                 — Семантический + текстовый поиск
/chat                   — AI чат: вопросы по контенту
/settings               — Управление каналами, API ключи, категории
```

### Dashboard (/)
- Общий дайджест "Главное за период" через все каналы
- Переключатель формата: Headlines | Brief | Deep | Q&A | Actions
- Карточки каналов по категориям с мини-саммари
- Каждый пункт: ссылка на оригинал + кнопка "спросить AI"
- Кнопка "Обработать новые" → триггерит скрапинг

### Channel Page (/channels/:id)
- Последний дайджест
- Таймлайн дайджестов (недельные/месячные)
- Генерация сводки за произвольный период с прогресс-баром
- Статистика: постов, комментариев, тем

### Search (/search)
- Строка ввода для семантического запроса
- Фильтры: период, каналы, категории
- AI-синтез результатов сверху (с подтемами)
- Переключатель формата
- Список оригинальных постов снизу (со score)
- Кнопка "уточнить" → переход в AI chat

### AI Chat (/chat)
- Чат-интерфейс
- Контекст подтягивается автоматически через vector search
- Ответы с цитатами и ссылками

---

## 6. GitHub Actions Workflows

### scrape.yml
- **Trigger**: `workflow_dispatch` (из UI) + `schedule` (ежедневно)
- **Job**: Python → Telethon скрапинг → Supabase insert → embeddings
- **Secrets**: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`, `SUPABASE_URL`, `SUPABASE_KEY`, `CLAUDE_API_KEY`, `VOYAGE_API_KEY`
- **Artifacts**: Telethon session file (или Supabase Storage)

### digest-weekly.yml
- **Trigger**: `schedule` (каждый понедельник 06:00 UTC)
- **Job**: для каждого канала — генерация недельного дайджеста из сырых постов

### digest-monthly.yml
- **Trigger**: `schedule` (1-е число месяца 07:00 UTC)
- **Job**: для каждого канала — синтез месячного дайджеста из 4 недельных

### digest-half-year.yml
- **Trigger**: `schedule` (1 января, 1 июля)
- **Job**: синтез полугодовых дайджестов из месячных

---

## 7. Security & Secrets

- **Telethon session**: шифруется, хранится в Supabase Storage или GitHub Secrets
- **API ключи**: GitHub Secrets → env vars в Actions
- **Supabase RLS**: включены, но один пользователь → упрощённые policies
- **Vercel env vars**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GITHUB_TOKEN` (для trigger)

---

## 8. Cost Estimation (Free Tier)

| Сервис | Free Tier | Наш расход |
|--------|-----------|------------|
| Supabase | 500MB DB, 1GB Storage | ~200-400MB при 600K записей/год |
| Vercel | 100GB bandwidth | Один пользователь — минимум |
| GitHub Actions | 2000 мин/мес | ~200-300 мин/мес |
| Claude API | Pay-per-use | ~$10-30/мес при 50 каналов |
| Voyage Embeddings | Pay-per-use | ~$5-10/мес |

---

## 9. Future (v2)

- Автоответы в каналах от имени пользователя (через Telethon)
- Периодические DM нужным людям ("как дела" по расписанию)
- Мобильный UI / PWA
- Экспорт дайджестов в Telegram (self-send)
- Мультиязычность дайджестов
