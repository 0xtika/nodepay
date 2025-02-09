import asyncio
import json
import os
import random
import sys
import time
import uuid
from urllib.parse import urlparse
import schedule
import cloudscraper
import requests
from curl_cffi import requests
from loguru import logger
from pyfiglet import figlet_format
from termcolor import colored
from daily import run_daily_claim
from fake_useragent import UserAgent

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

logger.remove()
logger.add(
    sink=sys.stdout,
    format="<r>[Nodepay]</r> | <white>DATE: {time:YYYY-MM-DD}</white> | <white>TIME: {time:HH:mm:ss}</white> | "
           "<level>{level: ^7}</level> | <cyan>{line: <3}</cyan> | {message}",
    colorize=True
)
logger.add("log.txt", rotation="10 MB", level="INFO", encoding="utf-8")
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
        logger.error(f"<red>File '{filename}' not found.</red>")
        return []

def load_proxies():
    return load_file('proxy.txt')

def assign_proxies_to_tokens(tokens, proxies):
    if proxies is None:
        proxies = []
    paired = list(zip(tokens[:len(proxies)], proxies))
    remaining = [(token, None) for token in tokens[len(proxies):]]
    return paired + remaining

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

    try:
        response = requests.post(url, json=data, headers=headers, impersonate="safari15_5", proxies={"http": proxy, "https": proxy}, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if SHOW_REQUEST_ERROR_LOG:
            logger.error(f"Request error during API call to {url}: {e}")
    return None

async def get_account_info(token, proxy=None):
    url = DOMAIN_API["SESSION"]
    try:
        response = await call_api(url, {}, token, proxy)
        if response and response.get("code") == 0:
            return response["data"]
    except Exception as e:
        logger.error(f"<red>Error fetching account info for token {truncate_token(token)}: {e}</red>")
    return None

async def start_ping(token, account_info, proxy=None, ping_interval=60.0, browser_id=None):
    global last_ping_time, status_connect
    browser_id = browser_id or str(uuid.uuid4())
    
    current_time = time.time()
    if proxy:
        last_ping_time[proxy] = current_time

    if not DOMAIN_API["PING"]:
        logger.error("<red>No PING URLs available.</red>")
        return

    url = DOMAIN_API["PING"][0]

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
            logger.info(f"<green>PING SUCCESSFUL</green> | TOKEN: {truncate_token(token)}")
    except Exception as e:
        logger.error(f"<red>Error during pinging via proxy {proxy}: {e}</red>")

async def process_account(token, use_proxy, proxies=None, ping_interval=2.0):
    proxies = proxies or []
    proxy = proxies[0] if proxies else None
    browser_id = str(uuid.uuid4())

    account_info = await get_account_info(token, proxy=proxy)

    if not account_info:
        logger.error(f"<red>Account info not found for token: {truncate_token(token)}</red>")
        return

    await start_ping(token, account_info, proxy, ping_interval, browser_id)

async def main():
    tokens = load_file("token.txt")
    if not tokens:
        return logger.error("<red>No tokens found in 'token.txt'. Exiting.</red>")

    proxies = ask_user_for_proxy()
    token_proxy_pairs = assign_proxies_to_tokens(tokens, proxies)

    logger.info("Processing accounts...")
    
    users_data = await asyncio.gather(*(get_account_info(token) for token in tokens), return_exceptions=True)
    users_data = [data for data in users_data if not isinstance(data, Exception)]

    logger.info("Waiting before starting tasks...")
    await asyncio.sleep(5)

    tasks = [process_account(token, use_proxy=bool(proxy), proxies=[proxy] if proxy else []) for token, proxy in token_proxy_pairs]
    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted. Exiting gracefully...")
