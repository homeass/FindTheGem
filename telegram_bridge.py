"""
ProteusP Telegram Bridge Module
텔레그램 봇 토큰/챗ID 관리 및 메시지 전송
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from proteusp.config import ProteusPConfig, get_config


TELEGRAM_CONFIG_PATH = Path.home() / ".codex" / "telegram-bridge.json"

# Built-in fallback defaults (embedded for permanent use)
_DEFAULT_BOT_TOKEN = "8736805585:AAEGHLH4DQQ_wrgJQEw-1ZXxXm9vWf2Yqns"
_DEFAULT_CHAT_IDS = [202447617]


def load_telegram_config(config_path: Optional[str] = None) -> Optional[Dict]:
    """
    Load Telegram config from JSON file.
    Falls back to embedded defaults if file doesn't exist.
    """
    path = Path(config_path) if config_path else TELEGRAM_CONFIG_PATH

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bot_token = data.get("botToken", "")
            chat_ids = data.get("chatIds", [])

            if bot_token and chat_ids:
                return {
                    "bot_token": bot_token,
                    "chat_ids": chat_ids if isinstance(chat_ids, list) else [chat_ids],
                    "config_path": str(path),
                }
        except (json.JSONDecodeError, IOError, KeyError):
            pass

    # Fallback to built-in defaults
    return {
        "bot_token": _DEFAULT_BOT_TOKEN,
        "chat_ids": _DEFAULT_CHAT_IDS,
        "config_path": "built-in",
    }


def save_telegram_config(
    bot_token: str,
    chat_ids: List[int],
    config_path: Optional[str] = None,
) -> bool:
    """
    Save Telegram config to JSON file.
    Creates parent directories if needed.
    """
    path = Path(config_path) if config_path else TELEGRAM_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "botToken": bot_token.strip(),
        "chatIds": chat_ids,
    }

    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except IOError as e:
        print(f"Failed to save Telegram config: {e}")
        return False


def validate_bot_token(token: str) -> Tuple[bool, str]:
    """
    Validate a Telegram bot token by calling getMe API.
    Returns (is_valid, bot_name_or_error).
    """
    import httpx

    token = token.strip()
    if not token:
        return False, "토큰이 비어 있습니다."

    try:
        resp = httpx.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                bot_name = data["result"].get("first_name", "Unknown")
                username = data["result"].get("username", "")
                return True, f"✅ @{username} ({bot_name})"
            return False, "API 응답이 ok가 아닙니다."
        elif resp.status_code == 401:
            return False, "❌ 유효하지 않은 토큰입니다 (401 Unauthorized)."
        else:
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except httpx.ConnectError:
        return False, "❌ Telegram API에 연결할 수 없습니다. 인터넷 연결을 확인하세요."
    except Exception as e:
        return False, f"오류: {e}"


def send_telegram_message(
    message: str,
    config_path: Optional[str] = None,
    chat_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Send a Telegram message using the configured bot.
    Uses the telegram-bridge-send script if available, otherwise direct API call.

    Returns (success, response_message).
    """
    # Try using the existing telegram send script first
    script_candidates = [
        Path.home() / ".opencode" / "skills" / "shared_skills" / "telegram-bridge-send" / "scripts" / "send_telegram.py",
        Path.home() / ".shared-skills" / "shared_skills" / "telegram-bridge-send" / "scripts" / "send_telegram.py",
        Path.home() / ".codex" / "skills" / "telegram-bridge-send" / "scripts" / "send_telegram.py",
    ]

    for script in script_candidates:
        if script.exists():
            try:
                cmd = [sys.executable, str(script), "--message", message]
                if chat_id is not None:
                    cmd.extend(["--chat-id", str(chat_id)])
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return True, "메시지 전송 성공"
                else:
                    return False, f"스크립트 오류: {result.stderr[:200]}"
            except subprocess.TimeoutExpired:
                return False, "스크립트 타임아웃"
            except Exception as e:
                return False, str(e)

    # Fallback: direct API call
    config = load_telegram_config(config_path)
    if not config:
        return False, "Telegram 설정이 없습니다. 먼저 봇 토큰을 설정하세요."

    bot_token = config["bot_token"]
    target_chat_id = chat_id or config["chat_ids"][0]

    try:
        import httpx
        resp = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": target_chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            return True, "메시지 전송 성공"
        else:
            return False, f"Telegram API 오류: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def send_file_via_telegram(
    file_path: str,
    caption: str = "",
    config_path: Optional[str] = None,
    chat_id: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Send a file via Telegram.
    """
    config = load_telegram_config(config_path)
    if not config:
        return False, "Telegram 설정이 없습니다."

    bot_token = config["bot_token"]
    target_chat_id = chat_id or config["chat_ids"][0]

    try:
        import httpx
        path = Path(file_path)
        if not path.exists():
            return False, f"파일을 찾을 수 없습니다: {file_path}"

        with open(path, "rb") as f:
            resp = httpx.post(
                f"https://api.telegram.org/bot{bot_token}/sendDocument",
                data={"chat_id": target_chat_id, "caption": caption},
                files={"document": (path.name, f, "application/octet-stream")},
                timeout=60.0,
            )

        if resp.status_code == 200:
            return True, f"파일 전송 성공: {path.name}"
        else:
            return False, f"전송 실패: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def get_config_status() -> Dict:
    """
    Get Telegram connection status for display.
    """
    config = load_telegram_config()
    if config:
        return {
            "configured": True,
            "bot_token": config["bot_token"][:8] + "..." + config["bot_token"][-4:],
            "chat_ids": config["chat_ids"],
            "path": config["config_path"],
        }
    return {"configured": False, "bot_token": _DEFAULT_BOT_TOKEN[:8] + "...", "chat_ids": _DEFAULT_CHAT_IDS}
