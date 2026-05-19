import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHECK_URL = os.environ.get("CHECK_URL", "https://kino.pub/")
CHECK_COOKIE = os.environ.get("CHECK_COOKIE", "").strip()
CHECK_USER_AGENT = os.environ.get(
    "CHECK_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "60"))
STATE_FILE = Path(os.environ.get("STATE_FILE", "kinopub_bot_state.json"))
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "20"))
SLOW_RESPONSE_SECONDS = float(os.environ.get("SLOW_RESPONSE_SECONDS", "10"))
RECOVERY_CONFIRMATION_CHECKS = int(os.environ.get("RECOVERY_CONFIRMATION_CHECKS", "3"))

STATUS_ALIVE = "alive"
STATUS_DOWN = "down"
ERROR_BODY_MARKERS = (
    b"an internal server error occurred",
)
LOGIN_REDIRECT_MARKERS = (
    "/user/login",
)


def status_from_http_code(code):
    return STATUS_DOWN if code == 404 or 500 <= code <= 599 else STATUS_ALIVE


def status_from_http_response(code, body, elapsed_seconds=0, headers=None):
    if elapsed_seconds > SLOW_RESPONSE_SECONDS:
        return STATUS_DOWN

    if status_from_http_code(code) == STATUS_DOWN:
        return STATUS_DOWN

    location = ""
    if headers is not None:
        location = headers.get("Location", "")
    if CHECK_COOKIE and 300 <= code <= 399:
        normalized_location = location.lower()
        if any(marker in normalized_location for marker in LOGIN_REDIRECT_MARKERS):
            return STATUS_DOWN

    normalized_body = body.lower()
    if any(marker in normalized_body for marker in ERROR_BODY_MARKERS):
        return STATUS_DOWN

    return STATUS_ALIVE


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_dotenv():
    env_file = Path(".env")
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_state():
    state = {
        "status": STATUS_ALIVE,
        "alive_checks": 0,
        "subscribers": [],
        "telegram_offset": None,
    }

    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
            state.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

    extra_chat_ids = os.environ.get("TELEGRAM_CHAT_IDS", "")
    for raw_chat_id in extra_chat_ids.split(","):
        raw_chat_id = raw_chat_id.strip()
        if raw_chat_id:
            add_subscriber(state, int(raw_chat_id))

    return state


def save_state(state):
    tmp_file = STATE_FILE.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2, sort_keys=True)
    tmp_file.replace(STATE_FILE)


def add_subscriber(state, chat_id):
    if chat_id not in state["subscribers"]:
        state["subscribers"].append(chat_id)


def telegram_api(method, payload=None):
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN before starting the bot.")

    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text):
    telegram_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
    )


def notify_subscribers(state, text):
    for chat_id in list(state["subscribers"]):
        try:
            send_message(chat_id, text)
        except Exception as exc:
            print(f"failed to notify {chat_id}: {exc}", file=sys.stderr)


def fetch_updates(state):
    payload = {
        "timeout": 10,
        "allowed_updates": ["message"],
    }
    if state.get("telegram_offset") is not None:
        payload["offset"] = state["telegram_offset"]

    response = telegram_api("getUpdates", payload)
    if not response.get("ok"):
        return []
    return response.get("result", [])


def handle_updates(state):
    try:
        updates = fetch_updates(state)
    except Exception as exc:
        print(f"failed to fetch telegram updates: {exc}", file=sys.stderr)
        return

    for update in updates:
        state["telegram_offset"] = update["update_id"] + 1
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()

        if chat_id is None or not text.startswith("/"):
            continue

        command = text.split()[0].split("@")[0].lower()
        if command in {"/start", "/status"}:
            add_subscriber(state, chat_id)
            if command == "/start":
                send_message(chat_id, "Subscribed. Use /status to check kinopub status.")
            else:
                send_message(chat_id, f"kinopub is {state['status']}")
        elif command == "/stop":
            if chat_id in state["subscribers"]:
                state["subscribers"].remove(chat_id)
            send_message(chat_id, "Unsubscribed.")

    if updates:
        save_state(state)


def get_site_status():
    headers = {
        "User-Agent": CHECK_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if CHECK_COOKIE:
        headers["Cookie"] = CHECK_COOKIE

    request = urllib.request.Request(
        CHECK_URL,
        headers=headers,
        method="GET",
    )

    started_at = time.monotonic()
    try:
        opener = urllib.request.build_opener(NoRedirectHandler)
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(4096)
            elapsed_seconds = time.monotonic() - started_at
            return status_from_http_response(
                response.status,
                body,
                elapsed_seconds,
                response.headers,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(4096)
        elapsed_seconds = time.monotonic() - started_at
        return status_from_http_response(exc.code, body, elapsed_seconds, exc.headers)
    except Exception as exc:
        print(f"site check failed, marking down: {exc}", file=sys.stderr)
        return STATUS_DOWN


def check_site_and_notify(state):
    previous_status = state.get("status", STATUS_ALIVE)
    previous_alive_checks = state.get("alive_checks", 0)
    raw_status = get_site_status()

    if raw_status == STATUS_ALIVE:
        state["alive_checks"] = state.get("alive_checks", 0) + 1
        if previous_status == STATUS_DOWN and state["alive_checks"] < RECOVERY_CONFIRMATION_CHECKS:
            current_status = STATUS_DOWN
        else:
            current_status = STATUS_ALIVE
    else:
        state["alive_checks"] = 0
        current_status = STATUS_DOWN

    if current_status != previous_status:
        state["status"] = current_status
        save_state(state)
        if current_status == STATUS_DOWN:
            notify_subscribers(state, "kinopub is down")
        else:
            notify_subscribers(state, "kinopub is alive")
    elif state.get("alive_checks", 0) != previous_alive_checks:
        save_state(state)

    print(
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} {CHECK_URL} => {current_status}"
        f" raw={raw_status} alive_checks={state.get('alive_checks', 0)}",
        flush=True,
    )


def main():
    state = load_state()
    save_state(state)

    should_stop = False

    def stop(_signum, _frame):
        nonlocal should_stop
        should_stop = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    next_check_at = 0.0
    while not should_stop:
        handle_updates(state)

        now = time.monotonic()
        if now >= next_check_at:
            check_site_and_notify(state)
            next_check_at = now + CHECK_INTERVAL_SECONDS

        time.sleep(1)


if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    main()
