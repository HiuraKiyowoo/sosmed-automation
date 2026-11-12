# Keamanan

Repo ini **tidak memuat kredensial apa pun**. Yang ada hanya kode dan dokumentasi.

## Yang TIDAK boleh masuk repo (sudah dicegah oleh .gitignore)

| Berkas / pola | Isi |
|---|---|
| `data/ig-accounts.json` | cookie sesi akun Instagram (chmod 600) |
| `data/ig-follows.json`, `ig-likes.json`, `ig-saves.json`, `ig-progress.json` | log tindakan + daftar target |
| `*/cookies*.json`, `*storage*.json`, `*store*.json` | ekspor cookie browser |
| `*.pw`, `*.jks`, `*.keystore`, `credentials*`, `*.env` | sandi keystore, kunci, rahasia |
| `vncpass.txt`, `*.log` | sandi VNC, log yang memuat cookie/URL bertanda tangan |
| `profile/`, `profile-*/`, `*.user-data` | profil Chromium (memuat cookie di disk) |

## Periksa sebelum push

```bash
grep -rInE "sessionid[=:][A-Za-z0-9%_-]{10,}|csrftoken[=:][A-Za-z0-9%_-]{10,}|tt_csrf_token[=:][A-Za-z0-9]{10,}|BEGIN [A-Z ]*PRIVATE KEY|[A-Za-z0-9_%:.-]{60,}" . \
  | grep -viE "https?://|mozilla|webkit|chrome/[0-9]"
```

Keluaran kosong = bersih. Kalau tidak kosong, **jangan push** — bersihkan dulu.

## Catatan

- Cookie kedaluwarsa begitu pemiliknya logout / ganti sandi / "log out all devices" — ambil ulang,
  bukan tambal.
- Jalankan runner hanya di perangkat sendiri, dengan akun sendiri. Batas kerja: aksi hanya untuk
  akun dan target yang diberikan pemiliknya.
- Dokumentasi (`instagram/SKILL.md`, `tiktok/SKILL.md`) menyebut nama akun contoh dan aturan
  penamaan internal; kalau repo ini mau dibuka publik, bersihkan dulu bagian itu.
