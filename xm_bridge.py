"""Read-only bridge from a locally logged-in MetaTrader 5 terminal to the web UI."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

try:
    import MetaTrader5 as mt5
except ImportError as exc:  # pragma: no cover - shown directly to the user
    raise SystemExit("MetaTrader5 chưa được cài. Hãy chạy setup_xm.bat trước.") from exc

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


HOST = "127.0.0.1"
PORT = int(os.environ.get("XM_BRIDGE_PORT", "8766"))
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"


def load_local_environment() -> None:
    """Load simple KEY=VALUE entries from the local, git-ignored .env file."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


load_local_environment()

PREFERRED_SYMBOL = os.environ.get("XM_SYMBOL", "GOLD").strip()
MT5_PATH = os.environ.get("XM_MT5_PATH", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
SERPER_ENDPOINT = "https://google.serper.dev/search"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
DEFAULT_ALLOWED_ORIGINS = {
    f"http://{HOST}:{PORT}",
    f"http://localhost:{PORT}",
    "https://jadenguyen208.github.io",
}
ALLOWED_ORIGINS = DEFAULT_ALLOWED_ORIGINS | {
    origin.strip().rstrip("/")
    for origin in os.environ.get("XM_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}
MT5_LOCK = threading.Lock()
ACTIVE_SYMBOL: str | None = None
SYMBOL_CACHE: dict[str, str] = {}
TIMEFRAMES = {
    "M1": (mt5.TIMEFRAME_M1, 60),
    "M5": (mt5.TIMEFRAME_M5, 5 * 60),
    "M15": (mt5.TIMEFRAME_M15, 15 * 60),
    "M30": (mt5.TIMEFRAME_M30, 30 * 60),
    "H1": (mt5.TIMEFRAME_H1, 60 * 60),
    "H4": (mt5.TIMEFRAME_H4, 4 * 60 * 60),
    "D1": (mt5.TIMEFRAME_D1, 24 * 60 * 60),
}


def proxy_json(url: str, headers: dict[str, str], payload: dict, timeout: int = 35) -> tuple[int, dict]:
    """POST JSON to a configured upstream without exposing its API key to the browser."""
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return response.status, data
    except HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {"error": {"message": f"Upstream HTTP {exc.code}"}}
        return exc.code, data
    except (URLError, TimeoutError) as exc:
        return 502, {"error": {"message": f"Không kết nối được dịch vụ bên ngoài: {exc.reason if isinstance(exc, URLError) else exc}"}}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 502, {"error": {"message": "Dịch vụ bên ngoài trả về dữ liệu không hợp lệ."}}


def initialize_mt5() -> tuple[bool, str]:
    """Connect to the existing terminal session without storing credentials."""
    kwargs = {"path": MT5_PATH} if MT5_PATH else {}
    if mt5.initialize(**kwargs):
        return True, ""
    code, message = mt5.last_error()
    return False, f"Không kết nối được MT5 ({code}): {message}"


def resolve_market_symbol(requested_symbol: str) -> tuple[str | None, str]:
    """Resolve a user-facing symbol to the exact name exposed by the terminal."""
    requested_symbol = requested_symbol.strip()
    if not requested_symbol:
        return None, "Mã tài sản không được để trống."

    cache_key = requested_symbol.upper()
    cached = SYMBOL_CACHE.get(cache_key)
    if cached and mt5.symbol_info(cached):
        return cached, ""

    candidates = [requested_symbol]
    if cache_key in {"GOLD", "XAUUSD", "XAU/USD"}:
        candidates.extend([PREFERRED_SYMBOL, "GOLD", "XAUUSD"])

    symbols = mt5.symbols_get() or ()
    names = [symbol.name for symbol in symbols]

    exact_lookup = {name.upper(): name for name in names}
    for candidate in candidates:
        match = exact_lookup.get(candidate.upper())
        if match:
            SYMBOL_CACHE[cache_key] = match
            mt5.symbol_select(match, True)
            return match, ""

    aliases = {cache_key.replace("/", "")}
    if cache_key in {"GOLD", "XAUUSD", "XAU/USD"}:
        aliases.update({"GOLD", "XAUUSD"})
    partial = [name for name in names if any(alias in name.upper() for alias in aliases)]
    if partial:
        match = sorted(partial, key=lambda name: (not name.upper().startswith(cache_key), len(name)))[0]
        SYMBOL_CACHE[cache_key] = match
        mt5.symbol_select(match, True)
        return match, ""

    return None, f"Không tìm thấy mã {requested_symbol}. Hãy thêm mã vào Market Watch hoặc kiểm tra tên mã của broker."


def resolve_gold_symbol() -> tuple[str | None, str]:
    """Find XM's gold symbol while preferring the configured name."""
    global ACTIVE_SYMBOL
    if ACTIVE_SYMBOL and mt5.symbol_info(ACTIVE_SYMBOL):
        return ACTIVE_SYMBOL, ""

    ACTIVE_SYMBOL, error = resolve_market_symbol(PREFERRED_SYMBOL)
    return ACTIVE_SYMBOL, error


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


def get_bars_payload(symbol_request: str, timeframe_request: str, count: int) -> tuple[int, dict]:
    """Return read-only OHLC bars for charting and closed-candle indicators."""
    timeframe_name = timeframe_request.upper()
    timeframe = TIMEFRAMES.get(timeframe_name)
    if timeframe is None:
        return 400, {"ok": False, "error": f"Khung thời gian không hỗ trợ: {timeframe_request}"}

    count = max(50, min(count, 1000))
    with MT5_LOCK:
        if mt5.terminal_info() is None:
            connected, error = initialize_mt5()
            if not connected:
                return 503, {"ok": False, "error": error}

        symbol, error = resolve_market_symbol(symbol_request)
        if not symbol:
            return 404, {"ok": False, "error": error}

        rates = mt5.copy_rates_from_pos(symbol, timeframe[0], 0, count)
        info = mt5.symbol_info(symbol)
        if rates is None or info is None:
            code, message = mt5.last_error()
            return 503, {"ok": False, "error": f"Không lấy được nến {symbol} ({code}): {message}"}
        if len(rates) < 30:
            return 503, {"ok": False, "error": f"Chưa đủ dữ liệu nến {symbol} để tính xu hướng."}

        ordered_rates = sorted(rates, key=lambda rate: int(rate["time"]))
        bars = [
            {
                "time": int(rate["time"]),
                "open": float(rate["open"]),
                "high": float(rate["high"]),
                "low": float(rate["low"]),
                "close": float(rate["close"]),
                "tickVolume": int(rate["tick_volume"]),
                "spread": int(rate["spread"]),
                "realVolume": int(rate["real_volume"]),
                "closed": index < len(ordered_rates) - 1,
            }
            for index, rate in enumerate(ordered_rates)
        ]
        last_bar_time = bars[-1]["time"]
        now_seconds = int(time.time())
        return 200, {
            "ok": True,
            "symbol": symbol,
            "timeframe": timeframe_name,
            "timeframeSeconds": timeframe[1],
            "digits": int(info.digits),
            "bars": bars,
            "stale": now_seconds - last_bar_time > timeframe[1] * 2,
            "serverTime": now_seconds,
        }


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "XMReadOnlyBridge/2.0"

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin", "").rstrip("/")
        return not origin or origin in ALLOWED_ORIGINS

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin", "").rstrip("/")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send_bytes(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self, maximum_bytes: int = 2_000_000) -> tuple[dict | None, str]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None, "Content-Length không hợp lệ."
        if content_length <= 0 or content_length > maximum_bytes:
            return None, "Kích thước yêu cầu không hợp lệ."
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, "Nội dung JSON không hợp lệ."
        if not isinstance(payload, dict):
            return None, "Nội dung phải là JSON object."
        return payload, ""

    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "Origin không được phép."})
            return
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "Origin không được phép."})
            return
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/config":
            self._send_json(200, {
                "ok": True,
                "geminiConfigured": bool(GEMINI_API_KEY),
                "serperConfigured": bool(SERPER_API_KEY),
                "model": GEMINI_MODEL,
            })
            return
        if path == "/api/xm-tick":
            status, payload = get_tick_payload()
            self._send_json(status, payload)
            return
        if path == "/api/xm-bars":
            query = parse_qs(parsed.query)
            symbol = query.get("symbol", [PREFERRED_SYMBOL])[0]
            timeframe = query.get("timeframe", ["M5"])[0]
            try:
                count = int(query.get("count", ["300"])[0])
            except ValueError:
                self._send_json(400, {"ok": False, "error": "count phải là số nguyên."})
                return
            status, payload = get_bars_payload(symbol, timeframe, count)
            self._send_json(status, payload)
            return
        if path in {"/", "/index.html"}:
            try:
                self._send_bytes(200, INDEX_FILE.read_bytes(), "text/html; charset=utf-8")
            except OSError as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "Origin không được phép."})
            return
        path = urlparse(self.path).path
        payload, error = self._read_json()
        if payload is None:
            self._send_json(400, {"ok": False, "error": error})
            return

        if path == "/api/serper-search":
            if not SERPER_API_KEY:
                self._send_json(503, {"ok": False, "error": "SERPER_API_KEY chưa được cấu hình."})
                return
            query = str(payload.get("q", "")).strip()
            if not query or len(query) > 1000:
                self._send_json(400, {"ok": False, "error": "Câu tìm kiếm không hợp lệ."})
                return
            try:
                result_count = max(1, min(int(payload.get("num", 7)), 10))
            except (TypeError, ValueError):
                result_count = 7
            status, response_payload = proxy_json(
                SERPER_ENDPOINT,
                {"X-API-KEY": SERPER_API_KEY},
                {
                    "q": query,
                    "num": result_count,
                    "gl": str(payload.get("gl", "us"))[:8],
                    "hl": str(payload.get("hl", "en"))[:8],
                },
            )
            self._send_json(status, response_payload)
            return

        if path == "/api/gemini-analyze":
            if not GEMINI_API_KEY:
                self._send_json(503, {"ok": False, "error": "GEMINI_API_KEY chưa được cấu hình."})
                return
            allowed_payload = {
                key: payload[key]
                for key in ("contents", "generationConfig")
                if key in payload
            }
            if "contents" not in allowed_payload:
                self._send_json(400, {"ok": False, "error": "Thiếu nội dung phân tích."})
                return
            status, response_payload = proxy_json(
                GEMINI_ENDPOINT,
                {"x-goog-api-key": GEMINI_API_KEY},
                allowed_payload,
                timeout=60,
            )
            self._send_json(status, response_payload)
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def log_message(self, format: str, *args: object) -> None:
        if urlparse(self.path).path not in {"/api/xm-tick", "/api/xm-bars", "/api/config"}:
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
    configured_services = [
        name
        for name, configured in (("Gemini", GEMINI_API_KEY), ("Serper", SERPER_API_KEY))
        if configured
    ]
    print(
        f"API key local: {', '.join(configured_services)}"
        if configured_services
        else "API key local chưa cấu hình. Chạy setup_keys.bat rồi khởi động lại bridge."
    )
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
