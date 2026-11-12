#!/usr/bin/env python3
"""Runner TikTok hemat-memori (browser TAMPAK) dengan penjaga RAM adaptif.

Bedanya dengan runner IG:
- memakai Chromium TAMPAK di DISPLAY :99 (headless dideteksi TikTok: klik
  dijawab 200 body kosong dan status follow balik lagi setelah reload)
- Xvfb dikelola terpisah (start_lite.sh); runner ini hanya mengurus chrome,
  jadi restart jauh lebih cepat (tidak perlu menyalakan ulang X server)
- VNC TIDAK dinyalakan; kalau captcha muncul, runner berhenti dan melapor,
  lalu start_vnc.sh dinyalakan hanya saat itu

Prinsip hemat memori (sama seperti IG):
- renderer 1, gambar mati, heap JS 128 MB, layar 480x800
- restart chrome SETIAP akun (default) — baseline browser tampak lebih tinggi
- kalau memori tetap sempit setelah beberapa restart: BERHENTI dan lapor

Penjaga identitas: cookie `multi_sids` = "<user_id>:<sessionid>". Setelah cookie
dipasang, nilai itu dibaca ulang dan HARUS cocok dengan user_id akun. Kalau
tidak, akun dilewati — lebih baik gagal daripada follow dengan akun salah.

Pakai:
  python3 -u run.py <target> follow akun1,akun2,...
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

CHROME = "/root/.hermes/tools/chromium-1208/chrome-linux/chrome"
WORK = "/root/.hermes/cache/scratch/livebrowser"
PROFILE = f"{WORK}/profile"
PORT = 9222
DISPLAY = ":99"
POS = "/data/data/com.termux/files/home/buzzmon/data/tt-progress.json"

ARGS = [
    CHROME, "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
    "--renderer-process-limit=1",
    "--js-flags=--max-old-space-size=128",
    "--blink-settings=imagesEnabled=false",
    "--disable-features=Translate,MediaRouter,CalculateNativeWinOcclusion",
    "--disable-background-networking", "--disable-sync",
    "--disable-extensions", "--disable-default-apps",
    f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--remote-allow-origins=*", "--window-size=480,800", "--window-position=0,0",
    "--no-first-run", "--no-default-browser-check",
    "--disable-session-crashed-bubble", "about:blank",
]

AMAN_MIN = 850          # MB MemAvailable minimum untuk lanjut
CHROME_MAKS = 900       # MB; chrome di atas ini -> restart
GAGAL_RESTART_MAKS = 3

# drive.py membaca port CDP dari env ini. WAJIB diset SEBELUM import —
# tanpa ini ia menyambung ke 9334 (port headless IG) dan selalu URLError.
os.environ["CDP_PORT"] = "9222"

sys.path.insert(0, "/root/igchrome")
import drive as D  # noqa: E402


def mem_avail_mb():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    return 0


def _proses(pola):
    out = subprocess.run(["ps", "-eo", "rss,args"], capture_output=True, text=True).stdout
    hasil = []
    for line in out.splitlines():
        if pola in line and "ps -eo" not in line:
            bagian = line.split(None, 1)
            try:
                hasil.append((int(bagian[0]), bagian[1]))
            except Exception:
                pass
    return hasil


def chrome_rss_mb():
    p = _proses("chrome-linux/chrome")
    return sum(r for r, _ in p) // 1024, len(p)


def chrome_pids():
    out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
    return [int(l.split(None, 1)[0]) for l in out.splitlines()
            if "chrome-linux/chrome" in l and "ps -eo" not in l]


def xvfb_hidup():
    # ps menampilkan "Xvfb :99 ..." (bukan path lengkap), jadi cocokkan namanya
    return bool(_proses("Xvfb"))


def _port_bebas(timeout=20):
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2).read()
            time.sleep(0.5)          # masih ada yang menjawab → tunggu
        except Exception:
            return True
    return False


def hentikan_chrome():
    """Matikan chrome dan TUNGGU sampai benar-benar hilang.

    Kalau tidak ditunggu, instance baru gagal start dengan
    'UKM database is locked' + 'bind(): Address already in use'.
    """
    for sig in (signal.SIGTERM, signal.SIGKILL):
        pids = chrome_pids()
        if not pids:
            break
        for p in pids:
            try:
                os.kill(p, sig)
            except Exception:
                pass
        for _ in range(24):
            time.sleep(0.5)
            if not chrome_pids():
                break
    # sisa kunci profil bikin instance berikutnya menolak jalan
    for f in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            os.remove(f"{PROFILE}/{f}")
        except Exception:
            pass
    return _port_bebas()


LOG_CHROME = "/tmp/ttchrome_stderr.log"
SKRIP_CHROME = "/root/ttchrome/chrome_only.sh"


def jalankan_chrome():
    """Nyalakan ulang chrome lewat skrip shell (bukan Popen).

    Meluncurkan chrome langsung dari Python di lingkungan ini menghasilkan
    proses yang hidup tapi DevTools-nya tidak bisa dihubungi dari 127.0.0.1;
    peluncuran identik dari shell selalu berhasil. Skrip shell itu juga yang
    membersihkan port + SingletonLock.
    """
    r = subprocess.run(["bash", SKRIP_CHROME], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"!! chrome_only.sh gagal: {(r.stderr or '').strip()[:200]}", flush=True)
        return False
    D._ws = None
    for _ in range(10):
        try:
            D.siap()
            return True
        except Exception as e:
            print(f"   (siap() ulang: {type(e).__name__})", flush=True)
            time.sleep(2)
            D._ws = None
    return False


def lapor(tag):
    av = mem_avail_mb()
    mb, n = chrome_rss_mb()
    print(f"   [{tag}] RAM {av} MB · chrome {mb} MB / {n} proses", flush=True)
    return av, mb


# ---------- pembacaan halaman TikTok ----------

def baca_tombol():
    return D.js("""(() => {
      const b = document.querySelector('button[data-e2e="follow-button"]');
      if (b) return (b.innerText||'').trim();
      const alt = [...document.querySelectorAll('button')]
        .map(x=>(x.innerText||'').trim())
        .filter(t=>/^(Follow|Following|Friends|Ikuti|Mengikuti)$/i.test(t));
      return alt.length ? ('ALT:'+alt[0]) : 'NONE';
    })()""") or "NONE"


def captcha_ada():
    return bool(D.js("""(() => {
      const el = document.querySelectorAll('[class*="cap-"], [id*="captcha"], [class*="captcha"]').length;
      const t = /drag the slider|geser|puzzle|verify/i.test(document.body.innerText||'');
      return el > 0 || t;
    })()"""))


def klik_tombol():
    box = D.js("""(() => {
      const b = document.querySelector('button[data-e2e="follow-button"]');
      if (!b) return null;
      b.scrollIntoView({block:'center'});
      const r = b.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return null;
      return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
    })()""")
    if not box:
        return False
    pos = json.loads(box)
    for tipe in ("mouseMoved", "mousePressed", "mouseReleased"):
        kw = {"type": tipe, "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1}
        if tipe != "mouseMoved":
            kw["buttons"] = 1
        D.cdp("Input.dispatchMouseEvent", **kw)
        time.sleep(0.08)
    return True


def muat_pos():
    try:
        return json.load(open(POS, encoding="utf-8"))
    except Exception:
        return {}


def simpan_pos(data):
    os.makedirs(os.path.dirname(POS), exist_ok=True)
    tmp = POS + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, POS)


def kerjakan_akun(target, akun):
    uid = str(akun["user_id"])
    url = f"https://www.tiktok.com/@{target}"

    D.cdp("Network.clearBrowserCookies")
    time.sleep(0.6)
    n = 0
    for k, v in akun["cookies"].items():
        try:
            D.cdp("Network.setCookie", name=k, value=v, domain=".tiktok.com",
                  path="/", secure=True)
            n += 1
        except Exception:
            pass
    time.sleep(0.8)

    D.nav(url, 25)
    time.sleep(5)

    sesi = D.js("""(() => {
      const m = (document.cookie||'').match(/multi_sids=([^;]+)/);
      return m ? decodeURIComponent(m[1]).split(':')[0] : '';
    })()""") or ""
    if sesi != uid:
        return {"status": "dibatal", "catatan": f"sesi {sesi or '-'} tidak cocok {uid}"}

    if captcha_ada():
        return {"status": "captcha", "catatan": "captcha muncul — perlu manual"}

    awal = baca_tombol()
    if awal.lower() in ("following", "friends", "mengikuti"):
        return {"status": "done", "catatan": f"sudah following ('{awal}', tanpa klik)"}
    if awal == "NONE":
        return {"status": "gagal", "catatan": "tombol follow tidak ditemukan"}

    if not klik_tombol():
        return {"status": "gagal", "catatan": "klik gagal (tombol tidak terlihat)"}
    time.sleep(4)
    sesudah = baca_tombol()

    D.nav(url, 25)
    time.sleep(5)
    akhir = baca_tombol()
    if akhir.lower() in ("following", "friends", "mengikuti"):
        return {"status": "done", "catatan": f"menetap (klik '{awal}' → '{sesudah}' → reload '{akhir}')"}
    return {"status": "gagal", "catatan": f"tidak menetap (reload '{akhir}')"}


def main():
    target = sys.argv[1].lstrip("@")
    aksi = sys.argv[2] if len(sys.argv) > 2 else "follow"
    if aksi != "follow":
        print(f"aksi '{aksi}' belum didukung di runner TikTok", flush=True)
        return 1
    diminta = [a for a in sys.argv[3].split(",") if a] if len(sys.argv) > 3 else []

    data_akun = json.load(open(
        "/data/data/com.termux/files/home/buzzmon/data/tiktok-accounts.json",
        encoding="utf-8"))["accounts"]
    peta = {a["username"]: a for a in data_akun if a.get("username")}
    akun = [peta[a] for a in diminta if a in peta]
    hilang = [a for a in diminta if a not in peta]
    if hilang:
        print(f"!! akun tidak ada di data: {', '.join(hilang)}", flush=True)

    pos = muat_pos()
    kunci = f"{aksi}:{target}"
    sudah = {a for a, v in pos.get(kunci, {}).items() if v.get("status") == "done"}
    sisa = [a for a in akun if a["username"] not in sudah]

    print(f"target=@{target} aksi={aksi} · diminta {len(akun)} · sudah {len(sudah)} · sisa {len(sisa)}", flush=True)
    print(f"penjaga: lanjut bila RAM >= {AMAN_MIN} MB · restart bila chrome > {CHROME_MAKS} MB", flush=True)
    if not sisa:
        print("tidak ada yang perlu dikerjakan", flush=True)
        return 0

    if not xvfb_hidup():
        print("!! Xvfb belum jalan — jalankan start_lite.sh dulu", flush=True)
        return 1
    selalu = os.environ.get("TT_RESTART_TIAP", "1") == "1"
    print(f"mode: restart chrome {'SETIAP akun' if selalu else 'bila memori menipis'}", flush=True)

    if not jalankan_chrome():
        print("!! chrome gagal start", flush=True)
        return 1
    lapor("awal")

    hasil = {"done": 0, "gagal": 0, "dilewati": 0, "captcha": 0}
    gagal_restart = 0
    for i, a in enumerate(sisa, 1):
        nama = a["username"]
        av = mem_avail_mb()
        mb, _ = chrome_rss_mb()
        if selalu or av < AMAN_MIN or mb > CHROME_MAKS:
            print(f"   ⚠ RAM {av} MB / chrome {mb} MB → restart browser", flush=True)
            if not jalankan_chrome():
                print("!! restart gagal", flush=True)
                return 1
            av2, mb2 = lapor("setelah restart")
            if av2 < AMAN_MIN - 150 or mb2 > CHROME_MAKS:
                gagal_restart += 1
                if gagal_restart >= GAGAL_RESTART_MAKS:
                    print(f"!! memori tetap sempit (RAM {av2}, chrome {mb2}) — BERHENTI", flush=True)
                    break
                time.sleep(20)
            else:
                gagal_restart = 0

        print(f"\n[{i}/{len(sisa)}] @{nama}", flush=True)
        r = {"status": "gagal", "catatan": "tidak dijalankan"}
        for percobaan in (1, 2):
            try:
                r = kerjakan_akun(target, a)
            except Exception as e:
                r = {"status": "gagal", "catatan": f"{type(e).__name__}: {e}"}
            if r["status"] in ("done", "captcha"):
                break
            if percobaan == 1:
                print(f"   ulang sekali: {r['catatan']}", flush=True)
                if not jalankan_chrome():
                    break

        pos.setdefault(kunci, {})[nama] = r
        simpan_pos(pos)
        print(f"@{nama}: {r['catatan']}", flush=True)
        if r["status"] == "done":
            hasil["done"] += 1
        elif r["status"] == "captcha":
            hasil["captcha"] += 1
            print("\n!! captcha — berhenti. Jalankan start_vnc.sh lalu selesaikan manual.", flush=True)
            break
        elif r["status"] == "dibatal":
            hasil["dilewati"] += 1
        else:
            hasil["gagal"] += 1
        lapor("sesudah")
        time.sleep(2)

    print("\n" + "=" * 46, flush=True)
    print(f"  follow → {target}", flush=True)
    print(f"  berhasil: {hasil['done']}", flush=True)
    print(f"  dilewati: {hasil['dilewati']}", flush=True)
    print(f"  captcha : {hasil['captcha']}", flush=True)
    print(f"  gagal   : {hasil['gagal']}", flush=True)
    print("=" * 46, flush=True)

    hentikan_chrome()
    print(f"\nbrowser ditutup · RAM {mem_avail_mb()} MB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
