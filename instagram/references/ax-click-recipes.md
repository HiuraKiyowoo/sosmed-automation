# Mengklik elemen Instagram dengan andal

Resep ini dipakai untuk tombol yang tidak punya teks unik (like, save, repost) dan untuk semua aksi yang butuh klik asli, bukan `element.click()`.

## Kenapa bukan `querySelector` + `.click()`

| Masalah | Gejala | Gantinya |
|---|---|---|
| Tombol tanpa teks unik | `aria-label="Like"` juga dipakai tombol like **komentar** | jangkar ke action bar: `svg[aria-label="Comment"]` → `.closest('section')` → cari like/unlike di dalamnya. **Bukan** urutan `y`/DOM — tombol komentar justru lebih atas |
| Klik koordinat | bisa mendarat di `<section>` pembungkus: `elementFromPoint` mengembalikan `SECTION`, tidak terjadi apa pun | klik node yang sudah diverifikasi: `DOM.resolveNode` → `Runtime.callFunctionOn` pada `.closest('button, div[role=button]')`; `click_at_xy` hanya cadangan |
| `element.click()` pada elemen yang salah | state tidak berubah, tidak ada error | pastikan dulu elemennya tombol postingan (lihat baris pertama), baru klik |
| Query seluruh dokumen | `Runtime.evaluate timed out after 5s` | `queryAXTree` terfilter, atau batasi ke `<main>` |
| `getFullAXTree` | ≈2.700 node di halaman IG, melewati timeout 5 detik | `queryAXTree` dengan `accessibleName` + `role` (≈2 detik) |

## Alur

```python
# 1. root dokumen (murah, depth=1)
root = cdp("DOM.getDocument", depth=1)["root"]["nodeId"]

# 2. cari kandidat — satu panggilan per nama yang mungkin (locale ID/EN)
res = cdp("Accessibility.queryAXTree", nodeId=root, accessibleName="Like", role="button")

# 3. saring yang punya kotak, hitung titik tengah
q = cdp("DOM.getBoxModel", backendNodeId=nid)["model"]["content"]
x, y = (q[0] + q[2]) / 2, (q[1] + q[5]) / 2

# 4. klik asli
click_at_xy(int(x), int(y))

# 5. verifikasi lewat nama node, bukan warna ikon
#    "Like" -> "Unlike"  |  "Suka" -> "Batal Suka"
```

Jangan memilih kandidat dengan `sort(key=y)` maupun dengan hasil pertama `queryAXTree`. Di halaman post, tombol like **komentar** (16×16) berada di `y` lebih kecil daripada action bar postingan (terukur: komentar `y=495`, action bar `y=504`), jadi "yang paling atas" = komentar.

Jangkar yang benar — tombol like postingan, diambil dari section yang sama dengan tombol Comment:

```javascript
(() => {
  const c = document.querySelector('svg[aria-label="Comment"], svg[aria-label="Komentar"]');
  if (!c) return null;
  const sec = c.closest('section');            // action bar postingan
  const lk = sec && sec.querySelector('[aria-label="Like"], [aria-label="Unlike"], [aria-label="Suka"], [aria-label="Batal Suka"]');
  return lk ? lk.getAttribute('aria-label') : null;   // "Unlike" = sudah ter-like
})()
```

Untuk mengkliknya, ambil `backendNodeId` elemen itu lalu jalankan `Runtime.callFunctionOn` (bukan `click_at_xy`: koordinat bisa mendarat di `<section>` pembungkus dan kliknya hilang).

Cara cepat memastikan tombol yang diklik memang benar: sadap respons GraphQL di halaman. Like **postingan** tidak memakai `xig_comment_like`; kalau mutasi itu yang muncul, berarti yang ter-like komentar.

## Reel: blokir video dulu

`/reel/<kode>` dialihkan ke `/reels/<kode>` dan pemutar video membuat tab sibuk sehingga `Runtime.evaluate` timeout — bahkan ketika `js("1+1")` di detik yang sama masih menjawab. Sebelum navigasi:

```python
cdp("Network.enable")
cdp("Network.setBlockedURLs", urls=["*.mp4*", "*.m4s*", "*.webm*"])
```

Tombol like tetap ter-render; halaman hanya jauh lebih ringan. Bersihkan dengan `urls=[]` setelah selesai supaya tidak memengaruhi navigasi berikutnya.

## Klik tampak berhasil tapi tidak tersimpan

Dua bentuk gejala: (a) klik tidak melakukan apa-apa — state tidak berubah; (b) UI berubah optimistis lalu balik sendiri setelah reload. Sebelum mengutak-atik selector atau timing, periksa **apa yang sebenarnya ada di titik itu**:

```javascript
document.elementFromPoint(x, y)   // tag, class, dan teks elemen yang menerima klik
```

Kalau yang kembali bukan tombol target, ada lapisan di atasnya. Dua yang sudah terukur: pembungkus `<section>` (IG — pindahkan klik ke node hasil verifikasi), dan lapisan **captcha** (TikTok — teks "Drag the slider to fit the puzzle", elemen ber-class `cap-*`). Lapisan captcha menjelaskan kedua gejala sekaligus: `.click()` mengubah state lokal React, sementara klik mouse asli mendarat di captcha dan tidak terjadi apa-apa.

Aturan umum: **respons `200` dengan body kosong bukan bukti sukses.** Platform membalas begitu untuk menolak tanpa memberi pesan error. Satu-satunya bukti yang sah adalah state baru yang **bertahan setelah halaman dimuat ulang**.

## Verifikasi hasil

- State tombol: baca lewat jangkar action bar di atas, **setelah halaman dimuat ulang**. UI Instagram berubah optimistis lalu bisa balik sendiri; satu pembacaan sebelum reload bukan bukti.
- Bukti visual: `capture_screenshot()` lalu baca dengan vision — konfirmasi ikon hati terisi. Dua lapis ini yang membuat laporan bisa dipercaya.
- Kalau state masih `Like` setelah reload, urutan diagnosisnya:
  1. pastikan elemen yang dibaca memang tombol postingan (bukan komentar) — ini penyebab paling sering;
  2. baru pertimbangkan klik yang tidak kena (layout bergeser karena bilah komentar memuat) → ambil `backendNodeId`/`getBoxModel` baru lalu klik lagi;
  3. jangan mengulang klik pada postingan yang sudah `Unlike` — klik kedua **membatalkan** like (toggle).
- Rekonsiliasi di akhir: untuk tiap akun ambil status **terakhir** dari log; kalau pernah `gagal` lalu `liked`/`sudah liked`, yang menang adalah yang positif. **Tapi log yang ditulis skrip dengan elemen salah juga salah** — jangan laporkan satu batch sebagai selesai hanya dari log. Baca ulang beberapa akun dengan jalur pembacaan yang berbeda dari yang menulis log (JS berjangkar action bar, setelah reload) sebelum menyatakan target beres. Laporan "17/17 sukses" yang dibangun di atas deteksi keliru jauh lebih mahal daripada satu putaran verifikasi tambahan.

## Batas

Hanya klik URL yang user kirim persis. Aksi seperti like/save menempel ke satu postingan tertentu dan salah sasaran tidak bisa ditarik tanpa ketahuan; jangan mencari postingan sendiri dari profil.
