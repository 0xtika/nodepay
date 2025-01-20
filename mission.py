from loguru import logger
from curl_cffi import requests
import time
import sys

logger.remove()
logger.add(
    sink=sys.stdout,
    format="<r>[Nodepay]</r> | <white>DATE: {time:YYYY-MM-DD}</white> | <white>TIME: {time:HH:mm:ss}</white> |"
           "<level>{level: ^7}</level> | <cyan>{line: <3}</cyan> | {message}",
    colorize=True
)
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

def post_survey_challenge5(token):
    url = "https://api.nodepay.org/api/mission/survey/qna-challenge-3"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://app.nodepay.ai",
        "Referer": "https://app.nodepay.ai/",
        "Accept": "*/*",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
    }
    data = {
        "search_tool": ["X", "DISCORD", "TELEGRAM"],
        "verification_frequency": "A_FEW_TIMES_PER_WEEK",
        "research_type": "NEWS_AND_UPDATES",
        "search_frustration": "HARD_TO_VERIFY_CURRENCY",
        "real_time_importance": "EXTREMELY_IMPORTANT",
        "switch_feature": ["TOKEN_UNLOCK_ALERTS", "SMART_CONTRACT_VERIFICATION", "SCAM_CHECK"],
        "verification_step": "check the smart contract and project info",
        "time_sensitive_info": ["TEAM_UPDATES", "PRICE_MOVEMENTS", "COMMUNITY_SENTIMENT"],
        "result_format": "DETAILED_ANALYSIS",
        "ideal_search_tool": "More detailed about team info and project"
    }

    try:
        response = requests.post(url, headers=headers, json=data, impersonate="safari15_5")

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                logger.success(f"Token: {truncate_token(token)} | Survey challenge completed successfully | Request Status: {response.status_code} ")
            else:
                logger.info(f"Token: {truncate_token(token)} | Survey challenge already completed or issue occurred | Request Status: {response.status_code}")
        else:
            logger.error(f"Token: {truncate_token(token)} | Request Status: {response.status_code} | Response: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.exception(f"Token: {truncate_token(token)} | Request error: {e}")

def claim_mission(token):
    url = "https://api.nodepay.org/api/mission/complete-mission"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://app.nodepay.ai",
        "Referer": "https://app.nodepay.ai/",
        "Accept": "*/*",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
    }
    data = {
        "mission_id":"25",
    }

    try:
        response = requests.post(url, headers=headers, json=data, impersonate="safari15_5")

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                logger.success(f"Token: {truncate_token(token)} | Claim Mission successfully | Request Status: {response.status_code} ")
            else:
                logger.info(f"Token: {truncate_token(token)} | Claim mission already completed or issue occurred | Request Status: {response.status_code}")
        else:
            logger.error(f"Token: {truncate_token(token)} | Request Status: {response.status_code} | Response: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.exception(f"Token: {truncate_token(token)} | Request error: {e}")

def run_mission():
    try:
        with open('token.txt', 'r') as file:
            tokens = file.read().splitlines()

        for token in tokens:
            claim_mission(token)

        # Send a final message after all operations are done
        logger.success(f"All tokens processed")

    except FileNotFoundError:
        logger.error(f"The file 'token.txt' was not found. Please make sure it exists.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_mission()
