"""
utils/ge_api.py - Async wrapper around the OSRS wiki real-time prices API.

Endpoints used
--------------
    GET /mapping  -> full item catalogue (id, name, limit, highalch, members, ...)
    GET /latest  ->  live high/low prices for all items (or single id= param)
    
The mapping is fetched once per session and cached in module-level memory.
Individual price lookups hit /latest?id=X so they are always live.

API docs: https://oldschool.runescape.wiki/w/Runescape:Real-time_Prices

"""

from __future__ import annotations

import asyncio
import urllib.request
import urllib.error
import json
import time
from dataclasses import dataclass, field
from typing import Optional


# CONSTANTs

_BASE = "https://prices.runescape.wiki/api/v1/osrs"
_UA = "osrs-tui / github.com/8bitmaidenless/osrs_tui"

_mapping_cache: dict[str, "GEItem"] = {}
_mapping_loaded: bool = False


# Domain models

@dataclass
class GEItem:
    id: int
    name: str
    examine: str = ""
    members: bool = False
    limit: Optional[int] = None
    highalch: Optional[int] = None
    lowalch: Optional[int] = None
    value: Optional[int] = None
    icon: str = ""


@dataclass
class GEPrice:
    item_id: int
    name: str
    high: Optional[int]
    high_time: Optional[int]
    low: Optional[int]
    low_time: Optional[int]
    fetched_at: float = field(default_factory=time.time)

    @property
    def mid(self) -> Optional[int]:
        """Simple mid-price."""
        if self.high is not None and self.low is not None:
            return (self.high + self.low) // 2
        return self.high or self.low
    
    @property
    def spread(self) -> Optional[int]:
        if self.high is not None and self.low is not None:
            return self.high - self.low
        return None
    
    @property
    def high_time_str(self) -> str:
        if self.high_time is None:
            return "-"
        import datetime
        return datetime.datetime.fromtimestamp(self.high_time).strftime("%H:%M:%S")
    
    @property
    def low_time_str(self) -> str:
        if self.low_time is None:
            return "-"
        import datetime
        return datetime.datetime.fromtimestamp(self.low_time).strftime("%H:%M:%S")
    

class GEAPIError(Exception):
    pass


# Public async interface

async def fetch_mapping() -> dict[str, GEItem]:
    """
    Fetch and cache the full item mapping (name + GEItem).
    Returns from cache on subsequent calls within the same process lifetime.
    """
    global _mapping_cache, _mapping_loaded
    if _mapping_loaded:
        return _mapping_cache
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        _blocking_fetch_mapping
    )
    _mapping_cache = result
    _mapping_loaded = True
    return result


async def search_items(query: str) -> list[GEItem]:
    """
    Return all items whose name contains `query` (case-insensitive).
    Fetches mapping on first call.
    """
    mapping = await fetch_mapping()
    q = query.lower().strip()
    return [item for name, item in mapping.items() if q in name]


async def fetch_price(item_id: int) -> GEPrice:
    """Fetch live high/low price for a single item by ID."""
    mapping = await fetch_mapping()

    name = next((i.name for i in mapping.values() if i.id == item_id), f"Item #{item_id}")
    price = await asyncio.get_event_loop().run_in_executor(
        None,
        _blocking_fetch_price,
        item_id
    )
    price.name = name
    return price


async def fetch_prices_bulk(item_ids: list[int]) -> dict[int, GEPrice]:
    """
    Fetch live prices for a list of item ID in on /latest call.
    """
    mapping = await fetch_mapping()
    id_to_name = {i.id: i.name for i in mapping.values()}
    raw = await asyncio.get_event_loop().run_in_executor(
        None,
        _blocking_fetch_latest_all
    )
    result: dict[int, GEPrice] = {}
    for iid in item_ids:
        entry = raw.get(str(iid)) or raw.get(iid)
        if entry:
            result[iid] = GEPrice(
                item_id=iid,
                name=id_to_name.get(iid, f"Item #{iid}"),
                high=entry.get("high"),
                high_time=entry.get("highTime"),
                low=entry.get("low"),
                low_time=entry.get("lowTime")
            )
    return result


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise GEAPIError(f"HTTP {e.code}: {url}") from e
    except urllib.error.URLError as e:
        raise GEAPIError(f"Network error: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise GEAPIError(f"Bad JSON from API: {e}") from e
    

def _blocking_fetch_mapping() -> dict[str, GEItem]:
    data = _http_get(f"{_BASE}/mapping")
    result: dict[str, GEItem] = {}
    for entry in data:
        item = GEItem(
            id=entry["id"],
            name=entry.get("name", ""),
            examine=entry.get("examine", ""),
            members=entry.get("members", False),
            limit=entry.get("limit"),
            highalch=entry.get("highalch"),
            lowalch=entry.get("lowalch"),
            value=entry.get("value"),
            icon=entry.get("icon", "")
        )
        result[item.name.lower()] = item
    return result


def _blocking_fetch_price(item_id: int) -> GEPrice:
    data = _http_get(f"{_BASE}latest?id={item_id}")
    entry = data.get("data", {}).get(str(item_id), {})
    return GEPrice(
        item_id=item_id,
        name="",
        high=entry.get("high"),
        high_time=entry.get("highTime"),
        low=entry.get("low"),
        low_time=entry.get("lowTime")
    )


def _blocking_fetch_latest_all() -> dict:
    data = _http_get(f"{_BASE}/latest")
    return data.get("data", {})

