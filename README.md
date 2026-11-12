# sosmed-automation

Otomasi tindakan media sosial (Instagram & TikTok) lewat **Chromium yang dikendalikan CDP** — bukan
API resmi. Dipakai untuk follow, like, dan save/bookmark postingan dari sekumpulan akun yang sudah
login (cookie tersimpan di luar repo ini).

Repo ini adalah **cermin** dari skill lokal di Hermes (`instagram-follow-executor`,
`tiktok-follow-headed`) plus runner hidup yang dipakai sehari-hari, supaya alur yang sudah teruji
tidak perlu dirakit ulang dari nol.

## Isi

```
instagram/
  SKILL.md                     panduan lengkap: alur, jebakan, irama batch, ekonomi bukti
  references/ax-click-recipes.md  resep klik (kapan querySelector/element.click gagal, reel, AX tree)
  scripts/
    run.py         runner per pekerjaan: checkpoint, penjaga RAM, restart adaptif, tutup tab basi
    ig_flow.py     alur kanonik: follow_target, like_target, save_target, state/klik, captcha, store
    drive.py       klien CDP tipis (port lewat env CDP_PORT; 9334 headless, 9222 tampak)
    antre.sh       rantai antrean (flock: hanya satu rantai hidup) dengan ulang-otomatis
    antre_tail.sh  varian untuk argumen berawalan aksi: follow:<target> / like:<kode> / save:<kode>
    livecdp.py     klien untuk browser tampak (mode headed)
    start_live.sh  Xvfb + chrome tampak + VNC (untuk captcha / TikTok)
tiktok/
  SKILL.md                     panduan TikTok: kenapa headless dideteksi, headed berhasil
  scripts/
    run.py, livecdp.py, cek_kesiapan.py, start_lite.sh, start_live.sh, start_vnc.sh, chrome_only.sh
```

## Kebutuhan

- Python 3 (stdlib saja), Chromium/Chrome yang bisa dijalankan dengan `--remote-debugging-port`
- Linux (diuji di Termux/proot ARM64 dan x86_64). Tidak butuh Selenium/Playwright.
- Cookie akun **tidak** disertakan. Format store yang dipakai runner:

  `data/ig-accounts.json` — `{"accounts": [{"username": "...", "ds_user_id": "...", "cookies": [{"name": "...", "value": "...", ...}]}, ...]}`

  Ditulis oleh fungsi `simpan_banyak()` di `instagram/scripts/ig_flow.py`. **Berkas ini tidak boleh
  masuk git** (lihat `.gitignore`).

## Menjalankan

```bash
# satu pekerjaan: follow satu target dari daftar akun
python3 -u run.py <target> <follow|like|save> akun1,akun2,... > /tmp/igrun.log 2>&1

# rantai banyak pekerjaan (flock: aman dijalankan meski rantai lain masih jalan — ia mengantre)
bash antre_tail.sh "follow:targetakun" "like:DfXyZ123" "save:DfAbC456:akun1,akun2"
```

Target: `follow` = username, `like`/`save` = **kode post** (URL yang dipakai runner: `/p/<kode>/`).
Tanpa daftar akun, rantai memakai 17 akun pertama dari store. Daftar akun **tidak** ditanam di skrip:
`antre.sh`/`antre_tail.sh` membacanya dari store, dan bisa ditimpa lewat env `AKUN`/`SEMUA`
atau `AKUN_STORE=<jalur berkas lain>`.

Env yang berpengaruh:

| Env | Arti |
|---|---|
| `IG_RESTART_TIAP=1` | matikan-nyalakan Chromium tiap akun (paling hemat RAM, paling lambat) |
| `CDP_PORT` | port debug (bawaan 9334; 9222 untuk browser tampak) |
| `AKUN_STORE` | jalur berkas store cookie alternatif |

## Batas yang disengaja

- **Cookie tidak pernah masuk repo.** Kredensial hidup hanya di berkas lokal bermode 600 di luar git.
- **Akun tetap di jaringan residensial.** Rentang IP datacenter (AWS/GCP/Hetzner/OVH/DO) sudah
  diblokir Instagram lebih dulu; VPS hanya untuk penjadwal/panel, bukan untuk browser akun.
- **Captcha tidak ditembus otomatis.** Kalau muncul, batch berhenti di akun itu, lanjut ke akun
  berikutnya, dan akun yang tertahan dilaporkan untuk diselesaikan manusia.
- **Hanya aksi yang diminta.** Runner tidak mencari target sendiri dan tidak menyentuh akun yang
  cookie-nya tidak disediakan.

Detail lengkap (termasuk jebakan yang sudah memakan waktu — ukuran batch vs sisa RAM, bug `fork`
proot, tab menumpuk, `pkill -f` yang membunuh shell sendiri, dsb.) ada di `instagram/SKILL.md`.
