#!/bin/bash
# Nyalakan ULANG chrome tampak saja (Xvfb dibiarkan hidup).
#
# Dipisah dari run.py karena meluncurkan chrome lewat Popen (Python) di
# lingkungan ini menghasilkan chrome yang hidup tapi DevTools-nya tidak bisa
# dihubungi dari 127.0.0.1 — sementara peluncuran yang sama dari shell selalu
# berhasil. Jalur shell + setsid ini yang terbukti.
#
# Keluar dengan 0 kalau CDP sudah menjawab, 1 kalau gagal.
set -u

PORT=9222
CHROME=/root/.hermes/tools/chromium-1208/chrome-linux/chrome
WORK=/root/.hermes/cache/scratch/livebrowser
PROFILE="$WORK/profile"
LOG="$WORK/chrome-lite.log"

# 1. matikan chrome lama, tunggu benar-benar hilang
for putaran in 1 2 3; do
  pids=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
  [ -z "$pids" ] && break
  [ "$putaran" -eq 3 ] && kill -9 $pids 2>/dev/null || kill $pids 2>/dev/null
  sleep 2
done

# 2. pastikan port lepas (kalau tidak, chrome start tapi DevTools gagal bind)
for _ in 1 2 3 4 5 6; do
  curl -s -m 2 -o /dev/null "http://127.0.0.1:$PORT/json/version" || break
  fuser -k "$PORT/tcp" >/dev/null 2>&1
  sleep 1
done

# 3. sisa kunci profil bikin instance baru menolak jalan
rm -f "$PROFILE"/Singleton* 2>/dev/null

# 4. luncurkan
setsid env DISPLAY=:99 "$CHROME" \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --renderer-process-limit=1 \
  --js-flags=--max-old-space-size=128 \
  --blink-settings=imagesEnabled=false \
  --disable-features=Translate,MediaRouter,CalculateNativeWinOcclusion \
  --disable-background-networking --disable-sync \
  --disable-extensions --disable-default-apps \
  --user-data-dir="$PROFILE" \
  --remote-debugging-port=$PORT --remote-allow-origins='*' \
  --window-size=480,800 --window-position=0,0 \
  --no-first-run --no-default-browser-check --disable-session-crashed-bubble \
  about:blank >"$LOG" 2>&1 < /dev/null &

# 5. tunggu CDP menjawab
for _ in $(seq 1 40); do
  sleep 1
  if curl -s -m 3 -o /dev/null "http://127.0.0.1:$PORT/json/version"; then
    exit 0
  fi
done

echo "chrome tidak menjawab di port $PORT — ekor log:" >&2
tail -5 "$LOG" >&2
exit 1