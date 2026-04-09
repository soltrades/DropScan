-- Initial migration for DropScan

-- Create contracts table
CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    chain_id INTEGER NOT NULL,          -- e.g. 1=ETH, 8453=Base, 42161=Arb, 137=Polygon
    contract_address TEXT NOT NULL,
    token_address TEXT,
    token_symbol TEXT,
    token_name TEXT,
    claim_method TEXT,                   -- e.g. "claim", "claimTokens", "claimReward"
    abi_snippet JSONB,                   -- just the claim + isClaimed functions
    deadline TIMESTAMPTZ,
    project_name TEXT,
    project_url TEXT,
    claim_url TEXT,                      -- the original claiming page deep link
    source TEXT,                         -- where we discovered this (e.g. "airdrops_io", "the_graph", "manual")
    status TEXT DEFAULT 'active',        -- active | expired | unverified
    verified BOOLEAN DEFAULT false,      -- manually reviewed
    UNIQUE (chain_id, contract_address)
);

-- Create wallets table
CREATE TABLE IF NOT EXISTS wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address TEXT NOT NULL UNIQUE,        -- checksummed EVM address
    created_at TIMESTAMPTZ DEFAULT now(),
    last_scanned_at TIMESTAMPTZ
);

-- Create alert_subscriptions table
CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID REFERENCES wallets(id) ON DELETE CASCADE,
    telegram_chat_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (wallet_id, telegram_chat_id)
);

-- Create claim_events table
CREATE TABLE IF NOT EXISTS claim_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL,
    contract_id UUID REFERENCES contracts(id) ON DELETE CASCADE,
    is_eligible BOOLEAN NOT NULL,
    amount_raw TEXT,                     -- raw on-chain amount
    checked_at TIMESTAMPTZ DEFAULT now()
);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for contracts table
CREATE TRIGGER update_contracts_updated_at
BEFORE UPDATE ON contracts
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
