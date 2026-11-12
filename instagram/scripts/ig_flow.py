"""Alur follow Instagram yang sudah terbukti — dipakai ulang untuk tiap akun.

Pakai di dalam browser_exec:
    exec(open('/tmp/ig_flow.py').read())
    hasil = follow_target('freyaanindya84', 'https://www.instagram.com/asdp191/')
    print(hasil)

Yang ditangani otomatis:
  - ambil cookie akun dari data/ig-accounts.json
  - jeda acak ala manusia sebelum swap
  - TUNGGU tombol Follow benar-benar ter-render (polling, bukan sleep buta)
  - verifikasi identitas sesi SEBELUM aksi apa pun
  - klik Follow, lalu tunggu sampai state jadi Following (bukan asumsi)
  - screenshot target (sebelum/sesudah) + screenshot identitas akun
  - catat ke data/ig-follows.json
"""

import json
import os
import random
import shutil
import time

DATA = "/data/data/com.termux/files/home/buzzmon/data"
AKUN_FILE = os.path.join(DATA, "ig-accounts.json")
LOG_FILE = os.path.join(DATA, "ig-follows.json")
OUT = "/root/.hermes/cache/documents"

# JS: cari tombol follow/following yang sudah ter-render
JS_TOMBOL = """(() => {
  const main = document.querySelector('main') || document.body;
  // 1) cek lewat aria-label pada svg (paling ringan)
  const sv = main.querySelector('svg[aria-label="Following"], svg[aria-label="Mengikuti"], svg[aria-label="Follow"], svg[aria-label="Ikuti"]');
  if (sv) {
    const l = sv.getAttribute('aria-label');
    return { state: /^(Following|Mengikuti)$/i.test(l) ? 'following' : 'follow', teks: l };
  }
  // 2) fallback: hanya tombol di dalam main (bukan seluruh div halaman)
  const btns = main.querySelectorAll('button, div[role=button]');
  for (const b of btns) {
    const t = (b.innerText || '').trim();
    if (/^(Follow|Following|Ikuti|Mengikuti)$/i.test(t)) {
      return { state: /^(Following|Mengikuti)$/i.test(t) ? 'following' : 'follow', teks: t };
    }
  }
  return null;
})()"""

JS_SESI = """(async () => {
  try {
    const r = await fetch('/api/v1/accounts/edit/web_form_data/',
      { headers: { 'x-ig-app-id': '936619743392459' }, credentials: 'include' });
    const d = await r.json();
    return d?.form_data?.username || null;
  } catch (e) { return null; }
})()"""


def muat_akun(username):
    data = json.load(open(AKUN_FILE, encoding="utf-8"))
    for a in data.get("accounts", []):
        if a["username"].lower() == username.lower():
            return a
    raise ValueError(f"akun {username} tidak ada di {AKUN_FILE}")


def pasang_cookie(akun):
    # bersihkan cookie akun sebelumnya supaya fingerprint tidak tercampur
    try:
        cdp("Network.clearBrowserCookies")
    except Exception:
        pass
    for k, v in akun["cookies"].items():
        cdp("Network.setCookie", name=k, value=v, domain=".instagram.com", path="/",
            secure=True, httpOnly=(k in ("sessionid", "ig_did", "datr")))


def tunggu_tombol(timeout=75, reload_kalau_nihil=True):
    """Polling sampai tombol Follow/Following muncul.

    Render profil IG bisa >35 detik (terukur), jadi batas 25 detik terlalu ketat:
    akibatnya dilaporkan "tombol tidak muncul" padahal halaman cuma lambat.
    Kalau tetap nihil setelah timeout, halaman dimuat ulang sekali lalu dicoba lagi.
    """
    batas = time.time() + timeout
    time.sleep(4)
    while time.time() < batas:
        try:
            t = js(JS_TOMBOL)
            if t:
                return t
        except Exception:
            pass  # timeout CDP sesaat: jangan gagalkan, coba lagi
        time.sleep(2)
    if reload_kalau_nihil:
        try:
            js("location.reload()")
        except Exception:
            return None
        time.sleep(8)
        batas = time.time() + 45
        while time.time() < batas:
            try:
                t = js(JS_TOMBOL)
                if t:
                    return t
            except Exception:
                pass
            time.sleep(2)
    return None




def sesi_dari_cookie():
    """Baca ds_user_id dari cookie — sinkron, tanpa fetch, jadi tidak bisa hang.

    Verifikasi lewat fetch('/api/v1/accounts/edit/...') sering menggantung >5s
    dan memicu RuntimeError. ds_user_id tidak httpOnly, jadi bisa dibaca langsung.
    """
    for _ in range(5):
        try:
            v = js("(document.cookie.match(/ds_user_id=(\\d+)/) || [])[1] || null")
            if v:
                return v
        except Exception:
            pass
        time.sleep(1)
    return None


def tunggu_identitas(timeout=20):
    batas = time.time() + timeout
    while time.time() < batas:
        u = js(JS_SESI)
        if u:
            return u
        time.sleep(1)
    return None


def _simpan(nama):
    """Screenshot sekarang, simpan dengan nama tertentu."""
    capture_screenshot()
    src = "/root/.config/browser-harness/tmp/p-953b57936f16/shot.png"
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, nama)
    shutil.copy(src, dst)
    return dst


def _simpan_aman(nama, coba=2):
    """Screenshot TIDAK boleh membatalkan aksi yang sudah terjadi.

    Page.captureScreenshot bisa timeout >60s di halaman berat (video/animasi).
    Waktu itu terjadi, klik follow/like-nya SUDAH jalan — jadi kembalikan None
    dan lanjutkan pencatatan, bukan melempar exception.
    """
    for i in range(1, coba + 1):
        try:
            return _simpan(nama)
        except Exception as e:
            print(f"  [ss] {nama} gagal ({type(e).__name__})")
            if i == coba:
                return None
            time.sleep(3)


def _log(entri):
    log = json.load(open(LOG_FILE, encoding="utf-8")) if os.path.exists(LOG_FILE) else {"follows": []}
    log["follows"].append(entri)
    json.dump(log, open(LOG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def follow_target(username, url, jeda_min=10, jeda_max=20, ambil_identitas=True):
    """Follow satu target dari satu akun. Balik dict berisi hasil & path screenshot."""
    akun = muat_akun(username)
    target = url.rstrip("/").split("/")[-1].split("?")[0]
    waktu = time.strftime("%Y-%m-%d %H:%M:%S")

    jeda = random.randint(jeda_min, jeda_max)
    print(f"[{username}] jeda swap {jeda}s")
    time.sleep(jeda)

    pasang_cookie(akun)
    # PANAS: buka beranda dulu. Kalau langsung ke profil di browser yang baru
    # menyala, IG sering menyajikan cangkang login (tanpa <main>, tanpa tombol)
    # sehingga akun dilaporkan "tombol tidak muncul" padahal sesi sehat.
    try:
        goto_url("https://www.instagram.com/")
        wait_for_load()
        time.sleep(4)
    except Exception:
        pass
    goto_url(url if url.startswith("http") else f"https://www.instagram.com/{target}/")
    try:
        wait_for_load()
    except Exception:
        pass

    # Pastikan halaman BENAR-BENAR sudah pindah ke profil target. Kalau belum,
    # state tombol yang terbaca berasal dari halaman sebelumnya — ini pernah
    # melaporkan "sudah following" padahal itu profil lama (target baru).
    mau = "/" + target.lower()
    for _ in range(4):
        href = (js("location.pathname") or "").lower()
        if mau in href:
            break
        try:
            wait_for_load()
        except Exception:
            pass
        time.sleep(2)
    else:
        hasil = {"akun": username, "target": target,
                 "status": f"gagal: halaman tidak pindah ke /{target}", "waktu": waktu}
        _log(hasil)
        return hasil

    tombol = tunggu_tombol()
    if not tombol:
        hasil = {"akun": username, "target": target, "status": "gagal: tombol tidak muncul",
                 "waktu": waktu}
        _log(hasil)
        return hasil

    sesi = sesi_dari_cookie()
    if sesi != str(akun.get("ds_user_id")):
        hasil = {"akun": username, "target": target,
                 "status": f"gagal: ds_user_id browser = {sesi}, harusnya {akun.get('ds_user_id')}",
                 "waktu": waktu}
        _log(hasil)
        return hasil

    ss = {}
    status = tombol["state"]
    if status == "follow":
        ss["sebelum"] = _simpan_aman(f"{username}__{target}__sebelum.png")
        js("""(() => {
          const main = document.querySelector('main') || document.body;
          const sv = main.querySelector('svg[aria-label="Follow"], svg[aria-label="Ikuti"]');
          if (sv) { (sv.closest('button, div[role=button]') || sv.parentElement).click(); return; }
          for (const b of main.querySelectorAll('button, div[role=button]')) {
            if (/^(Follow|Ikuti)$/i.test((b.innerText || '').trim())) { b.click(); return; }
          }
        })()""")
        batas = time.time() + 15
        akhir = None
        while time.time() < batas:
            akhir = js(JS_TOMBOL)
            if akhir and akhir["state"] == "following":
                break
            time.sleep(1)
        if not akhir or akhir["state"] != "following":
            hasil = {"akun": username, "target": target, "status": "gagal: klik tidak berubah",
                     "waktu": waktu, **ss}
            _log(hasil)
            return hasil
        status = "following (baru diklik)"
        time.sleep(2)
    else:
        status = "sudah following (tanpa klik)"

    ss["sesudah"] = _simpan_aman(f"{username}__{target}__sesudah.png")

    if ambil_identitas:
        goto_url(f"https://www.instagram.com/{username}/")
        try:
            wait_for_load()
        except Exception:
            pass
        batas = time.time() + 20
        while time.time() < batas:
            teks = js("(document.body.innerText || '')")
            if teks and username.lower() in teks.lower():
                break
            time.sleep(1)
        time.sleep(1)
        ss["identitas"] = _simpan_aman(f"{username}__identitas.png")

    hasil = {"akun": username, "target": target, "status": status, "waktu": waktu, **ss}
    _log(hasil)
    return hasil

def follow_aman(username, url, coba=3, **kw):
    """Bungkus follow_target dengan coba-ulang (tanpa ensure_real_tab).

    Browser harness kadang timeout (Runtime.evaluate > 5s) tepat setelah cookie
    dibersihkan. ensure_real_tab() memulihkan, lalu dicoba lagi.
    """
    import time as _t
    for i in range(1, coba + 1):
        try:
            hasil = follow_target(username, url, **kw)
            if hasil.get("status", "").startswith("gagal"):
                raise RuntimeError(hasil["status"])
            return hasil
        except Exception as e:
            print(f"[{username}] percobaan {i}/{coba} gagal: {type(e).__name__}")
            if i == coba:
                return {"akun": username, "target": url.rstrip("/").split("/")[-1],
                        "status": f"gagal setelah {coba} percobaan: {type(e).__name__}"}
            _t.sleep(6)
    return {"akun": username, "status": "gagal"}


# ---------- LIKE (AX tree + klik koordinat) ----------
NAMA_LIKE = ("Like", "Suka")
NAMA_UNLIKE = ("Unlike", "Batal Suka")


def ax_tombol_like():
    """Cari tombol like POSTINGAN (bukan komentar) dengan query AX terfilter.

    getFullAXTree terlalu berat (2700 node > timeout 5s). queryAXTree hanya
    mengembalikan node yang cocok, ~2 detik. Kalau ada beberapa kandidat,
    dipilih yang paling atas (y terkecil) karena action bar postingan berada
    di atas daftar komentar.
    """
    doc = cdp("DOM.getDocument", depth=1)
    root = doc["root"]["nodeId"]
    kandidat = []
    for nama in ("Like", "Suka", "Unlike", "Batal Suka"):
        try:
            res = cdp("Accessibility.queryAXTree", nodeId=root,
                      accessibleName=nama, role="button")
        except Exception:
            continue
        for n in res.get("nodes", []):
            if n.get("ignored"):
                continue
            nid = n.get("backendDOMNodeId")
            if not nid:
                continue
            try:
                q = cdp("DOM.getBoxModel", backendNodeId=nid)["model"]["content"]
            except Exception:
                continue
            kandidat.append({"nama": nama, "id": nid, "x": (q[0]+q[2])/2, "y": (q[1]+q[5])/2})
    if not kandidat:
        return None, None
    kandidat.sort(key=lambda k: k["y"])
    k = kandidat[0]
    return k["nama"], k["id"]


def klik_ax(nid):
    box = cdp("DOM.getBoxModel", backendNodeId=nid)["model"]
    q = box["content"]
    click_at_xy(int((q[0] + q[2]) / 2), int((q[1] + q[5]) / 2))




def klik_nid(nid):
    """Klik elemen PERSIS yang dipilih AX tree (bukan elemen pertama di DOM).

    JS querySelectorAll('svg[aria-label="Like"]')[0] bisa menunjuk tombol like
    KOMENTAR, sehingga mutasi yang terkirim xig_comment_like — bukan like post.
    """
    obj = cdp("DOM.resolveNode", backendNodeId=nid)["object"]["objectId"]
    cdp(
        "Runtime.callFunctionOn",
        objectId=obj,
        functionDeclaration="function(){ const el = this.closest('button, div[role=button]') || this.parentElement; if (el) el.click(); }",
        awaitPromise=False,
    )



JS_LIKE_POST = """(() => {
  // 1) Jangkar paling andal: tombol like di section yang sama dengan Comment.
  const c = document.querySelector('svg[aria-label="Comment"], svg[aria-label="Komentar"]');
  if (c) {
    const sec = c.closest('section');
    const lk = sec && sec.querySelector('[aria-label="Like"], [aria-label="Unlike"], [aria-label="Suka"], [aria-label="Batal Suka"]');
    if (lk) {
      const l = lk.getAttribute('aria-label');
      return { state: /^(Unlike|Batal Suka)$/i.test(l) ? 'sudah' : 'belum', teks: l, cara: 'comment' };
    }
  }
  // 2) Kalau tombol Comment tidak ada (komentar dimatikan), pilih dari UKURAN:
  //    like postingan ~24px, like komentar ~16px. Ambil >=20px lalu yang teratas.
  const kand = [];
  document.querySelectorAll('[aria-label="Like"], [aria-label="Unlike"], [aria-label="Suka"], [aria-label="Batal Suka"]').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width >= 20 && r.height >= 20) kand.push({ el, y: r.y, l: el.getAttribute('aria-label') });
  });
  if (!kand.length) return null;
  kand.sort((a, b) => a.y - b.y);
  const q = kand[0];
  return { state: /^(Unlike|Batal Suka)$/i.test(q.l) ? 'sudah' : 'belum', teks: q.l, cara: 'ukuran' };
})()"""


def state_like_post():
    return js(JS_LIKE_POST)


def klik_like_post():
    """Klik tombol like POSTINGAN (bukan komentar). Lihat JS_LIKE_POST."""
    return js("""(() => {
      const pilih = () => {
        const c = document.querySelector('svg[aria-label="Comment"], svg[aria-label="Komentar"]');
        if (c) {
          const sec = c.closest('section');
          const lk = sec && sec.querySelector('[aria-label="Like"], [aria-label="Unlike"], [aria-label="Suka"], [aria-label="Batal Suka"]');
          if (lk) return lk;
        }
        const kand = [];
        document.querySelectorAll('[aria-label="Like"], [aria-label="Unlike"], [aria-label="Suka"], [aria-label="Batal Suka"]').forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.width >= 20 && r.height >= 20) kand.push({ el, y: r.y });
        });
        if (!kand.length) return null;
        kand.sort((a, b) => a.y - b.y);
        return kand[0].el;
      };
      const lk = pilih();
      if (!lk) return false;
      (lk.closest('button, div[role=button]') || lk.parentElement).click();
      return true;
    })()""")


def tunggu_ax_like(timeout=20):
    batas = time.time() + timeout
    time.sleep(3)
    while time.time() < batas:
        try:
            nama, nid = ax_tombol_like()
            if nama:
                return nama, nid
        except Exception:
            pass
        time.sleep(1.5)
    return None, None

def like_target(username, url, jeda_min=10, jeda_max=20, ambil_identitas=True):
    akun = muat_akun(username)
    waktu = time.strftime("%Y-%m-%d %H:%M:%S")
    kode_post = url.rstrip("/").split("/")[-1].split("?")[0]

    jeda = random.randint(jeda_min, jeda_max)
    print(f"[{username}] jeda swap {jeda}s")
    time.sleep(jeda)

    pasang_cookie(akun)
    # PANAS: beranda dulu, alasannya sama seperti follow_target.
    try:
        goto_url("https://www.instagram.com/")
        wait_for_load()
        time.sleep(4)
    except Exception:
        pass
    try:
        cdp("Network.enable")
        cdp("Network.setBlockedURLs", urls=["*.mp4*", "*.m4s*", "*.webm*"])
    except Exception:
        pass
    goto_url(url)
    try:
        wait_for_load()
    except Exception:
        pass

    st = tunggu_like_post(timeout=75)
    if not st:
        # Action bar kadang belum ter-render meski caption sudah tampil.
        goto_url(url)
        try:
            wait_for_load()
        except Exception:
            pass
        st = tunggu_like_post(timeout=60)
    if not st:
        h = {"akun": username, "target": kode_post, "jenis": "like",
             "status": "gagal: tombol like tidak ter-render (DOM)", "waktu": waktu}
        _log_like(h)
        return h

    sesi = sesi_dari_cookie()
    if sesi != str(akun.get("ds_user_id")):
        h = {"akun": username, "target": kode_post, "jenis": "like",
             "status": f"gagal: ds_user_id di browser = {sesi}, harusnya {akun.get('ds_user_id')}",
             "waktu": waktu}
        _log_like(h)
        return h

    ss = {}
    if st.get("state") == "sudah":
        status = "sudah liked (tanpa klik)"
    else:
        ss["sebelum"] = _simpan_aman(f"{username}__{kode_post}__like_sebelum.png")
        # Klik lewat DOM (jangkar tombol Comment), BUKAN AX tree: pada sebagian
        # layout, tombol like postingan tidak muncul sebagai node AX sama sekali.
        try:
            klik_like_post()
        except Exception:
            pass
        batas = time.time() + 20
        akhir = None
        while time.time() < batas:
            time.sleep(1.5)
            try:
                akhir = state_like_post()
            except Exception:
                akhir = None
            if akhir and akhir.get("state") == "sudah":
                break
        if not (akhir and akhir.get("state") == "sudah"):
            # fallback: sekali lagi, kadang klik pertama kena overlay/reflow
            try:
                klik_like_post()
            except Exception:
                pass
            time.sleep(3)
            for _ in range(4):
                try:
                    akhir = state_like_post()
                except Exception:
                    akhir = None
                if akhir and akhir.get("state") == "sudah":
                    break
                time.sleep(2)
        if not (akhir and akhir.get("state") == "sudah"):
            h = {"akun": username, "target": kode_post, "jenis": "like",
                 "status": f"gagal: state tetap {akhir}", "waktu": waktu, **ss}
            _log_like(h)
            return h
        status = "liked (baru diklik)"
        time.sleep(2)

    ss["sesudah"] = _simpan_aman(f"{username}__{kode_post}__like_sesudah.png")

    if ambil_identitas:
        goto_url(f"https://www.instagram.com/{username}/")
        try:
            wait_for_load()
        except Exception:
            pass
        batas = time.time() + 20
        while time.time() < batas:
            try:
                if username.lower() in (js("(document.body.innerText || '')") or "").lower():
                    break
            except Exception:
                pass
            time.sleep(1)
        time.sleep(1)
        ss["identitas"] = _simpan_aman(f"{username}__identitas.png")

    try:
        cdp("Network.setBlockedURLs", urls=[])
    except Exception:
        pass
    h = {"akun": username, "target": kode_post, "jenis": "like", "status": status,
         "waktu": waktu, **ss}
    _log_like(h)
    return h


def _log_like(entri):
    p = os.path.join(DATA, "ig-likes.json")
    log = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"likes": []}
    log["likes"].append(entri)
    json.dump(log, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def like_aman(username, url, coba=3, **kw):
    import time as _t
    for i in range(1, coba + 1):
        # JANGAN panggil ensure_real_tab() di sini: helper itu membuat tab baru
        # dan justru membuat CDP timeout. Cukup ulangi alurnya apa adanya.
        try:
            h = like_target(username, url, **kw)
            if h.get("status", "").startswith("gagal"):
                raise RuntimeError(h["status"])
            return h
        except Exception as e:
            print(f"[{username}] like percobaan {i}/{coba} gagal: {type(e).__name__}")
            if i == coba:
                return {"akun": username, "status": f"gagal setelah {coba}x: {type(e).__name__}"}
            _t.sleep(6)


# ---------- SIMPAN COOKIE (dari ig_simpan.py) ----------
def _bersih(v):
    """Buang spasi/baris baru yang sering ikut saat copy-paste."""
    return re.sub(r"\s+", "", str(v))


def _cek(ck):
    cookie = "; ".join(f"{k}={v}" for k, v in ck.items())
    r = subprocess.run(
        ["curl", "-s", "-m", "30", "--compressed", "-o", "/tmp/_who.json", "-w", "%{http_code}",
         "-H", f"User-Agent: {UA}", "-H", f"Cookie: {cookie}", "-H", "Accept: */*",
         "-H", "x-ig-app-id: 936619743392459", "-H", f"x-csrftoken: {ck.get('csrftoken','')}",
         "-H", "Referer: https://www.instagram.com/",
         "https://www.instagram.com/api/v1/accounts/edit/web_form_data/"],
        capture_output=True, text=True)
    kode = r.stdout.strip()
    try:
        fd = json.load(open("/tmp/_who.json", encoding="utf-8", errors="ignore")).get("form_data") or {}
    except Exception:
        fd = {}
    return kode, fd


def simpan_banyak(daftar):
    data = json.load(open(AKUN_FILE, encoding="utf-8")) if os.path.exists(AKUN_FILE) else {"accounts": []}
    hasil = []
    for i, mentah in enumerate(daftar, 1):
        ck = {k: _bersih(v) for k, v in mentah.items() if v}
        kode, fd = _cek(ck)
        nama = fd.get("username")
        if not nama:
            hasil.append({"ke": i, "status": f"GAGAL (HTTP {kode})", "ds_user_id": ck.get("ds_user_id")})
            print(f"  {i}. GAGAL  HTTP {kode}  id={ck.get('ds_user_id')}")
            continue
        data["accounts"] = [a for a in data["accounts"] if a.get("ds_user_id") != ck["ds_user_id"]]
        data["accounts"].append({
            "username": nama, "nama": (fd.get("first_name") or "").strip(),
            "email": fd.get("email"), "ds_user_id": ck["ds_user_id"], "cookies": ck,
            "status": "ok", "ditambah": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        hasil.append({"ke": i, "status": "ok", "username": nama, "ds_user_id": ck["ds_user_id"]})
        print(f"  {i}. OK     @{nama}")

    json.dump(data, open(AKUN_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.chmod(AKUN_FILE, 0o600)
    print(f"\ntotal tersimpan: {len(data['accounts'])} akun")
    return hasil

def cek_semua_cookie():
    """Uji setiap cookie akun lewat curl (bukan browser). Balik (hidup, mati).

    endpoint accounts/edit balas 200 + username cocok = hidup; 302 = sesi dicabut.
    """
    import subprocess as sp
    hasil = {"hidup": [], "mati": []}
    data = json.load(open(AKUN_FILE, encoding="utf-8"))["accounts"]
    for a in data:
        ck = a["cookies"]
        cookie = "; ".join(f"{k}={v}" for k, v in ck.items())
        r = sp.run(["curl", "-s", "-m", "25", "--compressed", "-o", "/tmp/_cek.json", "-w", "%{http_code}",
                    "-H", "User-Agent: Mozilla/5.0 (Linux; Android 13; SM-A536E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                    "-H", f"Cookie: {cookie}", "-H", "Accept: */*",
                    "-H", "x-ig-app-id: 936619743392459", "-H", f"x-csrftoken: {ck.get('csrftoken','')}",
                    "-H", "Referer: https://www.instagram.com/",
                    "https://www.instagram.com/api/v1/accounts/edit/web_form_data/"],
                   capture_output=True, text=True)
        kode = r.stdout.strip()
        try:
            u = (json.load(open("/tmp/_cek.json", encoding="utf-8", errors="ignore")).get("form_data") or {}).get("username")
        except Exception:
            u = None
        if u and u.lower() == a["username"].lower():
            hasil["hidup"].append(a["username"])
        else:
            hasil["mati"].append({"username": a["username"], "http": kode})
    return hasil

# ---------- SAVE (bookmark postingan) ----------
# Tombol Save duduk di action bar yang sama dengan Comment/Like/Repost/Share,
# jadi jangkarnya sama seperti like: section tempat svg[aria-label="Comment"] berada.
# Verifikasi WAJIB lewat reload — UI berubah optimistis lalu bisa balik sendiri.

LOG_SAVE = os.path.join(DATA, "ig-saves.json")

JS_SAVE_POST = """(() => {
  // CATATAN: layout IG sekarang TIDAK memakai <article> (baik /p/ maupun /reels/),
  // jadi jangan mensyaratkannya — itu pernah membuat semua akun "gagal: tombol Save
  // tidak ter-render". Jangkar yang benar: section tempat svg[aria-label="Comment"] ada
  // (isinya tepat Unlike, Comment, Repost, Share, Save).
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const sel = '[aria-label="Save"], [aria-label="Remove"], [aria-label="Simpan"], [aria-label="Batalkan Simpan"]';
  const c = document.querySelector('svg[aria-label="Comment"], svg[aria-label="Komentar"]');
  const sec = c ? c.closest('section') : null;
  let el = sec ? sec.querySelector(sel) : null;
  let cara = 'section-comment';
  if (!el) {
    const art = document.querySelector('article');
    el = art ? art.querySelector(sel) : null;
    if (el) cara = 'article';
  }
  if (!el) {
    // /reels/ merender banyak reel di kolom yang sama; ambil yang paling atas
    // DI DALAM viewport = reel yang sedang dibuka.
    const kand = [...document.querySelectorAll(sel)].filter(vis).map((x) => ({ x, y: x.getBoundingClientRect().y }));
    const layar = kand.filter((k) => k.y >= 0 && k.y <= window.innerHeight);
    const pakai = (layar.length ? layar : kand).sort((a, b) => a.y - b.y)[0];
    if (!pakai) return null;
    el = pakai.x;
    cara = 'viewport-atas';
  }
  const l = el.getAttribute('aria-label') || '';
  return { state: /^(Remove|Batalkan Simpan)$/i.test(l) ? 'sudah' : 'belum', teks: l, cara: cara };
})()"""


def state_save_post():
    return js(JS_SAVE_POST)


def klik_save_post():
    """Klik tombol Save (bookmark) POSTINGAN, bukan elemen lain di halaman."""
    return js("""(() => {
      const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      const sel = '[aria-label="Save"], [aria-label="Remove"], [aria-label="Simpan"], [aria-label="Batalkan Simpan"]';
      const pilih = () => {
        const c = document.querySelector('svg[aria-label="Comment"], svg[aria-label="Komentar"]');
        const sec = c && c.closest('section');
        let el = sec && sec.querySelector(sel);
        if (el) return el;
        const art = document.querySelector('article');
        el = art && art.querySelector(sel);
        if (el) return el;
        const kand = [...document.querySelectorAll(sel)].filter(vis).map((x) => ({ x, y: x.getBoundingClientRect().y }));
        const layar = kand.filter((k) => k.y >= 0 && k.y <= window.innerHeight);
        const pakai = (layar.length ? layar : kand).sort((a, b) => a.y - b.y)[0];
        return pakai ? pakai.x : null;
      };
      const el = pilih();
      if (!el) return false;
      (el.closest('button, div[role=button]') || el.parentElement).click();
      return true;
    })()""")


def tunggu_save_post(timeout=75):
    """Polling sampai action bar + tombol Save benar-benar ter-render."""
    batas = time.time() + timeout
    while time.time() < batas:
        try:
            st = state_save_post()
        except Exception:
            st = None
        if st:
            return st
        time.sleep(3)
    return None


def _log_save(entri):
    os.makedirs(DATA, exist_ok=True)
    try:
        d = json.load(open(LOG_SAVE, encoding="utf-8"))
    except Exception:
        d = []
    d.append(entri)
    with open(LOG_SAVE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def save_target(username, url, jeda_min=10, jeda_max=20, ambil_identitas=False):
    akun = muat_akun(username)
    waktu = time.strftime("%Y-%m-%d %H:%M:%S")
    kode_post = url.rstrip("/").split("/")[-1].split("?")[0]

    jeda = random.randint(jeda_min, jeda_max)
    print(f"[{username}] jeda swap {jeda}s")
    time.sleep(jeda)

    pasang_cookie(akun)
    try:
        goto_url("https://www.instagram.com/")
        wait_for_load()
        time.sleep(4)
    except Exception:
        pass
    try:
        cdp("Network.enable")
        cdp("Network.setBlockedURLs", urls=["*.mp4*", "*.m4s*", "*.webm*"])
    except Exception:
        pass
    goto_url(url)
    try:
        wait_for_load()
    except Exception:
        pass

    st = tunggu_save_post(timeout=75)
    if not st:
        goto_url(url)
        try:
            wait_for_load()
        except Exception:
            pass
        st = tunggu_save_post(timeout=60)
    if not st:
        h = {"akun": username, "target": kode_post, "jenis": "save",
             "status": "gagal: tombol Save tidak ter-render (DOM)", "waktu": waktu}
        _log_save(h)
        return h

    sesi = sesi_dari_cookie()
    if sesi != str(akun.get("ds_user_id")):
        h = {"akun": username, "target": kode_post, "jenis": "save",
             "status": f"gagal: ds_user_id di browser = {sesi}, harusnya {akun.get('ds_user_id')}",
             "waktu": waktu}
        _log_save(h)
        return h

    ss = {}
    if st.get("state") == "sudah":
        status = "sudah tersimpan (tanpa klik)"
    else:
        ss["sebelum"] = _simpan_aman(f"{username}__{kode_post}__save_sebelum.png")
        try:
            klik_save_post()
        except Exception:
            pass
        batas = time.time() + 20
        akhir = None
        while time.time() < batas:
            time.sleep(1.5)
            try:
                akhir = state_save_post()
            except Exception:
                akhir = None
            if akhir and akhir.get("state") == "sudah":
                break
        if not (akhir and akhir.get("state") == "sudah"):
            try:
                klik_save_post()
            except Exception:
                pass
            time.sleep(3)
            for _ in range(4):
                try:
                    akhir = state_save_post()
                except Exception:
                    akhir = None
                if akhir and akhir.get("state") == "sudah":
                    break
                time.sleep(2)
        # Gerbang verifikasi: UI optimistis bisa balik sendiri → reload dulu.
        try:
            goto_url(url)
            wait_for_load()
            time.sleep(5)
        except Exception:
            pass
        akhir2 = None
        for _ in range(6):
            try:
                akhir2 = state_save_post()
            except Exception:
                akhir2 = None
            if akhir2:
                break
            time.sleep(2)
        if not (akhir2 and akhir2.get("state") == "sudah"):
            h = {"akun": username, "target": kode_post, "jenis": "save",
                 "status": f"gagal: setelah reload state tetap {akhir2}", "waktu": waktu, **ss}
            _log_save(h)
            return h
        status = "tersimpan (baru diklik, lolos reload)"
        time.sleep(2)

    ss["sesudah"] = _simpan_aman(f"{username}__{kode_post}__save_sesudah.png")
    h = {"akun": username, "target": kode_post, "jenis": "save", "status": status, "waktu": waktu, **ss}
    _log_save(h)
    return h


def save_aman(username, url, coba=3, **kw):
    for i in range(1, coba + 1):
        try:
            return save_target(username, url, **kw)
        except Exception as e:
            print(f"[{username}] save percobaan {i}/{coba} gagal: {type(e).__name__}")
            time.sleep(3)
    return {"akun": username, "status": "gagal: semua percobaan"}

# ---------- CHECKPOINT, DETEKSI CAPTCHA, LANJUT DARI LANGKAH TERAKHIR ----------

PROGRES_FILE = os.path.join(DATA, "ig-progress.json")


def _muat_progres():
    try:
        return json.load(open(PROGRES_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _simpan_progres(d):
    os.makedirs(DATA, exist_ok=True)
    tmp = PROGRES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRES_FILE)


def tanda_selesai(target, akun, aksi="follow", status="done", catatan=""):
    """Catat satu (target, akun, aksi) supaya tidak dikerjakan ulang."""
    d = _muat_progres()
    kunci = f"{aksi}:{target.lower()}"
    d.setdefault(kunci, {})[akun] = {
        "status": status, "catatan": catatan,
        "waktu": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _simpan_progres(d)


def sudah_selesai(target, aksi="follow"):
    """Daftar akun yang sudah beres untuk target+aksi ini."""
    d = _muat_progres()
    k = d.get(f"{aksi}:{target.lower()}", {})
    return {a for a, v in k.items() if v.get("status") == "done"}


def perlu_manual(target, aksi="follow"):
    """Daftar akun yang tertahan captcha/challenge untuk target+aksi ini."""
    d = _muat_progres()
    k = d.get(f"{aksi}:{target.lower()}", {})
    return {a: v.get("catatan", "") for a, v in k.items() if v.get("status") == "captcha"}


JS_CAPTCHA = """(() => {
  // Deteksi captcha/challenge. Dua rupa yang sudah terbukti:
  //  - TikTok  : "Drag the slider to fit the puzzle" + puluhan elemen class "cap-*"
  //  - Instagram: halaman /challenge/ atau teks "confirm it's you"
  const t = (document.body && document.body.innerText || '').slice(0, 4000);
  const cap = document.querySelectorAll('[class*="cap-"]').length;
  const pola = /drag the slider|fit the puzzle|captcha|verify you|confirm it'?s you|konfirmasi bahwa ini|verifikasi bahwa ini|unusual activity|aktivitas tidak biasa/i;
  const adaTeks = pola.test(t);
  const diChallenge = /[/]challenge[/]/i.test(location.pathname);
  return {
    captcha: !!(adaTeks || diChallenge || cap > 5),
    sebab: adaTeks ? 'teks captcha' : (diChallenge ? 'url /challenge/' : (cap > 5 ? 'elemen cap-*' : '')),
    elemen_cap: cap,
    url: location.href.slice(0, 80)
  };
})()"""


def ada_captcha():
    """True kalau halaman sekarang menampilkan captcha/challenge."""
    try:
        r = js(JS_CAPTCHA)
        return bool(r and r.get("captcha")), (r or {}).get("sebab", ""), (r or {}).get("elemen_cap", 0)
    except Exception:
        return False, "gagal baca", 0


def jalankan_target(target, akun_list, aksi="follow", jeda_min=3, jeda_max=6,
                    url=None, paksa_ulang=False):
    """Batch runner dengan checkpoint.

    - Akun yang sudah berstatus "done" DILEWATI (pekerjaan tidak diulang).
    - Kalau captcha muncul di tengah: akun itu ditandai "captcha", lalu loop
      LANJUT ke akun berikutnya — bukan menghentikan seluruh proses.
    - Balik dict: {selesai, dilewati, captcha, gagal}.
    """
    if url is None:
        # Untuk like DAN save, target adalah KODE POST — bukan username.
        # Tanpa "/p/", URL yang dibuka jadi halaman profil dan tombol tak pernah ada.
        url = (f"https://www.instagram.com/p/{target}/" if aksi in ("like", "save")
               else f"https://www.instagram.com/{target}/")
    beres = set() if paksa_ulang else sudah_selesai(target, aksi)
    hasil = {"selesai": [], "dilewati": [], "captcha": [], "gagal": []}

    for nama in akun_list:
        if nama in beres:
            print(f"@{nama}: LEWATI (sudah beres)")
            hasil["dilewati"].append(nama)
            continue

        try:
            if aksi == "follow":
                h = follow_target(nama, url, jeda_min=jeda_min, jeda_max=jeda_max, ambil_identitas=False)
            elif aksi == "save":
                h = save_target(nama, url, jeda_min=jeda_min, jeda_max=jeda_max, ambil_identitas=False)
            else:
                h = like_target(nama, url, jeda_min=jeda_min, jeda_max=jeda_max, ambil_identitas=False)
            st = str(h.get("status", ""))
        except Exception as e:
            st = f"ERROR {type(e).__name__}"
            h = {}

        kena, sebab, ncap = ada_captcha()

        if kena:
            print(f"@{nama}: CAPTCHA ({sebab}, {ncap} elemen) — ditandai, lanjut ke akun berikutnya")
            tanda_selesai(target, nama, aksi, "captcha", sebab)
            hasil["captcha"].append(nama)
        elif "following" in st or "liked" in st or "sudah" in st or "tersimpan" in st:
            tanda_selesai(target, nama, aksi, "done", st)
            hasil["selesai"].append(nama)
            print(f"@{nama}: {st} → dicatat")
        else:
            tanda_selesai(target, nama, aksi, "gagal", st)
            hasil["gagal"].append(nama)
            print(f"@{nama}: {st}")

    print("\n" + "=" * 46)
    print(f"  {aksi} → {target}")
    print(f"  selesai : {len(hasil['selesai'])}")
    print(f"  dilewati: {len(hasil['dilewati'])} (sudah beres sebelumnya)")
    print(f"  gagal   : {len(hasil['gagal'])}")
    if hasil["captcha"]:
        print("\n  ⚠️  CAPTCHA — BUTUH TANGAN MANUSIA:")
        for n in hasil["captcha"]:
            print(f"      @{n}  →  selesaikan verifikasi untuk akun ini")
        print("  Setelah selesai, bilang ke Merlin — dia lanjut dari sini,")
        print("  akun yang sudah beres tidak dikerjakan ulang.")
    print("=" * 46)
    return hasil

def tunggu_like_post(timeout=75):
    """Polling state_like_post sampai tombol like postingan benar-benar ter-render.

    Halaman /p/ bisa menampilkan caption lebih dulu sementara action bar
    (tombol Comment + Like) belum ada — state_like_post lalu balik None.
    """
    batas = time.time() + timeout
    while time.time() < batas:
        try:
            st = state_like_post()
        except Exception:
            st = None
        if st:
            return st
        time.sleep(3)
    return None
