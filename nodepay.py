import asyncio
import time
import uuid
from datetime import datetime
from curl_cffi import requests
from loguru import logger
from fake_useragent import UserAgent
from colorama import Fore, Style, init

# Khởi tạo colorama với autoreset để tự động reset màu sau mỗi print
init(autoreset=True)

# Các hằng số
PING_INTERVAL = 60  # Thời gian ping mỗi proxy (giây)
MAX_RETRIES = 5  # Số lần thử lại tối đa khi ping thất bại
TOKEN_FILE = 'token.txt'  # Tệp chứa token
DOMAIN_API = {
    "SESSION": "https://api.nodepay.org/api/auth/session",
    "PING": "https://nw.nodepay.org/api/network/ping",  # Menambahkan endpoint PING
    "DAILY_CLAIM": "https://api.nodepay.org/api/mission/complete-mission"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

# Biến toàn cục
status_connect = CONNECTION_STATES["NONE_CONNECTION"]
account_info = {}

# Khởi tạo UserAgent một lần để tái sử dụng
try:
    ua = UserAgent()
except Exception as e:
    logger.error(f"Lỗi khi khởi tạo UserAgent: {e}")
    ua = None  # Nếu không thể khởi tạo, sẽ sử dụng User-Agent mặc định

def uuidv4():
    return str(uuid.uuid4())

def log_message(message, color=Fore.WHITE):
    """
    Hàm để in thông báo log với màu sắc và định dạng căn lề.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(color + f"[{timestamp}] {message}" + Style.RESET_ALL)

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Phản hồi không hợp lệ")
    return resp

def load_tokens_from_file(filename):
    try:
        with open(filename, 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        logger.error(f"Không thể tải token: {e}")
        raise SystemExit("Thoát chương trình do lỗi khi tải token")

def dailyclaim(token):
    """
    Hàm thực hiện yêu cầu hàng ngày (daily claim) cho một tài khoản.
    """
    url = DOMAIN_API["DAILY_CLAIM"]
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": ua.random if ua else "Mozilla/5.0",
        "Content-Type": "application/json",
        "Origin": "https://app.nodepay.ai",
        "Referer": "https://app.nodepay.ai/",
        "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site"
    }
    data = {
        "mission_id": "1"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=15
        )
        if response.status_code != 200:
            log_message("Yêu cầu hàng ngày THẤT BẠI, có thể đã được yêu cầu trước đó?", Fore.RED)
            return False

        response_json = response.json()
        if response_json.get("success"):
            log_message("Yêu cầu hàng ngày THÀNH CÔNG", Fore.GREEN)
            return True
        else:
            log_message("Yêu cầu hàng ngày THẤT BẠI, có thể đã được yêu cầu trước đó?", Fore.RED)
            return False
    except Exception as e:
        log_message(f"Lỗi trong yêu cầu hàng ngày: {e}", Fore.RED)
        return False

async def call_api(url, data, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": ua.random if ua else "Mozilla/5.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site"
    }

    try:
        response = requests.post(
            url, 
            json=data, 
            headers=headers,
            timeout=30
        )

        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        log_message(f"Lỗi khi gọi API tới {url}: {e}", Fore.RED)
        raise ValueError(f"Gọi API tới {url} thất bại")

async def ping(token):
    global status_connect

    try:
        data = {
            "id": account_info.get("uid"),
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        response = await call_api(DOMAIN_API["PING"], data, token)  # Endpoint PING ditambahkan
        if response["code"] == 0:
            status_connect = CONNECTION_STATES["CONNECTED"]
            log_message("Kết nối thành công!", Fore.GREEN)
        else:
            status_connect = CONNECTION_STATES["DISCONNECTED"]
            log_message("Kết nối thất bại.", Fore.RED)
    except Exception as e:
        log_message(f"Ping thất bại: {e}", Fore.RED)

async def start_ping(token):
    try:
        await ping(token)
    except asyncio.CancelledError:
        log_message(f"Nhiệm vụ ping đã bị hủy", Fore.YELLOW)
    except Exception as e:
        log_message(f"Lỗi trong start_ping: {e}", Fore.RED)

async def render_profile_info(token):
    global account_info

    try:
        response = await call_api(DOMAIN_API["SESSION"], {}, token)
        valid_resp(response)
        account_info = response["data"]
        if account_info.get("uid"):
            log_message("Đang thực hiện yêu cầu hàng ngày...", Fore.YELLOW)
            dailyclaim(token)
            await start_ping(token)
        else:
            log_message("Lỗi khi lấy thông tin tài khoản.", Fore.RED)
    except Exception as e:
        log_message(f"Lỗi trong render_profile_info: {e}", Fore.RED)

async def multi_account_mode(all_tokens):
    token_tasks = []

    for token in all_tokens:
        task = asyncio.create_task(render_profile_info(token))
        token_tasks.append(task)

    await asyncio.gather(*token_tasks)

def main():
    tokens = load_tokens_from_file(TOKEN_FILE)
    asyncio.run(multi_account_mode(tokens))

if __name__ == "__main__":
    main()
