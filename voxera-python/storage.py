import json
import logging
from typing import Set
import config

logger = logging.getLogger("voxera.storage")


def load_processed_calls() -> Set[str]:
    """
    Loads the set of processed call IDs from the storage file.
    Recovers gracefully from errors like missing files, empty files, or corrupted JSON.
    """
    if not config.PROCESSED_CALLS_FILE.exists():
        # Auto-create file with empty list if it doesn't exist
        save_processed_calls([])
        return set()

    try:
        with open(config.PROCESSED_CALLS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return set()
            data = json.loads(content)
            if isinstance(data, list):
                return set(data)
            else:
                logger.warning("Storage file format is invalid (not a list). Reinitializing empty storage.")
                return set()
    except json.JSONDecodeError as e:
        logger.warning(f"Storage file corrupted ({e}). Reinitializing empty storage.")
        # Attempt to backup the corrupted file and recreate a fresh one
        try:
            backup_path = config.PROCESSED_CALLS_FILE.with_suffix(".json.corrupted")
            if config.PROCESSED_CALLS_FILE.exists():
                config.PROCESSED_CALLS_FILE.replace(backup_path)
                logger.info(f"Backed up corrupted storage to {backup_path}")
        except Exception as rename_err:
            logger.error(f"Failed to backup corrupted storage: {rename_err}")
        
        save_processed_calls([])
        return set()
    except Exception as e:
        logger.error(f"Error reading processed calls storage: {e}")
        return set()

def save_processed_calls(call_ids: list) -> None:
    """
    Saves the list of processed call IDs to the storage file.
    """
    try:
        # Write to a temp file and rename (atomic replace) for robustness
        temp_file = config.PROCESSED_CALLS_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(list(call_ids), f, indent=2)
        temp_file.replace(config.PROCESSED_CALLS_FILE)
    except Exception as e:
        logger.error(f"Error saving processed calls storage: {e}")

def save_processed_call(call_id: str) -> None:
    """
    Adds a single call ID to the stored list.
    """
    if not call_id:
        return
    call_ids = load_processed_calls()
    if call_id not in call_ids:
        call_ids.add(call_id)
        save_processed_calls(list(call_ids))

def is_processed(call_id: str) -> bool:
    """
    Checks if a call ID has already been processed.
    """
    if not call_id:
        return False
    return call_id in load_processed_calls()
