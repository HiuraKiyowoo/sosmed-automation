"""Pengendali CDP minimal untuk browser TAMPAK (Xvfb + chrome headed, port 9222).

Harness Hermes hanya bisa headless, jadi browser tampak dikendalikan sendiri.
Tujuan: user melihat halaman lewat noVNC dan menyelesaikan captcha dengan tangan,
sementara otomasi membaca/mengubah halaman yang SAMA.

Dipakai dari execute_code:
    import sys; sys.path.insert(0, "<dir skill>/scripts")
    import livecdp as L
    L.nav("https://www.tiktok.com/@target", tunggu=12)
    print(L.js("document.title"))
"""
import json
import urllib.request

from websockets.sync.client import connect

CDP_HTTP = "http://127.0.0.1:9222"
_ws = None
_id = 0


def _target_ws():
    d = json.loads(urllib.request.urlopen(CDP_HTTP + "/json", timeout=8).read())
    for t in d:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("tidak ada target 'page' di browser tampak")


def hubung():
    """Buka (atau pakai ulang) koneksi ke tab aktif."""
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
    _ws = connect(_target_ws(), max_size=64 * 1024 * 1024, open_timeout=15, close_timeout=5)
    return _ws


def kirim(method, **params):
    """Kirim satu method CDP mentah, balik result-nya."""
    global _id
    w = hubung()
    _id += 1
    mid = _id
    w.send(json.dumps({"id": mid, "method": method, "params": params}))
    while True:
        pesan = json.loads(w.recv(timeout=60))
        if pesan.get("id") == mid:
            if "error" in pesan:
                raise RuntimeError(f"{method}: {pesan['error']}")
            return pesan.get("result", {})


def nav(url, tunggu=3.0):
    import time
    kirim("Page.enable")
    kirim("Page.navigate", url=url)
    time.sleep(tunggu)


def js(expr, await_promise=True):
    """Jalankan JS di halaman, balik nilainya."""
    bungkus = f"(async () => {{ return ({expr}); }})()" if await_promise else expr
    r = kirim("Runtime.evaluate", expression=bungkus, awaitPromise=await_promise,
              returnByValue=True)
    if r.get("exceptionDetails"):
        raise RuntimeError(str(r["exceptionDetails"])[:200])
    return r.get("result", {}).get("value")


def pasang_cookie(ck, domain=".tiktok.com"):
    """Pasang banyak cookie sekaligus."""
    for k, v in ck.items():
        try:
            kirim("Network.setCookie", name=k, value=v, domain=domain, path="/", secure=True)
        except Exception:
            pass


def bersihkan_cookie():
    try:
        kirim("Network.clearBrowserCookies")
    except Exception:
        pass


def shot(path="/root/.hermes/cache/documents/live.png"):
    import base64
    r = kirim("Page.captureScreenshot", format="png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(r["data"]))
    return path


def ukuran(w=1000, h=900):
    kirim("Emulation.setDeviceMetricsOverride", width=w, height=h,
          deviceScaleFactor=1, mobile=False)
