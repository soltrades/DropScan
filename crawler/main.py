import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from crawler.sources import airdrops_io, the_graph
from crawler.db import get_db
from crawler.api import api_router

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def crawler_loop():
    """
    Background task running asynchronously.
    """
    while True:
        logger.info("--- Starting Discovery Cycle ---")
        try:
            # Note: Depending on the scraping library (httpx vs requests), 
            # if they are synchronous we might want to run them in threadpool.
            # airdrops_io.crawl() and the_graph.crawl() might be blocking.
            # Using asyncio.to_thread just in case they are synchronous.
            await asyncio.to_thread(the_graph.crawl)
            await asyncio.to_thread(airdrops_io.crawl)
            
            logger.info("--- Discovery Cycle Completed Successfully ---")
        except Exception as e:
            logger.error(f"Critical error during discovery cycle: {e}")
        
        # Sleep for 30 minutes
        await asyncio.sleep(1800)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("[READY] DropScan FastAPI Server Initializing.")
    try:
        get_db()
        logger.info("Connected to Supabase.")
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        sys.exit(1)

    task = asyncio.create_task(crawler_loop())
    
    yield
    
    # Shutdown
    logger.info("Gracefully shutting down DropScan background tasks.")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="DropScan Web Server", lifespan=lifespan)
app.include_router(api_router)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
