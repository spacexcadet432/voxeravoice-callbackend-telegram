import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any
from config import TIMEZONE

logger = logging.getLogger("voxera.formatter")

def format_call_timestamp(start_timestamp_ms: Any) -> str:
    """
    Formats the Retell start_timestamp (in ms) into exactly:
    '22 May 2026 • 4:43 PM IST'
    """
    try:
        tz = ZoneInfo(TIMEZONE)
    except Exception as e:
        logger.warning(f"Invalid timezone configuration '{TIMEZONE}': {e}. Falling back to UTC.")
        tz = ZoneInfo("UTC")

    if not start_timestamp_ms:
        # Fallback to current time if start_timestamp is missing
        dt = datetime.now(tz=tz)
    else:
        try:
            dt = datetime.fromtimestamp(start_timestamp_ms / 1000.0, tz=tz)
        except Exception as e:
            logger.error(f"Error parsing timestamp {start_timestamp_ms}: {e}")
            dt = datetime.now(tz=tz)

    day = dt.day
    month = dt.strftime("%B")  # Full month name (e.g. "May")
    year = dt.strftime("%Y")
    
    # 12-hour clock hour without leading zero
    hour_12 = dt.hour % 12
    if hour_12 == 0:
        hour_12 = 12
    
    minute = dt.strftime("%M")
    am_pm = dt.strftime("%p")
    
    # Timezone name/abbreviation (e.g., IST)
    tz_name = dt.strftime("%Z")
    if not tz_name:
        tz_name = TIMEZONE
        
    return f"{day} {month} {year} • {hour_12}:{minute} {am_pm} {tz_name}"

def format_disconnection_reason(reason: Any) -> str:
    """
    Formats disconnection reason like 'user_hangup' to 'User Hangup'.
    """
    if not reason:
        return "Unknown"
    
    # Replace underscores with spaces and capitalize each word
    formatted = str(reason).replace("_", " ").strip().title()
    return formatted if formatted else "Unknown"

def format_call_message(call: Dict[str, Any]) -> str:
    """
    Formats a Retell Call Object exactly as:
    
    📞 New Call Summary
    
    👤 Caller: +91XXXXXXXXXX
    ⏱ Duration: 25s
    📅 22 May 2026 • 4:43 PM IST
    
    📊 Call Analysis
    • Call Status: Successful
    • User Sentiment: Neutral
    • Disconnection: User Hangup
    
    📝 Conversation Summary
    [summary from Retell]
    """
    # 1. Caller Number (from_number for inbound, to_number for outbound)
    direction = call.get("direction", "inbound")
    if direction == "inbound":
        caller = call.get("from_number")
    else:
        caller = call.get("to_number")
        
    if not caller:
        # Fallback for web calls or missing fields
        call_type = call.get("call_type", "Call")
        caller = f"Web Call / {call_type.title()}"

    # 2. Duration (convert duration_ms to seconds)
    duration_ms = call.get("duration_ms", 0)
    if duration_ms is None:
        duration_ms = 0
    duration_s = int(round(duration_ms / 1000.0))
    duration_str = f"{duration_s}s"

    # 3. Timestamp
    timestamp_str = format_call_timestamp(call.get("start_timestamp"))

    # 4. Call Status (Successful / Failed)
    analysis = call.get("call_analysis") or {}
    if not isinstance(analysis, dict):
        analysis = {}
        
    is_successful = analysis.get("call_successful")
    if is_successful is True:
        status_str = "Successful"
    elif is_successful is False:
        status_str = "Failed"
    else:
        # If call_successful is missing, fallback to ended status vs error status
        call_status = call.get("call_status")
        if call_status == "error" or call.get("disconnection_reason") in ["dial_failed", "dial_busy", "error"]:
            status_str = "Failed"
        else:
            status_str = "Successful"

    # 5. User Sentiment
    sentiment = analysis.get("user_sentiment")
    if not sentiment:
        sentiment = "Neutral"
    else:
        sentiment = str(sentiment).strip().title()

    # 6. Disconnection Reason
    disconnection = format_disconnection_reason(call.get("disconnection_reason"))

    # 7. Retell Summary
    summary = analysis.get("call_summary") or analysis.get("summary")
    if not summary:
        summary = "No summary available."
    else:
        summary = str(summary).strip()

    # Construct the formatted message
    message = (
        f"📞 New Call Summary\n\n"
        f"👤 Caller: {caller}\n"
        f"⏱ Duration: {duration_str}\n"
        f"📅 {timestamp_str}\n\n"
        f"📊 Call Analysis\n"
        f"• Call Status: {status_str}\n"
        f"• User Sentiment: {sentiment}\n"
        f"• Disconnection: {disconnection}\n\n"
        f"📝 Conversation Summary\n"
        f"{summary}"
    )
    
    return message
