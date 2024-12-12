import asyncio
import json
import os
import random
import sys
import time
import uuid
from urllib.parse import urlparse

import cloudscraper
import requests
from loguru import logger
from pyfiglet import figlet_format
from termcolor import colored


# Global configuration
SHOW_REQUEST_ERROR_LOG = False

PING_INTERVAL = 60
RETRIES = 60

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": ["https://nw.nodepay.org/api/network/ping"],
    "DAILY_CLAIM": "https://api.nodepay.org/api/mission/complete-mission",
    "DEVICE_NETWORK": "https://api.nodepay.org/api/network/device-networks"
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
    format="<r>[Nodepay]</r> | <white>{time:YYYY-MM-DD HH:mm:ss}</white> | "
           "<level>{level: ^7}</level> | <cyan>{line: <3}</cyan> | {message}",
    colorize=True
)
logger = logger.opt(colors=True)

def print_header():
    ascii_art = figlet_format("NodepayBot", font="slant")
    colored_art = colored(ascii_art, color="cyan")
    border = "=" * 40

    print(border)
    print(colored_art)
    print(colored("by Enukio", color="cyan", attrs=["bold"]))
    print("\nWelcome to NodepayBot - Automate your tasks effortlessly!")

def print_file_info():
    tokens = load_file('token.txt')
    proxies = load_file('proxies.txt')
    border = "=" * 40

    print(border)
    print(
        f"\nTokens: {len(tokens)} - Loaded {len(proxies)} proxies"
        "\nNodepay only supports 3 connections per account. Using too many proxies may cause issues.\n"
        f"\n{border}"
    )

def load_file(filename, split_lines=True):
    try:
        with open(filename, 'r') as file:
            content = file.read()
            return content.splitlines() if split_lines else content
    except FileNotFoundError:
        logger.error(f"<red>File '{filename}' not found. Please ensure it exists.</red>")
        return []

def load_proxies():
    return load_file('proxies.txt')

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

def dailyclaim(token):
    tokens = load_file("token.txt")
    if not tokens or token not in tokens:
        return False

    proxies = load_file("proxies.txt") if os.path.exists("proxies.txt") else []

    url = DOMAIN_API["DAILY_CLAIM"]
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://app.nodepay.ai",
        "Referer": "https://app.nodepay.ai/"
    }
    data = {
        "mission_id": "1"
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code != 200:
            logger.info(f"<yellow>Reward Already Claimed!</yellow>")
            return False

        response_json = response.json()
        if response_json.get("success"):
            logger.info(f"<green>Claim Reward Success!</green>")
            return True
        else:
            logger.info(f"<yellow>Reward Already Claimed!</yellow>")
            return False
    except Exception as e:
        logger.error(f"Request failed: {e}") if SHOW_REQUEST_ERROR_LOG else None
        return False

async def get_account_info(token, proxy=None):
    url = DOMAIN_API["SESSION"]
    try:
        response = await call_api(url, {}, token, proxy)
        if response:
            logger.info(f"<green>Account info for token {token[-10:]}: {response}</green>")
            if response.get("code") == 0:
                data = response["data"]
                return {
                    "name": data.get("name", "Unknown"),
                    "ip_score": data.get("ip_score", "N/A"),
                    **data
                }
            else:
                logger.error(f"<red>Error: {response.get('message', 'No message')}")
        else:
            logger.error("<red>No response received from API</red>")
    except Exception as e:
        logger.error(f"<red>Error fetching account info for token {token[-10:]}: {e}</red>")
    return None

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
        logger.info(f"Sending request to {url} with token: {token[-10:]} and proxy: {proxy}")
        response = requests.post(url, json=data, headers=headers, proxies={"http": proxy, "https": proxy}, timeout=15)
        logger.info(f"Received response: {response.status_code} {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during API call to {url}: {e}") if SHOW_REQUEST_ERROR_LOG else None
        if response and response.status_code == 403:
            logger.error("<red>Access denied (HTTP 403). Possible invalid token or blocked IP/proxy.</red>")
            time.sleep(random.uniform(5, 10))
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

async def start_ping(token, account_info, proxy, ping_interval, browser_id=None):
    global last_ping_time, RETRIES, status_connect
    browser_id = browser_id or str(uuid.uuid4())
    url_index = 0
    last_valid_points = 0
    name = account_info.get("name", "Unknown")
    
    RETRIES = 0

    while True:
        current_time = time.time()

        if proxy:
            last_ping_time[proxy] = current_time

        if not DOMAIN_API["PING"]:
            logger.error("<red>No PING URLs available in DOMAIN_API['PING'].</red>")
            return

        url = DOMAIN_API["PING"][url_index]

        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        try:
            response = await call_api(url, data, token, proxy=proxy, timeout=120)
            if response and response.get("data"):

                status_connect = CONNECTION_STATES["CONNECTED"]
                response_data = response["data"]
                ip_score = response_data.get("ip_score", "N/A")
                total_points = await get_total_points(token, ip_score=ip_score, proxy=proxy, name=name)
                total_points = last_valid_points if total_points == 0 and last_valid_points > 0 else total_points
                last_valid_points = total_points

                identifier = extract_proxy_ip(proxy) if proxy else get_ip_address()
                logger.info(
                    f"<green>Ping Successfully</green>, Network Quality: <cyan>{ip_score}</cyan>, "
                    f"{'Proxy' if proxy else 'IP Address'}: <cyan>{identifier}</cyan>")
                
                RETRIES = 0
            else:
                logger.warning(f"<yellow>Invalid or no response from {url}</yellow>")
                RETRIES += 1

                if RETRIES >= 3:
                    logger.error(f"<red>Exceeded retry limit for proxy {proxy}. Aborting.</red>")
                    break

            url_index = (url_index + 1) % len(DOMAIN_API["PING"])

        except Exception as e:
            logger.error(f"<red>Error during pinging via proxy {proxy}: {e}</red>")
            RETRIES += 1

            if RETRIES >= 3:
                logger.error(f"<red>Exceeded retry limit for proxy {proxy}. Aborting.</red>")
                break

        await asyncio.sleep(ping_interval)


# Main logic
async def main():
    if not (tokens := load_file("token.txt")):
        return logger.error("<red>No tokens found in 'token.txt'. Exiting.</red>")


    users_data = await asyncio.gather(*(get_account_info(token) for token in tokens), return_exceptions=True)
    log_user_data([data for data in users_data if not isinstance(data, Exception)])

    logger.info("Waiting before starting tasks...")
    await asyncio.sleep(5)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"<red>Task failed: {result}</red>")

if __name__ == '__main__':
    asyncio.run(main())
