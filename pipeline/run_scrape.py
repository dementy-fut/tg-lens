"""
Entry point for scraping pipeline.
Usage: python run_scrape.py [--channel USERNAME] [--max-posts N] [--skip-comments]
"""
import asyncio
import argparse
import logging
from datetime import datetime, timezone
from supabase import create_client
from src.config import Settings
from src.db import SupabaseDB
from src.scraper import TelegramScraper, DEFAULT_MAX_POSTS, DEFAULT_MAX_COMMENTS_PER_POST

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def scrape_channel(scraper: TelegramScraper, db: SupabaseDB, channel: dict,
                          max_posts: int, max_comments_per_post: int, skip_comments: bool):
    since = None
    if channel.get("last_scraped_at"):
        since = datetime.fromisoformat(channel["last_scraped_at"])

    label = channel['username'] or channel['telegram_id']
    logger.info(f"Scraping {label} since={since} max_posts={max_posts} skip_comments={skip_comments}")

    posts, comments = await scraper.scrape_channel(
        channel_id_or_username=channel.get("username") or channel["telegram_id"],
        db_channel_id=channel["id"],
        channel_username=channel.get("username", ""),
        since=since,
        max_posts=max_posts,
        max_comments_per_post=max_comments_per_post,
        skip_comments=skip_comments,
    )

    if posts:
        saved_posts = db.insert_posts(posts)
        logger.info(f"Saved {len(saved_posts)} posts for {label}")

        post_id_map = {p["telegram_msg_id"]: p["id"] for p in saved_posts}

        for comment in comments:
            parent_msg_id = comment.pop("_parent_telegram_msg_id", None)
            if parent_msg_id and parent_msg_id in post_id_map:
                comment["post_id"] = post_id_map[parent_msg_id]

        comments_with_post = [c for c in comments if c.get("post_id")]
        if comments_with_post:
            saved_comments = db.insert_comments(comments_with_post)
            logger.info(f"Saved {len(saved_comments)} comments for {label}")
    else:
        logger.info(f"No new posts for {label}")

    db.update_last_scraped(channel["id"], datetime.now(timezone.utc).isoformat())


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", type=str, help="Scrape specific channel username")
    parser.add_argument("--max-posts", type=int, default=DEFAULT_MAX_POSTS,
                        help=f"Max posts per channel (default {DEFAULT_MAX_POSTS})")
    parser.add_argument("--max-comments", type=int, default=DEFAULT_MAX_COMMENTS_PER_POST,
                        help=f"Max comments per post (default {DEFAULT_MAX_COMMENTS_PER_POST})")
    parser.add_argument("--skip-comments", action="store_true",
                        help="Skip fetching comments entirely")
    args = parser.parse_args()

    settings = Settings()
    supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)
    db = SupabaseDB(client=supabase_client)
    scraper = TelegramScraper(settings.telegram_api_id, settings.telegram_api_hash)

    await scraper.connect(settings.telegram_phone)

    try:
        if args.channel:
            channels = db.get_active_channels()
            channel = next((c for c in channels if c["username"] == args.channel), None)
            if not channel:
                logger.error(f"Channel {args.channel} not found in DB")
                return
            await scrape_channel(scraper, db, channel,
                                 args.max_posts, args.max_comments, args.skip_comments)
        else:
            channels = db.get_active_channels()
            logger.info(f"Scraping {len(channels)} active channels")
            for i, channel in enumerate(channels, 1):
                logger.info(f"--- Channel {i}/{len(channels)} ---")
                try:
                    await scrape_channel(scraper, db, channel,
                                         args.max_posts, args.max_comments, args.skip_comments)
                except Exception as e:
                    logger.error(f"Error scraping {channel.get('username')}: {e}")
    finally:
        await scraper.disconnect()

    logger.info("Scraping complete")


if __name__ == "__main__":
    asyncio.run(main())
