#!/usr/bin/env bash
# setup_local.sh - cài Postiz, PostgreSQL, Redis cho content-factory (Ubuntu/WSL, RAM 4GB, không Docker).
# Chạy lại nhiều lần an toàn. Cách dùng: bash setup_local.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$ROOT/vendor"
mkdir -p "$VENDOR" "$ROOT/data/scripts" "$ROOT/data/drive_inbox" "$ROOT/data/published"

say() { printf '\n== %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

say "1/6 Gói hệ thống (apt)"
$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends \
  git curl ca-certificates build-essential unzip \
  ffmpeg postgresql redis-server rclone

say "2/6 Swap 2GB (giúp build Postiz khi RAM 4GB)"
if swapon --show | grep -q .; then
  echo "Đã có swap, bỏ qua."
else
  read -r -p "Tạo /swapfile 2GB? [y/N] " ans
  if [ "${ans:-N}" = "y" ] || [ "${ans:-N}" = "Y" ]; then
    $SUDO fallocate -l 2G /swapfile
    $SUDO chmod 600 /swapfile
    $SUDO mkswap /swapfile
    $SUDO swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
  fi
fi

say "3/6 Node.js, pnpm, PM2"
# Postiz yêu cầu Node >=22.12 <23 và pnpm 10.6.1 (theo package.json của repo tại thời điểm kiểm tra).
NODE_OK=0
if have node; then
  node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a===22&&b>=12?0:1)' && NODE_OK=1 || true
fi
if [ "$NODE_OK" -ne 1 ]; then
  echo "Chưa có Node 22.x (>=22.12). Cài bằng nvm theo hướng dẫn chính thức tại github.com/nvm-sh/nvm, rồi chạy:"
  echo "  nvm install 22 && nvm use 22"
  echo "Sau đó chạy lại script này."
  exit 1
fi
have pnpm || npm install -g pnpm@10.6.1
have pm2 || npm install -g pm2

say "4/6 PostgreSQL và Redis (thay Docker)"
$SUDO service postgresql start || true
$SUDO service redis-server start || true
echo "TODO: tạo user/database cho Postiz, ví dụ:"
echo "  sudo -u postgres psql -c \"CREATE USER postiz WITH PASSWORD 'doi-mat-khau';\""
echo "  sudo -u postgres psql -c \"CREATE DATABASE postiz OWNER postiz;\""
echo "Rồi điền DATABASE_URL, REDIS_URL vào vendor/postiz-app/.env (xem .env.example của Postiz)."

say "5/6 Clone Postiz và Humanizer"
[ -d "$VENDOR/postiz-app" ] || git clone --depth 1 https://github.com/gitroomhq/postiz-app "$VENDOR/postiz-app"
[ -d "$VENDOR/humanizer" ] || git clone --depth 1 https://github.com/blader/humanizer "$VENDOR/humanizer"

say "6/6 Proxy ClewdR: chạy riêng bên ngoài, script này không cài"
echo "Mở file exe ClewdR của bạn trước khi dùng ứng dụng. Địa chỉ và mật khẩu API nhập trong mục Cài đặt của ứng dụng."

cat <<EOF

HOÀN TẤT CÀI ĐẶT. Các bước tiếp theo (làm thủ công):

A) ClewdR: chạy file exe riêng của bạn, không nằm trong script này.

B) Cài và chạy Postiz bằng PM2 (tối ưu RAM 4GB):
   cd "$VENDOR/postiz-app"
   cp .env.example .env     # điền DATABASE_URL, REDIS_URL, JWT_SECRET, các URL localhost
   export NODE_OPTIONS=--max-old-space-size=1536
   pnpm install
   pnpm run build           # build một lần; không dùng dev mode
   pm2 start pnpm --name postiz -- start   # TODO: đối chiếu script start/pm2 trong package.json của Postiz
   pm2 save

C) Viết kịch bản: dùng ứng dụng ContentFactory.exe (hoặc chạy: python3 app/main.py).

Theo dõi RAM: pm2 monit   |   free -h
EOF