import asyncio
import time
import uuid
from datetime import datetime
from curl_cffi import requests
from loguru import logger
from fake_useragent import UserAgent
from colorama import Fore, Style, init
import inquirer  # Thêm thư viện inquirer

# Khởi tạo colorama với autoreset để tự động reset màu sau mỗi print
init(autoreset=True)

# Import hàm show_banner từ banner.py
from utils.banner import show_banner

# Các hằng số
PING_INTERVAL = 60  # Thời gian ping mỗi proxy (giây)
MAX_RETRIES = 5  # Số lần thử lại tối đa khi ping thất bại
TOKEN_FILE = 'token.txt'  # Tệp chứa token
PROXY_FILE = 'proxy.txt'  # Tệp chứa proxy
DOMAIN_API = {
    "SESSION": "https://api.nodepay.org/api/auth/session",
    "PING": "https://nw.nodepay.org/api/network/ping",
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
last_ping_time = {}
proxy_index = 0  # Chỉ số để vòng quay proxy
proxy_browser_ids = {}  # Biến để lưu trữ ID trình duyệt và User-Agent cho mỗi proxy
used_proxies = set()  # Tập hợp các proxy đã được sử dụng

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

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        if len(proxies) < 3:
            raise ValueError("Danh sách proxy phải có ít nhất 3 proxy.")
        return proxies
    except Exception as e:
        logger.error(f"Không thể tải proxy: {e}")
        raise SystemExit("Thoát chương trình do lỗi khi tải proxy")

def dailyclaim(token, proxy_info):
    """
    Hàm thực hiện yêu cầu hàng ngày (daily claim) cho một tài khoản thông qua proxy được chỉ định.
    """
    url = DOMAIN_API["DAILY_CLAIM"]
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": proxy_info.get('user_agent', "Mozilla/5.0"),
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
            proxies=parse_proxy(proxy_info['proxy']),
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

def parse_proxy(proxy_str):
    """
    Hàm phân tích định dạng proxy và trả về một dictionary phù hợp với curl_cffi.
    """
    if '://' not in proxy_str:
        proxy_str = f'http://{proxy_str}'
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_str)
        
        proxy_dict = {
            'http': proxy_str,
            'https': proxy_str
        }
        
        if parsed.scheme in ['socks4', 'socks5']:
            proxy_dict['http'] = proxy_str
            proxy_dict['https'] = proxy_str
        
        return proxy_dict
    except Exception as e:
        log_message(f"Định dạng proxy không hợp lệ: {proxy_str}. Lỗi: {e}", Fore.RED)
        return None

def is_valid_proxy(proxy):
    return parse_proxy(proxy) is not None

def load_session_info(proxy):
    # Tải thông tin session từ proxy (nếu cần)
    return {}

def save_session_info(proxy, data):
    # Lưu thông tin session vào proxy (nếu cần)
    pass

def save_status(proxy, status):
    # Lưu trạng thái kết nối của proxy (nếu cần)
    pass

def handle_logout(proxy):
    global status_connect, account_info
    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    save_status(proxy, None)
    log_message(f"Đã đăng xuất và xóa thông tin session cho proxy {proxy}", Fore.RED)

def remove_proxy_from_list(proxy):
    global all_proxies
    # Hàm loại bỏ proxy khỏi danh sách (nếu cần)
    try:
        all_proxies.remove(proxy)
        log_message(f"Đã loại bỏ proxy: {proxy}", Fore.YELLOW)
    except ValueError:
        log_message(f"Proxy {proxy} không tồn tại trong danh sách.", Fore.YELLOW)

async def get_real_ip(proxy):
    parsed_proxies = parse_proxy(proxy)
    if not parsed_proxies:
        return "N/A"
    
    try:
        response = requests.get(
            "https://api64.ipify.org/", 
            proxies=parsed_proxies,
            timeout=10
        )
        return response.text.strip()
    except Exception as e:
        log_message(f"Không thể lấy IP thực qua proxy {proxy}: {e}", Fore.RED)
        return "N/A"

async def call_api(url, data, proxy_info, token):
    parsed_proxies = parse_proxy(proxy_info['proxy'])
    if not parsed_proxies:
        raise ValueError(f"Proxy không hợp lệ: {proxy_info['proxy']}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": proxy_info.get('user_agent', "Mozilla/5.0"),
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
            proxies=parsed_proxies,
            timeout=30,
            impersonate="safari15_5"
        )

        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        log_message(f"Lỗi khi gọi API tới {url} qua proxy {proxy_info['proxy']}: {e}", Fore.RED)
        raise ValueError(f"Gọi API tới {url} thất bại")

async def ping(proxy_info, token):
    global last_ping_time, RETRIES, status_connect

    proxy = proxy_info['proxy']
    current_time = time.time()

    if proxy in last_ping_time and (current_time - last_ping_time[proxy]) < PING_INTERVAL:
        log_message(f"Bỏ qua ping cho proxy {proxy}, chưa đủ thời gian đã trôi qua", Fore.YELLOW)
        return

    last_ping_time[proxy] = current_time

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": proxy_browser_ids.get(proxy, {}).get('browser_id', uuidv4()),
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        response = await call_api(DOMAIN_API["PING"], data, proxy_info, token)
        if response["code"] == 0:
            ip_score = response.get('data', {}).get('ip_score', 'N/A')
            real_ip = await get_real_ip(proxy)
            # Căn lề và thêm màu sắc cho từng phần chi tiết
            log_message(
                f"Tài khoản: {Fore.LIGHTGREEN_EX}{account_info.get('email', 'N/A'):<25}{Style.RESET_ALL} | " + 
                f"ID Trình duyệt: {Fore.LIGHTMAGENTA_EX}{proxy_browser_ids.get(proxy, {}).get('browser_id', 'N/A'):<36}{Style.RESET_ALL} | " +
                f"IP: {Fore.LIGHTYELLOW_EX}{real_ip:<15}{Style.RESET_ALL} | " + 
                f"Điểm IP: {Fore.LIGHTRED_EX}{ip_score:<5}{Style.RESET_ALL}", 
                Fore.CYAN
            )
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response)
    except Exception as e:
        log_message(f"Ping thất bại qua proxy {proxy}: {e}", Fore.RED)
        handle_ping_fail(proxy, None)

def handle_ping_fail(proxy, response):
    global RETRIES

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout(proxy)
    if RETRIES >= MAX_RETRIES:
        log_message(f"Ping thất bại quá nhiều lần cho proxy {proxy}. Đang loại bỏ proxy này.", Fore.RED)
        remove_proxy_from_list(proxy)
        RETRIES = 0
    else:
        log_message(f"Ping thất bại cho proxy {proxy}. Số lần thử lại: {RETRIES}", Fore.RED)

async def start_ping(proxy_info, token):
    try:
        await ping(proxy_info, token)
    except asyncio.CancelledError:
        log_message(f"Nhiệm vụ ping cho proxy {proxy_info['proxy']} đã bị hủy", Fore.YELLOW)
    except Exception as e:
        log_message(f"Lỗi trong start_ping cho proxy {proxy_info['proxy']}: {e}", Fore.RED)

async def render_profile_info(proxy_info, token):
    global account_info, proxy_browser_ids

    try:
        proxy = proxy_info['proxy']
        if proxy not in proxy_browser_ids:
            if ua:
                user_agent = ua.random
            else:
                user_agent = "Mozilla/5.0"
            proxy_browser_ids[proxy] = {
                'browser_id': uuidv4(),
                'user_agent': user_agent
            }

        np_session_info = load_session_info(proxy)

        if not np_session_info:
            response = await call_api(DOMAIN_API["SESSION"], {}, proxy_info, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(proxy, account_info)
                # Thực hiện daily claim sau khi thiết lập session
                log_message("Đang thực hiện yêu cầu hàng ngày...", Fore.YELLOW)
                dailyclaim(token, proxy_info)
                await start_ping(proxy_info, token)
            else:
                handle_logout(proxy)
        else:
            account_info = np_session_info
            # Thực hiện daily claim sau khi thiết lập session
            log_message("Đang thực hiện yêu cầu hàng ngày...", Fore.YELLOW)
            dailyclaim(token, proxy_info)
            await start_ping(proxy_info, token)
    except Exception as e:
        log_message(f"Lỗi trong render_profile_info cho proxy {proxy}: {e}", Fore.RED)
        error_message = str(e)
        if any(phrase in error_message for phrase in [
            "sent 1011 (internal error) keepalive ping timeout; no close frame received",
            "500 Internal Server Error"
        ]):
            log_message(f"Loại bỏ proxy lỗi khỏi danh sách: {proxy}", Fore.RED)
            remove_proxy_from_list(proxy)
            return None
        else:
            log_message(f"Lỗi kết nối: {e}", Fore.RED)
            return proxy_info

async def multi_account_mode(all_tokens, all_proxies, proxies_per_account=3):
    valid_proxies = [proxy for proxy in all_proxies if is_valid_proxy(proxy)]
    available_proxies = valid_proxies.copy()  # Danh sách proxy có thể sử dụng
    token_tasks = []

    for index, token in enumerate(all_tokens, 1):
        token_proxies = []
        for _ in range(proxies_per_account):
            if available_proxies:
                proxy = available_proxies.pop(0)
                token_proxies.append({'proxy': proxy})
                used_proxies.add(proxy)
            else:
                break  # Không còn proxy nào để phân phối

        if not token_proxies:
            log_message(f"Không có proxy nào cho Token {index}", Fore.YELLOW)
            continue

        proxy_list = [proxy_info['proxy'] for proxy_info in token_proxies]
        log_message(f"Token {index} với Proxies: {proxy_list}", Fore.BLUE)
        
        task = asyncio.create_task(process_token(token, token_proxies, all_proxies, available_proxies, proxies_per_account))
        token_tasks.append(task)
    
    if token_tasks:
        await asyncio.gather(*token_tasks)

async def process_token(token, proxies, all_proxies, available_proxies, proxies_per_account):
    tasks = {asyncio.create_task(render_profile_info(proxy_info, token)): proxy_info['proxy'] for proxy_info in proxies}

    while tasks:
        done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            failed_proxy = tasks[task]
            try:
                result = task.result()
            except Exception as e:
                log_message(f"Lỗi task cho proxy {failed_proxy}: {e}", Fore.RED)
                result = None

            if result is None:
                log_message(f"Đang loại bỏ proxy lỗi: {failed_proxy}", Fore.YELLOW)
                proxies = [p for p in proxies if p['proxy'] != failed_proxy]
                used_proxies.discard(failed_proxy)

                # Thêm proxy mới chưa được chọn vào danh sách
                available_new_proxies = [p for p in all_proxies if p not in [proxy['proxy'] for proxy in proxies] and p not in used_proxies and is_valid_proxy(p)]
                if available_new_proxies:
                    new_proxy = available_new_proxies.pop(0)
                    proxies.append({'proxy': new_proxy})
                    used_proxies.add(new_proxy)
                    new_task = asyncio.create_task(render_profile_info({'proxy': new_proxy}, token))
                    tasks[new_task] = new_proxy
                    log_message(f"Đã thay thế bằng proxy mới: {new_proxy}", Fore.GREEN)
                else:
                    log_message("Không còn proxy nào để thay thế. Tiếp tục với các proxy live.", Fore.YELLOW)
            tasks.pop(task)

        for proxy in set([proxy_info['proxy'] for proxy_info in proxies]) - set(tasks.values()):
            new_task = asyncio.create_task(render_profile_info({'proxy': proxy}, token))
            tasks[new_task] = proxy
        
        await asyncio.sleep(3)
    
    await asyncio.sleep(10)

async def single_account_mode(token, all_proxies, proxies_per_account=3):
    active_proxies = [
        {'proxy': proxy} for proxy in all_proxies if is_valid_proxy(proxy)][:proxies_per_account]
    used_proxies.update([proxy_info['proxy'] for proxy_info in active_proxies])
    tasks = {asyncio.create_task(render_profile_info(proxy_info, token)): proxy_info['proxy'] for proxy_info in active_proxies}

    while tasks:
        done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            failed_proxy = tasks[task]
            try:
                result = task.result()
            except Exception as e:
                log_message(f"Lỗi task cho proxy {failed_proxy}: {e}", Fore.RED)
                result = None

            if result is None:
                log_message(f"Đang loại bỏ proxy lỗi: {failed_proxy}", Fore.YELLOW)
                active_proxies = [p for p in active_proxies if p['proxy'] != failed_proxy]
                used_proxies.discard(failed_proxy)

                # Thêm proxy mới chưa được chọn vào danh sách
                available_proxies = [p for p in all_proxies if p not in [proxy_info['proxy'] for proxy_info in active_proxies] and p not in used_proxies and is_valid_proxy(p)]
                if available_proxies:
                    new_proxy = available_proxies.pop(0)
                    active_proxies.append({'proxy': new_proxy})
                    used_proxies.add(new_proxy)
                    new_task = asyncio.create_task(render_profile_info({'proxy': new_proxy}, token))
                    tasks[new_task] = new_proxy
                    log_message(f"Đã thay thế bằng proxy mới: {new_proxy}", Fore.GREEN)
                else:
                    log_message("Không còn proxy nào để thay thế. Tiếp tục với các proxy live.", Fore.YELLOW)
            tasks.pop(task)

        for proxy_info in active_proxies:
            proxy = proxy_info['proxy']
            if proxy not in tasks.values():
                new_task = asyncio.create_task(render_profile_info(proxy_info, token))
                tasks[new_task] = proxy
        await asyncio.sleep(3)
    await asyncio.sleep(10)

async def main():
    # Hiển thị logo từ banner.py
    show_banner()

    log_message("ĐANG CHẠY VỚI PROXIES", Fore.WHITE)
    
    # Sử dụng inquirer để tạo menu
    questions = [
        inquirer.List(
            'mode',
            message="Chọn Chế Độ",
            choices=['1. Chạy duy nhất 1 tài khoản', '2. Chạy nhiều tài khoản'],
        )
    ]
    answers = inquirer.prompt(questions)
    mode_choice = answers['mode'] if answers else '1. Chạy duy nhất 1 tài khoản'
    
    all_proxies = load_proxies(PROXY_FILE)
    tokens = load_tokens_from_file(TOKEN_FILE)

    if mode_choice.startswith('1'):
        # Chạy duy nhất 1 tài khoản
        log_message("Chọn Chế Độ: Chạy duy nhất 1 tài khoản", Fore.BLUE)
        token = input(Fore.LIGHTYELLOW_EX + "Nhập Token Nodepay: ").strip()
        if not token:
            log_message("Token không thể để trống. Thoát chương trình.", Fore.RED)
            exit()
        
        # Phân bổ 3 proxy cho tài khoản đơn
        token_proxies = []
        global proxy_index
        for _ in range(3):
            if proxy_index >= len(all_proxies):
                proxy_index = 0  # Quay lại đầu danh sách nếu hết proxy
            proxy = all_proxies[proxy_index]
            if is_valid_proxy(proxy):
                token_proxies.append({'proxy': proxy})
                used_proxies.add(proxy)
            proxy_index += 1

        if len(token_proxies) < 3:
            log_message("Không đủ proxy để phân bổ cho tài khoản đơn. Thoát chương trình.", Fore.RED)
            exit()

        log_message(f"Token duy nhất được phân bổ với Proxies: {[p['proxy'] for p in token_proxies]}", Fore.BLUE)
        
        # Thực hiện daily claim cho tài khoản đơn với proxy đầu tiên
        log_message("Đang thực hiện yêu cầu hàng ngày...", Fore.YELLOW)
        dailyclaim(token, token_proxies[0])
        
        # Khởi chạy ping cho tất cả các proxy của tài khoản
        await single_account_mode(token, all_proxies)
    
    elif mode_choice.startswith('2'):
        # Chạy nhiều tài khoản
        log_message("Chọn Chế Độ: Chạy nhiều tài khoản", Fore.BLUE)
        if not tokens:
            log_message("Không tìm thấy token nào trong token.txt", Fore.RED)
            exit()
        
        # Phân bổ 3 proxy cho mỗi tài khoản
        tokens_proxies = {}
        num_proxies = len(all_proxies)
        for token in tokens:
            token_proxies = []
            for _ in range(3):
                if proxy_index >= num_proxies:
                    proxy_index = 0  # Quay lại đầu danh sách nếu hết proxy
                proxy = all_proxies[proxy_index]
                if is_valid_proxy(proxy):
                    token_proxies.append({'proxy': proxy})
                    used_proxies.add(proxy)
                proxy_index += 1
            tokens_proxies[token] = token_proxies

        # Thực hiện daily claim cho từng tài khoản với proxy đầu tiên
        for token, proxies in tokens_proxies.items():
            log_message(f"Đang thực hiện yêu cầu hàng ngày cho Token: {Fore.LIGHTGREEN_EX}{token:<25}{Style.RESET_ALL}...", Fore.YELLOW)
            dailyclaim(token, proxies[0])
        
        await multi_account_mode(tokens, all_proxies)
    
    else:
        log_message("Lựa chọn không hợp lệ. Thoát chương trình.", Fore.RED)
        exit()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log_message("Chương trình đã bị người dùng dừng lại.", Fore.RED)
