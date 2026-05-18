"""Progress tracker for Slack message updates during long agent runs."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from slack_bolt.async_app import AsyncApp

log = logging.getLogger(__name__)


class ProgressTracker:
    """Edits a single Slack message in-place as agent milestones arrive.

    All updates are async — store `tracker.add` in ADK session state as
    `_on_progress` and await it from the CA client during streaming.

    A background ticker appends elapsed time every `tick_interval` seconds
    so users know the bot is still working.
    """

    def __init__(
        self,
        app: "AsyncApp",
        channel: str,
        ts: str,
        tick_interval: int = 60,
    ) -> None:
        self._app = app
        self._channel = channel
        self._ts = ts
        self._tick_interval = tick_interval
        self._pinned: list[str] = [":hourglass_flowing_sand: Thinking..."]
        self._working: str = ""   # single line that replaces in place
        self._working_base: str = ""  # label without elapsed suffix
        self._start = time.monotonic()
        self._ticker_task: asyncio.Task[None] | None = None
        self._query_ticker_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def add(self, step: str) -> None:
        """Append a permanent step (e.g. routing) and edit the Slack message."""
        self._pinned.append(step)
        log.info("Progress pinned: %s", step)
        await self._edit()

    async def set_working(self, step: str) -> None:
        """Replace the current working step (e.g. CA progress labels) in place.

        If a query ticker was running, clears both the pinned CA step and the
        BQ line before showing the new step.
        """
        if self._query_ticker_task:
            # Remove the pinned CA step that was frozen while BQ ran
            if self._pinned and self._pinned[-1] != ":hourglass_flowing_sand: Thinking...":
                last = self._pinned[-1]
                if last.startswith(":arrows_counterclockwise:"):
                    self._pinned.pop()
        self._cancel_query_ticker()
        self._working_base = step
        elapsed = int(time.monotonic() - self._start)
        self._working = "%s _(%ds)_" % (step, elapsed)
        log.info("Progress working: %s", self._working)
        await self._edit()

    async def start_query_ticker(self) -> None:
        """Add a BigQuery-running line below the last CA step, ticking every 3s.

        The last CA step is pinned; the BQ line ticks beneath it.
        Both are cleared when set_working() is called (results arrived).
        """
        self._cancel_query_ticker()
        # Pin the last CA step so it stays visible while BQ runs
        if self._working:
            self._pinned.append(self._working)
            self._working = ""
        self._working_base = ":mag: Fetching data"
        await self._edit_query_elapsed()
        self._query_ticker_task = asyncio.create_task(self._query_tick())

    def start_ticker(self) -> None:
        """Start the elapsed-time background ticker."""
        self._ticker_task = asyncio.create_task(self._tick())

    def stop_ticker(self) -> None:
        """Cancel both tickers (call when the response is ready)."""
        if self._ticker_task:
            self._ticker_task.cancel()
        self._cancel_query_ticker()

    def _cancel_query_ticker(self) -> None:
        if self._query_ticker_task:
            self._query_ticker_task.cancel()
            self._query_ticker_task = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _render(self, extra: str = "") -> str:
        lines = list(self._pinned)
        if self._working:
            lines.append(self._working)
        if extra:
            lines.append(extra)
        return "\n".join(lines)

    async def _edit(self, extra: str = "") -> None:
        text = self._render(extra)
        try:
            await self._app.client.chat_update(
                channel=self._channel,
                ts=self._ts,
                text=text,
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
            )
            log.info("Slack chat_update sent: %s", (self._working or self._pinned[-1]) if (self._working or self._pinned) else "")
        except Exception as exc:
            log.warning("Progress update failed: %s", exc)

    async def _edit_query_elapsed(self) -> None:
        elapsed = int(time.monotonic() - self._start)
        self._working = "%s _(%ds)_" % (self._working_base, elapsed)
        await self._edit()

    async def _query_tick(self) -> None:
        while True:
            await asyncio.sleep(10)
            await self._edit_query_elapsed()

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(self._tick_interval)
            elapsed = int(time.monotonic() - self._start)
            await self._edit(extra="_still working... (%ds)_" % elapsed)
