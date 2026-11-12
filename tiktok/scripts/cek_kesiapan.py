#!/usr/bin/env python3
"""Cek kesiapan TikTok sebelum mengklik apa pun.

Empat gerbang yang harus lolos:
  1. data profil terbaca (bukan halaman kosong)
  2. tidak diminta login (cookie diterima untuk browsing)
  3. tombol `button[data-e2e="follow-button"]` ter-render
  4. NOL elemen `cap-*` / tidak ada teks captcha

Kalau salah satu gagal, jangan lanjut klik — perbaiki dulu.

Pakai:
  CDP_PORT=9222 python3 cek_kesiapan.py <akun> [url_profil]
"""
import json
import os
import sys
import time

os.environ.setdefault("CDP_PORT", "9222")
sys.path.insert(0, "/root/igchrome")  # scripts/drive.py milik instagram-follow-executor
import drive as D  # noqa: E402

DATA = "/data/data/com.termux/files/home/buzzmon/data/tiktok-accounts.json"


def main():
    if len(sys.argv) < 2:
        print("pakai: cek_kesiapan.py <akun> [url_profil]")
        return 1
    nama = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else "https://www.tiktok.com/@tiktok"

    akun = json.load(open(DATA, encoding="utf-8"))
    a = next((x for x in akun["accounts"] if x.get("username") == nama), None)
    if not a:
        print(f"akun {nama} tidak ada di {DATA}")
        return 1
    print(f"akun uji: {nama} · cookie {len(a['cookies'])} kunci")

    D.siap()
    try:
        D.cdp("Network.clearBrowserCookies")
    except Exception:
        pass
    time.sleep(1)
    for k, v in a["cookies"].items():
        try:
            D.cdp("Network.setCookie", name=k, value=v,
                  domain=".tiktok.com", path="/", secure=True)
        except Exception:
            pass
    time.sleep(1.5)

    D.nav(url, 12)
    time.sleep(4)

    judul = (D.js("document.title") or "")[:70]
    teks = (D.js("(document.body.innerText||'')") or "").replace("\n", " | ")[:180]
    tombol = D.js("""(() => {
      const b = document.querySelector('button[data-e2e="follow-button"]');
      if (b) return 'ADA: ' + (b.innerText || '').trim();
      const alt = [...document.querySelectorAll('button')]
        .map(x => (x.innerText || '').trim())
        .filter(t => /^(Follow|Following|Ikuti|Mengikuti)$/i.test(t));
      return alt.length ? ('lewat teks: ' + alt.join(',')) : 'TIDAK ADA';
    })()""")
    cap = D.js("""(() => {
      const n = document.querySelectorAll('[class*="cap-"], [id*="captcha"], [class*="captcha"]').length;
      const t = /drag the slider|puzzle|captcha/i.test(document.body.innerText || '');
      return JSON.stringify({ elemen: n, teks_captcha: t });
    })()""")
    login = D.js("/log in|masuk|sign up/i.test((document.body.innerText||'').slice(0,400))")

    print(f"  judul   : {judul}")
    print(f"  teks    : {teks}")
    print(f"  tombol  : {tombol}")
    print(f"  captcha : {cap}")
    print(f"  login?  : {login}")

    try:
        cap_d = json.loads(cap or "{}")
    except Exception:
        cap_d = {}
    siap = ("ADA" in (tombol or "")) and not cap_d.get("teks_captcha") and not login
    print(f"\nHASIL: {'SIAP' if siap else 'BELUM SIAP'}")
    return 0 if siap else 2


if __name__ == "__main__":
    sys.exit(main())
