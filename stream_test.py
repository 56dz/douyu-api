import json, time, hashlib, urllib.request, urllib.parse, ssl, sys, uuid

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")
# 设备 id: 服务端不校验来源, 任意 32 位十六进制串均可
DID = hashlib.md5(uuid.uuid4().bytes).hexdigest()
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
H = {"User-Agent": UA, "Referer": "https://www.douyu.com/", "Origin": "https://www.douyu.com"}

def http(url, method="GET", data=None, headers=None):
    hd = dict(H); hd.update(headers or {})
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        hd["Content-Type"] = "application/x-www-form-urlencoded"
    r = urllib.request.Request(url, data=body, headers=hd, method=method)
    with urllib.request.urlopen(r, timeout=20, context=ctx) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")

def md5(s): return hashlib.md5(s.encode()).hexdigest()

def get_key(did=DID):
    st, b = http("https://www.douyu.com/wgapi/livenc/liveweb/websec/getEncryption?did=" + did)
    return json.loads(b)["data"]

def sign_stream(key, rid, ts=None, did=DID):
    ts = ts or int(time.time())
    o = f"{rid}{ts}"
    f = key["rand_str"]
    for _ in range(int(key.get("enc_time") or 1)):
        f = md5(f + key["key"])
    auth = md5(f + key["key"] + o)
    return auth, ts

def get_h5play(rid=1024, rate=-1, cdn="", iar=1, ive=0, did=DID):
    k = get_key(did)
    auth, ts = sign_stream(k, rid, did=did)
    form = {
        "enc_data": k["enc_data"], "tt": ts, "did": did, "auth": auth,
        "cdn": cdn, "rate": rate, "ver": "Douyu_224011102",
        "iar": iar, "ive": ive, "prev": 1, "bs": 2,
    }
    st, b = http(f"https://www.douyu.com/lapi/live/getH5PlayV1/{rid}", "POST", form)
    return st, b

if __name__ == "__main__":
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else 1024
    st, b = get_h5play(rid)
    print("status", st)
    try:
        j = json.loads(b)
        print(json.dumps(j, indent=1, ensure_ascii=False)[:6000])
    except Exception:
        print(b[:2000])
