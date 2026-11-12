#!/bin/bash
# Nyalakan VNC (x11vnc + websockify) DI ATAS browser tampak yang sudah jalan.
#
# Dipakai hanya saat captcha benar-benar muncul dan perlu digeser manual.
# Menyalakannya sejak awal memakan ±150-200 MB dan itulah yang membuat
# rangkaian "browser tampak" sebelumnya kena OOM.
set -u

DISPLAY_NUM=":99"
PORT_VNC=5900
PORT_WEB=6080
WORK=/root/.hermes/cache/scratch/livebrowser
PASS_FILE="$WORK/vncpass.txt"

# pastikan browser tampak sudah hidup
if ! curl -s -m 5 -o /dev/null "http://127.0.0.1:9222/json/version"; then
  echo "browser tampak BELUM jalan — jalankan start_lite.sh dulu"
  exit 1
fi

if [ ! -f "$PASS_FILE" ]; then
  head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$PASS_FILE"
fi
VPASS=$(cat "$PASS_FILE")

x11vnc -display "$DISPLAY_NUM" -rfbport $PORT_VNC -passwd "$VPASS" \
  -forever -shared -listen 0.0.0.0 -quiet -noxdamage >"$WORK/x11vnc.log" 2>&1 &
sleep 2

websockify --web=/usr/share/novnc $PORT_WEB localhost:$PORT_VNC >"$WORK/websockify.log" 2>&1 &
sleep 2

echo "=== VNC aktif ==="
echo "  noVNC  : http://127.0.0.1:$PORT_WEB/vnc.html?autoconnect=1&resize=scale"
echo "  sandi  : $VPASS"
echo "  catatan: dari HP lain pakai IP LAN/WiFi, bukan 127.0.0.1"
ps -eo rss,args | grep -E "[x]11vnc|[w]ebsockify" | awk '{printf "  %5d MB  %s\n", $1/1024, substr($0, index($0,$2), 40)}'