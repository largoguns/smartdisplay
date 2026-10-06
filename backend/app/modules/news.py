"""Agregador de feeds RSS/Atom."""

from __future__ import annotations

import asyncio
import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from ..config import NewsConfig, NewsFeed
from ..schemas.models import NewsData, NewsItem
from .base import PollingModule, utcnow

_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACES.sub(" ", html.unescape(_TAGS.sub("", text))).strip()


def _published(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def parse_feed(raw: bytes, feed: NewsFeed) -> list[NewsItem]:
    parsed = feedparser.parse(raw)
    items: list[NewsItem] = []
    for entry in parsed.entries:
        title = _clean(entry.get("title", ""))
        if not title:
            continue
        link = entry.get("link") or None
        key = entry.get("id") or link or title
        items.append(
            NewsItem(
                id=hashlib.sha1(f"{feed.name}|{key}".encode()).hexdigest()[:16],
                title=title,
                source=feed.name,
                link=link,
                published_at=_published(entry),
            )
        )
    return items


class NewsModule(PollingModule[NewsData]):
    name = "news"

    def __init__(self, cfg: NewsConfig, client: httpx.AsyncClient) -> None:
        super().__init__(cfg.update_interval_minutes * 60, retry_seconds=120)
        self._cfg = cfg
        self._client = client
        self._per_feed: dict[str, list[NewsItem]] = {}

    async def _fetch_feed(self, feed: NewsFeed) -> list[NewsItem]:
        response = await self._client.get(feed.url, follow_redirects=True)
        response.raise_for_status()
        return await asyncio.to_thread(parse_feed, response.content, feed)

    async def fetch(self) -> NewsData:
        results = await asyncio.gather(*(self._fetch_feed(f) for f in self._cfg.feeds), return_exceptions=True)
        failures = 0
        for feed, result in zip(self._cfg.feeds, results):
            if isinstance(result, BaseException):
                failures += 1
                self.report_source(feed.name, result)
            else:
                self.report_source(feed.name, None)
                self._per_feed[feed.name] = result

        if self._cfg.feeds and failures == len(self._cfg.feeds):
            raise RuntimeError("Ningún feed disponible")

        oldest = datetime.min.replace(tzinfo=timezone.utc)
        merged = sorted(
            (item for items in self._per_feed.values() for item in items),
            key=lambda item: item.published_at or oldest,
            reverse=True,
        )
        seen: set[str] = set()
        unique: list[NewsItem] = []
        for item in merged:
            key = item.title.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) == self._cfg.max_items:
                break

        return NewsData(
            status="stale" if failures else "ok",
            fetched_at=utcnow(),
            ticker_speed_seconds=self._cfg.ticker_speed_seconds,
            items=unique,
        )
