"""Read-only bridge from a locally logged-in MetaTrader 5 terminal to the web UI."""

from __future__ import annotations

import json
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    import MetaTrader5 as mt5
except ImportError as exc:  # pragma: no cover - shown directly to the user
    raise SystemExit("MetaTrader5 chưa được cài. Hãy chạy setup_xm.bat trước.") from exc


HOST = "127.0.0.1"
PORT = int(os.environ.get("XM_BRIDGE_PORT", "8766"))
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
PREFERRED_SYMBOL = os.environ.get("XM_SYMBOL", "GOLD").strip()
MT5_PATH = os.environ.get("XM_MT5_PATH", "").strip()
MT5_LOCK = threading.Lock()
ACTIVE_SYMBOL: str | None = None


def initialize_mt5() -> tuple[bool, str]:
    """Connect to the existing terminal session without storing credentials."""
    kwargs = {"path": MT5_PATH} if MT5_PATH else {}
    if mt5.initialize(**kwargs):
        return True, ""
    code, message = mt5.last_error()
    return False, f"Không kết nối được MT5 ({code}): {message}"


def resolve_gold_symbol() -> tuple[str | None, str]:
    """Find XM's gold symbol while preferring the exact configured name."""
    global ACTIVE_SYMBOL
    if ACTIVE_SYMBOL and mt5.symbol_info(ACTIVE_SYMBOL):
        return ACTIVE_SYMBOL, ""

    preferred = PREFERRED_SYMBOL.upper()
    candidates = [PREFERRED_SYMBOL, "GOLD", "XAUUSD"]
    symbols = mt5.symbols_get() or ()
    names = [symbol.name for symbol in symbols]

    exact_lookup = {name.upper(): name for name in names}
    for candidate in candidates:
        match = exact_lookup.get(candidate.upper())
        if match:
            ACTIVE_SYMBOL = match
            mt5.symbol_select(match, True)
            return match, ""

    partial = [name for name in names if preferred in name.upper() or "GOLD" in name.upper()]
    if partial:
        ACTIVE_SYMBOL = sorted(partial, key=len)[0]
        mt5.symbol_select(ACTIVE_SYMBOL, True)
        return ACTIVE_SYMBOL, ""

    return None, f"Không tìm thấy mã {PREFERRED_SYMBOL}. Hãy thêm GOLD vào Market Watch hoặc đặt XM_SYMBOL."


def get_tick_payload() -> tuple[int, dict]:
    """Return the latest Bid/Ask tick. No trading operation is exposed."""
    with MT5_LOCK:
        if mt5.terminal_info() is None:
            connected, error = initialize_mt5()
            if not connected:
                return 503, {"ok": False, "error": error}

        symbol, error = resolve_gold_symbol()
        if not symbol:
            return 404, {"ok": False, "error": error}

        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick is None or info is None or tick.bid <= 0 or tick.ask <= 0:
            code, message = mt5.last_error()
            return 503, {"ok": False, "error": f"Chưa nhận được giá {symbol} ({code}): {message}"}

        now_msc = int(time.time() * 1000)
        tick_time_msc = int(tick.time_msc)
        return 200, {
            "ok": True,
            "symbol": symbol,
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "spread": float(tick.ask - tick.bid),
            "digits": int(info.digits),
            "timeMsc": tick_time_msc,
            "stale": now_msc - tick_time_msc > 10_000,
        }


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "XMReadOnlyBridge/1.0"

    def _send_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send_bytes(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/xm-tick":
            status, payload = get_tick_payload()
            self._send_json(status, payload)
            return
        if path in {"/", "/index.html"}:
            try:
                self._send_bytes(200, INDEX_FILE.read_bytes(), "text/html; charset=utf-8")
            except OSError as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        self._send_json(404, {"ok": False, "error": "Not found"})

    def log_message(self, format: str, *args: object) -> None:
        if urlparse(self.path).path != "/api/xm-tick":
            super().log_message(format, *args)


def main() -> None:
    connected, error = initialize_mt5()
    if connected:
        symbol, symbol_error = resolve_gold_symbol()
        print(f"Đã kết nối XM MT5 · {symbol}" if symbol else symbol_error)
    else:
        print(error)
        print("Hãy mở và đăng nhập XM MT5; trang web vẫn mở để bạn bấm kết nối lại.")

    server = ThreadingHTTPServer((HOST, PORT), BridgeHandler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Cầu nối chỉ-đọc đang chạy tại {url}")
    print("Nhấn Ctrl+C để dừng.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        mt5.shutdown()


if __name__ == "__main__":
    main()
