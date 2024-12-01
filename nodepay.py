import asyncio
import cloudscraper
import json
import time
from loguru import logger
import requests
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, init, Style
import sys


init(autoreset=True, strip=False)


logger.remove()
logger.add(
    sys.stderr,
    format="<level>{level: <8}</level> | {time:YYYY-MM-DD HH:mm} | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
    colorize=True
)

PING_INTERVAL = 5
RETRIES = 60

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    
    "PING": [
        "http://18.142.29.174/api/network/ping",
        "https://nw.nodepay.org/api/network/ping"
        
    
    ]
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

def load_proxies():
    try:
        with open('proxy.txt', 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

BASE_PROXY = load_proxies()[0]


class AccountInfo:
    def __init__(self, token):
        self.token = token
        self.proxies = [BASE_PROXY] * 3
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
        self.account_data = {}
        self.retries = 0
        self.last_ping_status = 'Waiting...'
        self.browser_id = {
            'ping_count': 0,
            'successful_pings': 0,
            'score': 0,
            'start_time': time.time(),
            'last_ping_time': None
        }

    def reset(self):
        self.status_connect = CONNECTION_STATES["NONE_CONNECTION"]
        self.account_data = {}
        self.retries = 3


scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)


async def load_tokens():
    try:
        with open('token.txt', 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")


async def call_api(url, data, account_info, proxy):
    headers = {
        "Authorization": f"Bearer {account_info.token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://app.nodepay.ai/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cors-site"
    }

    proxy_config = {
        "http": proxy,
        "https": proxy
    }

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=30) as executor:
        try:
            response = await loop.run_in_executor(
                executor,
                lambda: scraper.post(url, json=data, headers=headers, proxies=proxy_config, timeout=30)
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error during API call for token {account_info.token} with proxy {proxy}: {e}")
            raise ValueError(f"Failed API call to {url}")

    return response.json()


async def render_profile_info(account_info):
    try:
        for proxy in account_info.proxies:
            try:
                response = await call_api(DOMAIN_API["SESSION"], {}, account_info, proxy)
                if response.get("code") == 0:
                    account_info.account_data = response["data"]
                    if account_info.account_data.get("uid"):
                        await start_ping(account_info)
                        return
                else:
                    logger.warning(f"Session failed for token {account_info.token} using proxy {proxy}")
            except Exception as e:
                logger.error(f"Failed to render profile info for token {account_info.token} using proxy {proxy}: {e}")

        logger.error(f"All proxies failed for token {account_info.token}")
    except Exception as e:
        logger.error(f"Error in render_profile_info for token {account_info.token}: {e}")


async def start_ping(account_info):
    try:
        logger.info(f"Starting ping for token {account_info.token}")
        url_index = 0
        while True:
            for proxy in account_info.proxies:
                try:
                    await asyncio.sleep(PING_INTERVAL)
                    await ping(account_info, proxy, url_index)
                    url_index = (url_index + 1) % len(DOMAIN_API["PING"])
                except Exception as e:
                    logger.error(f"Ping failed for token {account_info.token} using proxy {proxy}: {e}")
    except asyncio.CancelledError:
        logger.info(f"Ping task for token {account_info.token} was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping for token {account_info.token}: {e}")


async def ping(account_info, proxy, url_index):
    url = DOMAIN_API["PING"][url_index]
    try:
        data = {
            "id": account_info.account_data.get("uid"),
            "browser_id": account_info.browser_id,
            "timestamp": int(time.time())
        }
        response = await call_api(url, data, account_info, proxy)
        if response["code"] == 0:
            if '@' in proxy:
                proxy_ip = proxy.split('@')[-1].split(':')[0]
            else:
                proxy_ip = proxy.split('://')[-1].split(':')[0]
            logger.info(f"{Fore.GREEN}Ping successful for token using proxy IP {proxy_ip}{Style.RESET_ALL}")
            
            account_info.browser_id['successful_pings'] += 1
            if account_info.browser_id['successful_pings'] == 3:
                logger.info(f"{Fore.YELLOW}Switching account for token {account_info.token}{Style.RESET_ALL}")
                return
            
            return
    except Exception as e:
        if '@' in proxy:
            proxy_ip = proxy.split('@')[-1].split(':')[0]
        else:
            proxy_ip = proxy.split('://')[-1].split(':')[0]
        logger.error(f"Ping failed for token {account_info.token} using URL {url} and proxy IP {proxy_ip}: {e}")


async def process_account(token):
    """
    Process a single account: Initialize proxies and start asyncio event loop for this account.
    """
    account_info = AccountInfo(token)
    await render_profile_info(account_info)


async def process_account_threaded(token):
    """
    Wrapper function to run process_account in a thread.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, asyncio.run, process_account(token))


async def main():
    tokens = await load_tokens()

    # Use ThreadPoolExecutor to run account processes in separate threads
    global executor
    executor = ThreadPoolExecutor(max_workers=20)

    # Use asyncio.gather to run all account processes concurrently
    await asyncio.gather(*(process_account_threaded(token) for token in tokens))

    # Shutdown the executor
    executor.shutdown(wait=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
