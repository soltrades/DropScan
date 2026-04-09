# DropScan &mdash; Free EVM Airdrop Checker

DropScan is an EVM airdrop checker foundation designed to discover and track airdrop contracts across multiple chains (ETH, Base, Arbitrum, Polygon, etc.). This repository contains the crawler and storage logic.

## Features
- **Discovery**: Scrapes `airdrops.io` for new airdrop candidates.
- **The Graph Integration**: Skeleton for querying Merkle Distributor subgraphs.
- **Seed Data**: Includes real airdrop contracts (Uniswap, Aerodrome, Arbitrum) for immediate testing.
- **Storage**: Uses Supabase (Postgres) for reliable data persistence.
- **Scheduling**: Automated runs every 30 minutes with graceful interruption handling.

## Tech Stack
- **Python 3.11**
- **Supabase** (Postgres & Client SDK)
- **httpx + BeautifulSoup4** (Crawling & HTML Parsing)
- **Schedule** (Cron-like loop)
- **Loguru-style logging** (Python standard logging)

## Setup

### 1. Supabase Configuration
1. Create a new project on [Supabase Dashboard](https://supabase.com/dashboard).
2. Go to the **SQL Editor** and run the contents of `supabase/migrations/001_init.sql` to set up the schema.
3. Retrieve your **Project URL** and **Service Role Key** (under Project Settings -> API).

### 2. Environment Variables (.env)
Create a `.env` file in the root directory (refer to `.env.example`):
```bash
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
ALCHEMY_API_KEY=your-alchemy-key
INFURA_API_KEY=your-infura-key
```

### 3. Local Installation
```bash
pip install -r requirements.txt
```

### 4. Run Locally
```bash
python -m crawler.main
```

## Deployment

### Railway (Recommended)
1. Fork this repository or initialize a new GitHub repo.
2. Link the repository to a new project in [Railway](https://railway.app/).
3. Set the Environment Variables (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, etc.) in the Railway dashboard.
4. **Start Command**: `python -m crawler.main`

## Troubleshooting
- **Airdrops.io Blocks**: If you encounter 403 errors, `airdrops.io` may have temporarily blocked the IP. Consider using a proxy or rotating user agents in `crawler/sources/airdrops_io.py`.
- **DB Connection**: Ensure your Supabase project is "Active" and the Service Key has permissions to perform `upsert`.
