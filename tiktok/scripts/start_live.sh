#!/bin/bash
# Browser TAMPAK (bukan headless) + VNC, supaya user bisa berinteraksi langsung
# dan menyelesaikan captcha sendiri. Setelah itu otomasi lanjut dari posisi terakhir.
set -u

DISPLAY_NUM=":99"
SCREEN="1000x900x24"
PORT_CDP=9222
PORT_VNC=5900
PORT_WEB=6080
CHROME=/root/.hermes/tools/chromium-1208/chrome-linux/chrome
WORK=/root/.hermes/cache/scratch/livebrowser
PASS_FILE="$WORK/vncpass.txt"
mkdir -p "$WORK/profile"

# hentikan sisa proses lama
pkill -f "Xvfb $DISPLAY_NUM" 2>/dev/null
pkill -f "x11vnc -display $DISPLAY_NUM" 2>/dev/null
pkill -f "websockify.*$PORT_WEB" 2>/dev/null
pkill -f "remote-debugging-port=$PORT_CDP" 2>/dev/null
sleep 1

# 1. layar virtual
Xvfb "$DISPLAY_NUM" -screen 0 "$SCREEN" -nolisten tcp >"$WORK/xvfb.log" 2>&1 &
sleep 2

# 2. chrome mode tampak
DISPLAY="$DISPLAY_NUM" "$CHROME" \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --disable-features=Translate,MediaRouter \
  --user-data-dir="$WORK/profile" \
  --remote-debugging-port=$PORT_CDP --remote-allow-origins='*' \
  --window-size=1000,900 --window-position=0,0 \
  --no-first-run --no-default-browser-check --disable-session-crashed-bubble \
  about:blank >"$WORK/chrome.log" 2>&1 &
sleep 5

# 3. sandi VNC acak (sekali saja, disimpan)
if [ ! -f "$PASS_FILE" ]; then
  head -c 3 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$PASS_FILE"
fi
VPASS=$(cat "$PASS_FILE")

# 4. VNC server
x11vnc -display "$DISPLAY_NUM" -rfbport $PORT_VNC -passwd "$VPASS" \
  -forever -shared -listen 0.0.0.0 -quiet -noxdamage >"$WORK/x11vnc.log" 2>&1 &
sleep 2

# 5. noVNC lewat websockify
websockify --web=/usr/share/novnc $PORT_WEB localhost:$PORT_VNC >"$WORK/websockify.log" 2>&1 &
sleep 2

echo "=== SIAP ==="
echo "  layar     : $SCREEN"
echo "  CDP       : http://127.0.0.1:$PORT_CDP  (otomasi)"
echo "  VNC       : port $PORT_VNC"
echo "  noVNC     : http://127.0.0.1:$PORT_WEB/vnc.html?autoconnect=1&resize=scale"
echo "  sandi VNC : $VPASS"
echo
echo "  cek proses:"
for p in "Xvfb $DISPLAY_NUM" "remote-debugging-port=$PORT_CDP" "x11vnc -display" "websockify.*$PORT_WEB"; do
  n=$(pgrep -fc "$p" 2>/dev/null || echo 0)
  printf "    %-32s %s\n" "$p" "$([ "$n" -gt 0 ] && echo HIDUP || echo MATI)"
done
