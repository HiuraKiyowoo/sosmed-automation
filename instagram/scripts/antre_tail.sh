#!/bin/bash
# Rantai EKOR: menjalankan pekerjaan campuran (follow/like) SETELAH semua
# antrean/runner lain benar-benar berhenti.
#
# Kenapa harus menunggu: dua proses yang memakai port CDP 9334 + profil chrome
# yang sama akan saling menggagalkan (cookie ds_user_id tertukar, "browser gagal
# start"). Dulu penantiannya cuma cek "tidak ada run.py", dan itu RACE: dua
# rantai yang diantrekan berdekatan sama-sama melihat 0 proses lalu jalan
# berdampingan — terbukti merusak (ds_user_id tertukar). Sekarang dipakai kunci
# flock supaya benar-benar hanya satu rantai yang hidup.
#
# Argumen: <aksi>:<target>[:akun,...]   (akun default = 17 akun Xena)
set -u

ATTEMPT=6
# Daftar akun tidak ditanam di skrip: dibaca dari store cookie (berkasnya tidak
# ikut ke repo). Timpa dengan env SEMUA=akun1,akun2 bila perlu.
SEMUA="${SEMUA:-${AKUN_STORE:-$(python3 -c 'import json;''d=json.load(open("/root/buzzmon/data/ig-accounts.json"));''a=d.get("accounts") if isinstance(d,dict) else d;''print(",".join(x["username"] for x in a[:17]))')}}"
PROG="/data/data/com.termux/files/home/buzzmon/data/ig-progress.json"
SELF=$$

# Kunci tunggal: rantai berikutnya menunggu di sini sampai rantai ini tutup.
exec 9>/root/igchrome/.rantai.lock
flock 9 || { echo "gagal mengambil kunci rantai"; exit 1; }

bersihkan() {
  pids=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
  [ -n "$pids" ] && kill -9 $pids 2>/dev/null
  fuser -k 9334/tcp >/dev/null 2>&1
  rm -f /root/igchrome/profile/Singleton* 2>/dev/null
  sleep 4
}

jml_lain() {
  # Hanya hitung proses run.py.
  #
  # Versi pertama menghitung juga proses "antre*.sh" lain sambil mencoba
  # mengecualikan diri sendiri + induknya. Itu gagal: induk sebenarnya adalah
  # proses Hermes, bukan pembungkus shell-nya, sehingga pembungkus sendiri
  # ikut terhitung dan skrip menunggu selamanya. Karena desainnya hanya
  # mengizinkan satu rantai hidup, cukup tunggu sampai tidak ada run.py.
  ps -eo pid,args | awk '$0 ~ /run\.py/ && $0 !~ /awk/ {print $1}' | wc -l
}

sisa_gagal() {
  # Hitung akun yang belum berstatus "done" untuk aksi:target ini.
  # Kunci di berkas progres memakai huruf kecil untuk like, jadi dicoba dua bentuk.
  python3 - "$PROG" "$1" "$2" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(0)
    raise SystemExit
aksi, target = sys.argv[2], sys.argv[3]
for k in (f"{aksi}:{target}", f"{aksi}:{target.lower()}"):
    v = d.get(k)
    if isinstance(v, dict):
        print(sum(1 for c in v.values() if str(c.get("status")) != "done"))
        raise SystemExit
print(0)
PY
}

tunggu=0
while [ "$(jml_lain)" -gt 0 ]; do
  sleep 15
  tunggu=$((tunggu+15))
  [ $tunggu -ge 10800 ] && break
done
sleep 10

cd /root/igchrome || exit 1

for item in "$@"; do
  aksi="${item%%:*}"
  sisa="${item#*:}"
  target="${sisa%%:*}"
  if [ "$sisa" = "$target" ]; then akun="$SEMUA"; else akun="${sisa#*:}"; fi
  jml=$(echo "$akun" | tr ',' '\n' | wc -l)

  echo "########## $aksi @$target · $jml akun ##########"
  for n in $(seq 1 $ATTEMPT); do
    bersihkan
    echo "----- $aksi @$target percobaan $n/$ATTEMPT -----"
    IG_RESTART_TIAP="${IG_RESTART_TIAP:-0}" timeout 3000 python3 -u run.py "$target" "$aksi" "$akun"
    rc=$?
    sisaGagal=$(sisa_gagal "$aksi" "$target")
    if [ "$rc" -eq 0 ] && [ "$sisaGagal" -eq 0 ]; then
      echo "----- $aksi @$target selesai (rc=0, akun gagal tersisa 0) -----"
      break
    fi
    # Keluar rc=0 tapi masih ada akun berstatus gagal BUKAN berarti beres.
    # Dulu itu dianggap selesai sehingga akun yang gagal tidak pernah dicoba lagi.
    echo "----- $aksi @$target rc=$rc · akun gagal tersisa $sisaGagal, ulang -----"
  done
done

bersihkan
echo "########## RANTAI EKOR SELESAI ##########"