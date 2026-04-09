import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from web3 import Web3

from crawler.db import get_db
from crawler.web3_utils import check_claim_status
from crawler.coingecko import get_token_price

api_router = APIRouter()

class ScanRequest(BaseModel):
    addresses: List[str]

@api_router.get("/feed")
async def get_feed():
    try:
        db = get_db()
        response = db.table("contracts").select("*").order("updated_at", desc=True).limit(20).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/scan")
async def scan_wallets(req: ScanRequest):
    if not req.addresses or len(req.addresses) > 5:
        raise HTTPException(status_code=400, detail="Must provide between 1 and 5 addresses.")
    
    for addr in req.addresses:
        if not Web3.is_address(addr):
            raise HTTPException(status_code=400, detail=f"Invalid EVM address: {addr}")
    req.addresses = [Web3.to_checksum_address(a) for a in req.addresses]
    
    try:
        db = get_db()
        # Fetch active contracts
        contracts_res = db.table("contracts").select("*").eq("status", "active").execute()
        contracts_data = contracts_res.data
        if not contracts_data:
            return {"status": "success", "data": {}}
        
        # Build tasks for all (wallet, contract) pairs
        tasks = []
        task_meta = []
        for wallet in req.addresses:
            for contract in contracts_data:
                tasks.append(check_claim_status(contract, wallet))
                task_meta.append(wallet)
                
        # Run all RPC lookups concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Fetch token prices from CoinGecko concurrently for standard unique tokens
        unique_tokens = list(set((c.get("chain_id"), c.get("token_address")) for c in contracts_data if c.get("token_address")))
        price_tasks = [get_token_price(ch, addr) for ch, addr in unique_tokens]
        prices_res = await asyncio.gather(*price_tasks, return_exceptions=True)
        
        # Build pricing dict mapping (chain_id, token_address.lower()) -> usd_price
        pricing_map = {}
        for idx, (ch, addr) in enumerate(unique_tokens):
            if not isinstance(prices_res[idx], Exception):
                pricing_map[(ch, addr.lower())] = prices_res[idx]

        # Aggregate the results
        aggregated = {addr: [] for addr in req.addresses}
        
        for i, res in enumerate(results):
            wallet = task_meta[i]
            if isinstance(res, Exception):
                continue
                
            if res.get("is_eligible"): # We might only want to return eligible ones, but the user requested grouped by wallet and each item has specific fields. Let's append all or only eligible. The user said runs checks against all active, returns results grouped by wallet. I'll include 'is_eligible' in the item and return it.
                token_addr = res.get("token_address")
                res.pop("token_address", None)
                res["usd_value"] = 0.0
                if token_addr:
                    price = pricing_map.get((res["chain_id"], token_addr.lower()), 0.0)
                    try:
                        amount = float(res.get("amount_raw", 0) or 0)
                    except (ValueError, TypeError):
                        amount = 0.0
                    res["usd_value"] = round(price * amount, 4)
                
                aggregated[wallet].append(res)
                
        return {"status": "success", "data": aggregated}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/airdrops")
async def get_airdrops():
    try:
        db = get_db()
        res = db.table("contracts").select("*").eq("status", "active").eq("verified", True).order("created_at", desc=True).execute()
        return {"status": "success", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/wallets")
async def register_wallet(body: dict):
    address = body.get("address", "").strip()
    if not Web3.is_address(address):
        raise HTTPException(status_code=400, detail="Invalid EVM address")
    address = Web3.to_checksum_address(address)
    try:
        db = get_db()
        db.table("wallets").upsert({"address": address}, on_conflict="address").execute()
        return {"status": "success", "address": address}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
