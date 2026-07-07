import time
import logging
import requests
from typing import List, Dict, Any
import config

logger = logging.getLogger("voxera.retell")

def fetch_latest_calls() -> List[Dict[str, Any]]:
    """
    Fetches the latest 20 calls from Retell AI API.
    Retries once on failure, includes timeout protection, and filters for completed calls.
    
    Returns:
        List of completed call objects.
    """
    if not config.RETELL_API_KEY:
        logger.error("RETELL_API_KEY is not set. Cannot fetch calls.")
        return []

    url = "https://api.retellai.com/v2/list-calls"
    headers = {
        "Authorization": f"Bearer {config.RETELL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "limit": 20,
        "sort_order": "descending"
    }

    # Retry once on failure (up to 2 attempts)
    for attempt in range(1, 3):
        try:
            logger.info(f"Polling Retell (attempt {attempt}/2)...")
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            data = response.json()
            
            # Retrieve calls array from response
            if isinstance(data, list):
                calls = data
            elif isinstance(data, dict) and "items" in data:
                calls = data["items"]
            elif isinstance(data, dict):
                # Fallback in case the schema changes
                calls = data.get("calls", [])
            else:
                calls = []

            # Filter for completed calls: status is ended, error, or not_connected
            completed_calls = []
            for call in calls:
                status = call.get("call_status")
                # Retell statuses for completed calls are usually ended, error, not_connected
                if status in ["ended", "error", "not_connected"]:
                    completed_calls.append(call)
            
            logger.info(f"Successfully fetched {len(calls)} calls. Filtered to {len(completed_calls)} completed calls.")
            return completed_calls

        except requests.exceptions.RequestException as e:
            logger.warning(f"Retell API request error on attempt {attempt}: {e}")
            if attempt < 2:
                time.sleep(2)  # Wait 2 seconds before retry
            else:
                logger.error("Retell API polling failed after maximum retries.")
                return []
        except Exception as e:
            logger.error(f"Unexpected error fetching calls from Retell: {e}")
            return []

    return []
