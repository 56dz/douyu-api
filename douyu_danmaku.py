"""
斗鱼弹幕 (danmaku) 客户端 —— 纯 Python, 无需 cookie/登录。

协议要点 (逆向自 js/page-*.js + js/1154-*.js):
  * WebSocket 使用**二进制帧**: <u32 len><u32 len><i16 689><u8 0><u8 0><utf8 text><0x00>
  * 序列化格式 STT: k@=v/k@=v/ ; 转义 '@'->'@A'  '/'->'@S'
  * 网关 socket:  wss://wsproxy.douyu.com:{6671..6676}/  (来自 /lapi/live/gateway/web/{rid}?isH5=1 的 data.wss)
  * 弹幕 socket:  wss://danmuproxy.douyu.com:{8501..8506}/ (来自网关下发的 msgrepeaterproxylist)
  * 网关 loginreq 需要 vk = md5(rt + "r5*^5;}2#${XF[h+;'./.Q'1;,-]f'p[" + devid)
  * 匿名游客登录即可收到全部弹幕 (username=visitorXXXXXXX)
"""
import asyncio, json, hashlib, time, ssl, sys, struct, urllib.request, uuid

import websockets

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")
# 设备 id: 服务端不校验来源, 任意 32 位十六进制串均可, 每次启动随机生成
DID = hashlib.md5(uuid.uuid4().bytes).hexdigest()
WEB_LOGIN_VERSION = "20190610"
WEB_COUNT_VERSION = "218101901"
VK_SALT = "r5*^5;}2#${XF[h+;'./.Q'1;,-]f'p["

# ---------------- STT 序列化 ----------------
def _esc(s):
    return str(s).replace("@", "@A").replace("/", "@S")


def stt(obj):
    return "".join(_esc(k) + "@=" + _esc(v) + "/" for k, v in obj.items())


def stt_decode(s):
    res, key, buf, i, n = {}, "", [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "/":
            if key or buf:
                res[key] = "".join(buf)
            key, buf = "", []
        elif c == "@" and i + 1 < n:
            i += 1
            c2 = s[i]
            if c2 == "A":
                buf.append("@")
            elif c2 == "S":
                buf.append("/")
            elif c2 == "=":
                key = "".join(buf)
                buf = []
        else:
            buf.append(c)
        i += 1
    if key or buf:
        res[key] = "".join(buf)
    return res


def unescape_once(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "@" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "A":
                out.append("@"); i += 2; continue
            if nxt == "S":
                out.append("/"); i += 2; continue
        out.append(c)
        i += 1
    return "".join(out)


def decode_list(raw):
    """斗鱼 list 值是被二次转义的: 'id@AA=0@ASnr@AA=0@AS...@S@S...'
    解两层转义后用 '//' 分割, 再按 STT 解析每一项."""
    u1 = unescape_once(raw)
    u2 = unescape_once(u1)
    items = []
    for chunk in u2.split("//"):
        chunk = chunk.strip()
        if not chunk:
            continue
        d = stt_decode(chunk)
        if d:
            items.append(d)
    return items


def stt_decode_deep(s):
    """also decode nested @A=...@S... sub-objects into lists/dicts (best effort)"""
    d = stt_decode(s)
    for k, v in list(d.items()):
        if "@A=" in v or "@S" in v:
            d[k] = stt_decode(v)
    return d


# ---------------- 二进制帧 ----------------
def ws_encode(text: str) -> bytes:
    payload = text.encode("utf-8") + b"\x00"
    length = 8 + len(payload)
    return (struct.pack("<I", length) + struct.pack("<I", length)
            + struct.pack("<h", 689) + b"\x00\x00" + payload)


def ws_decode(buf: bytes):
    out = []
    while len(buf) >= 12:
        (length,) = struct.unpack_from("<I", buf, 0)
        if length < 12 or len(buf) < length + 4:
            break
        out.append(buf[12:length - 1].decode("utf-8", "replace"))
        buf = buf[length + 4:]
    return out, buf


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.douyu.com/"})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        return json.loads(r.read().decode())


def ssl_ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    c.set_ciphers("DEFAULT:@SECLEVEL=0")
    return c


class DouyuDanmaku:
    def __init__(self, rid, on_msg=None):
        self.rid = int(rid)
        self.on_msg = on_msg or (lambda m: None)
        self.gid = "-9999"
        self.uid = 0
        self.uname = ""
        self.barrage_hosts = []
        self.vbw = 0          # 已发送字节数, 心跳用
        self.kd = ""          # 服务端下发的心跳密钥
        self._stop = False

    async def _gateway(self):
        gw = http_get("https://www.douyu.com/lapi/live/gateway/web/%d?isH5=1" % self.rid)
        wss = gw.get("data", {}).get("wss") or []
        if not wss:
            raise RuntimeError("no wss gateway for rid=%s" % self.rid)
        host = "%s:%s" % (wss[0]["domain"], wss[0]["port"])
        return await websockets.connect("wss://" + host + "/", ssl=ssl_ctx(),
                                        server_hostname=None, origin="https://www.douyu.com",
                                        user_agent_header=UA, max_size=None, open_timeout=15)

    def _login_gateway(self):
        rt = int(time.time())
        return stt({
            "type": "loginreq", "roomid": self.rid, "username": "", "password": "",
            "ltkid": "", "biz": "", "stk": "", "devid": DID, "ct": 0, "pt": 2,
            "cvr": 0, "tvr": 7, "apd": "", "jwt": "", "rt": rt,
            "vk": hashlib.md5((str(rt) + VK_SALT + DID).encode()).hexdigest(),
            "ver": WEB_LOGIN_VERSION, "aver": WEB_COUNT_VERSION,
            "dmbt": "chrome", "dmbv": "156", "er": 1,
        })

    async def run(self):
        gw = await self._gateway()
        await gw.send(ws_encode(self._login_gateway()))
        barrage_task = None
        try:
            async for raw in gw:
                if isinstance(raw, str):
                    raw = raw.encode()
                msgs, _ = ws_decode(raw)
                for m in msgs:
                    d = stt_decode(m)
                    t = d.get("type")
                    if t == "loginres":
                        self.uid = d.get("userid", 0)
                        self.uname = d.get("username", "")
                        self.kd = d.get("keeplive", self.kd) or self.kd
                        self.on_msg({"type": "_loginres", **d})
                        # 启动心跳
                        asyncio.create_task(self._heartbeat(gw))
                    elif t == "setmsggroup":
                        self.gid = d.get("gid", self.gid)
                        self.on_msg({"type": "_setmsggroup", "gid": self.gid})
                    elif t == "msgrepeaterproxylist":
                        items = decode_list(d.get("list", ""))
                        hosts = []
                        for v in items:
                            ip = (v.get("ip") or "").strip().rstrip("@")
                            port = (v.get("port") or "").strip().rstrip("@")
                            if ip:
                                hosts.append("%s:%s" % (ip, port))
                        self.barrage_hosts = hosts
                        self.on_msg({"type": "_barragelist", "hosts": hosts})
                        if hosts and barrage_task is None:
                            barrage_task = asyncio.create_task(
                                self._barrage_loop(hosts))
                    else:
                        self.on_msg({"type": t, **d})
        finally:
            self._stop = True
            if barrage_task:
                barrage_task.cancel()
            await gw.close()

    async def _heartbeat(self, gw):
        """每 45 秒发一次 keeplive。"""
        while not self._stop:
            await asyncio.sleep(45)
            if self._stop:
                return
            try:
                await gw.send(ws_encode(stt({
                    "type": "keeplive", "vbw": self.vbw, "cdn": "",
                    "tick": int(time.time()), "kd": self.kd,
                })))
            except Exception:
                return

    async def _barrage_loop(self, hosts):
        """依次尝试 barrage 主机, 连上后持续收包。"""
        for hostport in hosts:
            if self._stop:
                return
            try:
                ws = await websockets.connect(
                    "wss://" + hostport + "/", ssl=ssl_ctx(),
                    server_hostname=None, origin="https://www.douyu.com",
                    user_agent_header=UA, max_size=None, open_timeout=15)
            except Exception as e:
                self.on_msg({"type": "_barrage_error", "host": hostport, "err": str(e)})
                continue
            try:
                await ws.send(ws_encode(stt({
                    "type": "loginreq", "roomid": self.rid, "username": self.uname,
                    "uid": self.uid, "ver": WEB_LOGIN_VERSION,
                    "aver": WEB_COUNT_VERSION, "ct": 0,
                })))
                self.on_msg({"type": "_barrage_connected", "host": hostport})
                async for raw in ws:
                    if isinstance(raw, str):
                        raw = raw.encode()
                    msgs, _ = ws_decode(raw)
                    for m in msgs:
                        d = stt_decode(m)
                        t = d.get("type")
                        if t == "loginres":
                            await ws.send(ws_encode(stt({
                                "type": "joingroup", "rid": self.rid, "gid": self.gid})))
                            self.on_msg({"type": "_joined", "gid": self.gid})
                        else:
                            self.on_msg({"type": t, **d})
                return
            except Exception as e:
                self.on_msg({"type": "_barrage_error", "host": hostport, "err": str(e)})
            finally:
                try:
                    await ws.close()
                except Exception:
                    pass


def cli(rid, seconds=60):
    def printer(m):
        t = m.get("type")
        if t == "chatmsg":
            print("[弹幕] %s: %s" % (m.get("nn"), m.get("txt")))
        elif t in ("dgb", "uenter", "rss", "ssd", "gift"):
            print("[%s] %s" % (t, json.dumps({k: m[k] for k in list(m)[:5]}, ensure_ascii=False)))
        elif t and t.startswith("_"):
            print("[sys] %s %s" % (t, {k: v for k, v in m.items() if k != "type"}))

    async def runner():
        c = DouyuDanmaku(rid, printer)
        try:
            await asyncio.wait_for(c.run(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    asyncio.run(runner())


if __name__ == "__main__":
    r = sys.argv[1] if len(sys.argv) > 1 else "1024"
    sec = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    cli(r, sec)
