import time
import logging
import requests
from typing import List
import config

logger = logging.getLogger("voxera.telegram")

def chunk_message(text: str, limit: int = 4000) -> List[str]:
    """
    Chunks a long message into multiple parts to avoid exceeding Telegram's 4096 character limit.
    Splits at newlines or spaces if possible to preserve words/lines.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining_text = text
    
    while len(remaining_text) > limit:
        # Find a clean split point (newline or space) near the limit
        split_idx = remaining_text.rfind('\n', 0, limit)
        if split_idx == -1:
            split_idx = remaining_text.rfind(' ', 0, limit)
        if split_idx == -1:
            split_idx = limit
            
        chunks.append(remaining_text[:split_idx])
        remaining_text = remaining_text[split_idx:].lstrip()
        
    if remaining_text:
        chunks.append(remaining_text)
        
    return chunks

def send_telegram_message(text: str) -> bool:
    """
    Sends a message to the configured Telegram chat.
    Chunks the message if it is too long, and retries once on failure.
    
    Returns:
        bool: True if all chunks were successfully sent, False otherwise.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = chunk_message(text)
    all_success = True

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": chunk
        }
        
        chunk_success = False
        # Retry once on failure
        for attempt in range(1, 3):
            try:
                # Add part info if chunked
                if len(chunks) > 1:
                    logger.info(f"Sending message chunk {i+1}/{len(chunks)} (attempt {attempt}/2)...")
                else:
                    logger.info(f"Sending Telegram message (attempt {attempt}/2)...")
                
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                
                res_data = response.json()
                if res_data.get("ok"):
                    chunk_success = True
                    break
                else:
                    logger.warning(f"Telegram API responded with error on attempt {attempt}: {res_data}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Telegram API request failure on attempt {attempt}: {e}")
                if attempt < 2:
                    time.sleep(2)  # Wait 2 seconds before retry
            except Exception as e:
                logger.error(f"Unexpected error sending Telegram message on attempt {attempt}: {e}")
                if attempt < 2:
                    time.sleep(2)
        
        if not chunk_success:
            logger.error(f"Failed to send message chunk {i+1} after all attempts.")
            all_success = False
            
    return all_success
