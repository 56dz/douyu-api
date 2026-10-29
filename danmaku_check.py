"""弹幕真实连通性检查: 连上直播间, 收 15 秒消息, 报告收到哪些类型。

用法: PYTHONIOENCODING=utf-8 python danmaku_check.py [rid] [秒数]
"""
import asyncio
import sys
import time

from douyu_danmaku import DouyuDanmaku


def main(rid=24422, seconds=15):
    got = {"chatmsg": 0, "uenter": 0, "dgb": 0}
    samples = []
    t0 = time.time()

    def on_msg(m):
        t = m.get("type") or ""
        if t in got:
            got[t] += 1
            if t == "chatmsg" and len(samples) < 5:
                samples.append("%s: %s" % (m.get("nn"), m.get("txt")))
        elif t.startswith("_"):
            print("  [sys]", t, {k: v for k, v in m.items() if k != "type"})

    async def runner():
        c = DouyuDanmaku(rid, on_msg)
        try:
            await asyncio.wait_for(c.run(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    print("连接直播间 %s, 采集 %s 秒..." % (rid, seconds))
    asyncio.run(runner())
    print("\n耗时 %.1fs" % (time.time() - t0))
    print("弹幕 chatmsg : %d 条" % got["chatmsg"])
    print("进场 uenter : %d 条" % got["uenter"])
    print("礼物 dgb    : %d 条" % got["dgb"])
    for s in samples:
        print("   >", s)
    if got["chatmsg"] == 0 and got["uenter"] == 0:
        print("\n[警告] 15 秒内没有收到任何消息, 可能房间冷清或连接异常")
        return 1
    print("\n[OK] 弹幕链路正常")
    return 0


if __name__ == "__main__":
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else 24422
    sec = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    sys.exit(main(rid, sec))
