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
        result = self.client.table("comments").upsert(comments).execute()
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
