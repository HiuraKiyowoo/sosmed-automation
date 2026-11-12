---
name: tiktok-follow-headed
description: Use when following on TikTok via headed browser.
version: 1.0.0
author: Merlin Hermes
license: MIT
metadata:
  hermes:
    tags: [tiktok, browser-automation, cdp, xvfb, vnc, follow]
    related_skills: [instagram-follow-executor]
---

# Follow TikTok lewat browser tampak

## When to Use

Dipakai kalau user minta follow/like di TikTok dari akun yang cookienya sudah tersimpan, atau minta alur apa pun di TikTok yang butuh klik sungguhan.

## Aturan utama: JANGAN headless

TikTok menantang browser headless dengan captcha slider (`Drag the slider to fit the puzzle`, puluhan elemen class `cap-*`). Request follow tetap terkirim tapi dibalas **200 dengan body kosong**, dan state balik sendiri setelah reload — gejala yang menipu, seolah masalahnya cookie atau signature.

Di browser **tampak** (Xvfb): nol captcha, follow berhasil dan menetap. Sudah dibuktikan berulang (`@tiktok`, `@mrbeast`).

Jangan buang waktu mengejar signature `X-Bogus` sebelum mencoba browser tampak — yang menghalangi bukan signature.

**Tapi browser tampak tidak harus mahal.** Kalau RAM sempit, ringankan dengan dua aturan: (a) **jangan nyalakan VNC sampai captcha muncul**, dan (b) kecilkan Xvfb ke 480x800 lalu beri Chromium flag hemat. Terukur di HP ini (RAM total 7,6 GB tapi hanya ±1,2–1,9 GB yang tersedia):

| Rangkaian | Biaya | Hasil |
|---|---|---|
| Xvfb + chrome tampak + x11vnc + websockify | ±1.000 MB | mepet, OOM di tengah jalan |
| Xvfb 480x800 + chrome tampak, TANPA VNC | **612 MB idle · 776 MB setelah halaman penuh** | jalan, ±1,2 GB tersisa |

Flag chrome tampak yang dipakai (sama semangat dengan headless hemat):

```
--no-sandbox --disable-gpu --disable-dev-shm-usage
--renderer-process-limit=1 --js-flags=--max-old-space-size=128
--blink-settings=imagesEnabled=false
--disable-features=Translate,MediaRouter,CalculateNativeWinOcclusion
--disable-background-networking --disable-sync
--disable-extensions --disable-default-apps
--window-size=480,800
```

Kesiapan diuji **tanpa mengklik apa pun** (`scripts/cek_kesiapan.py`): muat profil TikTok publik dengan cookie tersimpan, lalu pastikan empat hal — data profil terbaca, tidak diminta login, `button[data-e2e="follow-button"]` ada, dan **nol elemen `cap-*` / tidak ada teks captcha**. Terukur pada profil besar: 96,6M followers terbaca, tombol `Follow` ada, captcha 0. Kalau salah satu gagal, jangan lanjut klik — perbaiki dulu.

Klien CDP: `scripts/drive.py` milik skill `instagram-follow-executor` sudah menerima port lewat env (`CDP_PORT`, bawaan 9334 headless, isi `9222` untuk browser tampak). Pakai klien itu, jangan tulis klien CDP baru — di sana juga ada `tutup_tab_lain()` yang wajib dipanggil tiap ganti akun, karena tab yang menumpuk membuat CDP menempel ke tab basi dan tombol terbaca "tidak ada" padahal halamannya sehat.

## Langkah

1. **Nyalakan browser tampak versi RINGAN** (default): `scripts/start_lite.sh` → Xvfb `:99` (480x800x24) + Chromium tampak `--remote-debugging-port=9222`, **tanpa VNC**. VNC dinyalakan menyusul hanya kalau captcha benar-benar muncul: `scripts/start_vnc.sh` (x11vnc 5900 + websockify 6080, sandi dari `vncpass.txt`). Jangan pakai `scripts/start_live.sh` (yang menyalakan VNC sejak awal) kecuali memang butuh mengawasi layar terus-menerus — lihat bagian hemat memori di bawah.
2. **Login**: `livecdp.pasang_cookie(cookies)` lalu `nav('https://www.tiktok.com/@<user>')`.
3. **Tunggu tombol**: `button[data-e2e="follow-button"]` baru muncul setelah **±20–40 detik** (halaman render bertahap, sempat hanya skeleton). Polling sabar, jangan simpulkan gagal.
4. **Klik**: ambil tengah tombol dari `getBoundingClientRect()`, lalu `Input.dispatchMouseEvent` berturut `mouseMoved` → `mousePressed` → `mouseReleased` (atau pakai `livecdp.klik(x, y)`). Ini event trusted, bukan `.click()`.
5. **Verifikasi**: teks tombol jadi `Following`, lalu **`nav()` ulang** dan pastikan tetap `Following`. Tanpa reload, laporan belum sah.
6. **Screenshot**: `shot(path)` untuk bukti.

## Runner siap pakai (`scripts/run.py` + `scripts/chrome_only.sh`)

Sudah ada runner batch untuk follow TikTok, pola hemat-memori yang sama dengan `instagram-follow-executor/run.py`:

```
cd /root/ttchrome && TT_RESTART_TIAP=1 python3 -u run.py <target> follow akun1,akun2,...
```

Yang dilakukannya per akun: pasang cookie → **penjaga identitas** → tunggu tombol → klik mouse sungguhan → reload → catat verdict → checkpoint ke `data/tt-progress.json` → ulang chrome. Akun yang sudah `done` di checkpoint dilewati, jadi aman diulang. Default `TT_RESTART_TIAP=1`: chrome di-restart TIAP akun (biayanya cuma ±6,5 detik, jauh lebih murah dari risiko OOM).

Ambang memori: lanjut bila RAM ≥ 850 MB, restart bila chrome > 900 MB, dan **berhenti rapi** kalau memori tetap sempit setelah 3 kali restart — lebih baik lapor daripada dibunuh OOM.

**Penjaga identitas (wajib, ini pengaman utama).** Cookie `multi_sids` berisi `<user_id>:<sessionid>`. Setelah cookie dipasang, nilai itu dibaca ulang dari `document.cookie` dan HARUS sama dengan `user_id` akun yang dimaksud. Kalau tidak cocok → akun dilewati, tidak ada klik. Sama semangatnya dengan penjaga `ds_user_id` di skrip IG: follow salah akun jauh lebih buruk daripada tidak follow.

**Captcha → berhenti, jangan tembus.** Kalau elemen `cap-*` atau teks captcha terdeteksi, runner berhenti dan melapor supaya user menjalankan `scripts/start_vnc.sh` dan menyelesaikannya manual, lalu runner dilanjutkan (checkpoint membuatnya tidak mengulang dari awal).

**Verdict hanya sah setelah reload.** Teks tombol dibaca tiga kali: sebelum klik, sesudah klik, dan **sesudah `nav()` ulang**. Yang menentukan adalah pembacaan ketiga. Di headless, pembacaan sesudah klik bisa `Following` juga — itu sebabnya reload wajib.

## Kalau follow GAGAL di browser tampak: periksa akun, bukan browsernya

Gejala: klik diterima (tombol berubah `Follow` → `Following`), **tidak ada captcha**, **tidak ada toast/error**, tapi setelah reload tombol kembali `Follow` dan tidak ada apa pun yang tercatat di server. Cookie valid, halaman profil terbaca utuh, tidak diminta login.

Urutan pemeriksaan yang membedakan penyebab:

1. **Uji target lain yang jelas publik** (mis. `@tiktok`). Kalau di situ pun gagal, penyebabnya **batas akun**, bukan target atau halaman.
2. Kalau akun gagal ke semua target: jangan buang waktu mengutak-atik flag Chromium, UA, atau signature. Mode tampak sudah terbukti bekerja untuk akun lain di mesin yang sama.
3. Cek umur/keadaan akun: sesi yang baru dibuat (login baru dari perangkat lain) hampir selalu dibatasi beberapa jam. Penyelesaiannya di sisi user — verifikasi nomor/email, pemanasan manual, lalu coba lagi nanti.

Jangan laporkan "berhasil" dari teks tombol sesaat setelah klik; satu-satunya bukti sah adalah pembacaan **sesudah reload** (dan runner sudah melakukan itu).

## Bukti screenshot: lebar viewport menentukan terbaca atau tidak

Viewport 480 px yang dipakai untuk hemat RAM **memotong label tombol** jadi `Followi...` — TikTok memendekkannya sendiri, bukan tangkapannya yang salah. Untuk laporan bukti, ambil ulang pada viewport lebar:

```
cdp("Emulation.setDeviceMetricsOverride", width=1000, height=820, deviceScaleFactor=1, mobile=False)
```

Di 1000 px labelnya utuh `Following`. Tiga catatan supaya buktinya tidak menyesatkan:

- **Jangan menggambar sorotan (outline) pada tombol lalu memotret.** Sorotan diterapkan sebelum layout tenang, lalu elemen bergeser — hasilnya kotak merah mendarat di elemen lain (terukur: menyorot tombol follow tapi kotak merah muncul di tombol `Post video`). Celakanya itu bisa terbaca sebagai bukti. Krop saja bagian header (`ffmpeg -i full.png -vf "crop=<w>:<h>:0:<y>" out.jpg`), tanpa gambar tambahan.
- **Krop harus memuat nama akun, bukan cuma tombolnya.** Potongan yang mulai terlalu rendah kehilangan username dan angka following/followers; geser `y` ke atas sampai ketiganya masuk.
- **Verifikasi isi tangkapan sebelum mengirim**, jangan mengandalkan hasil skrip. Baca gambarnya dan pastikan teks tombolnya benar-benar `Following` (lengkap, bukan terpotong) — screenshot yang masih memperlihatkan `Follow` adalah bukti kegagalan.

## Menambah akun TikTok baru dari blok cookie

Tiga langkah, dan yang tengah itu yang paling sering bikin salah:

1. **Pulihkan JSON-nya sebelum diparse.** Blok yang ditempel ke chat sering rusak di dua tempat: kunci kehilangan kutip pembuka (`hostOnly":false` setelah baris baru) dan `"expirationDate"` kehilangan titik dua. Parse gagal dengan pesan yang menunjuk posisi lain, jadi perbaiki polanya dulu (`,\nhostOnly":` → `,"hostOnly":`, `"expirationDate"\n` → `"expirationDate":`), baru `json.loads`. Kalau ada nama kembar (`msToken` muncul di dua domain), utamakan yang domainnya `.tiktok.com`.
2. **Username TIDAK ada di cookie.** Yang ada hanya `user_id` di `multi_sids` (`<user_id>:<sessionid>`) dan token sesi. Jangan menebak dari feed: tautan `a[href^="/@"]` di beranda memuat video penulis lain dan format `/@<id-numerik>/video/<id>`, jadi hasilnya acak dan menyesatkan. Yang benar: `[data-e2e="nav-profile"]` — elemen `<a>` dengan `href="/@<handle>"`. `img[alt="Profile photo"]` tidak dirender di layout ini, jadi jangan bergantung padanya.
3. **Verifikasi itu profil sendiri, lalu simpan.** Buka `/@<handle>`: tombol **"Edit profile"** harus ada (profil orang lain tidak punya) dan tidak ada permintaan login. Baru tulis entri `{user_id, username, cookies, ditambah}` ke `data/tiktok-accounts.json` — cocokkan lewat `user_id` supaya kiriman ulang memperbarui, bukan menggandakan.

Verifikasi ini bukan formalitas: satu akun pernah tersimpan tanpa username, sesinya mati, dan handle-nya tidak bisa dipulihkan dari token mana pun.

## Temuan penting

- **Satu klik = toggle dua arah.** Tidak ada menu dropdown "Unfollow": klik `Following` langsung jadi `Follow`, dan klik `Follow` langsung jadi `Following`. Jangan cari `[role=menuitem]` — tidak akan muncul.
- **Unfollow juga butuh reload** untuk dipastikan; tanpa itu bisa tampak berhasil padahal belum.
- **Render pertama sangat lambat** (bisa >35 detik). Kalau `document.title` sudah benar tapi isi kosong, itu render lambat — bukan blokir.
- **Satu akun TikTok per cookie.** "ALL AKUN" tidak berlaku seperti di IG; satu cookie = satu akun.
- **RAM:** yang mahal itu **VNC**, bukan mode tampak. Terukur: stack penuh (Xvfb + chrome tampak + x11vnc + websockify) ±1.000 MB dan itulah yang membuat rangkaian ini kena OOM; versi ringan (Xvfb 480x800 + chrome tampak ber-flag hemat, tanpa VNC) hanya **612 MB saat idle → 776 MB setelah halaman penuh**, menyisakan ±1,2 GB. Karena itu `start_lite.sh` jadi default dan VNC menyusul saat perlu. Matikan browser tampak sebelum menjalankan otomasi IG kalau RAM sedang sempit.
- **Matikan dengan benar:** `pkill` yang polanya muncul di baris perintah shell bisa membunuh shell-nya sendiri. Pakai pola ber-kurung (`chrome[-]linux`) atau telusuri `/proc` dan lewati PID sendiri.
- **Restart-per-akun itu lambat, dan itu disengaja.** Terukur ±6,5 detik hanya untuk chrome mati→hidup, ditambah tunggu CDP, pasang cookie, render profil belakangan (±20–40 detik), klik, lalu reload untuk verdict — total 2–3 menit per akun. Jangan menyimpulkan "macet" dari progres yang tidak bergerak beberapa menit; baca log, bukan angka.
- **Runner bisa mati dengan `ConnectionClosedError: keepalive ping timeout` atau stack trace websocket panjang di tengah proses** — itu CDP kehilangan ping saat chrome di-restart, bukan follow yang gagal. Verdict sudah ditulis ke `data/tt-progress.json` sebelum koneksi putus, jadi hitung hasil dari checkpoint, bukan dari log yang berakhir dengan traceback.

## Fungsi `scripts/livecdp.py`

Pengendali CDP minimal untuk browser tampak (harness Hermes hanya headless):

`hubung()`, `kirim(method, **params)`, `nav(url, tunggu)`, `js(expr)`, `pasang_cookie(ck, domain)`, `bersihkan_cookie()`, `shot(path)`, `ukuran(w, h)`, `klik(x, y)`.

Pakai dari `execute_code`:

```python
import sys; sys.path.insert(0, '/root/.hermes/cache/scratch/livebrowser')
import livecdp as L
L.bersihkan_cookie(); L.pasang_cookie(cookies)
L.nav('https://www.tiktok.com/@mrbeast', tunggu=14)
```

## Yang tidak boleh

Menyelesaikan captcha secara otomatis (slider puzzle). Kalau captcha tetap muncul, user yang menyelesaikan lewat noVNC (`http://<ip>:6080/vnc.html?autoconnect=1&resize=scale`); otomasi lanjut setelah itu.

## Jebakan saat menulis skrip ini

- **JANGAN meluncurkan Chrome lewat `subprocess.Popen` dari Python.** Gejalanya menipu: proses chrome hidup dan stderr-nya bahkan menulis `DevTools listening on ws://127.0.0.1:9222`, tapi koneksi ke `127.0.0.1:9222` ditolak (`Connection refused`) selama puluhan detik — padahal flag, profil, dan `DISPLAY` identik dengan yang berhasil. Peluncuran yang sama persis dari shell **selalu** berhasil. Jadi chrome dinyalakan skrip shell ber-`setsid` (`scripts/chrome_only.sh`), runner hanya memanggilnya.
- **`CDP_PORT` harus diset SEBELUM `import drive`.** `drive.py` membaca port itu saat diimpor (bawaan 9334 = headless IG). Runner browser tampak yang lupa menyetelnya akan menyambung ke 9334 dan gagal dengan `URLError`/`Connection refused` yang **sama persis** dengan gejala chrome gagal start — sehingga diagnosanya bisa berjam-jam ke arah yang salah. Baris `os.environ["CDP_PORT"] = "9222"` harus berada di atas `import drive`.
- **Chrome yang dipanggil ulang harus menunggu chrome lama benar-benar hilang.** Kalau tidak, chrome baru hidup tapi DevTools gagal bind (`bind() failed: Address already in use (98)`, `UKM database: 0 database is locked`) dan port punya proses lama. `chrome_only.sh` karena itu: matikan → tunggu sampai daftar proses kosong → `fuser -k <port>/tcp` → hapus `profile/Singleton*` → baru luncurkan.
- **Jangan buang stderr chrome ke `/dev/null`.** Di situ satu-satunya baris yang membedakan "chrome mati" dari "chrome hidup tapi port tidak terjangkau" (`DevTools listening on ...` vs `bind() failed ...`) — tanpa itu diagnosa cuma menebak.
- **`ps` menampilkan `Xvfb :99`, bukan `/Xvfb`.** Pendeteksi "Xvfb sudah jalan?" yang mencari `"/Xvfb"` selalu menjawab tidak, dan runner berhenti dengan pesan menyesatkan ("jalankan start_lite.sh dulu") padahal Xvfb hidup.
- **Jangan menyisipkan string berkutip di dalam program `awk` berkutip tunggal.** `awk '$0 ~ /Xvfb '":99"` memutus kutipan dan skrip gagal di parse (`bash: syntax error near unexpected token '('` di baris terakhir, menyesatkan). Pisahkan jadi dua uji: `awk '$0 ~ /Xvfb/ && $0 ~ /:99/ && $0 !~ /awk/ {print $1}'`.
- **Selalu `bash -n <skrip>` setelah mengedit skrip shell, sebelum menjalankannya.** Kesalahan kutip hanya muncul saat parse, dan `setsid` yang gagal memberi pesan yang menyesatkan (`Permission denied`) sehingga penyebab aslinya tersembunyi. Cek satu perintah: `bash -n skrip.sh && echo OK`.
- **`chmod +x` jalankan di panggilan terpisah** dari perintah yang memakainya; kalau digabung dengan perintah ber-`setsid`/`nohup`, panggilan itu bisa ditolak dan `chmod`-nya tidak pernah jalan.
- **Runner bisa mati di tengah batch karena bug thread Python 3.14 di proot:** `The futex facility returned an unexpected error code`. Bukan salah target, bukan OOM. Checkpoint per-akun tetap tersimpan, jadi obatnya **rantai ulang-otomatis**, bukan mengejar penyebab: bungkus `run.py` dalam skrip shell yang mengulang sampai `rc=0` (maks 4–6x). Akun berstatus `done` otomatis dilewati, jadi tidak ada follow ganda.
- **Skrip antrean yang menunggu LAMA lalu memanggil `run.py` akan gagal `browser gagal start`.** Port debug masih dipegang sisa chrome yang belum benar-benar mati, sehingga satu target bisa gagal 3 dari 4 percobaan padahal targetnya sehat. Sebelum tiap percobaan: matikan chrome → tunggu daftar proses kosong → `fuser -k 9334/tcp` → hapus `<profil>/Singleton*` → baru jalankan.
- **Jangan pindahkan akun ke VPS/datacenter IP.** Instagram dan TikTok sudah memblokir rentang CIDR cloud lebih dulu (`proxy_address_is_blocked`) bahkan sebelum akun berbuat apa pun, sementara IP seluler/rumah user lolos. VPS dipakai untuk panel, penjadwal, dan submit saja; browser + akun tetap di jaringan residensial.
- **Di Termux di luar proot, `/tmp` tidak ada / read-only.** Skrip yang menulis log ke `/tmp/...` mati dengan `mkdir: /tmp: Read-only file system` lalu gagal total. Simpan log di dalam direktori proyek (`logs/`), bukan `/tmp`.
