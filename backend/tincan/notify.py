"""Parent notifications: ntfy topic POST, optional SMTP email. Failures are logged, never raised."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from tincan.config import Config
from tincan.schemas import Notifications

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: Config):
        self.config = config
        self.sent: list[dict[str, str]] = []  # inspected by tests

    async def send(
        self, targets: Notifications, title: str, message: str, url: str | None = None
    ) -> None:
        self.sent.append({"title": title, "message": message, "url": url or ""})
        tasks = []
        if targets.ntfy_topic:
            tasks.append(self._ntfy(targets.ntfy_topic, title, message, url))
        if targets.email and self.config.smtp_host:
            tasks.append(asyncio.to_thread(self._email, targets.email, title, message, url))
        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, Exception):
                log.warning("notification failed: %s", result)

    async def _ntfy(self, topic: str, title: str, message: str, url: str | None) -> None:
        endpoint = topic if topic.startswith("http") else f"https://ntfy.sh/{topic}"
        headers = {"Title": title}
        if url:
            headers["Click"] = url
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(endpoint, content=message.encode(), headers=headers)
            r.raise_for_status()

    def _email(self, to: str, title: str, message: str, url: str | None) -> None:
        cfg = self.config
        msg = EmailMessage()
        msg["Subject"] = f"[Tin Can] {title}"
        msg["From"] = cfg.smtp_from or cfg.smtp_user or "tincan@localhost"
        msg["To"] = to
        msg.set_content(message + (f"\n\n{url}" if url else ""))
        with smtplib.SMTP(cfg.smtp_host or "", cfg.smtp_port, timeout=15) as s:
            s.starttls()
            if cfg.smtp_user:
                s.login(cfg.smtp_user, cfg.smtp_password or "")
            s.send_message(msg)
