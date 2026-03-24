import logging
import re
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def _clean_text(value: object, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _extract_page_title(markdown: str, html: str, fallback: str) -> str:
    for line in markdown.splitlines():
        candidate = str(line).strip()
        if candidate.startswith("#"):
            candidate = candidate.lstrip("#").strip()
            if candidate:
                return _clean_text(candidate, limit=140)

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        return _clean_text(title_match.group(1), limit=140)

    og_title_match = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    if og_title_match:
        return _clean_text(og_title_match.group(1), limit=140)

    return _clean_text(fallback, limit=140) or "Source"


def _extract_page_summary(markdown: str, html: str) -> str:
    for line in markdown.splitlines():
        candidate = str(line).strip()
        if not candidate or candidate.startswith("#") or candidate.startswith("!"):
            continue
        if len(candidate) >= 40:
            return _clean_text(candidate, limit=280)

    og_desc_match = re.search(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    if og_desc_match:
        return _clean_text(og_desc_match.group(1), limit=280)

    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    if desc_match:
        return _clean_text(desc_match.group(1), limit=280)

    return ""


def _extract_video_urls(html: str, page_url: str) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r'<meta[^>]+property=["\']og:video(?::url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<iframe[^>]+src=["\']([^"\']+)["\']',
        r'<video[^>]+src=["\']([^"\']+)["\']',
        r'<source[^>]+src=["\']([^"\']+)["\']',
        r'https?://(?:www\.)?(?:youtube\.com/watch\?v=[^\s"\'<>]+|youtu\.be/[^\s"\'<>]+|player\.vimeo\.com/video/[^\s"\'<>]+)',
    ]

    for pattern in patterns:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            candidate = urljoin(page_url, str(match).strip())
            if not candidate:
                continue
            if candidate not in candidates:
                candidates.append(candidate)
            if len(candidates) >= 3:
                return candidates

    return candidates


async def fetch_profile_link_updates(
    links: list[dict[str, str]],
    request_id: str,
    max_links: int = 3,
) -> list[dict[str, object]]:
    usable_links = [
        {
            "label": str(link.get("label") or link.get("url") or "Source").strip(),
            "url": str(link.get("url") or "").strip(),
        }
        for link in links[:max_links]
        if str(link.get("url") or "").strip()
    ]
    if not usable_links:
        return []

    updates: list[dict[str, object]] = []
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            for link in usable_links:
                try:
                    result = await crawler.arun(url=link["url"])
                    markdown = str(getattr(result, "markdown", "") or "").strip()
                    html = str(getattr(result, "html", "") or "").strip()
                    media = getattr(result, "media", None) or {}
                    image_items = media.get("images", []) if isinstance(media, dict) else []
                    image_urls: list[str] = []
                    for image in image_items:
                        if not isinstance(image, dict):
                            continue
                        src = str(image.get("src") or image.get("url") or "").strip()
                        if not src:
                            continue
                        absolute_src = urljoin(link["url"], src)
                        if absolute_src not in image_urls:
                            image_urls.append(absolute_src)
                        if len(image_urls) >= 3:
                            break

                    content = markdown or html
                    if not content:
                        logger.info(
                            "[rid=%s] crawl4ai: no content extracted for url=%s",
                            request_id,
                            link["url"],
                        )
                        continue

                    updates.append(
                        {
                            "label": link["label"],
                            "url": link["url"],
                            "title": _extract_page_title(markdown, html, link["label"]),
                            "summary": _extract_page_summary(markdown, html),
                            "content": content[:12000],
                            "image_urls": image_urls,
                            "video_urls": _extract_video_urls(html, link["url"]),
                        }
                    )
                except Exception as exc:
                    logger.warning(
                        "[rid=%s] crawl4ai failed for url=%s error=%s",
                        request_id,
                        link["url"],
                        str(exc),
                    )
    except Exception as exc:
        message = str(exc)
        logger.exception("[rid=%s] crawl4ai startup failed", request_id)
        if "playwright install" in message.lower() or "executable doesn't exist" in message.lower():
            return [
                {
                    "label": "Crawler setup required",
                    "url": "local://crawl4ai/setup",
                    "content": (
                        "Crawl4AI could not start because Playwright browser binaries are not installed. "
                        "Run 'playwright install' in the backend environment before using profile-based web updates."
                    ),
                    "title": "Crawler setup required",
                    "summary": "Install Playwright browser binaries in the backend environment to enable profile-based news crawling.",
                    "image_urls": [],
                    "video_urls": [],
                }
            ]
        return [
            {
                "label": "Crawler error",
                "url": "local://crawl4ai/error",
                "content": f"Crawl4AI could not start. Underlying error: {message}",
                "title": "Crawler error",
                "summary": _clean_text(message, limit=180),
                "image_urls": [],
                "video_urls": [],
            }
        ]

    return updates


def build_profile_update_prompt(
    query: str,
    goals: list[str],
    interests: list[str],
    crawled_updates: list[dict[str, object]],
) -> str:
    goals_text = "\n".join(f"- {goal}" for goal in goals) if goals else "- None provided"
    interests_text = "\n".join(f"- {interest}" for interest in interests) if interests else "- None provided"
    updates_text = "\n\n".join(
        (
            f"Source label: {item['label']}\n"
            f"Source url: {item['url']}\n"
            f"Source title: {item.get('title') or item['label']}\n"
            f"Source summary: {item.get('summary') or 'N/A'}\n"
            f"Extracted content:\n{item['content']}"
        )
        for item in crawled_updates
    )

    return (
        "You are preparing a personalized update for the user based on their saved goals, interests, and selected web sources.\n"
        "Focus primarily on what is new, useful, and actionable in the crawled pages.\n"
        "Prioritize updates that best match the user's goals and interests instead of listing everything.\n"
        "Explain why the updates matter for the user's goals and interests in direct, specific language.\n"
        "If a tool, framework, library, product, or trend appears that aligns with the user's profile, call that out explicitly and explain the relevance.\n"
        "When possible, compare the importance of the updates and highlight the highest-value one first.\n"
        "Keep the answer practical, concise, high-signal, and visually scannable. Avoid filler.\n"
        "Use markdown.\n"
        "Start with a 2-3 bullet 'At a glance' section.\n"
        "Then structure the response with these sections when relevant:\n"
        "1. Key updates\n"
        "2. Why this matters to you\n"
        "3. Suggested next steps\n"
        "4. Sources\n"
        "For each key update, prefer this sub-structure when possible: short headline, one-sentence proof point, and one-sentence implication.\n"
        "Do not include an Images or Videos section in the prose. Rich media will be rendered separately in the UI.\n\n"
        f"User request:\n{query}\n\n"
        f"User goals:\n{goals_text}\n\n"
        f"User interests:\n{interests_text}\n\n"
        f"Crawled source updates:\n{updates_text if updates_text else 'No source content was available.'}\n\n"
        "Answer:\n"
    )


def build_profile_images_markdown(crawled_updates: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for item in crawled_updates:
        label = str(item.get("label") or "Source")
        image_urls = item.get("image_urls")
        if not isinstance(image_urls, list) or not image_urls:
            continue

        lines = [f"### Images from {label}"]
        for idx, image_url in enumerate(image_urls[:3], start=1):
            lines.append(f"![{label} image {idx}]({str(image_url)})")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)