"""Preconnect speech providers before an outbound call is answered."""

import asyncio
import logging
from dataclasses import dataclass, field
from collections.abc import Awaitable
from typing import Any

from voice_agent.config import Settings
from voice_agent.contracts.packets import now_ms
from voice_agent.factory.provider_registry import ProviderRegistry
from voice_agent.factory.session_factory import SessionProviderBundle, create_session_provider_bundle

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PrewarmedProviderEntry:
    prewarm_id: str
    bundle: SessionProviderBundle
    created_ms: int
    aliases: set[str] = field(default_factory=set)


class ProviderWarmupPool:
    def __init__(self, settings: Settings, registry: ProviderRegistry) -> None:
        self.settings = settings
        self.registry = registry
        self._entries: dict[str, PrewarmedProviderEntry] = {}
        self._aliases: dict[str, str] = {}
        self._expiry_tasks: dict[str, asyncio.Task[None]] = {}
        self._health_tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def prewarm(
        self,
        prewarm_id: str,
        *,
        agent_id: str | None = None,
    ) -> PrewarmedProviderEntry:
        await self.expire_stale()
        started_ms = now_ms()
        logger.info("provider_prewarm_started prewarm_id=%s agent_id=%s", prewarm_id, agent_id)
        bundle = create_session_provider_bundle(
            self.settings,
            self.registry,
            agent_id=agent_id,
        )
        try:
            await asyncio.gather(
                bundle.stt.start(prewarm_id, language_hint=_stt_language_hint(bundle.settings)),
                bundle.tts.start(
                    prewarm_id,
                    voice=bundle.settings.agent_tts_voice,
                    language=bundle.settings.agent_tts_language
                    or bundle.settings.agent_default_language,
                ),
            )
        except Exception:
            await self._stop_bundle(bundle)
            raise

        entry = PrewarmedProviderEntry(
            prewarm_id=prewarm_id,
            bundle=bundle,
            created_ms=now_ms(),
        )
        async with self._lock:
            old_entry = self._entries.pop(prewarm_id, None)
            old_expiry_task = self._expiry_tasks.pop(prewarm_id, None)
            old_health_task = self._health_tasks.pop(prewarm_id, None)
            if old_entry is not None:
                self._remove_aliases(old_entry)
            self._entries[prewarm_id] = entry
            self._expiry_tasks[prewarm_id] = asyncio.create_task(self._expire_after(prewarm_id))
            self._health_tasks[prewarm_id] = asyncio.create_task(self._monitor_health(prewarm_id))
        self._cancel_expiry_task(old_expiry_task)
        self._cancel_health_task(old_health_task)
        if old_entry is not None:
            await self._stop_bundle(old_entry.bundle)
        logger.info(
            "provider_prewarm_ready prewarm_id=%s latency_ms=%s",
            prewarm_id,
            now_ms() - started_ms,
        )
        return entry

    async def add_alias(self, alias: str | None, prewarm_id: str | None) -> None:
        if not alias or not prewarm_id:
            return
        async with self._lock:
            entry = self._entries.get(prewarm_id)
            if entry is None:
                return
            entry.aliases.add(alias)
            self._aliases[alias] = prewarm_id

    async def claim(
        self,
        *,
        prewarm_id: str | None = None,
        call_id: str | None = None,
    ) -> SessionProviderBundle | None:
        await self.expire_stale()
        keys = tuple(key for key in (prewarm_id, call_id) if key)
        entry: PrewarmedProviderEntry | None = None
        async with self._lock:
            for key in keys:
                resolved_id = self._aliases.get(key, key)
                entry = self._entries.pop(resolved_id, None)
                if entry is None:
                    continue
                self._remove_aliases(entry)
                expiry_task = self._expiry_tasks.pop(entry.prewarm_id, None)
                health_task = self._health_tasks.pop(entry.prewarm_id, None)
                self._cancel_expiry_task(expiry_task)
                self._cancel_health_task(health_task)
                break
        if entry is None:
            return None
        if not await self._bundle_alive(entry.bundle):
            logger.warning(
                "provider_prewarm_dead_on_claim prewarm_id=%s call_id=%s",
                entry.prewarm_id,
                call_id,
            )
            await self._stop_bundle(entry.bundle)
            return None
        logger.info(
            "provider_prewarm_claimed prewarm_id=%s call_id=%s",
            entry.prewarm_id,
            call_id,
        )
        return entry.bundle

    async def discard(self, prewarm_id: str, *, reason: str = "discarded") -> None:
        async with self._lock:
            entry = self._entries.pop(prewarm_id, None)
            if entry is not None:
                self._remove_aliases(entry)
            expiry_task = self._expiry_tasks.pop(prewarm_id, None)
            health_task = self._health_tasks.pop(prewarm_id, None)
            self._cancel_expiry_task(expiry_task)
            self._cancel_health_task(health_task)
        if entry is not None:
            logger.info("provider_prewarm_discarded prewarm_id=%s reason=%s", prewarm_id, reason)
            await self._stop_bundle(entry.bundle)

    async def expire_stale(self) -> None:
        ttl_ms = max(1, int(self.settings.outbound_provider_prewarm_ttl_seconds * 1000))
        cutoff_ms = now_ms() - ttl_ms
        expired: list[PrewarmedProviderEntry] = []
        async with self._lock:
            for prewarm_id, entry in list(self._entries.items()):
                if entry.created_ms >= cutoff_ms:
                    continue
                expired.append(entry)
                self._entries.pop(prewarm_id, None)
                self._remove_aliases(entry)
                expiry_task = self._expiry_tasks.pop(prewarm_id, None)
                health_task = self._health_tasks.pop(prewarm_id, None)
                self._cancel_expiry_task(expiry_task)
                self._cancel_health_task(health_task)
        for entry in expired:
            logger.info("provider_prewarm_expired prewarm_id=%s", entry.prewarm_id)
            await self._stop_bundle(entry.bundle)

    async def close(self) -> None:
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
            self._aliases.clear()
            expiry_tasks = list(self._expiry_tasks.values())
            self._expiry_tasks.clear()
            health_tasks = list(self._health_tasks.values())
            self._health_tasks.clear()
        for task in expiry_tasks:
            self._cancel_expiry_task(task)
        for task in health_tasks:
            self._cancel_health_task(task)
        for entry in entries:
            await self._stop_bundle(entry.bundle)

    def _remove_aliases(self, entry: PrewarmedProviderEntry) -> None:
        for alias in entry.aliases:
            self._aliases.pop(alias, None)
        self._aliases.pop(entry.prewarm_id, None)

    async def _stop_bundle(self, bundle: SessionProviderBundle) -> None:
        await asyncio.gather(
            bundle.stt.stop(),
            bundle.tts.stop(),
            bundle.llm.stop(),
            return_exceptions=True,
        )

    async def _expire_after(self, prewarm_id: str) -> None:
        await asyncio.sleep(max(0.001, self.settings.outbound_provider_prewarm_ttl_seconds))
        await self.discard(prewarm_id, reason="ttl_expired")

    async def _monitor_health(self, prewarm_id: str) -> None:
        interval = max(0.1, self.settings.provider_health_check_seconds)
        while True:
            await asyncio.sleep(interval)
            async with self._lock:
                entry = self._entries.get(prewarm_id)
            if entry is None:
                return
            if await self._bundle_alive(entry.bundle):
                logger.debug("provider_prewarm_health_ok prewarm_id=%s", prewarm_id)
                continue
            logger.warning("provider_prewarm_provider_dropped prewarm_id=%s", prewarm_id)
            await self.discard(prewarm_id, reason="provider_dropped")
            return

    async def _bundle_alive(self, bundle: SessionProviderBundle) -> bool:
        stt_alive, tts_alive = await asyncio.gather(
            self._provider_alive(bundle.stt),
            self._provider_alive(bundle.tts),
            return_exceptions=True,
        )
        return stt_alive is True and tts_alive is True

    async def _provider_alive(self, provider: Any) -> bool:
        health_check = getattr(provider, "health_check", None)
        if callable(health_check):
            result = health_check()
            if isinstance(result, Awaitable):
                return bool(await result)
            return bool(result)
        if bool(getattr(provider, "stopped", False)):
            return False
        return bool(getattr(provider, "started", True))

    @staticmethod
    def _cancel_expiry_task(task: asyncio.Task[None] | None) -> None:
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()

    @staticmethod
    def _cancel_health_task(task: asyncio.Task[None] | None) -> None:
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()


def _stt_language_hint(settings: Settings) -> str:
    if settings.stt_provider == "sarvam":
        return settings.sarvam_stt_language_code
    return settings.deepgram_language
