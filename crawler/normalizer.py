import logging
from crawler.db import get_db
from datetime import datetime

logger = logging.getLogger(__name__)

def upsert_contract(data: dict):
    """
    Upserts a contract into the contracts table.
    Uses (chain_id, contract_address) as conflict key.
    """
    db = get_db()
    
    # Ensure chain_id and contract_address exist
    chain_id = data.get("chain_id")
    contract_address = data.get("contract_address")
    
    if chain_id is None or not contract_address:
        logger.warning(f"Skipping upsert: Missing chain_id or contract_address in data: {data}")
        return

    # Normalize contract address to lowercase
    data["contract_address"] = contract_address.lower()
    
    # Refresh updated_at on every upsert (Supabase trigger might handle this, but explicit here too)
    data["updated_at"] = datetime.now().isoformat()

    try:
        # Perform upsert
        # Note: on_conflict requires the unique constraint columns
        response = db.table("contracts").upsert(
            data, 
            on_conflict="chain_id,contract_address"
        ).execute()
        
        if response.data:
            # Check if it was an insert or update (if possible)
            # Typically Supabase response data contains the upserted row
            logger.info(f"Successfully upserted contract: {data.get('project_name')} ({contract_address}) on chain {chain_id}")
        else:
            logger.warning(f"Upsert returned no data for {contract_address}")
            
    except Exception as e:
        logger.error(f"Error upserting contract {contract_address}: {e}")
