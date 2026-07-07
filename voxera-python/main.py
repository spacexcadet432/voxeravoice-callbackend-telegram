import sys
import time
import logging
import schedule
from datetime import datetime, timezone

import config
import storage
import retell
import telegram
import formatter

# Configure logging to match the requested output format: [LEVEL] message
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("voxera.main")

# Keep track of call IDs we've already logged as ignored to avoid duplicate logs in every poll cycle
logged_ignored_calls = set()

def print_banner():
    banner = r"""
===================================================
__      __  ____   __   __  ______   _____           
\ \    / / / __ \  \ \ / / |  ____| |  __ \    /\    
 \ \  / / | |  | |  \ V /  | |__    | |__) |  /  \   
  \ \/ /  | |  | |   > <   |  __|   |  _  /  / /\ \  
   \  /   | |__| |  / . \  | |____  | | \ \ / ____ \ 
    \/     \____/  /_/ \_\ |______| |_|  \_/_/    \_\
                                                     
    VOXERA PYTHON AUTOMATION SYSTEM (PRODUCTION)
===================================================
[*] Starting up...
[*] Target timezone: {timezone}
[*] Poll interval: {interval} seconds
[*] Storage file: {storage_file}
===================================================
""".format(
        timezone=config.TIMEZONE,
        interval=config.POLL_INTERVAL_SECONDS,
        storage_file=config.PROCESSED_CALLS_FILE
    )
    print(banner)

def get_call_datetime(call) -> datetime:
    """
    Safely extracts the datetime of the call as a timezone-aware UTC datetime.
    Supports created_at (iso format or ms) and start_timestamp (ms).
    """
    # 1. Try created_at (string ISO or ms timestamp)
    created_at = call.get("created_at")
    if created_at is not None:
        try:
            if isinstance(created_at, (int, float)):
                return datetime.fromtimestamp(created_at / 1000.0, tz=timezone.utc)
            dt = datetime.fromisoformat(str(created_at))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass

    # 2. Try start_timestamp (Retell default, in ms)
    start_ts = call.get("start_timestamp")
    if start_ts is not None:
        try:
            return datetime.fromtimestamp(float(start_ts) / 1000.0, tz=timezone.utc)
        except Exception:
            pass

    # Default to current UTC time if no timestamp is found
    return datetime.now(timezone.utc)

def poll_job():
    """
    Job executed every 30 seconds to fetch, detect, and process new calls.
    """
    logger.info("Polling Retell...")
    
    # Check config validity on every run to help with recovery if config was fixed
    if not config.validate_config():
        logger.warning("Configuration is incomplete. Skipping this poll iteration.")
        return

    try:
        # 1. Fetch latest completed calls
        completed_calls = retell.fetch_latest_calls()
        if not completed_calls:
            logger.info("No calls returned or api failed.")
            return

        # 2. Identify new calls
        new_calls = []
        for call in completed_calls:
            call_id = call.get("call_id")
            if not call_id:
                continue
                
            # Date/time filtering check
            if config.START_FETCH_DATE:
                call_dt = get_call_datetime(call)
                if call_dt < config.START_FETCH_DATE:
                    if call_id not in logged_ignored_calls:
                        logger.info("Ignoring old call from before START_FETCH_DATE")
                        logged_ignored_calls.add(call_id)
                    continue

            # Agent-level filtering check
            if config.TARGET_AGENT_ID:
                agent_id = call.get("agent_id") or call.get("agent") or call.get("agentId") or call.get("agent_name")
                call_agent_clean = str(agent_id).strip() if agent_id is not None else ""
                target_agent_clean = config.TARGET_AGENT_ID.strip()

                if call_agent_clean != target_agent_clean:
                    display_name = agent_id if agent_id else "Unknown Agent"
                    if call_id not in logged_ignored_calls:
                        logger.info(f"Ignoring call from different agent: {display_name}")
                        logged_ignored_calls.add(call_id)
                    continue

            if not storage.is_processed(call_id):
                if config.TARGET_AGENT_ID:
                    logger.info(f"Processing call from target agent ID: {config.TARGET_AGENT_ID}")
                else:
                    logger.info("Processing new eligible call")
                new_calls.append(call)

        # 3. Process new calls (reverse them to process oldest first)
        new_calls_count = len(new_calls)
        logger.info(f"Found {new_calls_count} new call(s)")

        if new_calls_count > 0:
            for call in reversed(new_calls):
                call_id = call.get("call_id")
                
                # Format call summary
                message_text = formatter.format_call_message(call)
                
                # Send to Telegram
                success = telegram.send_telegram_message(message_text)
                if success:
                    storage.save_processed_call(call_id)
                    logger.info("Telegram message sent")
                else:
                    logger.error(f"Failed to send Telegram message for call {call_id}. Will retry in next poll.")

    except Exception as e:
        logger.error(f"Error during polling job: {e}", exc_info=True)

def main():
    print_banner()
    
    # Verify initial config and display warnings if needed
    config.validate_config()
    
    # Initialize the storage file if missing
    storage.load_processed_calls()

    # Run the job immediately on startup to get latest calls
    poll_job()

    # Schedule the job to run every N seconds
    schedule.every(config.POLL_INTERVAL_SECONDS).seconds.do(poll_job)
    
    logger.info(f"Setup complete. Polling loop running. Press Ctrl+C to exit.")

    # Infinite loop that never crashes or exits on exceptions
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down gracefully...")
            break
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}", exc_info=True)
            logger.info(f"Sleeping for 5 seconds before resuming loop...")
            time.sleep(5)

if __name__ == "__main__":
    main()
