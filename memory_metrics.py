"""Lightweight request and process memory metrics; no admission controls."""
import logging
import os
import time

logger = logging.getLogger("uvicorn.error")
DATA_PATHS = {"/specificity", "/psi_block", "/gene_expression", "/marker",
              "/highly_specific", "/non_specific"}


def rss_mb():
    try:
        with open('/proc/self/statm') as handle:
            return int(handle.read().split()[1]) * os.sysconf('SC_PAGE_SIZE') / 1048576
    except (OSError, ValueError, IndexError):
        return 0.0


class RequestMetrics:
    def __init__(self, app):
        self.app = app
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] not in DATA_PATHS:
            return await self.app(scope, receive, send)
        self.active += 1
        started = time.monotonic()
        before = rss_mb()
        try:
            await self.app(scope, receive, send)
        finally:
            self.active -= 1
            logger.info('request path=%s duration_s=%.3f rss_mb=%.1f rss_before_mb=%.1f active=%d',
                        scope['path'], time.monotonic()-started, rss_mb(), before, self.active)
