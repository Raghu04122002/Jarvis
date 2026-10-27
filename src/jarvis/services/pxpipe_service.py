"""pxpipe proxy subprocess manager."""

import asyncio
import logging
import shutil
import signal
import subprocess

import httpx

logger = logging.getLogger(__name__)

PXPIPE_URL = "http://127.0.0.1:47821"
PXPIPE_HEALTH_TIMEOUT = 10  # seconds to wait for proxy to become ready


class PxpipeService:
    """Manages the pxpipe-proxy subprocess lifecycle."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._healthy = False

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def base_url(self) -> str:
        return PXPIPE_URL

    async def start(self) -> bool:
        """Start the pxpipe-proxy subprocess and wait until healthy.

        Returns True if proxy is running and healthy, False otherwise.
        """
        # Check if already running externally
        if await self._health_check():
            logger.info("pxpipe proxy already running at %s", PXPIPE_URL)
            self._healthy = True
            return True

        npx = shutil.which("npx")
        if npx is None:
            logger.warning("npx not found — pxpipe proxy will not start")
            return False

        try:
            self._process = subprocess.Popen(
                [npx, "pxpipe-proxy"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Started pxpipe-proxy (pid=%d)", self._process.pid)
        except OSError as e:
            logger.warning("Failed to start pxpipe-proxy: %s", e)
            return False

        # Poll for readiness
        for _ in range(PXPIPE_HEALTH_TIMEOUT * 4):
            if await self._health_check():
                self._healthy = True
                logger.info("pxpipe proxy is healthy at %s", PXPIPE_URL)
                return True
            await asyncio.sleep(0.25)

        logger.warning("pxpipe proxy did not become healthy in time")
        await self.stop()
        return False

    async def stop(self) -> None:
        """Stop the pxpipe-proxy subprocess."""
        if self._process is None:
            return
        try:
            self._process.send_signal(signal.SIGTERM)
            self._process.wait(timeout=5)
            logger.info("pxpipe-proxy stopped")
        except (OSError, subprocess.TimeoutExpired):
            self._process.kill()
            logger.info("pxpipe-proxy killed")
        finally:
            self._process = None
            self._healthy = False

    async def _health_check(self) -> bool:
        """Check if pxpipe proxy is responding."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(PXPIPE_URL, timeout=2.0)
                return resp.status_code < 500
        except (httpx.HTTPError, OSError):
            return False
