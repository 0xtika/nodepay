import asyncio
import json
import sys
import time
import uuid
from urllib.parse import urlparse
import cloudscraper
import requests
from loguru import logger
from fake_useragent import UserAgent

# Global configuration
SHOW_REQUEST_ERROR_LOG = False

PING_INTERVAL = 60
RETRIES = 60

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": ["https://nw.nodepay.org/api/network/ping"],
    "DAILY_CLAIM": "https://api.nodepay.org/api/mission/complete-mission",
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES
account_info = {}
last_ping_time = {}
token_status = {}
browser_id = None

# Setup logger
logger.remove()
logger.add(
    sink=sys.stdout,
    format="<r>[Nodepay]</r> | <white>DATE: {time:YYYY-MM-DD}</white> | <white>TIME: {time:HH:mm:ss}</white> | "
           "<level>{level: ^7}</level> | <cyan>{line: <3}</cyan> | {message}",
    colorize=True
)
logger = logger.opt(colors=True)
def truncate_token(token):
    return f"{token[:4]}--{token[-4:]}"

def ask_user_for_proxy():
        return []

def load_file(filename, split_lines=True):
    try:
        with open(filename, 'r') as file:
            content = file.read()
            return content.splitlines() if split_lines else content
    except FileNotFoundError:
        logger.error(f"<red>File '{filename}' not found. Please ensure it exists.</red>")
        return []

def load_proxies():
    return load_file('proxy.txt')

def assign_proxies_to_tokens(tokens, proxies):
    if proxies is None:
        proxies = []
    paired = list(zip(tokens[:len(proxies)], proxies))
    remaining = [(token, None) for token in tokens[len(proxies):]]
    return paired + remaining

def extract_proxy_ip(proxy_url):
    try:
        return urlparse(proxy_url).hostname
    except Exception:
        return "Unknown"
def get_ip_address(proxy=None):
    try:
        url = "https://api.ipify.org?format=json"
        response = cloudscraper.create_scraper().get(url, proxies={"http": proxy, "https": proxy} if proxy else None)
        return response.json().get("ip", "Unknown") if response.status_code == 200 else "Unknown"
    except Exception as e:
        logger.error(f"<red>Failed to fetch IP address: {e}</red>")
    return "Unknown"

def log_user_data(users_data):
    if not users_data:
        logger.error("<red>No user data available.</red>")
        return

    try:
        for user_data in users_data:
            name = user_data.get("name", "Unknown")
            balance = user_data.get("balance", {})
            logger.info(f"User: <green>{name}</green>, "
                        f"Current Amount: <green>{balance.get('current_amount', 0)}</green>, "
                        f"Total Collected: <green>{balance.get('total_collected', 0)}</green>")

    except Exception as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"Logging error: {e}")


async def call_api(url, data, token, proxy=None, timeout=60):
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://app.nodepay.ai/",
            "Accept": "application/json, text/plain, */*",
            "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
            "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cors-site"
    }

    response = None

    try:
        response = requests.post(url, json=data, headers=headers, impersonate="safari15_5", proxies={"http": proxy, "https": proxy}, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during API call to {url}: {e}") if SHOW_REQUEST_ERROR_LOG else None
        if response and response.status_code == 403:
            logger.error("<red>Access denied (HTTP 403). Possible invalid token or blocked IP/proxy.</red>")
            time.sleep(random.uniform(60, 65))
            return None
        elif response and response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            logger.warning(f"<yellow>Rate limit hit (HTTP 429). Retry after {retry_after} seconds.</yellow>")
            time.sleep(int(retry_after) if retry_after != "unknown" else 5)
        else:
            logger.error(f"Request failed: {e}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response from {url}: {e}") if SHOW_REQUEST_ERROR_LOG else None
    except Exception as e:
        logger.error(f"Unexpected error during API call: {e}") if SHOW_REQUEST_ERROR_LOG else None

    return None

async def get_account_info(token, proxy=None):
    url = DOMAIN_API["SESSION"]
    try:
        response = await call_api(url, {}, token, proxy)
        if response and response.get("code") == 0:
            data = response["data"]
            return {
                "name": data.get("name", "Unknown"),
                "ip_score": data.get("ip_score", "N/A"),
                **data
            }
    except Exception as e:
        logger.error(f"<red>Error fetching account info for token {token[-10:]}: {e}</red>")
    return None
async def start_ping(token, account_info, proxy):
    browser_id = str(uuid.uuid4())

    if not DOMAIN_API["PING"]:
        logger.error("<red>No PING URLs available in DOMAIN_API['PING'].</red>")
        return

    url = DOMAIN_API["PING"][0]  # Gunakan URL pertama saja
    data = {
        "id": account_info.get("uid"),
        "browser_id": browser_id,
        "timestamp": int(time.time()),
        "version": "2.2.7"
    }

    try:
        response = await call_api(url, data, token, proxy)
        if response and response.get("data"):
            ip_score = response["data"].get("ip_score", "N/A")
            logger.info(f"<green>PING SUCCESS</green> | NETWORK QUALITY: <cyan>{ip_score}</cyan> | TOKEN: {token[:4]}...{token[-4:]}")
        else:
            logger.warning(f"<yellow>Invalid response from {url}</yellow>")
    except Exception as e:
        logger.error(f"<red>Error during ping: {e}</red>")

async def process_account(token, use_proxy, proxies):
    proxy = proxies[0] if use_proxy and proxies else None
    account_info = await get_account_info(token, proxy)

    if not account_info:
        logger.error(f"<red>Account info not found for token {token[:4]}...{token[-4:]}</red>")
        return

    await start_ping(token, account_info, proxy)

async def main():
    tokens = load_file("token.txt")
    if not tokens:
        return logger.error("<red>No tokens found in 'token.txt'. Exiting.</red>")

    proxies = ask_user_for_proxy()
    token_proxy_pairs = [(token, proxies[i] if i < len(proxies) else None) for i, token in enumerate(tokens)]

    for token, proxy in token_proxy_pairs:
        await process_account(token, use_proxy=bool(proxy), proxies=[proxy] if proxy else [])

    logger.info("All tasks completed. Exiting program.")
    sys.exit(0)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted. Exiting gracefully...")
    finally:
        print("Cleaning up resources before exiting.")
