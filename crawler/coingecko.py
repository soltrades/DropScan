import httpx
import time
import asyncio
import logging

logger = logging.getLogger(__name__)

# Simple in-memory cache: (chain, token_address) -> (price, timestamp)
_PRICE_CACHE = {}
CACHE_TTL = 300  # 5 minutes

# Map chain IDs to CoinGecko's chain ids
CHAIN_MAPPING = {
    1: "ethereum",
    8453: "base",
    42161: "arbitrum-one",
    10: "optimistic-ethereum",
    137: "polygon-pos"
}

async def get_token_price(chain_id: int, token_address: str) -> float:
    if not token_address:
        return 0.0

    chain_name = CHAIN_MAPPING.get(chain_id)
    if not chain_name:
        return 0.0

    token_address = token_address.lower()
    cache_key = (chain_id, token_address)
    now = time.time()

    if cache_key in _PRICE_CACHE:
        price, ts = _PRICE_CACHE[cache_key]
        if now - ts < CACHE_TTL:
            return price

    url = f"https://api.coingecko.com/api/v3/simple/token_price/{chain_name}"
    params = {
        "contract_addresses": token_address,
        "vs_currencies": "usd"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=5.0)
            if response.status_code == 429:
                logger.warning("CoinGecko rate limit hit — backing off")
                await asyncio.sleep(2)
                return 0.0  # don't cache this, let next call retry

            if response.status_code == 200:
                data = response.json()
                if token_address in data and "usd" in data[token_address]:
                    price = float(data[token_address]["usd"])
                    _PRICE_CACHE[cache_key] = (price, now)
                    return price
            
            # Cache zero price for unknown tokens to avoid repeat API calls
            _PRICE_CACHE[cache_key] = (0.0, now)
    except httpx.RequestError as e:
        logger.error(f"CoinGecko API error for {token_address} on chain {chain_id}: {e}")

    return 0.0
