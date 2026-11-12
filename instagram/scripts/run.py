#!/usr/bin/env python3
"""Runner IG hemat-memori dengan penjaga RAM adaptif.

Prinsip:
- Chromium sendiri (bukan harness): renderer 1, gambar mati, heap 128 MB.
- Screenshot dimatikan (berat, tidak wajib).
- SEBELUM tiap akun: baca MemAvailable. Kalau < AMAN_MIN atau chrome > CHROME_MAKS,
  browser di-restart dulu, lalu tunggu sampai memori lega.
- Kalau memori tetap sempit setelah beberapa restart: BERHENTI dan lapor.
  Lebih baik berhenti rapi daripada dibunuh OOM di tengah jalan.

Pakai:
  python3 -u run.py <target> <follow|like> akun1,akun2,...
"""
import json
import os
import signal
import subprocess
import sys
import time

CHROME = "/root/.hermes/tools/chromium-1208/chrome-linux/chrome"
PROFILE = "/root/igchrome/profile"
PORT = 9334
ARGS = [
    CHROME, "--no-sandbox", "--headless=new", "--disable-dev-shm-usage",
    "--disable-gpu", "--renderer-process-limit=1",
    "--js-flags=--max-old-space-size=128",
    "--blink-settings=imagesEnabled=false",
    "--disable-background-networking", "--disable-sync",
    "--disable-extensions", "--disable-default-apps",
    f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
    "--no-first-run", "--no-default-browser-check", "--window-size=900,600",
    "about:blank",
]

AMAN_MIN = 700          # MB MemAvailable minimum untuk lanjut
CHROME_MAKS = 950       # MB; chrome di atas ini -> restart
GAGAL_RESTART_MAKS = 3  # berhenti kalau tetap sempit setelah sekian restart

sys.path.insert(0, "/root/igchrome")
import drive as D  # noqa: E402


def mem_avail_mb():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    return 0


def chrome_pids():
    out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
    return [int(l.split(None, 1)[0]) for l in out.splitlines()
            if "chrome-linux/chrome" in l and "ps -eo" not in l]


def chrome_rss_mb():
    out = subprocess.run(["ps", "-eo", "rss,args"], capture_output=True, text=True).stdout
    total = n = 0
    for line in out.splitlines():
        if "chrome-linux/chrome" in line and "ps -eo" not in line:
            try:
                total += int(line.split()[0])
                n += 1
            except Exception:
                pass
    return total // 1024, n


def hentikan():
    for sig in (signal.SIGTERM, signal.SIGKILL):
        pids = chrome_pids()
        if not pids:
            return
        for p in pids:
            try:
                os.kill(p, sig)
            except Exception:
                pass
        time.sleep(3)


def jalankan():
    hentikan()
    subprocess.Popen(ARGS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    import urllib.request
    for _ in range(40):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=3).read()
            D._ws = None          # koneksi ulang ke proses baru
            D.siap()
            time.sleep(2)
            return True
        except Exception:
            continue
    return False


def lapor(tag):
    av = mem_avail_mb()
    mb, n = chrome_rss_mb()
    print(f"   [{tag}] RAM {av} MB · chrome {mb} MB / {n} proses", flush=True)
    return av, mb


def main():
    target, aksi = sys.argv[1], sys.argv[2]
    akun = sys.argv[3].split(",") if len(sys.argv) > 3 else []

    ns = {}
    exec(open("/tmp/ig_flow.py").read(), ns)
    ns["js"] = D.js
    ns["cdp"] = D.cdp
    ns["goto_url"] = lambda url: D.nav(url)
    ns["new_tab"] = lambda url: D.nav(url)
    ns["wait_for_load"] = lambda: None
    ns["ensure_real_tab"] = lambda: None
    ns["capture_screenshot"] = lambda *a, **k: None
    ns["_simpan"] = lambda *a, **k: None
    ns["_simpan_aman"] = lambda *a, **k: None

    _pasang_asli = ns["pasang_cookie"]

    def pasang_cookie_kuat(akun_d):
        # Pindah ke about:blank mematikan JS IG yang bisa menulis ulang cookie lama.
        try:
            D.nav("about:blank", 1.0)
        except Exception:
            pass
        _pasang_asli(akun_d)
        time.sleep(1.2)

    ns["pasang_cookie"] = pasang_cookie_kuat

    sudah = ns["sudah_selesai"](target, aksi)
    sisa = [a for a in akun if a not in sudah]
    print(f"target={target} aksi={aksi} · total {len(akun)} · sudah {len(sudah)} · sisa {len(sisa)}", flush=True)
    print(f"penjaga: lanjut bila RAM >= {AMAN_MIN} MB · restart bila chrome > {CHROME_MAKS} MB", flush=True)

    if not jalankan():
        print("!! browser gagal start", flush=True)
        return 1
    lapor("awal")

    gagal_restart = 0
    selalu = os.environ.get("IG_RESTART_TIAP", "0") == "1"
    if selalu:
        print("mode: restart browser SETIAP akun (paling ringan)", flush=True)
    for i, nama in enumerate(sisa, 1):
        av = mem_avail_mb()
        mb, _ = chrome_rss_mb()
        if selalu or av < AMAN_MIN or mb > CHROME_MAKS:
            print(f"   ⚠ RAM {av} MB / chrome {mb} MB → restart browser", flush=True)
            if not jalankan():
                print("!! restart gagal", flush=True)
                return 1
            av2, mb2 = lapor("setelah restart")
            if av2 < AMAN_MIN - 150 or mb2 > CHROME_MAKS:
                gagal_restart += 1
                if gagal_restart >= GAGAL_RESTART_MAKS:
                    print(f"!! memori tetap sempit (RAM {av2} MB, chrome {mb2} MB) — BERHENTI", flush=True)
                    break
                time.sleep(20)
            else:
                gagal_restart = 0

        try:
            tutup = D.tutup_tab_lain()
            if tutup:
                print(f"   (tutup {tutup} tab basi)", flush=True)
        except Exception:
            pass

        print(f"\n[{i}/{len(sisa)}] @{nama}", flush=True)
        try:
            ns["jalankan_target"](target, [nama], aksi=aksi, jeda_min=2, jeda_max=4)
        except Exception as e:
            print(f"   !! {type(e).__name__}: {e}", flush=True)
        lapor("sesudah")

    hentikan()
    print(f"\nbrowser ditutup · RAM {mem_avail_mb()} MB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())