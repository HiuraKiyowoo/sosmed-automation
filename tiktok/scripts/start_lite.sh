#!/bin/bash
# Browser TAMPAK versi ringan (Xvfb + chrome headed), TANPA VNC.
#
# Kenapa dipisah dari start_live.sh:
#   x11vnc + websockify memakan ±150-200 MB. Untuk kategori task yang hanya
#   perlu "tidak terdeteksi headless" (TikTok), VNC tidak diperlukan terus.
#   Kalau captcha benar-benar muncul, jalankan start_vnc.sh saat itu saja.
#
# Layar dikecilkan ke 480x800 supaya compositor tidak mengalokasikan buffer
# besar; flag lain sama dengan Chromium headless hemat (renderer 1, heap 128 MB,
# gambar mati).
set -u

DISPLAY_NUM=":99"
SCREEN="480x800x24"
PORT_CDP=9222
CHROME=/root/.hermes/tools/chromium-1208/chrome-linux/chrome
WORK=/root/.hermes/cache/scratch/livebrowser
mkdir -p "$WORK/profile"

stop() {
  pids=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
  [ -n "$pids" ] && kill $pids 2>/dev/null; sleep 3
  pids2=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
  [ -n "$pids2" ] && kill -9 $pids2 2>/dev/null
  xpids=$(ps -eo pid,args | awk '$0 ~ /Xvfb/ && $0 ~ /:99/ && $0 !~ /awk/ {print $1}')
  [ -n "$xpids" ] && kill $xpids 2>/dev/null
  sleep 2
}

stop

Xvfb "$DISPLAY_NUM" -screen 0 "$SCREEN" -nolisten tcp >"$WORK/xvfb-lite.log" 2>&1 &
sleep 2

DISPLAY="$DISPLAY_NUM" "$CHROME" \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --renderer-process-limit=1 \
  --js-flags=--max-old-space-size=128 \
  --blink-settings=imagesEnabled=false \
  --disable-features=Translate,MediaRouter,CalculateNativeWinOcclusion \
  --disable-background-networking --disable-sync \
  --disable-extensions --disable-default-apps \
  --user-data-dir="$WORK/profile" \
  --remote-debugging-port=$PORT_CDP --remote-allow-origins='*' \
  --window-size=480,800 --window-position=0,0 \
  --no-first-run --no-default-browser-check --disable-session-crashed-bubble \
  about:blank >"$WORK/chrome-lite.log" 2>&1 &
sleep 6

echo "=== browser tampak (ringan) ==="
curl -s -m 5 "http://127.0.0.1:$PORT_CDP/json/version" | grep -o '"Browser": "[^"]*"'
curl -s -m 5 -o /dev/null -w "  cdp: %{http_code}\n" "http://127.0.0.1:$PORT_CDP/json/version"
echo -n "  chrome RSS: "
ps -eo rss,args | grep "[c]hrome-linux/chrome" | awk '{s+=$1;n++} END {printf "%d MB / %d proses\n", s/1024, n+0}'
awk '/MemAvailable/{printf "  RAM tersedia: %d MB\n", $2/1024}' /proc/meminfo
echo "  VNC: tidak dinyalakan (jalankan start_vnc.sh bila captcha muncul)"