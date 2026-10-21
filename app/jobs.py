"""Hàng đợi job qua Google Drive cho Content Factory.

Hai chế độ truy cập Drive:
- drive_dir: thư mục content-factory đã đồng bộ cục bộ (Google Drive for Desktop).
- rclone_remote: dùng rclone (ví dụ gdrive:content-factory) khi không có thư mục đồng bộ.
Chỉ dùng thư viện chuẩn.
"""
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

JOB_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


def valid_id(job_id):
    return bool(JOB_ID_RE.match(job_id))


def make_job(job_id, script_text, stages=None, lang="en", use_claude_code=False, instruction=""):
    if not valid_id(job_id):
        raise RuntimeError("Mã job không hợp lệ.")
    return {
        "id": job_id,
        "script": script_text,
        "stages": stages or ["tts", "video", "lipsync", "upscale"],
        "lang": lang,
        "ref_lang": lang,
        "ref_audio": "voice/mau_giong.wav",
        "ref_text": "voice/mau_giong.txt",
        "use_claude_code": bool(use_claude_code),
        "instruction": instruction,
        "created": time.time(),
    }


def _rclone(args, timeout=600):
    if not shutil.which("rclone"):
        raise RuntimeError("Chưa cài rclone hoặc chưa đặt vào PATH. Hãy đặt 'drive_dir' trong Cài đặt hoặc cài rclone.")
    r = subprocess.run(["rclone", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("rclone lỗi: " + (r.stderr.strip()[-300:] or "không rõ"))
    return r.stdout


def push_job(cfg, job):
    data = json.dumps(job, ensure_ascii=False, indent=1)
    name = f"{job['id']}.json"
    drive_dir = cfg.get("drive_dir", "").strip()
    if drive_dir:
        d = Path(drive_dir) / "jobs" / "pending"
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / (name + ".tmp")
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(d / name)
        return str(d / name)
    remote = cfg["rclone_remote"].rstrip("/")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / name
        p.write_text(data, encoding="utf-8")
        _rclone(["copyto", str(p), f"{remote}/jobs/pending/{name}"])
    return f"{remote}/jobs/pending/{name}"


def get_status(cfg, job_id):
    if not valid_id(job_id):
        raise RuntimeError("Mã job không hợp lệ.")
    drive_dir = cfg.get("drive_dir", "").strip()
    try:
        if drive_dir:
            p = Path(drive_dir) / "jobs" / "status" / f"{job_id}.json"
            if not p.exists():
                return {"id": job_id, "state": "queued"}
            return json.loads(p.read_text(encoding="utf-8"))
        remote = cfg["rclone_remote"].rstrip("/")
        out = _rclone(["cat", f"{remote}/jobs/status/{job_id}.json"], timeout=60)
        return json.loads(out)
    except RuntimeError:
        return {"id": job_id, "state": "queued"}
    except (OSError, json.JSONDecodeError):
        return {"id": job_id, "state": "unknown"}


def pull_output(cfg, job_id, dest_root):
    if not valid_id(job_id):
        raise RuntimeError("Mã job không hợp lệ.")
    dest = Path(dest_root) / job_id
    dest.mkdir(parents=True, exist_ok=True)
    drive_dir = cfg.get("drive_dir", "").strip()
    if drive_dir:
        src = Path(drive_dir) / "output" / job_id
        if not src.is_dir():
            raise RuntimeError("Chưa có kết quả cho job này.")
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dest / f.name)
    else:
        remote = cfg["rclone_remote"].rstrip("/")
        _rclone(["copy", f"{remote}/output/{job_id}", str(dest)])
    return sorted(p.name for p in dest.iterdir() if p.is_file())