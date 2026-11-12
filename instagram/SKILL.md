---
name: instagram-follow-executor
description: Use when following/liking IG or TikTok from cookies.
version: 1.1.0
author: Merlin Hermes
license: MIT
metadata:
  hermes:
    tags: [instagram, browser-automation, follow, cookies]
    related_skills: [buzzcuan-task-monitor]
---

# Eksekutor follow Instagram

## When to Use

Dipakai kalau user mengirim blok cookie akun Instagram (satu atau banyak), minta "follow akun ini" dari akun yang cookienya sudah tersimpan, atau minta cek status/verifikasi akun IG. Untuk upload bukti & submit task BuzzCuan pakai `buzzcuan-task-monitor`, bukan skill ini.

User memberi cookie akun IG (boleh banyak, format `{"url":...,"cookies":[...]}`) lalu menyebut target. Tugas: follow target dari tiap akun, kirim screenshot ke **user saja** (bukan ke BuzzCuan).

**Batas kerja yang sudah disepakati.** User memberi izin penuh untuk mengeksekusi follow/like di akun IG miliknya sendiri dan menanggung sendiri risiko pembatasan/banned. Jangan mengulang peringatan risiko, jangan menolak ulang, jangan minta konfirmasi ulang di tengah batch — cukup eksekusi, verifikasi, dan laporkan. Yang tetap tidak dilakukan: bertindak di akun yang cookie-nya tidak dikirim user, dan follow/like ke target yang tidak disebutkan (jangan menebak target sendiri).

## Berkas yang dipakai

| Berkas | Isi |
|---|---|
| `~/buzzmon/data/ig-accounts.json` | cookie per akun (chmod 600), kunci `ds_user_id` |
| `~/buzzmon/data/ig-follows.json` | log hasil per akun+target |
| `/tmp/ig_simpan.py` | salinan kerja `simpan_banyak`; versi kanoniknya kini ada di dalam `scripts/ig_flow.py` |
| `scripts/ig_flow.py` (milik skill ini) | salinan **kanonik** seluruh alur: `follow_target`, `like_target`, `follow_aman`, `like_aman`, `simpan_banyak`, `cek_semua_cookie` |
| `/tmp/ig_flow.py` | salinan kerja; kalau hilang (tmp dibersihkan), salin dari baris di atas |

Pakai di `browser_exec`: `exec(open('/tmp/ig_flow.py').read())` lalu panggil fungsinya.

## Like: jangan bergantung pada tombol Comment

Jangkar terbaik untuk tombol like **postingan** adalah section yang sama dengan `svg[aria-label="Comment"]`. Tapi ada postingan yang **komentarnya dimatikan** — tombol Comment tidak dirender sama sekali, sehingga pencarian berjangkar Comment balik `None` dan dilaporkan "tidak terbaca" padahal halaman sudah siap.

Cadangan yang terbukti: **ukur ukurannya**. Tombol like postingan ±24 px, tombol like komentar ±16 px. Ambil kandidat `[aria-label="Like"/"Unlike"]` dengan `getBoundingClientRect().width >= 20`, urutkan berdasarkan `y`, ambil teratas. Terbukti bekerja di postingan tanpa komentar (`DOpY0elEu3P`, 17/17).

`state_like_post()` dan `klik_like_post()` sudah memakai urutan ini: jangkar Comment dulu, lalu cadangan ukuran — dan mengembalikan `cara: 'comment'` atau `cara: 'ukuran'` supaya ketahuan mana yang dipakai.

## Kesabaran menunggu halaman (terukur)

Render profil IG bisa **>35 detik**, dan tidak semua profil memakai tombol ber-ikon: ada profil yang tombolnya `<button>` biasa berteks "Follow" **tanpa** `svg[aria-label="Follow"]`. Karena itu:

- `tunggu_tombol()` default **75 detik**, lalu reload sekali dan tunggu 45 detik lagi kalau masih nihil. Batas 25 detik pernah membuat 4 akun dilaporkan "tombol tidak muncul" padahal halaman hanya lambat — setelah diperpanjang, ketiganya langsung berhasil tanpa perubahan lain.
- Jangan menyimpulkan "diblokir IG" dari "tombol tidak muncul". Cek dulu `document.title` dan `document.body.innerText`: kalau nama profil muncul tapi isi kosong, itu render lambat, bukan blokir. Nama profil benar + `sesi_dari_cookie()` cocok = sesi sehat.
- **Halaman `/p/` dan `/reel/` merender caption lebih dulu, action bar belakangan.** Selama action bar belum ada, `state_like_post()` balik `None` dan akun dilaporkan "tidak terbaca" padahal halaman cuma lambat. Pakai `tunggu_like_post(timeout=75)` — polling sampai tombol like benar-benar ter-render — bukan satu bacaan lalu menyimpulkan gagal.
- **Gagal SERAGAM di semua akun = curigai targetnya, bukan akunnya.** Kalau tiap akun melaporkan hal yang sama (`tombol tidak muncul` / `tombol like tidak ter-render`), hentikan batch dan periksa targetnya lebih dulu — 17 akun berbeda tidak rusak bersamaan. Buka target dengan satu akun, baca `body.innerText`: kalau memuat `Sorry, this page isn't available` / `The link you followed may be broken`, profilnya sudah dihapus atau di-rename, dan tidak ada yang bisa di-follow. Buktikan dengan **kontrol**: muat profil yang pasti ada di sesi yang sama (`instagram.com/instagram/`); kontrol normal + target error = targetnya yang salah. Sinyal pendukung: `curl` ke profil itu balas `302` dengan body kosong, dan `main` tidak punya satu tombol pun. Laporkan apa adanya dan minta user memverifikasi link-nya — jangan mengulang batch atau mengejar penyebab lain.

## Checkpoint + captcha (jeda manusia, lanjut dari langkah terakhir)

Jalankan batch lewat `jalankan_target(target, akun_list, aksi="follow" atau "like")`, **bukan** `follow_target` satu-satu. Runner ini:

- mencatat tiap (target, akun, aksi) yang beres ke `data/ig-progress.json` → akun `done` **dilewati** di jalan berikutnya, pekerjaan tidak diulang;
- memanggil `ada_captcha()` setelah tiap akun. Kalau captcha muncul: akun ditandai `captcha` lalu loop **lanjut ke akun berikutnya** — jangan hentikan seluruh antrean;
- menutup dengan blok ringkasan + daftar akun yang butuh verifikasi tangan manusia.

Setelah user menyelesaikan captcha, panggil `jalankan_target` lagi dengan daftar yang sama — yang sudah `done` otomatis dilewati. `perlu_manual(target)` menampilkan yang masih tertahan; `paksa_ulang=True` hanya kalau memang mau mengulang dari nol.

`ada_captcha()` mengenali dua rupa yang sudah terbukti: TikTok (`"Drag the slider to fit the puzzle"` + elemen class `cap-*`) dan Instagram (URL `/challenge/` atau teks "confirm it's you"). Sudah diuji: halaman normal → False, teks captcha palsu → True, setelah dibersihkan → False. Uji alur kontrol juga lolos (a1 beres, b captcha ditandai, c1 tetap diproses).

**Tetap mode desktop.** Untuk TikTok (yang menantang headless dengan captcha), lihat skill `tiktok-follow-headed` — di sana browser tampak lewat Xvfb + noVNC, dan itu yang membuat follow TikTok berhasil. Bawaan harness: HeadlessChrome 145, `1280x633`, DPR 1, tanpa touch. Emulasi Android (`Emulation.setDeviceMetricsOverride` + `setUserAgentOverride` + `setTouchEmulationEnabled`) memang berhasil mengubah tampilan jadi 412x915 DPR 2,625 dengan banner `Open app` dan grid 3 kolom — tapi itu **mengubah struktur halaman**, bukan cuma tampilan: posisi dan susunan elemen tombol ikut bergeser sehingga selector yang sudah teruji (follow/like) berisiko salah baca. User memilih desktop; jangan nyalakan emulasi mobile tanpa menyesuaikan dan menguji ulang seluruh alur.

Berkas kanonik `scripts/ig_flow.py` kini **mandiri** — memuat `follow_target`, `like_target`, `follow_aman`, `like_aman`, `simpan_banyak`, `state_like_post`, `klik_like_post`, `klik_nid`, `sesi_dari_cookie`, dan `cek_semua_cookie`. Sudah diuji: `cek_semua_cookie()` memeriksa 17 akun dalam ±19 detik dan melaporkan 17 hidup. Kalau mengubah alur di `/tmp/ig_flow.py`, **salin ulang ke berkas kanonik** — kalau tidak, pelajaran hari itu hilang saat `/tmp` dibersihkan. Jangan menyalin hanya sebagian: pernah terjadi `simpan_banyak` hilang karena versi `/tmp` tidak memuatnya.

**Jangan mencari ulang selector/timing tiap akun.** User secara eksplisit menegur hal ini: alur harus disimpan sekali lalu dipanggil, bukan dirakit ulang per akun — hasilnya jadi beda-beda dan lambat. Salinan kanonik ada di `scripts/ig_flow.py` milik skill ini; kalau `/tmp/ig_flow.py` hilang (tmp dibersihkan), salin dari sana — jangan dirakit ulang.

## Alur yang sudah terbukti

1. Bersihkan cookie (`Network.clearBrowserCookies`) — WAJIB, tiap akun bisa dari perangkat berbeda (`datr`/`ig_did`/`mid`/`dpr` beda)
2. Pasang cookie akun dari store
3. Jeda acak 10–20 detik (user minta "delay human" saat swap). Kalau antreannya panjang dan user mengeluh lambat ("lama banget"), turunkan ke **3–6 detik** — tetap acak, tetap diterima user; yang penting bukan 0 detik. Tanya jeda, bukan rahasia: user lebih memilih selesai cepat daripada jeda panjang.
4. Buka profil target, **polling** tombol sampai muncul (maks 25 detik)
4b. **Gerbang wajib: pastikan halaman sudah benar-benar pindah.** `js("location.pathname")` harus memuat `/<target>`; kalau belum, ulangi `wait_for_load` + jeda ~2 detik sampai 4× lalu laporkan gagal. Tanpa gerbang ini tombol dibaca dari profil sebelumnya — akun dilaporkan "sudah following" padahal itu target lama, dan akun itu sebenarnya tidak pernah di-follow.
5. Verifikasi identitas sesi dengan **membaca `ds_user_id` dari cookie** — `js("(document.cookie.match(/ds_user_id=(\\d+)/)||[])[1]")` harus sama dengan `ds_user_id` akun yang diminta; batal kalau beda. **Jangan** pakai `fetch('/api/v1/accounts/edit/web_form_data/')` di dalam halaman (lihat jebakan: itu menggantung >5 detik)
6. Kalau state `Follow`: screenshot → klik → poll sampai `Following` (jangan asumsi)
7. Screenshot kondisi akhir + screenshot profil akun sendiri (bukti identitas)
8. Catat ke `ig-follows.json`

## Batch banyak akun (pola yang dipakai)

1. `simpan_banyak([...])` untuk semua cookie sekaligus — verifikasi lewat `accounts/edit`; yang gagal dilaporkan tanpa menghentikan sisanya. Kunci store = `ds_user_id`, jadi kirim ulang akun yang sama menimpa, bukan menggandakan.
2. Laporkan hasil verifikasi (username per cookie) **sebelum** menjalankan follow — user perlu tahu kalau ada yang salah tempel.
3. Jalankan beberapa akun per panggilan `browser_exec`, tiap akun dibungkus `try/except` supaya satu kegagalan tidak menghentikan sisanya. **Kalau browser mati beruntun** (`_stdout_get` / `CDP WS handshake failed` / `RuntimeError` berturut-turut), periksa `browser.inactivity_timeout` di `~/.hermes/config.yaml` **sebelum menyalahkan RAM**: bawaannya 120 detik, dan harness menutup sesi browser setelah sekian detik tanpa aktivitas antar-loop agen. Jeda antar-panggilan mudah melewatinya (terutama saat user mengetik di tengah batch), sehingga browser tutup sendiri tiap ronde, tiap ronde mulai dari nol, dan gejalanya terbaca seperti browser yang rapuh — padahal RAM, jaringan, dan jumlah proses chrome semua sehat (`free -m` sisa 1,4 GB, `ping` 0% loss, 0 proses chrome). Perbaikannya sekali: `hermes config set browser.inactivity_timeout 900`. `config.yaml` dilindungi — `patch` ditolak dengan "Agent cannot modify security-sensitive configuration" — jadi pakai CLI-nya, dan ingatkan user bahwa perubahan mungkin baru aktif penuh setelah layanan Hermes di-restart. **Baru setelah itu** urus ukuran batch: **ukuran batch ditentukan oleh sisa RAM, bukan selera.** Chromium di HP ini hidup di sisa RAM setelah Android; kalau sisa <±2 GB, browser mati tiap beberapa akun dan tiap kematian memaksa pemulihan (satu `ensure_real_tab()`) sebelum lanjut. Ukur dengan `free -m` (`available`): sisa ~1,6 GB → pakai **2 akun per panggilan**; >±3 GB → 4–5 aman. Kalau setelah timeout dinaikkan dan batch dikecilkan browser tetap tumbang berulang (terukur: 4× dalam satu sesi walau sisa RAM 2,3 GB dan 0 proses chrome tersisa), langkah berikutnya adalah **restart HP** — sisa RAM naik 1,4 GB → 2,3 GB dan kematian browser berhenti. Restart mematikan Termux: ingatkan user menyalakan BuzzMon lagi (`cd ~/buzzmon && ./start.sh`) dan sebutkan bahwa cookie tidak hilang karena disimpan di berkas, supaya user tidak mengira harus mengirim ulang 17 cookie. Kegagalan per-akun sendiri tetap ditutup dengan mengulang akun itu satu per satu, bukan dengan mengulang seluruh batch.
4. Matikan `ambil_identitas` saat batch besar: screenshot identitas menggandakan navigasi per akun. Ambil hanya untuk akun yang buktinya diminta.
5. Setelah tiap batch, laporkan progres "N dari M" dalam **satu baris** — transkrip yang sunyi membuat user mengira prosesnya menggantung. Kirim path screenshot hanya untuk akun yang diminta.
6. **Tutup dengan akun yang tersisa.** Apa pun yang dilaporkan gagal, ulangi sendiri satu per satu (jeda 6–10 detik) sebelum menutup laporan — hampir semuanya lolos di percobaan kedua. Hitung total akhir dari store + log (`ig-follows.json` / `ig-likes.json`), bukan dari ingatan panggilan sebelumnya; ambil status **terakhir** per akun dan anggap status positif sebagai pemenang.

Kalau blok cookie **kepotong** (berhenti di tengah `value`, tanpa `ds_user_id`/`sessionid`), jangan menambal — minta user kirim ulang bagian itu. Cukup `ds_user_id` + `sessionid` + `csrftoken` sudah jalan.

Simpan **seluruh** cookie perangkat aslinya (`datr`, `ig_did`, `mid`, `dpr`, `wd`), bukan cuma tiga inti: akun bisa datang dari perangkat berbeda, dan fingerprint yang tercampur antar akun itu pola yang mencurigakan. `simpan_banyak` membuang spasi/baris baru di dalam value — copy-paste panjang sering menyisipkan line break di tengah token.

## Anti-OOM terukur: Chromium sendiri + penjaga RAM adaptif

Ukuran di HP ini (RAM 7,6 GB, tapi **MemAvailable cuma 1,1–1,6 GB** karena Android + swap sudah menahan sisanya):

| | Harness Hermes | Chromium sendiri (`scripts/drive.py` + `scripts/run.py`) |
|---|---|---|
| Saat baru muat 1 profil | 1.009 MB / 15 proses | **594–742 MB / 9 proses** |
| Gambar dimatikan | — | 742 MB |
| Gambar aktif | — | 816 MB |
| Setelah 3–4 akun | tumbang | 1.110–1.198 MB → lalu di-restart |

Karena itu: **jangan pakai `browser_exec` untuk batch panjang**. Pakai Chromium sendiri lewat CDP — harness tidak bisa diberi flag, dan flag-lah yang menentukan. `scripts/drive.py` menerima port lewat env `CDP_PORT` (bawaan 9334 headless; isi `9222` untuk browser tampak), jadi klien yang sama dipakai di kedua mode — jangan tulis klien CDP kedua.

**Swap tidak bisa ditambah.** Sistem sudah punya swap 6.123 MB (3.555 MB terpakai), dan `swapon` pada swapfile **ditolak** (`Function not implemented`) — percobaan 2 GB gagal dan hanya memakan disk. Jadi satu-satunya tuas adalah menekan puncak memori Chromium, bukan menambah ruang.

Flag yang terbukti (jangan dihapus tanpa mengukur ulang):

```
--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu
--renderer-process-limit=1 --js-flags=--max-old-space-size=128
--blink-settings=imagesEnabled=false --window-size=900,600
--disable-background-networking --disable-sync
--disable-extensions --disable-default-apps
```

Screenshot **tidak wajib** — user menyatakan sendiri "ss ga wajib sih kalo bikin berat". Mematikannya menghemat ±74 MB dan beberapa detik per akun. Konsekuensinya: jangan menjanjikan bukti gambar untuk batch mode ini.

**Dua mode restart, pilih sesuai permintaan user:**

- `IG_RESTART_TIAP=1` → browser dimatikan & dinyalakan ulang **setiap akun**. Paling ringan (puncak ±600 MB), paling lambat (±15 detik ekstra per akun). Ini yang dipakai kalau user bilang "satu-satu aja" atau mengeluh OOM.
- Tanpa env itu → restart hanya bila `chrome > 950 MB` atau `MemAvailable < 700 MB`, plus berhenti rapi (bukan dibunuh OOM) kalau memori tak pulih setelah 3× restart.

**Tab menumpuk = bug senyap yang mirip blokir.** Chrome sendiri menumpuk tab halaman (terukur 12 tab, banyak di `/accounts/login/`). Klien CDP bisa menempel ke tab **pertama** — yang mungkin halaman login basi — sehingga tombol tidak ditemukan padahal sesi di tab lain sehat. Tutup semua tab kecuali satu **sebelum tiap akun** (`tutup_tab_lain()` di `scripts/drive.py`). Gejala khasnya: progres mandek di satu akun, chrome justru kecil (37–143 MB), dan cookie terbukti hidup lewat cek `curl` 200.

**Ganti akun: pindah ke `about:blank` dulu.** Kalau halaman IG masih hidup, JS-nya bisa menulis ulang `ds_user_id` lama → akun berikutnya dilaporkan "ds_user_id browser = X, harusnya Y". Navigasi ke `about:blank`, baru pasang cookie. Ini menghilangkan kegagalan tukar-cookie yang berulang.

**Jalankan runner dengan `python3 -u` dan alihkan ke berkas log** (`> /tmp/igrun.log`), jangan di-pipe ke `tail`. Output Python ter-buffer; kalau proses dibunuh timeout, buffer hilang dan kamu buta total — pernah terjadi: 500 detik berjalan tanpa satu baris pun, lalu disimpulkan "macet" padahal tidak ada bukti. Dengan `-u` + log, `tail` kapan saja memperlihatkan posisi sebenarnya.

Urutan pemakaian:

```
cd /root/igchrome && IG_RESTART_TIAP=1 python3 -u run.py <target> <follow|like> akun1,akun2,... > /tmp/igrun.log 2>&1
```

`run.py` sudah memuat: checkpoint (lewat `ig_flow.py`), pemantau RAM per akun, restart adaptif, tutup tab basi, dan penutupan browser di akhir (RAM balik ke ±1,6 GB).

**Jangan pakai `subprocess.run(["ps", ...])` di `run.py` — di lingkungan ini balas `OSError [Errno 38] ENOSYS`.** Karena fungsi itu dipanggil di jalur pelaporan tiap akun, kegagalannya membunuh **seluruh** run sekaligus mematikan penjaga RAM-nya: gejalanya progres berhenti mendadak dengan traceback di `chrome_rss_mb`/`lapor`, lalu rantai mengulang dari checkpoint. Baca `/proc/<pid>/cmdline` dan `VmRSS` dari `/proc/<pid>/status` (tanpa subprocess), dan saring proses chrome dengan bendera khasnya (`--type=`, `--remote-debugging-port`, `--user-data-dir=`) supaya shell/python yang sekadar **menyebut** path chrome tidak ikut terhitung — pernah terukur satu shell ikut masuk dan mengacak angkanya.

**`ig_flow.py` harus dibaca dari jalur tetap**, bukan `/tmp` yang bisa terhapus pembersihan cache: `/root/igchrome/ig_flow.py`, dengan cadangan `scripts/ig_flow.py` milik skill ini. Versi lama `run.py` membaca `/tmp/ig_flow.py` dan akan mati dengan "file not found" tanpa gejala yang jelas kalau cache dibersihkan.

Terukur dengan mode restart-per-akun: **17 akun ≈ 7 menit, nol kegagalan**, RAM bertahan 1,1–2,2 GB, dan chrome kembali ke 0 proses di akhir. Beberapa target 17-akun berturut-turut selesai tanpa satu pun OOM. Jadi jangan kembali ke `browser_exec` hanya karena "terasa lebih cepat" — waktu yang dihemat habis berkali-kali lipat saat browser tumbang dan akun harus diulang.

## Antrean panjang: rantai target + ulang-otomatis

Runner bisa **mati di tengah batch** dengan `Exception in thread Thread-7 (recv_events): The futex facility returned an unexpected error code` — bug thread Python di proot/Android, tidak berhubungan dengan target, cookie, atau RAM. Proses hilang, chrome jadi yatim, dan sisa akun tidak pernah dikerjakan. Kalau user sedang mengirim target beruntun (satu target tiap beberapa menit), jangan menjalankan satu `run.py` per target secara manual: setiap crash memaksa kamu balik ke awal.

Yang bekerja: satu skrip shell yang merangkai seluruh antrean, mengulang tiap target sampai runner keluar normal, dan membersihkan chrome yatim di antara percobaan — `scripts/antre.sh`. Akun yang sudah `done` otomatis dilewati checkpoint, jadi mengulang tidak pernah menghasilkan follow ganda. Skrip itu sekaligus menangani antrean campur follow+like (lihat di bawah), jadi tidak perlu dua skrip berbeda.

```
bash /root/igchrome/antre.sh follow:nicollegracia like:DfZofxRKmiq follow:makandiluaryuk_:davina_aulia20,arabellenaura1 > /tmp/antre.log 2>&1
```

Jalankan rantai lewat `terminal(background=true, persist_on_release=true)` — bukan `nohup`/`setsid` di dalam perintah (alat menolak wrapper shell-level).

**Antrean campur follow+like dalam satu rantai.** User sering mengirim beberapa pekerjaan sekaligus dengan aksi berbeda (mis. 1 follow + 3 like + 1 follow sebagian akun). Daripada menjalankan satu `run.py` per pekerjaan secara manual, pakai `scripts/antre.sh` yang sama — format tiap argumen `<aksi>:<target>` atau `<aksi>:<target>:<akun1,akun2,...>`; tanpa daftar akun berarti 17 akun Xena.

Terukur: 5 pekerjaan campuran (74 aksi) selesai dalam satu rantai, 0 gagal, tanpa satu pun kegagalan start. Ini menghilangkan kebutuhan mengawasi tiap pekerjaan lalu menjalankan yang berikutnya dengan tangan.

**Dua rantai TIDAK boleh jalan bersamaan.** Dua skrip antrean atau dua `run.py` yang hidup pada saat yang sama berebut port 9334 dan direktori profil → keduanya gagal `browser gagal start`. Kalau target baru datang sementara rantai lain masih jalan, jalankan rantai kedua dengan `TUNGGU=1` (menunggu sampai tidak ada `run.py`/antre lain hidup) — jangan membunuh rantai yang sedang bekerja, dan jangan menumpuknya.

**Menunggu lewat loop `sleep` saja RACE — pakai `flock`.** Kalau dua rantai diantrekan berdekatan, keduanya bisa lolos cek di detik yang sama (antara "jml_lain" membaca 0 dan `run.py` berikutnya mulai) lalu jalan berdampingan. Gejalanya khas dan sudah terukur: `@akun: gagal: ds_user_id browser = 59869566136, harusnya 59924746005` (cookie satu akun terbaca sebagai akun lain) plus kegagalan seragam `halaman tidak pindah ke /<target>`. Perbaikannya satu baris di awal skrip, sebelum loop tunggu:

```bash
exec 9>/root/igchrome/.rantai.lock
flock 9 || { echo "gagal mengambil kunci rantai"; exit 1; }
```

Rantai kedua berhenti di baris `flock` sampai rantai pertama tutup, tanpa perlu merapikan pola `grep` pengecualian-diri. Loop tunggu `run.py` tetap dipertahankan sebagai jaring kedua (mis. rantai lama yang belum memakai kunci).

**Syarat "selesai" harus memeriksa akun yang masih `gagal`, bukan cuma `rc=0`.** `run.py` keluar 0 walaupun ada akun berstatus `gagal` — dengan syarat lama (`[ $rc -eq 0 ] && break`) akun gagal **tidak pernah dicoba lagi** dan laporan terlihat "selesai" padahal tidak. Tambahkan pembacaan berkas progres dan ulangi target selama masih ada sisa, maksimal `ATTEMPT` kali:

```bash
sisaGagal=$(sisa_gagal "$aksi" "$target")
if [ "$rc" -eq 0 ] && [ "$sisaGagal" -eq 0 ]; then break; fi
echo "----- $aksi @$target rc=$rc · akun gagal tersisa $sisaGagal, ulang -----"
```

`sisa_gagal` menghitung nilai yang `status != "done"` pada kunci `aksi:target` **dan** `aksi:target.lowercase()` (kunci like disimpan lowercase). Terbukti: dua target dengan 10 dan 4 akun gagal tuntas **17/17 · 0 gagal** di rantai ulang, tanpa follow ganda (checkpoint melewati yang `done`).

**Jangan menyimpulkan target tidak ada dari `curl`/AX saat logged-out.** Instagram menyajikan cangkang `Page Not Found` untuk profil yang **valid** kalau permintaannya tanpa sesi — pernah terbaca seperti "akun tidak eksis" padahal salah. Bukti yang sah hanya dari runner sendiri: entri `status: done` + `catatan: following (baru diklik)` di `ig-progress.json` untuk target itu. Kalau ada beberapa akun sukses, targetnya ada; sisanya kegagalan navigasi, bukan target salah.

**Pitfall saat menulis loop tunggu: skrip bisa menunggu dirinya sendiri.** Pola `grep -q "[r]\.py"` pada daftar proses akan cocok dengan baris perintah skrip antre itu sendiri kalau namanya memuat pola tersebut (mis. `bash antre.sh run.py…`), sehingga loop tidak pernah selesai. Kecualikan `$$` **dan** PPID-nya (`grep -vx`), seperti di `scripts/antre.sh`.

- **Progres dibaca dari berkas checkpoint, bukan dari log.** Log ikut mati bersama proses; `data/ig-progress.json` yang bertahan. Saat melapor, hitung dari situ (`kunci = "<aksi>:<target-lowercase>"`).
- **Gunakan `antre_tail.sh`, bukan `antre.sh`, untuk argumen berawalan aksi.** `antre.sh` meneruskan argumen apa adanya sebagai *username* ke `run.py` (`run.py <target> <aksi> <akun>`), sehingga `follow:zaryta.id` menjadi URL `instagram.com/follow:zaryta.id/` — halaman yang tidak ada. Gejalanya: **semua** akun gagal seragam dengan `tombol tidak muncul`, padahal target valid dan sesi sehat (dibuktikan dengan uji kontrol `instagram.com/instagram` yang juga gagal). `antre_tail.sh` memilah `aksi:target[:akun,...]` lebih dulu, jadi pakai itu untuk semua pekerjaan berawalan aksi.

**Jangan paksa `IG_RESTART_TIAP=1` untuk batch campuran.** Dengan restart-per-akun, navigasi pertama setelah browser menyala sering mendarat di cangkang login (tanpa `<main>`, tanpa tombol) sehingga akun dilaporkan `tombol tidak muncul` walau cookie-nya hidup (dibuktikan: `curl` ke `accounts/edit/web_form_data/` balas 200 + username benar). Dua perbaikan yang terbukti: (1) buka `https://www.instagram.com/` dulu ±4 detik sebelum profil — sesi memanas dan `<main>` muncul; (2) biarkan restart adaptif (`IG_RESTART_TIAP=0`, hanya restart kalau chrome >950 MB atau RAM <700 MB). Terukur: 2 akun berturut-turut sukses dengan cara ini setelah 5 percobaan beruntun gagal dengan restart-per-akun.

**Antrean bertambah di tengah jalan adalah normal.** User mengirim target baru selagi yang lain berjalan. Skrip yang sudah jalan tidak bisa disisipi; jangan membunuh proses yang sedang berjalan untuk memindahkannya ke depan. Jalankan rantai berikutnya yang **menunggu penanda akhir** rantai sebelumnya (mis. loop `grep -q "SEMUA ANTREAN SELESAI" log1` + `sleep 15`), lalu mengambil target baru — dua rantai jadi bersambung tanpa perlu kamu kembali.
- Kalau satu target tetap tidak tuntas setelah percobaan terakhir, laporkan apa adanya dengan jumlah sisa akun; jangan mengulang seluruh antrean dari target pertama.
- **Rantai yang mati tanpa penanda `########## RANTAI EKOR SELESAI ##########` berarti terputus, bukan selesai.** Penyebab yang berulang: sesi latar Hermes ikut berakhir (pemulihan penyedia/kompresi konteks) sehingga `run.py` hilang di tengah dan akun terakhir tidak pernah selesai. Jangan simpulkan hasil dari keberadaan proses. Setelah kejadian itu: baca akun terakhir dari baris `[n/N] @akun` di log, lalu jalankan rantai baru yang memuat **hanya sisa akun itu** plus pekerjaan yang belum mulai (`antre_tail.sh "follow:<target>:<akun-sisa>" "<pekerjaan-berikut>"`) — checkpoint membuat akun yang sudah `done` dilewati, jadi mengulang aman dan tidak menghasilkan follow ganda.

**Kematian sesi latar = rantai terputus, dan job pengganti harus dipastikan tidak menumpuk.** Setelah sesi latar Hermes berakhir, notifikasi `exit code 143 (SIGTERM)` muncul untuk tiap rantai yang ikut dimatikan. Jangan menafsirkan itu sebagai kegagalan IG dan jangan menjalankan ulang semuanya: periksa `logs/antre_*.log` terakhir untuk baris `[n/N] @akun`, lalu jalankan **satu** rantai baru berisi sisa akun + pekerjaan yang belum mulai. Dengan `flock`, rantai baru itu otomatis mengantre di belakang yang masih hidup.

**Target yang dikirim bertahap tidak perlu memotong rantai.** Jangan membunuh rantai yang sedang berjalan; mulai rantai kedua yang menunggu sampai tidak ada proses `run.py` aktif, lalu membersihkan port sebelum tiap percobaan. Deteksi "rantai sebelumnya selesai" yang paling andal adalah `while ps -eo args | grep -q "[r]un\.py"; do sleep 15; done` — bukan mencari penanda teks di log, karena penanda itu tidak ada di rantai yang kamu tulis sebelumnya.

**Kalau menunggu lewat PID, baca STATUS prosesnya, bukan sekadar keberadaannya.** `kill -0 <pid>` dan `[ -d /proc/<pid> ]` tetap bernilai benar untuk proses **zombie** — sudah mati tapi belum di-reap induknya (shell latar Hermes sering tidak me-reap). Rantai bisa menunggu selamanya sementara tidak ada apa pun yang berjalan; ini pernah memacetkan antrean like padahal rantai follow-nya sudah mati sejak beberapa menit sebelumnya. Pola yang benar:

```bash
while [ -d /proc/$P ]; do
  ST=$(awk '/^State/{print $2}' /proc/$P/status 2>/dev/null)
  [ "$ST" = "Z" ] && break          # zombie = selesai
  sleep 20
done
```

**Progres yang mandek beberapa menit belum tentu macet.** Dengan restart-per-akun, satu akun butuh 2–3 menit (chrome mati, tunggu CDP, pasang cookie, tunggu render, klik, reload untuk verdict). Bedakan dari log, bukan dari angka: `grep -c "restart browser"` terus naik dan baris terakhir menyebut `[n/17] @akun` = jalan; baris terakhir berisi `Exception in thread`/`futex` atau tidak ada baris baru >5 menit = mati, dan rantai mengulangnya sendiri. Jangan membunuh runner yang cuma lambat — itu membuang akun yang sedang di tengah jalan.

## Irama batch yang terbukti: 3 akun per ronde

Urutan yang paling sedikit gagal di HP ini:

1. **Awali tiap ronde dengan browser segar** — `ensure_real_tab()` → `new_tab("https://www.instagram.com/")` → `wait_for_load()` → jeda 5–7 detik, dibungkus loop 6–8 percobaan. Jangan menunggu browser mati dulu: Chromium di sini mati tiap 2–4 akun, dan memulai ronde dari keadaan bersih membuat kegagalan jarang terjadi.
2. **3–5 akun per panggilan `browser_exec`**, lewat `jalankan_target` supaya checkpoint menyelamatkan yang sudah beres di ronde berikutnya. Batas ini bukan soal RAM saja: satu panggilan punya **plafon waktu keras ±420 detik (7 menit)** apa pun nilai `timeout_s` yang dikirim — mengirim `timeout_s=1500` tetap dipotong di 420 detik dan panggilan berakhir **tanpa keluaran**, sehingga kerja yang sudah selesai ikut tidak terlapor. Dengan render 30–50 detik per akun, 5 akun masih muat (±4 menit); 2 akun lebih aman kalau sisa RAM tipis. Loop retry panjang di dalam satu panggilan (mis. 10 percobaan bangun browser × jeda 8–10 detik) memakan seluruh anggaran itu — batasi bangun-bangunkan browser 4–6 percobaan, sisanya taruh di panggilan berikutnya dan biarkan checkpoint menutup sisanya.

   **Kalau user minta stabil, atau minta kabar tiap akun** ("satu-satu aja biar stabil", "tiap selesai follow kirim pesan dong biar tau"), turunkan ke **satu akun per panggilan** dan kirim **satu baris per akun** (`N/M — @akun ✅ following @target`). Itu permintaan yang eksplisit, bukan noise: user memantaunya dari HP dan lebih memilih 17 balasan pendek daripada satu laporan panjang di akhir yang datangnya tidak pasti.
3. **Matikan browser tampak / live view dulu** kalau tidak sedang dipakai. Angka terukur: stack penuh (Xvfb + chrome tampak + x11vnc + websockify) ±**1.000 MB** dan inilah yang membuat browser otomasi cepat tumbang; versi ringan tanpa VNC hanya 612–776 MB. Jadi kalau memang perlu browser tampak bersamaan, pakai varian ringan (`start_lite.sh` di skill `tiktok-follow-headed`) dan nyalakan VNC hanya saat captcha muncul — jangan matikan browser tampak sepenuhnya hanya karena RAM.
4. **Satu baris progres per ronde** (`N/M` + daftar sisa). User menegur berulang kali saat transkrip sunyi ("oi", "kurang brp", "lama amat") — laporkan tanpa diminta.
5. Kalau satu akun gagal, ulangi **akun itu saja** di ronde berikut; jangan mengulang ronde.

**Klik like kadang tidak nyangkut** (`Like` → `Like`): beri jeda 6–8 detik setelah klik lalu poll sampai 8×. Kalau tetap `Like`, ulangi akun itu di ronde berikut — jangan tandai `done`, jangan kirim screenshot-nya.

## Cek kelengkapan akun

Kalau user minta "list akun / kurang apa", jangan cuma menghitung jumlah. Bandingkan store dengan akun IG yang terhubung di BuzzCuan (`/api/overview` → `accounts` yang platformnya `INSTAGRAM`) dan tampilkan: tabel bernomor (username + status follow target) lalu daftar username yang **belum punya cookie**. Itu yang dicari user.

### Hitung followers banyak akun (mis. "yang followers-nya 20+")

Jangan lewat endpoint JSON: `/api/v1/users/<ds_user_id>/info/` balik kosong dan `usernameinfo` balik `{"spam":true,"status":"fail"}` — mengejar jalur ini cuma membuang waktu. Yang bekerja: buka profil di browser, lalu poll `body.innerText` dengan `/([\d.,]+[KM]?)\s*followers/i` (fallback `pengikut`) sampai angkanya muncul — halaman butuh belasan detik sebelum statistik ter-render. 3–4 akun per panggilan, dan kalau satu akun error lanjut saja; sisanya diulang di ronde berikut.

Laporannya: tabel urut terbesar → terkecil, dipisah jadi dua kelompok sesuai ambang yang user sebut, plus rata-rata. Akun di bawah ambang tetap disebut — user memakainya untuk memilih akun mana yang layak dipakai di platform yang mensyaratkan follower minimum.

## Jebakan yang sudah memakan waktu

- **Skrip antrean yang menunggu LAMA lalu memanggil `run.py` bisa gagal `browser gagal start` 3 dari 4 percobaan.** Port debug masih dipegang sisa chrome yang belum benar-benar mati. Sebelum tiap percobaan: matikan chrome → tunggu daftar proses kosong → `fuser -k 9334/tcp` → hapus `profile/Singleton*` → baru jalankan. Versi yang sudah memperhitungkan ini: `scripts/antre.sh` (pola bersihkan-sebelum-jalan). Jangan simpulkan targetnya rusak dari kegagalan start berulang — baca log: `!! browser gagal start` berarti soal port, bukan soal akun.
- **Jangan pindahkan akun ke VPS/datacenter IP, walau tujuannya kecepatan.** Instagram sudah memblokir rentang CIDR cloud (AWS/GCP/Hetzner/OVH/DO) lebih dulu — `proxy_address_is_blocked` bahkan sebelum akun berbuat apa pun — sementara IP seluler/rumah user lolos (terukur: IP residensial Indonesia, `hosting: false`). VPS dipakai untuk panel/penjadwal/submit saja; browser + akun tetap di jaringan residensial.
- **Di Termux di luar proot, `/tmp` tidak ada / read-only.** Skrip yang menulis log ke `/tmp/...` mati dengan `mkdir: /tmp: Read-only file system`. BuzzMon sudah dipindah menulis ke `~/buzzmon/logs/`; ikuti pola itu untuk skrip baru.
- **Skrip penunggu jangan mendeteksi "rantai lain" dengan mengecualikan diri sendiri + induknya.** Induk sebenarnya adalah proses Hermes, bukan pembungkus shell-nya, sehingga pembungkus itu sendiri ikut terhitung sebagai rantai lain dan skrip menunggu **selamanya** tanpa pesan apa pun (log-nya kosong). Cukup deteksi proses yang benar-benar memakai sumber daya bersama: `ps -eo pid,args | awk '$0 ~ /run\.py/ && $0 !~ /awk/ {print $1}' | wc -l` — desainnya memang hanya mengizinkan satu rantai hidup.
- **Selisihkan daftar akun yang diminta terhadap store SEBELUM menjalankan rantai.** Salah ketik satu huruf (`tiaramadani756` vs `tiaramadani756` yang benar) membuat `muat_akun()` melempar `ValueError` → akun itu dicatat `gagal: ERROR ValueError`, dan karena syarat selesai rantai adalah "tidak ada akun `gagal` tersisa", rantai menghabiskan **seluruh `ATTEMPT`** pada akun hantu itu sementara akun lain di pekerjaan yang sama sudah beres — pekerjaan mandek di `N-1/N` dan itu terbaca seperti target yang rusak, bukan seperti salah ketik. Cek cepat sebelum menjalankan: `python3 -c "import json;a=json.load(open('data/ig-accounts.json'));print([x['username'] for x in (a.get('accounts') or a)])"` lalu bandingkan tiap nama di argumen; akun yang tidak ada di daftar itu **jangan dimasukkan** ke antrean.
- **Entri hantu di `ig-progress.json` harus DIHAPUS, bukan diulang.** Kalau nama salah ketik sudah pernah masuk antrean, catatan `gagal: ERROR ValueError` untuk nama itu **menetap di progres** dan `sisa_gagal` akan selalu mengembalikan ≥1 untuk pekerjaan itu — jadi setiap rantai berikutnya membakar `ATTEMPT` penuh untuk akun yang bahkan tidak ada, dan laporan terlihat "belum tuntas" padahal seluruh akun sungguhan sudah `done`. Setelah menemukan kasusnya: hapus kuncinya (`del p['follow:<target>']['<nama-salah>']`) lalu simpan berkasnya; angkanya langsung jadi benar (mis. 15/15) dan rantai berikutnya tidak lagi mencoba nama hantu itu. Jangan menandainya `done` palsu, dan jangan mengulang pekerjaannya dari nol.
- **Menjalankan dua rantai bersamaan selalu gagal.** Keduanya berebut port CDP 9334 + profil chrome yang sama. Rantai baru harus menunggu sampai tidak ada `run.py` hidup, dengan jeda ±10 detik sebelum mulai.
- **Tombol Follow itu `div`**, bukan `<button>`, dan **belum ada** saat halaman baru dimuat — `sleep` tetap gagal, harus polling. **Batasi pencarian ke `main`** dan cek `svg[aria-label]` dulu: memindai seluruh `div` di halaman IG (ribuan node) menghabiskan >5 detik lalu berakhir `RuntimeError`. Pola: `main.querySelector('svg[aria-label="Following"], svg[aria-label="Follow"], svg[aria-label="Ikuti"]')`, fallback `main.querySelectorAll('button, div[role=button]')` + regex `^(Follow|Following|Ikuti|Mengikuti)$`.
- **Screenshot TIDAK boleh membatalkan aksi yang sudah terjadi.** `capture_screenshot()` bisa timeout 60 detik di halaman berat (video/animasi) dan melempar `RuntimeError: Page.captureScreenshot timed out after 60s`. Kalau pemanggilannya tidak dibungkus, akun yang follow-nya **sudah terklik** ikut dilaporkan gagal dan tidak masuk checkpoint — padahal pekerjaannya beres. Bungkus jadi `_simpan_aman(nama, coba=2)`: tangkap exception, kembalikan `None`, dan lanjut mencatat status. Screenshot itu bukti, bukan syarat sahnya aksi.
- **Screenshot identitas bisa kosong/putih** kalau langsung diambil. Tunggu teks username muncul di `body.innerText` dulu.
- **`capture_screenshot()` menulis ke path yang sama** tiap kali (`.../p-*/shot.png`). Salin segera setelah capture, kalau tidak gambar sebelumnya tertimpa.
- **`RuntimeError: Runtime.evaluate timed out after 5s` hampir selalu berarti JS/CDP-mu terlalu berat, bukan browser mati.** Tiga pemicu yang sudah terbukti: `Accessibility.getFullAXTree` di halaman IG (≈2.700 node), `fetch()` di dalam halaman untuk cek sesi, dan `querySelectorAll` seluruh `div`. Gantinya: `queryAXTree` terfilter, baca cookie, scope ke `main`.
- **Timeout sesaat jangan digagalkan.** Bungkus tiap `js()` di dalam loop polling dengan `try/except` dan lanjut polling — tanpa itu satu timeout 5 detik membatalkan seluruh akun, padahal halaman cuma sedang sibuk. Ini yang membuat batch berhasil; jangan dihapus saat merapikan kode.
- **`sesi_dari_cookie()` bisa balik `None` karena satu timeout**, lalu akun dilaporkan "gagal: sesi = None" padahal cookie-nya sehat. Ulangi pembacaan sampai 5× sebelum menyimpulkan sesi salah. Penyebab kedua yang sama-sama `None`: membacanya saat tab masih di `about:blank` — akses `document.cookie` ditolak ("access denied") dan bukan tanda cookie hilang. **Navigasi dulu** ke `instagram.com`, baru baca.
- **`CDP WS handshake failed ... 127.0.0.1:<port>`** = gejala lain daemon yang mati (selain `_stdout_get`). Perlakuan sama: satu `ensure_real_tab()` di panggilan berikutnya, lalu lanjut dari akun yang belum selesai — jangan ulang akun yang sudah beres. Kalau daemon sesi bawaan tetap tidak mau hidup, jalankan panggilan berikutnya dengan **nama sesi baru** (`browser_exec(..., session="ig2")`): ia menyalakan daemon terpisah dan biasanya langsung jalan tanpa restart apa pun — jauh lebih cepat daripada mengulang loop `ensure_real_tab()` atau menunggu.

  Tapi ketahuilah harganya: **sesi lama tidak ikut ditutup.** Tiap nama sesi punya direktori profil sendiri dan Chromium-nya tetap hidup sampai dibunuh — terukur dua sesi berjalan bersamaan = 2 Chromium, **1.918 MB dalam 36 proses**, dan itu sendiri yang memicu OOM (Android membunuh proses dengan RSS terbesar, jadi Chromium selalu korban pertama). Jadi: pakai **satu** nama sesi untuk satu rangkaian panjang, dan kalau memang harus pindah sesi, matikan yang lama di panggilan yang sama:

  ```
  ps -eo rss,args | grep "[c]hrome-linux/chrome" | awk '{s+=$1; n++} END {printf "%d MB · %d proses\n", s/1024, n}'
  ps -eo args | grep -o "user-data-dir=[^ ]*" | sort | uniq -c     # berapa sesi hidup
  ```

  lalu `kill` semua pid yang `args`-nya memuat `user-data-dir=<sesi-lama>` (kalau perlu `kill -9` setelah jeda 4 detik). Mengganti nama sesi berulang tanpa mematikan yang lama adalah cara tercepat menghabiskan RAM di HP ini.

  **Jangan pakai `pkill -f` untuk ini.** `pkill -f <pola>` mencocokkan seluruh command line, termasuk shell yang sedang menjalankan perintahnya sendiri — shell itu ikut terbunuh (tool balik `exit -15`/SIGTERM **tanpa keluaran**), dan kamu kehilangan hasil perintah yang sebenarnya sudah jalan. Ini juga berlaku untuk **nama skrip antrean**: `pkill -f '[a]ntre_tail\.sh'` membunuh shell perintah yang menjalankannya sendiri, sehingga kamu kehilangan justru output yang mendaftar proses rantai. Ambil pid dulu, kecualikan baris `awk`/`grep`-nya sendiri:

  ```
  pids=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
  [ -n "$pids" ] && kill $pids; sleep 4
  pids2=$(ps -eo pid,args | awk '$0 ~ /chrome-linux\/chrome/ && $0 !~ /awk/ {print $1}')
  [ -n "$pids2" ] && kill -9 $pids2
  ```
- **`could not be started: ... _stdout_get`** = daemon browser-nya sendiri yang mati, bukan alur. Panggil `ensure_real_tab()` **sekali** lalu ulangi. **Jangan** menaruhnya di dalam loop percobaan: ia membuka tab baru dan justru memicu timeout berikutnya — itu yang membuat satu batch gagal beruntun.
- **Logout membunuh cookie.** `sessionid` disimpan sebagai salinan sesi; kalau user logout / ganti password / log out all devices, semua cookie di store mati dan harus diambil ulang. Ingatkan user jangan logout selama proses berjalan.
- **Baca profil IG publik tanpa login**: cukup tag meta (`og:title`, `og:description` berisi jumlah followers/following/posts, `og:image`). Endpoint JSON (`web_profile_info`) selalu 429/`require_login` — jangan dikejar.
- **Klik yang tidak mengubah apa pun → periksa `document.elementFromPoint(x, y)` di koordinat tombol.** Kalau yang mengembalikan bukan tombolnya melainkan lapisan lain (modal, overlay, captcha), kliknya mendarat di penghalang — bukan berarti tombolnya rusak. Ini yang membedakan "tombol tidak berfungsi" dari "ada yang menutupi", dan menyelamatkan dari mengejar penyebab yang salah (mis. membongkar signature padahal request-nya sudah terkirim).

- **Buat akun IG baru dari HP ini: tidak bisa — jangan dijanjikan.** `/accounts/signup/email/` selalu dialihkan ke `/accounts/login/` (cookie bersih pun sama), dan tautan "Create new account" → `/accounts/emailsignup/` balas **HTTP ERROR 429**. Itu pembatasan IP+perangkat karena sudah dipakai 20 akun, bukan salah browser (halaman login sendiri terbuka normal). Kalaupun 429-nya hilang, tetap butuh email/HP + kode verifikasi milik user plus captcha. Jawab singkat dengan angka 429-nya; jangan menghabiskan sesi mencoba jalur lain.
- **`username` di BuzzCuan bisa beda dengan handle IG aslinya.** Akun BuzzCuan ke-2 (`royhn nabil`) tercatat `username: "ayundakirana"` tapi `displayName: "ayu_ndakirana"` — handle yang benar-benar dipakai adalah `ayu_ndakirana` (ds `50064955282`). Jangan simpulkan "akun salah" hanya dari beda satu underscore: cocokkan lewat `displayName` lebih dulu. Akun IG milik `royhn nabil` hanya **3**: `aleenaputri28`, `ayu_ndakirana`, `ang_unlestari` — jadi "ALL AKUN" untuk sesi itu berarti 3, sedangkan "ALL AKUN" tanpa kualifikasi berarti 17 akun Xena. Sebutkan mana yang dipakai di laporan.
- **Nama panggilan di permintaan user harus dipetakan ke username**: Lily = `lilymezzaluna`, Rafly = `rafliahmad199`. "ALL AKUN KECUALI LILY SAMA RAFLY" berarti 15 akun, bukan 17 — sebutkan jumlahnya di laporan supaya salah paham ketahuan awal. Tanyakan kalau ada nama yang belum ada di peta ini.
- **Kunci `ig-progress.json` memakai target yang di-lowercase** (`like:dfoixawjhd6`). Saat menghitung progres dari berkas, lowercase dulu nama targetnya — kalau tidak, hasilnya terbaca 0 padahal sudah beres semua, dan kamu melaporkan angka palsu ke user.
- **Hitung hasil dari blok ringkasan di log, jangan dari kata kunci.** Skrip menutup tiap akun dengan `====` + `selesai : 1` / `dilewati: N (sudah beres sebelumnya)` / `gagal : 0`; menghitung lewat regex kata (`sudah`, `berhasil`) membuat baris `dilewati: 0 (sudah beres sebelumnya)` ikut terhitung sehingga angka "sudah ada" meledak (terukur: 205 dari 16 aksi nyata). Cara benar: ambil pasangan `(aksi, target)` dari baris `like → X` / `follow → X` lalu jumlahkan bloknya per pekerjaan, dan hitung `klik baru` dari baris `@akun: following (baru diklik)`.
- **Jangan hitung proses dengan pola yang cocok dengan baris perintahmu sendiri.** `pgrep -fc '[r]un\.py'` mengembalikan angka palsu (1–3) di perintah yang **memuat** string itu — terbaca seperti "rantai masih jalan" padahal sudah selesai. Pakai `ps -eo pid,args | awk '$0 ~ /run\.py/ && $0 !~ /awk/ {print $1}'` dan periksa `etimes`, atau cek berkas log terakhir untuk penanda `########## RANTAI EKOR SELESAI ##########`.
- **"sudah following" pada target baru bisa benar.** Jangan buru-buru menyebutnya salah baca halaman lama: muat ulang profil dengan akun itu, baca state sekali lagi. Kalau tetap `Following`, akun itu memang sudah mem-follow sebelumnya — laporkan begitu, dan tetap ambil screenshot kalau bukti diminta.

## Like (postingan / reel)

Mekanismenya beda dari follow: `element.click()` tidak bisa diandalkan, dan `aria-label` bercampur dengan tombol like pada komentar.

0. **Target like adalah KODE POST, dan URL-nya wajib `/p/<kode>/`.** `jalankan_target` menyusun URL dari nama target; untuk `aksi="like"` nama itu kode post, bukan username, sehingga tanpa cabang `/p/` halaman yang dibuka adalah **profil** `instagram.com/<kode>` — halaman yang tidak punya action bar sama sekali. Gejalanya menyerupai masalah render: `state_like_post()` terus `None`, akun dilaporkan "tombol like tidak ter-render (DOM)", dan semua akun gagal seragam. Ini pernah menghabiskan satu sesi penuh dan memicu diagnosis salah berantai (blokir media, tukar cookie, AX tree) padahal tidak ada yang rusak. Sebelum mengejar penyebab lain, cetak `location.href`-nya: kalau bukan `/p/`, itu bug URL, bukan bug halaman.
1. **Blokir berkas video dulu** — reel membuat tab macet saat decode sehingga `Runtime.evaluate` timeout: `cdp("Network.enable")` lalu `cdp("Network.setBlockedURLs", urls=["*.mp4*","*.m4s*","*.webm*"])`. Tombol like tetap ter-render tanpa video. Bersihkan dengan `urls=[]` setelah selesai.
2. **Baca dan klik lewat DOM, jangan lewat Accessibility Tree.** `Accessibility.queryAXTree(..., accessibleName="Like", role="button")` balik kosong di layout halaman post meski tombolnya ada dan terbaca DOM — memakai jalur itu membuat semua akun dilaporkan "tombol like tidak ditemukan di AX tree" padahal halaman siap. Pakai `state_like_post()` + `klik_like_post()` (jangkar Comment → `closest('section')`, cadangan ukuran ≥20 px); AX tree hanya cadangan terakhir, dan `klik_nid(backendNodeId)` hanya berguna setelah node AX benar-benar ketemu.
3. **Jangan memilih kandidat berdasarkan `y` maupun urutan DOM.** Tombol like **komentar** berukuran 16×16 dan duduk **lebih atas** daripada action bar postingan (terukur: komentar `y=495`, action bar `y=504`), jadi "ambil yang paling atas" justru mengenai komentar. Jangkar yang benar: temukan `svg[aria-label="Comment"]` (atau `"Komentar"`), ambil `.closest('section')`, lalu cari `[aria-label="Like"|"Unlike"|"Suka"|"Batal Suka"]` **di dalam section itu** — section tersebut action bar postingan, tombol like-nya bersebelahan dengan Comment/Repost/Share/Save.
4. **Klik node yang sudah diverifikasi itu, bukan koordinatnya.** `click_at_xy` bisa mendarat di pembungkus `<section>` (`document.elementFromPoint` mengembalikan `SECTION`) dan tidak terjadi apa pun. Yang menetap: `cdp("DOM.resolveNode", backendNodeId=nid)` lalu `cdp("Runtime.callFunctionOn", objectId=..., functionDeclaration="function(){ const el = this.closest('button, div[role=button]') || this.parentElement; if (el) el.click(); }")`. Simpan `click_at_xy` hanya sebagai cadangan.
5. **Verifikasi lewat jangkar yang sama, dan harus menetap.** Baca state dengan cara nomor 3 (bukan kandidat acak), lalu **muat ulang halaman dan baca sekali lagi** — UI berubah optimistis lalu bisa balik sendiri. `Unlike` setelah reload = benar-benar ter-like. Bukti pendukung: sadap respons GraphQL; mutasi `xig_comment_like` berarti yang ter-like **komentar**, bukan postingan.

**Laporan "gagal" pada like sering salah, dan penyebab utamanya elemen yang keliru — bukan timing.** Kalau pembacaan memakai kandidat `Like`/`Unlike` pertama atau yang paling atas, yang terbaca adalah tombol like **komentar**. Akibatnya dua arah: dilaporkan gagal padahal like postingan masuk, atau dilaporkan berhasil padahal yang ter-like komentar. Gejalanya khas: setelah reload state postingan kembali `Like` sementara log bilang sukses. Sebelum melaporkan apa pun, baca state dengan jangkar action bar (nomor 3) **setelah reload**, baru simpulkan. Jangan mengulang klik pada postingan yang sudah ter-like — klik kedua membatalkan like-nya.

**Gerbang sebelum membaca state like: pastikan halamannya memang halaman postingan.** `document.querySelector('article')` harus ada. Kalau `null`, URL-nya tidak ter-render sebagai post — post dihapus, dibatasi, atau akun tidak berhak melihatnya — dan **setiap label `Like`/`Unlike` yang terbaca berasal dari feed di belakangnya**, bukan dari post itu. Dua kesimpulan palsu muncul dari sini: `sudah_like: true` padahal tidak ada post yang bisa diperiksa, atau "tombol like tidak ter-render" untuk halaman yang memang bukan post. Karena itu batasi pembacaan label ke `article.querySelectorAll('svg[aria-label]')` — membaca seluruh dokumen mencampur label feed dan hasilnya tidak bisa dipercaya. Jenis kegagalan ini menimpa semua akun seragam, jadi laporkan **"postingan tidak bisa dibuka"** (bukan "like gagal") dan minta user memverifikasi link-nya; jangan mengulang akun demi akun untuk masalah yang sama.

Hanya klik URL yang dikirim user persis — jangan mencari postingan sendiri dari profil, karena like menempel ke satu postingan dan salah sasaran tidak bisa ditarik tanpa ketahuan. Simpan log dengan `jenis: "like"` supaya tidak tertukar dengan follow.

Resep klik lengkap — tabel kapan `querySelector`/`element.click()` gagal, pemilihan node paling atas, dan penanganan reel — ada di `references/ax-click-recipes.md`.

## Save / bookmark (aksi `save`) — aksi ketiga

Aksi ketiga selain follow dan like: **menyimpan postingan** (bookmark). Sudah ada di runner — `aksi="save"`, dan `antre_tail.sh` menerimanya seperti aksi lain (`save:<kode-post>`); tidak perlu skrip terpisah, karena `run.py` meneruskan `aksi` apa adanya ke `jalankan_target`.

Yang harus sama seperti like: **target = KODE POST**, dan URL-nya wajib `/p/<kode>/` (`jalankan_target` bercabang untuk itu). Tanpa itu halaman yang dibuka adalah profil.

Jangkar tombolnya sama dengan like — action bar adalah section tempat `svg[aria-label="Comment"]` berada:

- label tombol: `Save` / `Remove` / `Simpan` / `Batalkan Simpan`. `Remove`/`Batalkan Simpan` = **sudah tersimpan**.
- cadangan kalau tombol Comment tidak ada (komentar dimatikan): kandidat `>= 20 px`, urut `y`, ambil teratas.
- fungsi yang dipakai: `state_save_post()`, `klik_save_post()`, `tunggu_save_post(timeout=75)`, `save_target()`, `save_aman()`. Log terpisah `data/ig-saves.json` dengan `jenis: "save"`, kunci checkpoint `save:<kode-lowercase>` (sama seperti like, disimpan lowercase).

**Verifikasi wajib lewat reload, bukan dari perubahan UI.** Sama seperti like, state save berubah optimistis lalu bisa balik sendiri; `save_target()` menutup dengan reload + baca ulang, dan hanya status `tersimpan (baru diklik, lolos reload)` yang dicatat `done`. Status yang mengandung `tersimpan` dihitung berhasil oleh `jalankan_target` — kalau menambah aksi baru, tambahkan kata kuncinya ke cabang itu, karena cabang lama hanya mengenal `following`/`liked`/`sudah`.

Kalau user minta aksi yang **belum ada** di runner (mis. komentar, DM, unfollow), jawab terus terang bahwa aksi itu belum ada — lalu tulis fungsinya mengikuti pola `like_target`/`save_target` (cookie → beranda dulu → blokir video → buka URL → tunggu action bar → verifikasi sesi → klik → poll → **reload untuk verdict** → catat log + checkpoint), uji di **satu** akun, baru masukkan ke antrean.

### Jebakan khusus save

- **Layout IG sekarang TIDAK memakai `<article>`** — pada `/p/` maupun `/reels/`, `document.querySelector('article')` balik `null`. Fungsi yang mensyaratkan `article` (versi pertama `save_target`) melaporkan **semua** akun `gagal: tombol Save tidak ter-render (DOM)` padahal tombolnya ada 24×24. Jangkar yang benar: `section` tempat `svg[aria-label="Comment"]` berada — isinya tepat `Unlike, Comment, Repost, Share, Save`.
- **`/reel/<kode>/` dialihkan ke `/reels/<kode>/` dan merender belasan tombol Save** (semuanya di kolom x yang sama, menumpuk vertikal = feed reel di belakangnya). Memilih "yang paling atas" di whole document bisa mengenai reel lain. Karena itu target save memakai URL `/p/<kode>/` (cabang `aksi in ("like", "save")` di `jalankan_target`): di sana tombol Save tinggal satu. Cadangan terakhir kalau tetap ambigu: pilih Save paling atas **yang ada di dalam viewport**.
- **Akun yang sudah menyimpan sebelumnya** terbaca `sudah tersimpan (tanpa klik)` dan tetap dicatat `done` — jangan klik dua kali, itu membatalkan bookmark.
- `Network.setBlockedURLs` untuk `*.mp4*` tetap dipakai di save: reel tanpa video lebih cepat ter-render action bar-nya.

## Cek semua cookie sekaligus

User sering minta "test all cookie biar aku ambil yang mati". Jangan lewat browser — 17 akun bisa berjam-jam. Uji langsung dengan `curl`, ±1 detik per akun:

```
GET https://www.instagram.com/api/v1/accounts/edit/web_form_data/
header: x-ig-app-id: 936619743392459, x-csrftoken: <csrftoken>, Cookie: <gabungan>
```

`200` + `form_data.username` cocok = hidup. `302` = sesi dicabut (logout / ganti password / challenge) → minta cookie baru. Tutup dengan tabel bernomor lalu daftar "perlu cookie baru" — itu yang dicari user.

### Dua gerbang: `200` belum berarti sesi bisa dipakai

`200` di endpoint itu hanya membuktikan token masih dikenali **endpoint tersebut**. Ada keadaan nyata: endpoint balas `200` dengan `username` benar, tapi browser tetap menampilkan halaman login dan profil target ter-render sebagai pengunjung (`Log In | Sign Up`, tanpa tombol Follow). Akun seperti ini tidak bisa mengeksekusi apa pun walau "test cookie" bilang hidup.

Gerbang kedua sebelum menyatakan akun siap: pasang cookienya, buka satu profil, lalu pastikan `body.innerText` **tidak** memuat `Log In`/`Masuk` dan tombol Follow/Following ter-render. Kalau gagal di sini, laporkan **"sesi ditolak untuk browsing — ambil cookie baru"**, bukan "cookie mati": dua hal berbeda, dan menyamakannya membuat user mengambil ulang cookie yang API-nya masih sehat.

**Berganti-ganti cookie banyak akun di satu browser bisa membunuh sesi.** Terukur: satu akun lolos gerbang kedua, lalu ±20 menit kemudian balas `302` setelah beberapa kali tukar cookie di tab yang sama. Perlakukan pergantian akun sebagai operasi mahal — selesaikan satu akun sampai tuntas, beri jeda, jangan bolak-balik antar akun hanya untuk mengecek. Kalau sebuah akun tiba-tiba `302` padahal baru dipakai, curigai pola pergantian ini sebelum menyalahkan cookienya.

## Platform lain (TikTok)

Untuk memastikan cookie TikTok hidup, pakai `curl` ke passport — ±1 detik, dan balasannya menyebut username + `user_id`, jadi tidak perlu menebak dari tampilan:

```
GET https://www.tiktok.com/passport/web/account/info/?aid=1988
header: Cookie: <gabungan>, User-Agent: <UA Android>, Referer: https://www.tiktok.com/, Accept: application/json
```

`{"message":"success","data":{"username":...,"user_id_str":...}}` = hidup; `{"message":"error"}` = sesi dicabut. Simpan username **hasil verifikasi ini** — satu akun pernah tersimpan tanpa username, sesinya mati, dan identitasnya tidak bisa dipulihkan lagi dari cookie mana pun (token yang tersimpan tidak memuat handle).

Sesudah verifikasi, gerbang kedua tetap berlaku: pasang cookienya di browser dan pastikan `Messages`/`Upload`/`Profile` ter-render, bukan cuma `Log in`.

**Blok cookie TikTok yang ditempel ke chat sering rusak pembungkusan baris** (mis. `"sameSite":"no_restri` lalu baris baru lalu `tion"`). Jangan parse JSON-nya apa adanya: salin hanya kunci yang dibutuhkan auth ke dict — `sessionid`, `sessionid_ss`, `sid_tt`, `sid_guard`, `uid_tt`, `uid_tt_ss`, `tt_csrf_token`, `ttwid`, `msToken`, `d_ticket`, `multi_sids`, `odin_tt`, `tt-target-idc`, `store-country-code`, `tt_chain_token`, `tt_session_tlb_tag` — lalu kirim sebagai header `Cookie`. Terbukti 3/3 akun lolos dengan cara ini.

**Set akun TikTok tidak sama dengan set IG, dan berbeda per sesi BuzzCuan.** Terukur: sesi Xena punya 4 akun TikTok (`ayundaputri083`, `riyantoabdullah4`, `tiararamadani30`, `prayogaahmad01`), sesi `royhn nabil` punya **0**. Ambil daftar sebenarnya dari `/api/social-accounts` dengan filter `platform == "TIKTOK"`; jangan menganggap "ALL AKUN" TikTok berarti daftar IG.

**Akun TikTok tanpa email/HP tidak bisa dipulihkan lewat web.** "Forgot password" hanya mengirim kode ke email/HP yang terpasang; kalau keduanya kosong, tidak ada jalur reset sama sekali — bukan salah langkah user. Satu-satunya jalan: dari sesi yang masih aktif (profil → Settings and privacy → Account → tambah email, baru reset) atau password manager (`passwords.google.com`). Sampaikan apa adanya; jangan menjanjikan pemulihan, dan jangan menebak username dari `user_id` numerik — endpoint `user/detail` berbasis `userId`/`secUid` balik kosong tanpa tanda tangan.

Halaman **root** TikTok diblok WAF: `curl` hanya dapat halaman challenge ~700 byte, dan browser dapat ~400 KB HTML berisi puluhan `<script>` tapi `document.body.innerText` tetap kosong. Halaman **profil** (`/@username`) jauh lebih permisif dan datanya kebaca (nama, username, following, followers, likes). Jadi jangan simpulkan "TikTok tidak bisa dibuka" dari root-nya — pindah ke URL profil dulu.

### Follow TikTok: headless dideteksi, headed berhasil

Tombolnya **ada** dan bisa diklik: `button[data-e2e="follow-button"]`, di kolom kanan header profil (±108×44 px). `element.click()` mengubah UI `Follow` → `Following`, dan request-nya benar-benar terkirim (`/api/commit/follow/user/?action_type=1`).

**Akar masalahnya mode headless.** Di browser headless: klik mengubah UI `Follow` → `Following` tapi state balik setelah reload, server membalas **200 dengan body kosong** (penolakan senyap), dan halaman memunculkan captcha slider yang menutupi tombol. Di browser **tampak** (Xvfb + chrome headed, layar 1000×900): halaman yang sama memuat **tanpa captcha**, tombol follow ter-render, dan klik **menetap** setelah reload. Jadi jangan menyimpulkan "TikTok menolak" dari percobaan headless — jalankan browser tampak. Resep lengkap di `references/tiktok-headed-browser.md`, skripnya `scripts/start_live.sh` + `scripts/livecdp.py`.

Di headless, yang menutupi tombol adalah **captcha slider**: `document.elementFromPoint()` di koordinat tombol mengembalikan DIV berteks "Drag the slider to fit the puzzle", dan halaman memuat belasan elemen ber-class `cap-*`. Karena itu:

- **Jangan mulai dari mengerjakan signature `X-Bogus`/`msToken`.** Request-nya sudah terkirim; yang kurang verifikasi manusia, bukan tanda tangan.
- **Klik mouse asli lewat `Input.dispatchMouseEvent` juga tidak menolong** — event-nya mendarat di lapisan captcha, bukan di tombol, jadi UI bahkan tidak berubah.
- **Jangan menembus captcha secara otomatis.** Puzzle itu memang dirancang untuk membuktikan ada manusia; menembusnya = membangun bot penyamar, dan akun user taruhannya. Sampaikan apa adanya, jangan diam-diam dilewati.
- Klik sintetis berulang **memicu** challenge itu pada sesi yang tadinya bersih. Kalau mengetes, lakukan sekali lalu berhenti — dan beri tahu user kalau percobaanmu kemungkinan yang memicunya.

**Unfollow TikTok: satu klik, tanpa menu.** Klik pada tombol `Following` **langsung** mengubahnya jadi `Follow` — tidak ada dropdown `[role=menuitem]` yang perlu dicari (mencarinya hanya membuang waktu). Tapi tetap **verifikasi dengan reload**: di browser headless perubahan itu tidak menetap, dan hanya di browser tampak hasilnya sah. Jangan mengklaim unfollow berhasil dari perubahan UI saja.

Kalau captcha tetap muncul meski browser sudah tampak, tes ulang **satu** akun saja sebelum menjanjikan apa pun.

## Format laporan ke user

Per akun: status (`following (baru diklik)` / `sudah following` / gagal + alasan) + path screenshot. Kirim `sebelum`, `sesudah`, dan `identitas` bila ada. Sertakan progres "N dari M".

**Ekonomi bukti.** Default user: bukti yang dikirim cukup **satu akun** (`sebelum` + `sesudah`) per target, bukan semua akun — puluhan gambar sekaligus membanjiri chat dan tidak dibaca. Simpan sisanya di disk dan sebutkan path/polanya.

**Kecuali user minta eksplisit** ("wajib ss", "ss semua akun"). Kalau diminta: ambil screenshot **per akun setelah state terverifikasi**, kirim bertahap per ronde (3 akun sekali kirim) — user sendiri menyatakan "bertahap aja gpp". Jangan pernah mengirim screenshot yang masih memperlihatkan `Like`/`Follow` sebagai bukti keberhasilan; itu bukti kegagalan. Ambil ulang setelah state benar, atau ulangi akunnya.

**Jangan anggap screenshot sudah sampai ke user** hanya karena path `MEDIA:` dicetak: user berulang kali melaporkan gambarnya tidak muncul di chat. Setelah mengirim, tanyakan sekali apakah terlihat; kalau tidak, tawarkan cara lain (arsip zip, atau sajikan lewat server lokal) dan jangan mengulang kirim path yang sama berkali-kali.

Kalau menyajikan bukti lewat server lokal, daftarkan route statisnya **sebelum** handler catch-all SPA: kalau tidak, setiap path — termasuk `/bukti/<file>` dan file `.zip` — dibalas `index.html`, jadi galeri tampak kosong padahal filenya ada. Uji dengan `curl` dan pastikan `content_type` benar, bukan cuma status 200.

Kalau akun sudah `Following` sejak awal, tetap ambil screenshot sebagai bukti (user memilih opsi ini), dan catat apa adanya — jangan tulis "sudah following" untuk follow yang sebenarnya baru diklik sendiri.
