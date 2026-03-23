import logging
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


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
                            "content": content[:12000],
                            "image_urls": image_urls,
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
                    "image_urls": [],
                }
            ]
        return [
            {
                "label": "Crawler error",
                "url": "local://crawl4ai/error",
                "content": f"Crawl4AI could not start. Underlying error: {message}",
                "image_urls": [],
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
        "Keep the answer practical, concise, and high-signal. Avoid filler.\n"
        "Use markdown.\n"
        "Structure the response with these sections when relevant:\n"
        "1. Key updates\n"
        "2. Why this matters to you\n"
        "3. Suggested next steps\n"
        "4. Sources\n"
        "Do not include an Images section in the prose. Images will be appended separately if available.\n\n"
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