#!/bin/bash
# Jalankan beberapa target FOLLOW IG berurutan, tahan terhadap crash runner.
#
# `The futex facility returned an unexpected error code` adalah bug thread
# Python 3.14 di proot/Android — runner mati tapi checkpoint sudah tersimpan.
# Karena itu tiap target diulang sampai selesai (maks ATTEMPT kali); akun yang
# sudah `done` otomatis dilewati, jadi tidak ada follow ganda.
set -u

ATTEMPT=4
# Daftar akun tidak ditanam di skrip: dibaca dari store cookie (berkasnya tidak
# ikut ke repo). Timpa dengan env AKUN=akun1,akun2 bila perlu.
AKUN="${AKUN:-${AKUN_STORE:-$(python3 -c 'import json;''d=json.load(open("/root/buzzmon/data/ig-accounts.json"));''a=d.get("accounts") if isinstance(d,dict) else d;''print(",".join(x["username"] for x in a[:17]))')}}"

cd /root/igchrome || exit 1

for target in "$@"; do
  echo "########## TARGET @$target ##########"
  for n in $(seq 1 $ATTEMPT); do
    echo "----- @$target percobaan $n/$ATTEMPT -----"
    IG_RESTART_TIAP="${IG_RESTART_TIAP:-0}" timeout 1800 python3 -u run.py "$target" follow "$AKUN"
    rc=$?
    # selesai normal (browser ditutup) atau semua akun sudah done → lanjut
    if [ $rc -eq 0 ]; then
      echo "----- @$target selesai (rc=0) -----"
      break
    fi
    echo "----- @$target runner keluar rc=$rc, ulang -----"
    # bersihkan chrome yatim sebelum percobaan berikutnya
    pids=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null
    sleep 5
  done
done

pids=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
[ -n "$pids" ] && kill -9 $pids 2>/dev/null
echo "########## SEMUA ANTREAN SELESAI ##########"