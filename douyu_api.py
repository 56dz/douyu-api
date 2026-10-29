"""
douyu_api.py —— 斗鱼 (douyu.com) Web API 统一封装
================================================================
纯 Python 标准库 (+ websockets 仅用于弹幕), 无需 cookie, 无需登录。
所有接口均已实测通过 (2026-10)。

覆盖能力
--------
1. 首页推荐        get_home_recommend()      Next.js RSC 解析
                   get_hot_rooms()           mixList/0_0 全站最热
2. 搜索直播间      search_show() / search_user() / search_all() / search_rec()
3. 分类与子菜单    get_cate_nav() / get_cate_rooms()
4. 直播流(多清晰度) get_stream_urls() / get_play_info()
5. 直播弹幕        douyu_danmaku.DouyuDanmaku
6. 其它接口        见末尾 ENDPOINTS 清单

依赖:  pip install websockets     (仅弹幕需要)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import ssl
import time
import urllib.parse
import urllib.request
import uuid

# --------------------------------------------------------------------------
# 全局常量
# --------------------------------------------------------------------------
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")

# 设备 id: 对应浏览器 localStorage 里的 dyshid / 首页 URL 的 dyshid 参数。
# 服务端不校验它的来源, 任意 32 位十六进制串都能签名通过 (已实测),
# 所以这里每次进程启动随机生成一个, 避免把某个真实设备号写死在仓库里。
DEFAULT_DID = hashlib.md5(uuid.uuid4().bytes).hexdigest()

BASE = "https://www.douyu.com"
PLAYER_VER = "Douyu_224011102"          # 播放器版本号, 服务端校验
REFERER = BASE + "/"

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


# --------------------------------------------------------------------------
# 底层 HTTP
# --------------------------------------------------------------------------
def _headers(extra: dict | None = None) -> dict:
    h = {
        "User-Agent": UA,
        "Referer": REFERER,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if extra:
        h.update(extra)
    return h


def request(url: str, method: str = "GET", data: dict | None = None,
            headers: dict | None = None, timeout: int = 20) -> bytes:
    """发原始 HTTP 请求, 返回 bytes。"""
    body = None
    h = _headers(headers)
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw


def get_json(path: str, params: dict | None = None) -> dict:
    """GET 一个 JSON 接口。path 可为相对路径 (/gapi/...) 或完整 URL。"""
    url = path if path.startswith("http") else BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    return json.loads(request(url).decode("utf-8", "replace"))


def post_json(path: str, data: dict) -> dict:
    url = path if path.startswith("http") else BASE + path
    return json.loads(request(url, "POST", data).decode("utf-8", "replace"))


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


# ==========================================================================
# 需求 1: 首页推荐
# ==========================================================================
def _js_unescape(js: str) -> str:
    """把 RSC chunk 里的 JS 字符串转义序列还原。"""
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if c == "\\" and i + 1 < n:
            d = js[i + 1]
            if d == "n":
                out.append("\n"); i += 2; continue
            if d == "t":
                out.append("\t"); i += 2; continue
            if d == "r":
                out.append("\r"); i += 2; continue
            if d == '"':
                out.append('"'); i += 2; continue
            if d == "\\":
                out.append("\\"); i += 2; continue
            if d == "/":
                out.append("/"); i += 2; continue
            if d == "u":
                try:
                    out.append(chr(int(js[i + 2:i + 6], 16))); i += 6; continue
                except ValueError:
                    pass
        out.append(c)
        i += 1
    return "".join(out)


def _bracket_array(txt: str, key: str) -> str | None:
    """在 txt 中找到 "<key>": 后面那个 [...] 数组的原文 (括号配对, 忽略字符串内的括号)。"""
    i = txt.find('"%s":' % key)
    if i < 0:
        return None
    start = txt.index("[", i)
    depth, instr, esc = 0, False, False
    for j in range(start, len(txt)):
        ch = txt[j]
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
            continue
        if ch == '"':
            instr = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return txt[start:j + 1]
    return None


def get_home_recommend() -> list[dict]:
    """
    首页推荐位 (斗鱼首页 "推荐" 流)。

    斗鱼首页是 Next.js App Router 服务端渲染, 没有公开 JSON 接口。
    数据藏在 HTML 里 60+ 个 self.__next_f.push([1,"..."]) 的 RSC 流中,
    拼起来后找 "recommendCards":[...] 即可。

    返回: [{type, live:{rid, roomName, anchorName, cate2Id, cate2Name,
                        hot, cover{picUrl,...}, showId, ...}, cardId, ...}]
    """
    html = request(BASE + "/").decode("utf-8", "replace")
    import re
    pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    txt = _js_unescape("".join(pushes))
    arr = _bracket_array(txt, "recommendCards")
    if not arr:
        return []
    return json.loads(arr)


def get_hot_rooms(page: int = 1) -> dict:
    """
    全站最热房间列表 (mixList/0_0) —— 首页推荐的最佳 JSON 替代接口。
    返回 {rooms:[...], pgcnt:int, ct:{...}}
    """
    return get_cate_rooms(0, 0, page)


# ==========================================================================
# 需求 2: 搜索
# ==========================================================================
class DouyuRiskControl(RuntimeError):
    """搜索接口被风控拦截 (error=8/9)。等待冷却或换出口 IP 后重试。"""


def _data_or_raise(j: dict, path: str) -> dict:
    """
    统一处理 {"error":0,"data":{...}} 包装。
    风控 (error 8/9) 抛 DouyuRiskControl, 其它错误抛 RuntimeError。
    """
    err = j.get("error", j.get("code", 0))
    if err in (0, 200):
        return j.get("data") or {}
    msg = j.get("msg") or j.get("message") or ""
    if err in (8, 9) or "风险" in str(msg) or "异常" in str(msg):
        raise DouyuRiskControl("%s 被风控: error=%s msg=%s" % (path, err, msg))
    raise RuntimeError("%s 返回错误: error=%s msg=%s" % (path, err, msg))


def search_show(kw: str, page: int = 1, page_size: int = 20) -> dict:
    """搜索直播间/主播。返回 {relateShow:[{rid,nickName,roomName,roomSrc,
    cateName,cid,hot,isLive,avatar,...}], total, pageSize}

    ⚠ 该接口有 IP 级风控, 触发时抛 DouyuRiskControl。
    """
    return _data_or_raise(get_json("/japi/search/api/searchShow",
                                   {"kw": kw, "page": page, "pageSize": page_size}),
                          "searchShow")


def search_user(kw: str, page: int = 1, page_size: int = 10) -> dict:
    """搜索用户 (主播账号)。⚠ 同 searchShow, 有风控。"""
    return _data_or_raise(get_json("/japi/search/api/searchUser",
                                   {"kw": kw, "page": page, "pageSize": page_size}),
                          "searchUser")


def search_video(kw: str, page: int = 1, page_size: int = 20) -> dict:
    """搜索录播视频。⚠ 有风控。"""
    return _data_or_raise(get_json("/japi/search/api/searchVideo",
                                   {"kw": kw, "page": page, "pageSize": page_size}),
                          "searchVideo")


def search_topic(kw: str) -> dict:
    """搜索话题。"""
    return _data_or_raise(get_json("/japi/search/api/searchTopic", {"kw": kw}),
                          "searchTopic")


def search_rec(kw: str) -> list[dict]:
    """搜索联想/分类直达。返回 [{cid,icon,kw,name,shortName}]"""
    j = get_json("/japi/search/api/getSearchRec", {"kw": kw})
    return (j.get("data") or {}).get("cateResult", [])


def search_all(kw: str, page: int = 1, page_size: int = 20) -> dict:
    """
    聚合搜索 (V8) —— 一次拿到 直播间/主播/分类/视频/赛事/话题。
    返回 {relateShow, relateUser, relateCate, relateVideo, relateMatch,
          relateTopic, relateActivity, total, sort, guessIntention}

    ⚠ 该接口风控最严 (error=9 搜索行为异常), 触发时抛 DouyuRiskControl。
    """
    return _data_or_raise(get_json("/wgapi/livenc/search/overallSearchV8",
                                   {"kw": kw, "page": page, "pageSize": page_size}),
                          "overallSearchV8")


def search_hot_words() -> list:
    """搜索热词。"""
    d = get_json("/wgapi/livenc/search/searchWordDefault")
    return d.get("data") or d


def search_word_rec(kw: str) -> list:
    """搜索下拉推荐词。"""
    d = get_json("/wgapi/livenc/search/searchWordRec", {"kw": kw})
    return d.get("data") or d


def hot_rank() -> list[dict]:
    """主播热度榜。"""
    d = get_json("/japi/search/api/hotRankV1").get("data", {})
    return (d.get("anchorRank") or {}).get("list", [])


# ==========================================================================
# 需求 3: 分类 / 二级子菜单
# ==========================================================================
def get_cate_nav() -> dict:
    """
    左侧分类导航, 含全部一级/二级分类。

    返回 {"cateList":[{id, cn1, stn1, relId, isCate1,
                       list:[{cid1, cid2, cn2, stn2, url}]}],
          "matchList":[...]}
    """
    return get_json("/wgapi/live/liveweb/getLeftNav").get("data", {})


def iter_cates():
    """展平所有二级分区: yield (cid1, cid2, cn2, url)"""
    for c1 in get_cate_nav().get("cateList", []):
        for s in (c1.get("list") or []):
            yield s.get("cid1"), s.get("cid2"), s.get("cn2"), s.get("url")


def get_cate_rooms(cid1: int, cid2: int, page: int = 1) -> dict:
    """
    分区房间列表。cid1=0,cid2=0 为全站最热; 单个分区用 cid1=2。

    实测: cid2 取自 getLeftNav 的二级菜单, 请求路径固定用 2_{cid2}。
    返回 {rooms:[{rid,rn,nn,uid,av,ol,cid1,cid2,cid3,rs1,rs16,...}],
          pgcnt:int, ct:{...}}
    """
    d = get_json("/gapi/rkc/directory/mixList/%s_%s/%s" % (cid1, cid2, page)).get("data", {})
    return {"rooms": d.get("rl") or [], "pgcnt": d.get("pgcnt") or 0, "ct": d.get("ct") or {}}


def get_cate_rooms_all(cid2: int, max_pages: int = 10) -> list[dict]:
    """自动翻页拉完一个分区。"""
    out, page = [], 1
    while page <= max_pages:
        r = get_cate_rooms(2, cid2, page)
        out.extend(r["rooms"])
        if page >= (r["pgcnt"] or 1) or not r["rooms"]:
            break
        page += 1
    return out


def search_rooms_by_cate(kw: str) -> list[dict]:
    """
    不依赖搜索接口的「按关键词找直播间」兜底方案。

    搜索接口 (/japi/search/api/searchShow, searchUser, overallSearchV8) 有 IP 级风控,
    高频调用后会返回 {"error":8,"msg":"您的行为可能存在风险, 请完成验证"}。
    本函数改为: 关键词 → getSearchRec 映射到分类 → 拉该分类房间 → 按标题/主播名过滤。

    ⚠ 注意 getSearchRec 也会被风控, 但比 searchShow 宽松很多。
    """
    import time
    cands = []
    try:
        cands = search_rec(kw)
    except Exception:
        pass
    seen, out = set(), []
    for c in cands:
        cid = c.get("cid")
        if not cid:
            continue
        try:
            rooms = get_cate_rooms(2, cid)["rooms"]
        except Exception:
            continue
        for r in rooms:
            k = str(r.get("rid"))
            if k in seen:
                continue
            text = "%s %s" % (r.get("rn") or "", r.get("nn") or "")
            if kw.lower() in text.lower() or c.get("name", "") in text:
                seen.add(k)
                out.append(r)
        time.sleep(0.3)
    return out


# ==========================================================================
# 需求 4: 直播流 (含多清晰度)
# ==========================================================================
def get_encryption(did: str = DEFAULT_DID) -> dict:
    """
    取本次会话的签名密钥。

    返回 {key, rand_str, enc_time, expire_at, is_special,
          cpp:{danmu:{key_ver,key}, heartbeat:{key_ver,key}}, enc_data}
    """
    return get_json("/wgapi/livenc/liveweb/websec/getEncryption", {"did": did})["data"]


def sign_stream(enc: dict, rid: int | str, ts: int | None = None) -> tuple[str, int]:
    """
    直播流签名 (逆向自 js 播放器 signer):
        f = rand_str
        重复 enc_time 次: f = md5(f + key)
        auth = md5(f + key + str(rid) + str(ts))
    返回 (auth, ts)
    """
    ts = ts or int(time.time())
    f = enc["rand_str"]
    for _ in range(int(enc.get("enc_time") or 1)):
        f = md5(f + enc["key"])
    return md5(f + enc["key"] + str(rid) + str(ts)), ts


def get_play_info(rid: int | str, rate: int = -1, cdn: str = "", iar: int = 0,
                  ive: int = 0, did: str = DEFAULT_DID, enc: dict | None = None) -> dict:
    """
    请求 /lapi/live/getH5PlayV1/{rid} 拿到播放信息。

    ★ 关键参数 (决定能否拿到指定清晰度):
        iar=0  服务端才会**真正遵守 rate**; iar=1 时永远回最高清晰度。
        rate   目标清晰度 (0=原画, 4=蓝光4M, 3=超清, 2=高清) —— 具体值以
               multirates 列表为准, 每个直播间不同。
        ive=1  强制降级到最低档 (备用手段)
        cdn    "hw-h5" / "hs-h5" 切 CDN 线路

    返回 data 字典, 主要字段:
        room_id, rtmp_url, rtmp_live, rate, rtmp_cdn, selected_cdn,
        multirates:[{name, rate, bit, highBit}], cdnsWithName:[{name,cdn,isH265}],
        p2pMeta:{...}, p2pCid, streamStatus, show_id, client_ip
    播放地址 = rtmp_url + "/" + rtmp_live
    """
    enc = enc or get_encryption(did)
    auth, ts = sign_stream(enc, rid)
    form = {
        "enc_data": enc["enc_data"],
        "tt": ts,
        "did": did,
        "auth": auth,
        "cdn": cdn,
        "rate": rate,
        "ver": PLAYER_VER,
        "iar": iar,
        "ive": ive,
        "prev": 1,
        "bs": 2,
    }
    j = post_json("/lapi/live/getH5PlayV1/%s" % rid, form)
    if j.get("error"):
        raise RuntimeError("getH5PlayV1 error=%s msg=%s" % (j.get("error"), j.get("msg")))
    return j["data"]


def get_stream_urls(rid: int | str, did: str = DEFAULT_DID,
                    cdns: tuple[str, ...] = ("", "hw-h5", "hs-h5")) -> dict:
    """
    ★ 拿到一个直播间的**所有清晰度**播放地址。

    做法: 先请求一次拿到 multirates (该房间真实支持的档位列表),
    再对每个 rate 各请求一次 (iar=0 才生效), 拿到各自签名的 flv 地址。

    返回 {
      "room_id": int,
      "rates": [{"name":"原画1080P60","rate":0,"bit":14208,
                 "url":"https://.../xxx.flv?wsAuth=...","cdn":"hs-h5"}],
      "multirates": [...],          # 服务端原始档位表
      "cdns": [...],                # 可用 CDN 线路
      "p2p": {...},                 # P2P 元数据
    }
    说明: 直接改 rtmp_live 里的 _4000/_900 后缀是**无效**的 (wsAuth 与档位绑定,
          会 403), 必须每个档位单独请求签名。
    """
    enc = get_encryption(did)
    base = get_play_info(rid, rate=-1, iar=0, did=did, enc=enc)
    rates_out = []
    for mr in base.get("multirates") or []:
        r = int(mr.get("rate"))
        try:
            info = get_play_info(rid, rate=r, iar=0, did=did, enc=enc)
        except Exception as e:                                   # 某些档位可能不可用
            rates_out.append({"name": mr.get("name"), "rate": r,
                              "bit": mr.get("bit"), "url": None, "error": str(e)})
            continue
        rates_out.append({
            "name": mr.get("name"),
            "rate": r,
            "bit": mr.get("bit"),
            "actual_rate": info.get("rate"),
            "cdn": info.get("selected_cdn"),
            "url": "%s/%s" % (info.get("rtmp_url"), info.get("rtmp_live")),
        })
    return {
        "room_id": base.get("room_id"),
        "rates": rates_out,
        "multirates": base.get("multirates") or [],
        "cdns": base.get("cdnsWithName") or [],
        "p2p": base.get("p2pMeta") or {},
        "stream_status": base.get("streamStatus"),
    }


# ==========================================================================
# 需求 6: 房间信息 / 其它
# ==========================================================================
def get_room_info(rid: int | str) -> dict:
    """
    房间完整信息 (107KB 级大对象)。
    主要字段: room_id, room_name, nickname, owner_uid, avatar, cate_id,
              cate2_id, show_id, status, videoLoop, chat_level, ...
    """
    return get_json("/betard/%s" % rid).get("room", {})


def get_gateway(rid: int | str) -> dict:
    """弹幕网关地址列表: {gateway:[{ip,port}], wss:[{domain,port}], ...}"""
    return get_json("/lapi/live/gateway/web/%s?isH5=1" % rid).get("data", {})


def get_room_switch(rid: int | str) -> dict:
    """房间开关配置 (是否需要密码/付费/青少年模式等)。"""
    return get_json("/wgapi/live/liveweb/roomapi/biz/getSwitch", {"rid": rid}).get("data", {})


def get_room_loop_info(rid: int | str) -> dict:
    """轮播/回放信息。"""
    return get_json("/wgapi/live/liveweb/getRoomLoopInfo", {"rid": rid}).get("data", {})


def get_custom_cates() -> list:
    """登录用户的定制分区 (匿名返回 [])。"""
    d = get_json("/japi/weblist/apinc/getUserCustomConfigCate")
    return d.get("data") or []


def get_ads_info(posid: int | str = 1) -> dict:
    """首页广告位信息 (posid 必传, 否则 400)。"""
    return get_json("/japi/home/getAdsInfo", {"posid": posid}).get("data", {})


def get_latest_version() -> dict:
    """PC 客户端最新版本号。"""
    return get_json("/wgapi/livenc/release/pc/latestVersion").get("data", {})


# ==========================================================================
# 开放 API (open.douyucdn.cn) —— 老版公开接口, 仍在服务
# 优点: 结构简单、无需签名; 缺点: 每页最多 30 条、无多清晰度流地址
# ==========================================================================
OPEN = "https://open.douyucdn.cn/api/RoomApi"


def _open(path: str, params: dict | None = None) -> dict:
    url = OPEN + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    j = json.loads(request(url).decode("utf-8", "replace"))
    if j.get("error"):
        raise RuntimeError("RoomApi error=%s %s" % (j.get("error"), j.get("data")))
    return j.get("data")


def open_live(cid: int = 0, page: int = 1, limit: int = 30) -> list[dict]:
    """
    开放 API 的直播列表 (每页固定最多 30 条, limit 传更大无效)。
    cid 为开放 API 的**分类 id** (与 web 的 cid2 编号不同): 6=CS2, 1=英雄联盟,
    完整映射见 open_games() 的 cate_id。
    字段: room_id, room_src, room_name, owner_uid, online, hn, nickname, url
    """
    if cid:
        return _open("/live/%d" % cid, {"limit": limit, "page": page})
    return _open("/live", {"limit": limit, "page": page})


def open_room(rid: int | str) -> dict:
    """
    开放 API 的房间信息 + **完整礼物列表** (151 条, 含 id/name/pc(价格)/gx(经验)/img)。
    字段: room_id, room_thumb, cate_id, cate_name, room_name, room_status,
          start_time, owner_name, avatar, online, hn, fans_num, gift[]
    """
    return _open("/room/%s" % rid)


def open_games() -> list[dict]:
    """全部分类 (3222 个游戏/分区), 字段 cate_id, game_name, short_name, game_url, game_src, game_icon。"""
    return _open("/game")


def open_room_gifts(rid: int | str) -> list[dict]:
    """房间可送礼物列表 (来自 open_room)。"""
    return open_room(rid).get("gift") or []


# ==========================================================================
# 弹幕 (需求 5) —— 转发到 douyu_danmaku 模块
# ==========================================================================
def watch_danmaku(rid, on_message=None, seconds: int = 60):
    """
    订阅直播间弹幕。

        from douyu_api import watch_danmaku
        watch_danmaku(24422, lambda m: print(m.get("nn"), m.get("txt")), 60)

    回调收到 dict, type 字段区分: chatmsg(弹幕) / uenter(进场) / dgb(礼物)
    实现见 douyu_danmaku.py (需要 pip install websockets)
    """
    from douyu_danmaku import cli, DouyuDanmaku
    if on_message is None:
        return cli(rid, seconds)
    import asyncio

    async def runner():
        c = DouyuDanmaku(rid, on_message)
        try:
            await asyncio.wait_for(c.run(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
    asyncio.run(runner())


# ==========================================================================
# CLI 演示
# ==========================================================================
if __name__ == "__main__":
    import sys

    def show(title, obj, limit=5):
        print("\n" + "=" * 70)
        print(title)
        print("=" * 70)
        if isinstance(obj, list):
            for x in obj[:limit]:
                print(" ", json.dumps(x, ensure_ascii=False)[:200])
        elif isinstance(obj, dict):
            print(json.dumps(obj, ensure_ascii=False)[:1200])
        else:
            print(obj)

    show("1) 首页推荐", get_home_recommend(), 3)
    try:
        show("2) 搜索 cs2", search_show("cs2", page_size=3), 3)
    except DouyuRiskControl as e:
        print("\n" + "=" * 70)
        print("2) 搜索 cs2 —— 被风控 (%s)，改用分类兜底" % e)
        print("=" * 70)
        for r in search_rooms_by_cate("cs2")[:5]:
            print("   %-9s %-14s %s" % (r.get("rid"), r.get("nn"), str(r.get("rn"))[:30]))
    show("3) 分类导航", get_cate_nav().get("cateList", []), 2)
    print("\nCS2 分区 (cid2=6) 房间:")
    for r in get_cate_rooms(2, 6)["rooms"][:5]:
        print("   %-9s %-14s %s" % (r.get("rid"), r.get("nn"), str(r.get("rn"))[:30]))
    print("\n4) 多清晰度直播流 (rid=24422):")
    s = get_stream_urls(24422)
    for r in s["rates"]:
        print("   %-12s rate=%s bit=%s %s" % (r["name"], r["rate"], r["bit"], (r["url"] or "")[:90]))
