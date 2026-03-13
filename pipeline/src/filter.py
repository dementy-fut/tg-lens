import re

SKIP_PATTERNS = [
    r"^[\+\-\!\.]+$",
    r"^(ok|ок|да|нет|ага|угу|лол|кек)$",
    r"^спасибо[!\.]*$",
    r"^привет[!\.]*( всем[!\.]*)?$",
    r"^здравствуйте[!\.]*$",
    r"^добрый (день|вечер|утро)[!\.]*$",
    r"^(👍|👎|😂|🤣|❤️|🔥|👏|😭|🎉)+$",
]

SKIP_COMPILED = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]

MIN_TEXT_LENGTH = 20
MIN_ENGAGEMENT_TO_KEEP_SHORT = 50


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
        result = []
        for post in posts:
            text = post.get("text")
            if not text:
                continue
            text_stripped = text.strip()
            if any(p.match(text_stripped) for p in SKIP_COMPILED):
                engagement = NoiseFilter._engagement_score(post)
                if engagement < MIN_ENGAGEMENT_TO_KEEP_SHORT:
                    continue
            if len(text_stripped) < MIN_TEXT_LENGTH:
                engagement = NoiseFilter._engagement_score(post)
                if engagement < MIN_ENGAGEMENT_TO_KEEP_SHORT:
                    continue
            result.append(post)
        return result
