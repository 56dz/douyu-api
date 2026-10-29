"""douyu_api 全接口自检。用法: PYTHONIOENCODING=utf-8 python selftest.py"""
import json
import sys
import traceback

import douyu_api as d

OK, FAIL, SKIP = [], [], []


def check(name, fn):
    try:
        r = fn()
        n = len(r) if isinstance(r, (list, dict)) else r
        OK.append((name, n))
        print("  [OK]   %-32s %s" % (name, n))
        return r
    except d.DouyuRiskControl as e:
        SKIP.append((name, str(e)[:80]))
        print("  [SKIP] %-32s 风控拦截 (非代码问题)" % name)
        return None
    except Exception as e:
        FAIL.append((name, repr(e)[:120]))
        print("  [FAIL] %-32s %s" % (name, repr(e)[:120]))
        return None


print("=" * 78)
print("1. 首页推荐")
print("=" * 78)
rec = check("get_home_recommend()", d.get_home_recommend)
if rec:
    live = [c for c in rec if c.get("type") == 1]
    print("         卡片 %d 张 (直播 %d, 广告/其它 %d)" % (len(rec), len(live), len(rec) - len(live)))
    if live:
        L = live[0]["live"]
        print("         例: rid=%s %s / %s" % (L.get("rid"), L.get("anchorName"), L.get("roomName")))
check("get_hot_rooms()", lambda: d.get_hot_rooms()["rooms"])

print("\n" + "=" * 78)
print("2. 搜索")
print("=" * 78)
sh = check("search_show('cs2')", lambda: d.search_show("cs2")["relateShow"])
if sh:
    r = sh[0]
    print("         例: rid=%s %s | %s" % (r.get("rid"), r.get("nickName"), r.get("roomName")))
check("search_user('cs2')", lambda: d.search_user("cs2")["relateUser"])
check("search_rec('cs2')", lambda: d.search_rec("cs2"))
sa = check("search_all('英雄联盟')", lambda: d.search_all("英雄联盟"))
if sa:
    print("         聚合: 直播%d 用户%d 分类%d 视频%d 话题%d" % (
        len((sa.get("relateShow") or {}).get("list") or []),
        len((sa.get("relateUser") or {}).get("list") or []),
        len(sa.get("relateCate") or []),
        len(sa.get("relateVideo") or []),
        len(sa.get("relateTopic") or [])))
check("search_hot_words()", d.search_hot_words)
check("search_word_rec('dota')", lambda: d.search_word_rec("dota"))
check("hot_rank()", d.hot_rank)
check("search_video('cs2')", lambda: d.search_video("cs2")["relateVideo"])
check("search_topic('cs2')", lambda: d.search_topic("cs2")["relateTopic"])
check("search_rooms_by_cate('cs2')  # 风控兜底", lambda: d.search_rooms_by_cate("cs2"))

print("\n" + "=" * 78)
print("3. 分类 / 子菜单")
print("=" * 78)
nav = check("get_cate_nav()", d.get_cate_nav)
cates = list(d.iter_cates())
if nav:
    print("         一级 %d 个, 二级 %d 个" % (len(nav.get("cateList") or []), len(cates)))
    for c1 in nav["cateList"]:
        print("           %-8s (%d 个二级)" % (c1.get("cn1"), len(c1.get("list") or [])))
    cs2 = [c for c in cates if c[2] == "CS2"]
    print("         CS2 记录: cid1=%s cid2=%s url=%s" % (cs2[0][0], cs2[0][1], cs2[0][3]) if cs2 else "         CS2 未找到")
r = check("get_cate_rooms(2,6)  # CS2", lambda: d.get_cate_rooms(2, 6)["rooms"])
if r:
    for x in r[:5]:
        print("           %-9s %-16s %s" % (x.get("rid"), x.get("nn"), str(x.get("rn"))[:26]))

print("\n" + "=" * 78)
print("4. 直播流 (多清晰度)")
print("=" * 78)
check("get_encryption()", d.get_encryption)
for rid in (24422, 999):
    s = check("get_stream_urls(%s)" % rid, lambda rid=rid: d.get_stream_urls(rid))
    if not s:
        continue
    for x in s["rates"]:
        print("           %-12s rate=%s bit=%-6s actual=%-2s %s" % (
            x["name"], x["rate"], x["bit"], x.get("actual_rate"), (x.get("url") or x.get("error") or "")[:80]))
    print("           CDN 线路:", [c["name"] + "/" + c["cdn"] for c in s["cdns"]])

print("\n" + "=" * 78)
print("5. 弹幕 (协议自检, 不实际连接)")
print("=" * 78)
import douyu_danmaku as dm
frame = dm.ws_encode("type@=loginreq/roomid@=9999/")
print("  [OK]   ws_encode ->", len(frame), "bytes, header =", frame[:12].hex())
back, _ = dm.ws_decode(frame)
print("  [OK]   ws_decode roundtrip ->", back)
print("  [OK]   stt_decode ->", dm.stt_decode("type@=chatmsg/nn@=abc/txt@=hello@Sworld/"))
print("  [OK]   decode_list ->", dm.decode_list("ip@AA=danmuproxy.douyu.com@ASport@AA=8501@S@S")[:1])
check("get_gateway(24422)", lambda: d.get_gateway(24422)["wss"])
print("  (真实弹幕请运行: python douyu_danmaku.py 24422 30)")

print("\n" + "=" * 78)
print("6. 其它接口")
print("=" * 78)
check("get_room_info(24422)", lambda: d.get_room_info(24422))
check("get_room_switch(24422)", lambda: d.get_room_switch(24422))
check("get_room_loop_info(24422)", lambda: d.get_room_loop_info(24422))
check("get_custom_cates()", d.get_custom_cates)
check("get_ads_info()", d.get_ads_info)
check("get_latest_version()", d.get_latest_version)
check("get_json('/api/v1/timestamp')", lambda: d.get_json("/api/v1/timestamp"))
check("open_live(6)  # CS2", lambda: d.open_live(6))
check("open_room(24422)", lambda: d.open_room(24422))
check("open_room_gifts(24422)", lambda: d.open_room_gifts(24422))
check("open_games()", d.open_games)
check("get_json('/swf_api/getRoomCloseVod/24422')",
      lambda: d.get_json("/swf_api/getRoomCloseVod/24422")["roomlist"])
check("get_json('/wgapi/livenc/search/searchWordDefault')",
      lambda: d.get_json("/wgapi/livenc/search/searchWordDefault")["data"]["list"])

print("\n" + "=" * 78)
print("结果: %d 通过 / %d 失败 / %d 风控跳过" % (len(OK), len(FAIL), len(SKIP)))
if SKIP:
    print("风控跳过 (接口本身可用, 当前 IP 被限流):")
    for n, e in SKIP:
        print("   ~", n)
if FAIL:
    print("失败项:")
    for n, e in FAIL:
        print("   -", n, "->", e)
    sys.exit(1)
