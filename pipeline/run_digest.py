"""
Entry point for digest generation.
Usage:
  python run_digest.py --type weekly
  python run_digest.py --type monthly
  python run_digest.py --type custom --start 2026-01-01 --end 2026-03-01 [--channel mychan]
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
    today = datetime.now(timezone.utc)
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return last_monday.isoformat(), last_sunday.isoformat()


def get_month_range() -> tuple[str, str]:
    today = datetime.now(timezone.utc)
    first_of_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_of_prev_month = first_of_this_month - timedelta(seconds=1)
    first_of_prev_month = last_of_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_of_prev_month.isoformat(), last_of_prev_month.isoformat()


async def generate_channel_digest(db: SupabaseDB, classifier: AIClassifier,
                                    generator: DigestGenerator, channel: dict,
                                    start: str, end: str, period_type: str):
    existing = db.get_summary(channel["id"], period_type, start)
    if existing and existing["status"] == "done":
        logger.info(f"Summary already exists for {channel['username']} ({period_type} {start})")
        return existing

    summary_record = db.upsert_summary({
        "channel_id": channel["id"],
        "period_type": period_type,
        "period_start": start,
        "period_end": end,
        "status": "processing",
    })

    try:
        posts = db.get_posts_for_period(channel["id"], start, end)
        logger.info(f"{channel['username']}: {len(posts)} raw posts")

        if not posts:
            db.upsert_summary({**summary_record, "status": "done", "summary": "No posts in period.", "post_count": 0})
            return

        filtered = NoiseFilter.filter_posts(posts)
        logger.info(f"{channel['username']}: {len(filtered)} after noise filter")

        classified = await classifier.classify_all(filtered)
        logger.info(f"{channel['username']}: {len(classified)} important posts")

        if not classified:
            db.upsert_summary({**summary_record, "status": "done", "summary": "No important posts found.", "post_count": 0})
            return

        period_label = f"{start[:10]} — {end[:10]}"
        digests = await generator.generate_all_formats(classified, period_label)

        brief = next(d for d in digests if d["digest_type"] == "brief")
        total_tokens = sum(d["tokens_used"] for d in digests)

        db.upsert_summary({
            **summary_record,
            "status": "done",
            "summary": brief["summary"],
            "facts_json": {d["digest_type"]: d["summary"] for d in digests},
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
    parser.add_argument("--channel", type=str, help="Specific channel username")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD for custom")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD for custom")
    args = parser.parse_args()

    settings = Settings()
    supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)
    db = SupabaseDB(client=supabase_client)
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    classifier = AIClassifier(client=anthropic_client)
    generator = DigestGenerator(client=anthropic_client)

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

    channels = db.get_active_channels()
    if args.channel:
        channels = [c for c in channels if c["username"] == args.channel]

    logger.info(f"Generating {period_type} digests for {len(channels)} channels")

    for channel in channels:
        try:
            await generate_channel_digest(db, classifier, generator, channel, start, end, period_type)
        except Exception as e:
            logger.error(f"Failed for {channel.get('username')}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
