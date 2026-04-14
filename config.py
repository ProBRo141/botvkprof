import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path("/home/container" if os.path.exists("/home/container") else ".")
for p in [BASE / ".env", Path(".env")]:
    if p.exists():
        load_dotenv(p)
        break
else:
    load_dotenv()

# VK: Управление сообществом → Работа с API → ключ (сообщения, Long Poll)
VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN") or os.getenv("VK_TOKEN")
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", "0") or 0)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL") or "https://ollama.com"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL") or "gpt-oss:20b"
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

# Google Sheets: JSON сервисного аккаунта + ID таблицы из URL
GOOGLE_SPREADSHEET_ID = (os.getenv("GOOGLE_SPREADSHEET_ID") or "").strip()
_creds = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
GOOGLE_CREDENTIALS_PATH = Path(_creds) if _creds else (BASE / "credentials.json")
GOOGLE_SHEET_WORKSHEET = (os.getenv("GOOGLE_SHEET_WORKSHEET") or "").strip() or None

PROXY = os.getenv("PROXY", "").strip() or None
