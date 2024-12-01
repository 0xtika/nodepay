import asyncio
import aiohttp
from datetime import datetime
import uuid
import random
import pytz
import cloudscraper
from loguru import logger

# Constants
PING_INTERVAL = 60
RETRIES = 60
TIMEZONE = pytz.timezone("Asia/Jakarta")

DOMAIN_API_ENDPOINTS = {
    "SESSION": [
        "http://api.nodepay.ai/api/auth/session"
    ],
    "PING": [
        "https://nw.nodepay.org/api/network/ping"
    ]
}

def get_random_endpoint(endpoint_type):
    return random.choice(DOMAIN_API_ENDPOINTS[endpoint_type])

def get_endpoint(endpoint_type):
    if endpoint_type not in DOMAIN_API_ENDPOINTS:
        raise ValueError(f"Unknown endpoint type: {endpoint_type}")
    return get_random_endpoint(endpoint_type)

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}

def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

def get_current_time():
    return datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')

async def render_profile_info(token):
    global browser_id, account_info

    try:
        browser_id = uuidv4()
        response = await call_api(get_endpoint("SESSION"), {}, token)
        valid_resp(response)
        account_info = response["data"]
        if account_info.get("uid"):
            await start_ping(token)
        else:
            handle_logout()
    except Exception as e:
        logger.error(f"Error in render_profile_info: {e}")
        return None

async def call_api(url, data, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")

async def start_ping(token):
    try:
        while True:
            await ping(token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info("Ping task was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping: {e}")

async def ping(token):
    global last_ping_time, RETRIES, status_connect

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": get_current_time(),
            "version": "2.2.7"
        }

        response = await call_api(get_endpoint("PING"), data, token)
        if response["code"] == 0:
            logger.info(f"Ping successful at {get_current_time()}: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(response)
    except Exception as e:
        logger.error(f"Ping failed at {get_current_time()}: {e}")
        handle_ping_fail(None)

def handle_ping_fail(response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout()
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout():
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    logger.info(f"Logged out and cleared session info at {get_current_time()}")

async def main():
    try:
        with open('token.txt', 'r') as file:
            token = file.read().strip()
        if not token:
            raise ValueError("Token file is empty.")
    except Exception as e:
        logger.error(f"Error reading token file: {e}")
        return

    logger.info(f"Starting Nodepay Bot at {get_current_time()}...")
    await render_profile_info(token)
    await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info(f"Program terminated by user at {get_current_time()}.")