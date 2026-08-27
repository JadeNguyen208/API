"""Prompt once for local API keys and save them to the git-ignored .env file."""

from __future__ import annotations

import getpass
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def read_environment() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def prompt_secret(label: str, has_existing_value: bool) -> str:
    suffix = " (Enter để giữ key hiện tại)" if has_existing_value else ""
    while True:
        value = getpass.getpass(f"{label}{suffix}: ").strip()
        if value or has_existing_value:
            return value
        print("Key không được để trống.")


def main() -> None:
    print("Cấu hình key local — ký tự nhập sẽ không hiện trên màn hình.")
    print("Key chỉ được lưu trong file .env trên máy và file này đã bị Git bỏ qua.\n")
    values = read_environment()
    gemini = prompt_secret("Gemini API key", bool(values.get("GEMINI_API_KEY")))
    serper = prompt_secret("Serper API key", bool(values.get("SERPER_API_KEY")))
    if gemini:
        values["GEMINI_API_KEY"] = gemini
    if serper:
        values["SERPER_API_KEY"] = serper
    values.setdefault("GEMINI_MODEL", "gemini-3.6-flash")
    values.setdefault("XM_SYMBOL", "GOLD")

    temporary_file = BASE_DIR / ".env.tmp"
    temporary_file.write_text(
        "# Local secrets. Never commit this file.\n"
        + "\n".join(f"{name}={value}" for name, value in values.items())
        + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(ENV_FILE)
    print("\nĐã lưu cấu hình. Hãy đóng bridge cũ (nếu đang chạy) rồi mở start_xm.bat.")


if __name__ == "__main__":
    main()
