import httpx
from bs4 import BeautifulSoup
import time
import logging
from crawler.normalizer import upsert_contract

logger = logging.getLogger(__name__)

def crawl():
    """
    GET https://airdrops.io/latest/ and parse latest airdrops.
    """
    url = "https://airdrops.io/latest/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

    logger.info(f"Crawling {url}...")
    
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=20.0) as client:
            response = client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch {url}: {response.status_code}")
                return

            soup = BeautifulSoup(response.text, 'lxml')
            
            # Airdrops.io structure: "airdrop-home-items" cards
            articles = soup.select('article.airdrop-home-items')
            
            if not articles:
                # Fallback if class changes
                articles = soup.find_all('article')

            found_count = 0
            for article in articles:
                try:
                    # Title and Project URL are usually in h3 > a
                    title_elem = article.select_one('h3 a')
                    # Claim URL is usually a 'CLAIM AIRDROP' link
                    claim_link_elem = article.select_one('a.airdrop-home-link') or article.find('a', string=lambda s: s and 'CLAIM' in s.upper())
                    
                    if title_elem:
                        project_name = title_elem.text.strip()
                        project_url = title_elem.get('href', '')
                        claim_url = claim_link_elem.get('href', project_url) if claim_link_elem else project_url
                        
                        # Data point for normalization
                        contract_data = {
                            "project_name": project_name,
                            "project_url": project_url,
                            "claim_url": claim_url,
                            "source": "airdrops_io",
                            "status": "unverified",
                            "chain_id": 1, # Default to ETH, needs deep page parsing for others
                            "contract_address": f"pending_{project_name.lower().replace(' ', '_')}",
                            "verified": False
                        }
                        
                        logger.info(f"Found airdrop candidate: {project_name}")
                        upsert_contract(contract_data)
                        found_count += 1
                        
                        # Rate limiting per request
                        time.sleep(2.5) 
                        
                except Exception as e:
                    logger.error(f"Error parsing article card: {e}")

            logger.info(f"Finished airdrops.io crawl. Candidates found: {found_count}")

    except Exception as e:
        logger.error(f"Error crawling airdrops.io: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawl()
