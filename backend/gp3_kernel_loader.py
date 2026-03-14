"""
GP3 Kernel Loader — loads agent identity from gp3_kernels table on Supabase (zoda).

Drop this file into any GP3 Python service. Import and call:

    from gp3_kernel_loader import load_kernel
    prompt = load_kernel("cal", "d505483a-e07b-4376-b198-d9de5fd9a2bd")

Returns assembled K0-K5 system prompt string, or fallback if DB unavailable.

Env vars needed (already set in every GP3 service):
    SUPABASE_URL  — https://ezlmmegowggujpcnzoda.supabase.co
    SUPABASE_SERVICE_KEY or SUPABASE_KEY — service_role key

n0v8v LLC | 2026-03-14
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Cache: (app, tenant_id) -> assembled prompt string
_cache: dict[tuple[str, str], str] = {}


def _get_supabase_config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
    return url, key


def load_kernel(
    app: str,
    tenant_id: str,
    entities: Optional[list[str]] = None,
    use_cache: bool = True,
    fallback: Optional[str] = None,
) -> str:
    """Load and assemble K0-K5 kernel from gp3_kernels table.

    Args:
        app: Service name ('cal', 'orc', 'howl', 'pete', etc.)
        tenant_id: UUID of the tenant
        entities: List of entity names to load and layer. Defaults to ['default'].
                  For ORC, might be ['default', 'bunting-org', 'bunting-calibrations'].
                  Loaded in order — later entities override/append to earlier ones.
        use_cache: Cache the assembled prompt in memory. Default True.
        fallback: String to return if DB query fails. Default None returns empty string.

    Returns:
        Assembled system prompt string (K0 + K1 + K2 + K3 + K4 + K5, separated by double newlines).
    """
    if entities is None:
        entities = ["default"]

    cache_key = (app, tenant_id, tuple(entities))
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    prompt = _load_from_supabase(app, tenant_id, entities)

    if not prompt:
        logger.warning(f"gp3_kernels: no kernel found for app={app}, tenant={tenant_id}, entities={entities}")
        prompt = fallback or ""

    if use_cache and prompt:
        _cache[cache_key] = prompt

    return prompt


def clear_cache():
    """Clear the kernel cache. Call after updating kernels in DB."""
    _cache.clear()


def _load_from_supabase(app: str, tenant_id: str, entities: list[str]) -> str:
    """Query gp3_kernels via REST API (no supabase-py dependency required)."""
    import httpx

    url, key = _get_supabase_config()
    if not url or not key:
        logger.error("gp3_kernels: SUPABASE_URL or SUPABASE_KEY not set")
        return ""

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    k_blocks = ["k0", "k1", "k2", "k3", "k4", "k5"]
    assembled_parts: list[str] = []

    for entity in entities:
        try:
            rest_url = (
                f"{url}/rest/v1/gp3_kernels"
                f"?app=eq.{app}"
                f"&tenant_id=eq.{tenant_id}"
                f"&entity=eq.{entity}"
                f"&select={','.join(k_blocks)},version,tokens"
                f"&limit=1"
            )
            resp = httpx.get(rest_url, headers=headers, timeout=10.0)

            if resp.status_code != 200:
                logger.error(f"gp3_kernels REST error {resp.status_code}: {resp.text[:200]}")
                continue

            rows = resp.json()
            if not rows:
                logger.debug(f"gp3_kernels: no row for app={app}, entity={entity}")
                continue

            row = rows[0]
            for k in k_blocks:
                val = row.get(k)
                if val:
                    assembled_parts.append(val)

            logger.info(
                f"gp3_kernels: loaded app={app}, entity={entity}, "
                f"v{row.get('version', '?')}, {row.get('tokens', '?')} tokens"
            )

        except Exception as e:
            logger.error(f"gp3_kernels: failed to load entity={entity}: {e}")
            continue

    return "\n\n".join(assembled_parts)


async def aload_kernel(
    app: str,
    tenant_id: str,
    entities: Optional[list[str]] = None,
    use_cache: bool = True,
    fallback: Optional[str] = None,
) -> str:
    """Async version of load_kernel for FastAPI/async services."""
    import httpx

    if entities is None:
        entities = ["default"]

    cache_key = (app, tenant_id, tuple(entities))
    if use_cache and cache_key in _cache:
        return _cache[cache_key]

    url, key = _get_supabase_config()
    if not url or not key:
        logger.error("gp3_kernels: SUPABASE_URL or SUPABASE_KEY not set")
        return fallback or ""

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    k_blocks = ["k0", "k1", "k2", "k3", "k4", "k5"]
    assembled_parts: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for entity in entities:
            try:
                rest_url = (
                    f"{url}/rest/v1/gp3_kernels"
                    f"?app=eq.{app}"
                    f"&tenant_id=eq.{tenant_id}"
                    f"&entity=eq.{entity}"
                    f"&select={','.join(k_blocks)},version,tokens"
                    f"&limit=1"
                )
                resp = await client.get(rest_url, headers=headers)

                if resp.status_code != 200:
                    logger.error(f"gp3_kernels REST error {resp.status_code}: {resp.text[:200]}")
                    continue

                rows = resp.json()
                if not rows:
                    continue

                row = rows[0]
                for k in k_blocks:
                    val = row.get(k)
                    if val:
                        assembled_parts.append(val)

                logger.info(
                    f"gp3_kernels: loaded app={app}, entity={entity}, "
                    f"v{row.get('version', '?')}, {row.get('tokens', '?')} tokens"
                )
            except Exception as e:
                logger.error(f"gp3_kernels: failed to load entity={entity}: {e}")
                continue

    prompt = "\n\n".join(assembled_parts)

    if not prompt:
        prompt = fallback or ""

    if use_cache and prompt:
        _cache[cache_key] = prompt

    return prompt
