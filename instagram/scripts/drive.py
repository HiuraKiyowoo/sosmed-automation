"""Klien CDP minimal untuk Chromium milik sendiri (headless port 9334 / tampak 9222).

Harness Hermes tidak bisa diberi flag tambahan, jadi browser kita kendalikan
sendiri. Ini yang bikin penghematan memori bisa diatur: renderer dibatasi 1,
gambar dimatikan, heap JS dibatasi.

Port diambil dari env `CDP_PORT` supaya klien yang sama dipakai untuk dua mode:
9334 (headless, batch IG) dan 9222 (browser tampak, mis. TikTok).
"""
import os
import json
import time
import urllib.request
from websockets.sync.client import connect

CDP_HTTP = "http://127.0.0.1:" + os.environ.get("CDP_PORT", "9334")
_ws = None
_id = 0


def _tab():
    d = json.loads(urllib.request.urlopen(CDP_HTTP + "/json/list", timeout=8).read())
    pages = [t for t in d if t.get("type") == "page"]
    return pages[0]["webSocketDebuggerUrl"] if pages else None


def hubung():
    global _ws
    if _ws is not None:
        try:
            _ws.ping()
            return _ws
        except Exception:
            try:
                _ws.close()
            except Exception:
                pass
            _ws = None
    _ws = connect(_tab(), max_size=64 * 1024 * 1024, open_timeout=20, close_timeout=5)
    return _ws


def cdp(method, **params):
    global _id
    ws = hubung()
    _id += 1
    mid = _id
    ws.send(json.dumps({"id": mid, "method": method, "params": params}))
    batas = time.time() + 60
    while time.time() < batas:
        m = json.loads(ws.recv())
        if m.get("id") == mid:
            if "error" in m:
                raise RuntimeError(f"{method}: {m['error'].get('message')}")
            return m.get("result", {})
    raise TimeoutError(method)


def js(expr, await_promise=False):
    r = cdp("Runtime.evaluate", expression=expr, returnByValue=True,
            awaitPromise=await_promise, userGesture=True)
    return r.get("result", {}).get("value")


def nav(url, tunggu=6.0):
    cdp("Page.navigate", url=url)
    time.sleep(tunggu)
    # tunggu DOM siap
    batas = time.time() + 25
    while time.time() < batas:
        try:
            st = js("document.readyState")
            if st == "complete":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def pasang_cookie(ck, domain=".instagram.com"):
    cdp("Network.enable")
    for k, v in ck.items():
        try:
            cdp("Network.setCookie", name=k, value=v, domain=domain, path="/",
                secure=True, httpOnly=False)
        except Exception as e:
            print("  [cookie] gagal", k, str(e)[:40])


def siap():
    cdp("Page.enable")
    cdp("Network.enable")
    cdp("Runtime.enable")


def tutup_tab_lain():
    """Tutup semua tab halaman kecuali satu.

    Tab menumpuk bikin CDP bisa menempel ke tab yang salah (mis. halaman login
    basi dari navigasi sebelumnya), sehingga tombol tidak ditemukan padahal
    sesi di tab lain sehat. Sekalian menghemat memori.
    """
    try:
        d = json.loads(urllib.request.urlopen(CDP_HTTP + "/json/list", timeout=8).read())
    except Exception:
        return 0
    pages = [t for t in d if t.get("type") == "page"]
    if len(pages) <= 1:
        return 0
    tutup = 0
    for t in pages[1:]:
        try:
            urllib.request.urlopen(CDP_HTTP + "/json/close/" + t["id"], timeout=5).read()
            tutup += 1
        except Exception:
            pass
    global _ws
    _ws = None
    return tutup