import logging
from datetime import datetime, timezone
from telethon import TelegramClient

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
            "reply_to_comment_id": None,
        }

    async def scrape_channel(self, channel_id_or_username, db_channel_id: str,
                              channel_username: str, since: datetime = None) -> tuple[list, list]:
        """Scrape posts and comments from a channel since a given datetime."""
        posts = []
        comments = []

        async for msg in self.client.iter_messages(channel_id_or_username):
            if since and msg.date < since:
                break

            post_dict = self.parse_message(msg, channel_id=db_channel_id, channel_username=channel_username)
            posts.append(post_dict)

            try:
                async for reply in self.client.iter_messages(channel_id_or_username, reply_to=msg.id):
                    comment_dict = self.parse_comment(reply, post_id=None)
                    comment_dict["_parent_telegram_msg_id"] = msg.id
                    comments.append(comment_dict)
            except Exception as e:
                logger.debug(f"No comments for msg {msg.id}: {e}")

        posts.reverse()
        comments.reverse()
        logger.info(f"Scraped {len(posts)} posts and {len(comments)} comments from {channel_username}")
        return posts, comments
