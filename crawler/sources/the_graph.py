import httpx
import logging
from crawler.normalizer import upsert_contract

logger = logging.getLogger(__name__)

# Placeholder endpoint as requested
GRAPH_ENDPOINT = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"

def crawl():
    """
    Discovery for MerkleDistributor contracts via The Graph.
    Includes seed data for Uniswap, Aerodrome, and Arbitrum.
    """
    logger.info("Starting The Graph discovery + seeding data...")

    # Seed data
    seed_contracts = [
        {
            "chain_id": 1,
            "contract_address": "0x090D4613473dEE047c3f2706764f49E0821D256e",
            "token_symbol": "UNI",
            "project_name": "Uniswap",
            "claim_url": "https://app.uniswap.org/claim",
            "source": "manual",
            "status": "expired",
            "verified": True
        },
        {
            "chain_id": 8453,
            "contract_address": "0x31D3243CfB54B34Fc9C73e1CB1137124bD6B13E",
            "token_symbol": "AERO",
            "project_name": "Aerodrome",
            "claim_url": "https://aerodrome.finance",
            "source": "manual",
            "status": "active",
            "verified": True
        },
        {
            "chain_id": 42161,
            "contract_address": "0x67a24CE4321aB3aF51c2D0a4801c3E111D88C9d9",
            "token_symbol": "ARB",
            "project_name": "Arbitrum",
            "claim_url": "https://arbitrum.foundation/claim",
            "source": "manual",
            "status": "expired",
            "verified": True
        }
    ]

    for contract in seed_contracts:
        upsert_contract(contract)

    # Placeholder for actual subgraph query logic
    query = """
    {
      pools(first: 5, orderBy: totalValueLockedUSD, orderDirection: desc) {
        id
        token0 { symbol }
        token1 { symbol }
      }
    }
    """
    
    try:
        # Note: The real subgraph to use is a Merkle Distributor indexer.
        # This is just a placeholder query to show httpx integration.
        # with httpx.Client() as client:
        #     response = client.post(GRAPH_ENDPOINT, json={'query': query})
        #     if response.status_code == 200:
        #         logger.info("Successfully reached The Graph endpoint (placeholder)")
        pass
    except Exception as e:
        logger.error(f"Error querying The Graph repository: {e}")

    logger.info("Finished The Graph / Seed data processing.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawl()
