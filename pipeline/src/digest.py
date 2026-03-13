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
        results = []
        for fmt in self.FORMATS:
            result = await self.generate(fmt, posts, period)
            results.append(result)
            logger.info(f"Generated {fmt} digest: {result['tokens_used']} tokens")
        return results
