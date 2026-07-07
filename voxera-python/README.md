# Voxera Python Backend

A simple, reliable, production-usable Python automation system for Voxera. This continuously running service polls Retell AI API for completed calls, filters duplicates, formats clean summaries, and forwards them automatically to a Telegram channel or group.

## Features

1. **Continuous Polling:** Runs forever, polling Retell AI every 30 seconds without crashing or exiting.
2. **Retell AI Integration:** Accesses `/v2/list-calls` to retrieve call metadata, durations, and post-call summaries with automatic retry protection.
3. **Duplicate Prevention:** Tracks already processed call IDs in `processed_calls.json` with corruption-recovery mechanisms.
4. **Telegram Integration:** Sends clean call summary messages to Telegram using the Bot API with automatic text chunking if a conversation summary is extremely long.
5. **Robust Error Handling:** Keeps running during Retell AI or Telegram API outages.

---

## Directory Structure

```text
voxera-python/
│
├── main.py                   # Main loop & polling scheduler
├── retell.py                 # Retell AI integration (V2 list-calls API)
├── telegram.py               # Telegram Bot API client with chunking & retries
├── formatter.py              # Parsing and styling data into the required template
├── storage.py                # Local JSON database for duplicate prevention
├── config.py                 # Settings & env variable validation
├── processed_calls.json      # Local registry of sent call IDs (auto-created)
├── requirements.txt          # Python dependencies
├── .env.example              # Template configuration file
├── test_pipeline.py          # Integration and simulation tests
└── README.md                 # Project documentation
```

---

## Installation & Setup

### 1. Clone the repository and navigate to the directory
```bash
cd voxera-python
```

### 2. Install dependencies
Ensure you are using Python 3.11+. Install dependencies using `pip`:
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy the template `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Open `.env` and fill in the required keys:
*   `RETELL_API_KEY`: Your Retell API secret token.
*   `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token (obtained from `@BotFather`).
*   `TELEGRAM_CHAT_ID`: The ID of your target Telegram chat, group, or channel (e.g. `-100xxxxxxx` or `1234567`).
*   `POLL_INTERVAL_SECONDS`: The interval to poll Retell (defaults to `30`).
*   `TARGET_AGENT_ID`: The exact Retell agent ID to filter calls for. Use this instead of the display name for reliable matching.
*   `TIMEZONE`: The target timezone for formatting dates (defaults to `Asia/Kolkata` for IST).

---

## Running the Application

To run the application in production mode:
```bash
python main.py
```

### Running in Background (Linux / EC2 deployment)
To run the process in the background and ensure it persists after logging out:
```bash
nohup python main.py > voxera.log 2>&1 &
```

---

## Testing

To run the simulation and verification test suite:
```bash
python test_pipeline.py
```
This tests storage operations, corruption recovery, formatting accuracy, Telegram message chunking, retrying on API error, and duplicate detection without hitting live external APIs.

---

## Log Style

Logs are printed to `stdout` in the following format:
```text
===================================================
    VOXERA PYTHON AUTOMATION SYSTEM (PRODUCTION)
===================================================
[*] Starting up...
[*] Target timezone: Asia/Kolkata
[*] Poll interval: 30 seconds
[*] Storage file: C:\\Users\\...\\processed_calls.json
===================================================
[INFO] Polling Retell...
[INFO] Successfully fetched 20 calls. Filtered to 15 completed calls.
[INFO] Found 2 new call(s)
[INFO] Sending Telegram message (attempt 1/2)...
[INFO] Telegram message sent
[INFO] Sending Telegram message (attempt 1/2)...
[INFO] Telegram message sent
[INFO] Setup complete. Polling loop running. Press Ctrl+C to exit.
```
