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
        important = []
        for i in range(0, len(posts), BATCH_SIZE):
            batch = posts[i : i + BATCH_SIZE]
            classifications = await self.classify_batch(batch)

            for post in batch:
                category = classifications.get(post["id"], "SKIP")
                if category in KEEP_CATEGORIES:
                    post["_category"] = category
                    important.append(post)

            logger.info(f"Classified batch {i // BATCH_SIZE + 1}: {len(batch)} posts")

        return important
