import os
import asyncio
import logging
from web3 import AsyncWeb3
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ALCHEMY_KEY = os.environ.get("ALCHEMY_API_KEY", "")
INFURA_KEY = os.environ.get("INFURA_API_KEY", "")

# RPC mapping fallback
RPC_POOL = {
    1: f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}" if ALCHEMY_KEY else "https://cloudflare-eth.com",
    8453: f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}" if ALCHEMY_KEY else "https://mainnet.base.org",
    42161: f"https://arb-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}" if ALCHEMY_KEY else "https://arb1.arbitrum.io/rpc",
    10: f"https://opt-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}" if ALCHEMY_KEY else "https://mainnet.optimism.io",
    137: f"https://polygon-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}" if ALCHEMY_KEY else "https://polygon-rpc.com"
}

# Standard claim check ABI
STANDARD_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "isClaimed",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]

CLAIMABLE_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "claimableTokens",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "earned",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Singleton cache for Web3 instances per chain
# NOTE: not thread-safe, safe for single asyncio event loop only
w3_instances = {}

def get_w3(chain_id: int) -> AsyncWeb3:
    if chain_id not in w3_instances:
        rpc_url = RPC_POOL.get(chain_id)
        if not rpc_url:
            raise ValueError(f"Unsupported chain_id: {chain_id}")
        w3_instances[chain_id] = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
    return w3_instances[chain_id]


async def check_claim_status(contract_data: dict, wallet_address: str) -> dict:
    chain_id = contract_data.get("chain_id")
    contract_address = contract_data.get("contract_address")
    
    # Default response structure
    result = {
        "contract_id": contract_data.get("id"),
        "project_name": contract_data.get("project_name"),
        "token_symbol": contract_data.get("token_symbol"),
        "chain_id": chain_id,
        "claim_url": contract_data.get("claim_url"),
        # amount_raw: raw on-chain uint256 as string (wei or token units, 
        # divide by 10**decimals for display)
        "amount_raw": "0",
        "is_eligible": False,
        "already_claimed": False,
        "contract_address": contract_address,
        "token_address": contract_data.get("token_address")
    }

    try:
        w3 = get_w3(chain_id)
        checksum_contract = w3.to_checksum_address(contract_address)
        checksum_wallet = w3.to_checksum_address(wallet_address)
        
        # 1. Try checking if already claimed
        contract_std = w3.eth.contract(address=checksum_contract, abi=STANDARD_ABI)
        try:
            is_claimed = await contract_std.functions.isClaimed(checksum_wallet).call()
            if is_claimed:
                result["already_claimed"] = True
                result["is_eligible"] = False
                return result
        except Exception:
            pass  # Contract might not have isClaimed or reverts
            
        # 2. Try checking claimable balance
        contract_claim = w3.eth.contract(address=checksum_contract, abi=CLAIMABLE_ABI)
        
        amount = 0
        try:
            amount = await contract_claim.functions.claimableTokens(checksum_wallet).call()
        except Exception:
            try:
                amount = await contract_claim.functions.earned(checksum_wallet).call()
            except Exception:
                pass
                
        if amount > 0:
            result["is_eligible"] = True
            result["amount_raw"] = str(amount)
        else:
            result["is_eligible"] = False

    except Exception as e:
        logger.debug(f"Failed to check claim status for {wallet_address} on {contract_address} (Chain: {chain_id}): {e}")
        # Mark as not eligible or handle uniquely
        result["is_eligible"] = False

    return result

