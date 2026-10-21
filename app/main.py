#!/usr/bin/env python3
"""Content Factory: ứng dụng cục bộ (giao diện web) điều phối viết kịch bản, Colab và đăng bài.

ClewdR chạy riêng bên ngoài (file exe của bạn). Ứng dụng này chỉ gọi tới địa chỉ proxy
tương thích OpenAI mà bạn cấu hình. Chỉ dùng thư viện chuẩn.
"""
import json
import os
import re
import shutil
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    RES = Path(sys._MEIPASS)
    HOME = Path(sys.executable).resolve().parent
    UI_DIR = RES / "ui"
else:
    HOME = Path(__file__).resolve().parent.parent
    RES = HOME
    UI_DIR = Path(__file__).resolve().parent / "ui"

CONFIG_FILE = HOME / "config.json"
DATA = HOME / "data"
DIRS = {"scripts": DATA / "scripts", "inbox": DATA / "drive_inbox", "published": DATA / "published", "home": HOME}
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3"}
DEFAULTS = {
    "base_url": "http://127.0.0.1:8484",
    "password": "",
    "model": "claude-sonnet-4-6",
    "rclone_remote": "gdrive:content-factory",
    "port": 8765,
}
NOTEBOOKS = {
    "colab_openmontage.ipynb": "Dựng video (OpenMontage)",
    "colab_gpt_sovits.ipynb": "Clone giọng nói (GPT-SoVITS)",
    "colab_latentsync.ipynb": "Khớp khẩu hình (LatentSync)",
    "colab_video2x.ipynb": "Upscale 4K (Video2X)",
}


def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:50] or "kich-ban"


def rules_text():
    p = RES / "config" / "humanizer_rules.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def proxy_request(cfg, path, body=None, timeout=180):
    url = cfg["base_url"].rstrip("/") + path
    headers = {"Authorization": f"Bearer {cfg['password']}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generate_script(cfg, topic, notes):
    if not cfg["password"]:
        raise RuntimeError("Chưa nhập mật khẩu API của proxy trong mục Cài đặt.")
    user = f"Viết kịch bản video ngắn về chủ đề: {topic}"
    if notes:
        user += f"\nYêu cầu thêm: {notes}"
    body = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": rules_text()}, {"role": "user", "content": user}],
    }
    last = "không rõ"
    for attempt in range(3):
        try:
            data = proxy_request(cfg, "/v1/chat/completions", body)
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (401, 403):
                break
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
            last = f"{type(e).__name__}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Gọi proxy thất bại ({last}). Kiểm tra file exe proxy đang chạy, địa chỉ và mật khẩu.")


def list_dir(d, exts=None):
    d.mkdir(parents=True, exist_ok=True)
    items = [p for p in d.iterdir() if p.is_file() and (exts is None or p.suffix.lower() in exts)]
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "size": p.stat().st_size, "time": datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m %H:%M")} for p in items]


def safe_name(d, name):
    p = (d / Path(name).name)
    return p if p.parent.resolve() == d.resolve() else None


class Handler(BaseHTTPRequestHandler):
    server_version = "ContentFactory"

    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path, ctype, download=None):
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(raw)

    def host_ok(self):
        return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self.host_ok():
            return self.send_json({"error": "host"}, 403)
        path, _, query = self.path.partition("?")
        if path == "/":
            return self.send_file(UI_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/api/state":
            cfg = load_config()
            pub = {k: v for k, v in cfg.items() if k != "password"}
            pub["password_set"] = bool(cfg["password"])
            return self.send_json({
                "config": pub,
                "scripts": list_dir(DIRS["scripts"], {".txt"}),
                "inbox": list_dir(DIRS["inbox"], MEDIA_EXT),
                "published": list_dir(DIRS["published"], MEDIA_EXT),
                "notebooks": [{"file": k, "title": v} for k, v in NOTEBOOKS.items()],
            })
        if path == "/api/script":
            name = dict(x.split("=", 1) for x in query.split("&") if "=" in x).get("name", "")
            p = safe_name(DIRS["scripts"], urllib.parse.unquote(name))
            if not p or not p.exists():
                return self.send_json({"error": "Không thấy tệp."}, 404)
            return self.send_json({"name": p.name, "text": p.read_text(encoding="utf-8")})
        if path.startswith("/colab/"):
            name = urllib.parse.unquote(path[len("/colab/"):])
            if name in NOTEBOOKS and (RES / "colab" / name).exists():
                return self.send_file(RES / "colab" / name, "application/json", download=name)
        self.send_json({"error": "Không tìm thấy."}, 404)

    def do_POST(self):
        if not self.host_ok() or self.headers.get("X-CF") != "1":
            return self.send_json({"error": "Yêu cầu bị từ chối."}, 403)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except (ValueError, json.JSONDecodeError):
            return self.send_json({"error": "Dữ liệu không hợp lệ."}, 400)
        try:
            self.send_json(self.route(self.path, body))
        except RuntimeError as e:
            self.send_json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self.send_json({"error": f"Lỗi nội bộ: {type(e).__name__}"}, 500)

    def route(self, path, body):
        cfg = load_config()
        if path == "/api/config":
            for k in ("base_url", "model", "rclone_remote"):
                if isinstance(body.get(k), str) and body[k].strip():
                    cfg[k] = body[k].strip()
            if isinstance(body.get("password"), str) and body["password"].strip():
                cfg["password"] = body["password"].strip()
            if not re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?$", cfg["base_url"].rstrip("/")):
                raise RuntimeError("Địa chỉ proxy phải là http://127.0.0.1:<cổng> hoặc http://localhost:<cổng>.")
            save_config(cfg)
            return {"ok": True}
        if path == "/api/health":
            try:
                data = proxy_request(cfg, "/v1/models", timeout=8)
                ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
                return {"ok": True, "models": ids[:12]}
            except urllib.error.HTTPError as e:
                raise RuntimeError(f"Proxy trả lỗi HTTP {e.code}. Kiểm tra mật khẩu API.")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                raise RuntimeError("Không kết nối được proxy. Hãy mở file exe proxy trước.")
        if path == "/api/script":
            topic = str(body.get("topic", "")).strip()
            if not topic:
                raise RuntimeError("Chưa nhập chủ đề.")
            text = generate_script(cfg, topic, str(body.get("notes", "")).strip())
            DIRS["scripts"].mkdir(parents=True, exist_ok=True)
            p = DIRS["scripts"] / f"{slugify(topic)}-{datetime.now():%Y%m%d-%H%M%S}.txt"
            p.write_text(text + "\n", encoding="utf-8")
            return {"name": p.name, "text": text}
        if path == "/api/open":
            d = DIRS.get(body.get("folder"))
            if not d:
                raise RuntimeError("Thư mục không hợp lệ.")
            d.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(str(d))  # noqa: S606
            return {"ok": True, "path": str(d)}
        if path == "/api/publish":
            src = safe_name(DIRS["inbox"], str(body.get("name", "")))
            if not src or not src.exists():
                raise RuntimeError("Không thấy tệp.")
            DIRS["published"].mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(DIRS["published"] / src.name))
            return {"ok": True}
        raise RuntimeError("Lệnh không tồn tại.")


def main():
    cfg = load_config()
    for d in DIRS.values():
        d.mkdir(parents=True, exist_ok=True)
    port = int(cfg.get("port", 8765))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Content Factory chạy tại {url} (đóng cửa sổ này để thoát)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()