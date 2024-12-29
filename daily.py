from loguru import logger
from curl_cffi import requests
import time

logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=''),
    format=(
        "<green>{time:DD/MM/YY HH:mm:ss}</green> | "
        "<level>{level:8} | {message}</level>"
    ),
    colorize=True
)

# Read Tokens and Proxy count
def read_tokens():
    with open('token.txt', 'r') as file:
        tokens_content = sum(1 for line in file)
    return tokens_content

tokens_content = read_tokens()

# Print the token count
print()
print(f"🔑 Account Found: {tokens_content}.")
print()

def truncate_token(token):
    return f"{token[:4]}--{token[-4:]}"

# Function to claim reward using the provided token
def claim_reward(token):
    url = "https://api.nodepay.org/api/mission/complete-mission"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://app.nodepay.ai",
        "Referer": "https://app.nodepay.ai/"
    }
    data = {"mission_id": "1"}

    while True:
        try:
            response = requests.post(url, headers=headers, json=data, impersonate="chrome110")

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('success'):
                    logger.success(f"Token: {truncate_token(token)} | Reward claimed successfully")
                else:
                    logger.info(f"Token: {truncate_token(token)} | Reward already claimed or another issue occurred")
                break  # Exit loop if successful
            elif response.status_code == 403:
                logger.warning(f"Token: {truncate_token(token)} | Received HTTP 403. Retrying in 5 minutes...")
                time.sleep(300)  # Wait for 5 minutes before retrying
            else:
                logger.error(f"Token: {truncate_token(token)} | Failed request, HTTP Status: {response.status_code}")
                break
        except requests.exceptions.RequestException as e:
            logger.exception(f"Token: {truncate_token(token)} | Request error: {e}")
            break

def run_daily_claim():
    try:
        with open('token.txt', 'r') as file:
            tokens = file.read().splitlines()

        for token in tokens:
            claim_reward(token)

        # Send a final message after all operations are done
        logger.success(f"All tokens processed. Daily claim operation completed.")

    except FileNotFoundError:
        logger.error(f"The file 'token.txt' was not found. Please make sure it exists.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_daily_claim()
