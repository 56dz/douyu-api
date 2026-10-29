# 斗鱼 (douyu.com) Web API 逆向文档

对斗鱼网页版 `https://www.douyu.com/` 的接口逆向结果，**全部接口已实测通过**（2026-10）。

- 除弹幕外**不需要 cookie、不需要登录**，纯 HTTP 即可
- 弹幕走 WebSocket，**匿名游客登录**即可收全量弹幕
- 环境：Python 3.10+，仅弹幕需要 `pip install websockets`

### 六项能力一览

| # | 需求 | 实现 | 状态 |
|---|---|---|---|
| 1 | 首页推荐 | `get_home_recommend()` 解析 Next.js RSC 流 | ✅ 18 张卡片 |
| 2 | 搜索直播间 | `search_show()` / `search_all()` / `search_rec()` | ✅ |
| 3 | 分类子菜单（如 CS2 分区） | `get_cate_nav()` / `get_cate_rooms()` | ✅ 5 一级 + 55 二级 |
| 4 | 直播流地址 + 多清晰度 | `get_stream_urls()` | ✅ 4 档全部可播 |
| 5 | 直播弹幕 | `douyu_danmaku.DouyuDanmaku` | ✅ 匿名可收 |
| 6 | 尽量多接口 | 见 [ENDPOINTS.md](ENDPOINTS.md) | ✅ 100+ 个 |

> 本项目仅用于学习研究，请勿用于商业用途或高频抓取。接口随时可能变更。

---

## 目录

| 文件 | 说明 |
|---|---|
| `douyu_api.py` | **统一模块**，封装全部 HTTP 接口 |
| `douyu_danmaku.py` | 弹幕客户端（WebSocket 协议实现） |
| `selftest.py` | 全接口自检，31 项 |
| `danmaku_check.py` | 弹幕真实连通性检查（连房间收 N 秒） |
| `README.md` | 本文档：原理与用法 |
| `ENDPOINTS.md` | **接口速查表**：全部 100+ 接口及可用状态 |
| `home_recommend.py` | 首页推荐解析（独立版） |
| `stream_test.py` | 直播流签名（独立版，最小实现） |
| `grab_page_js.py` | 抓取任意页面引用的 JS chunk（逆向辅助） |
| `grab_js.py` | 批量抓取 JS chunk（旧版脚本） |

`js/`、`js_room/`（首页 / 直播间页的 JS bundle，各 39 个 chunk）体积约 8MB，
未纳入版本库，可用 `grab_page_js.py` 自行抓取。

快速开始：

```bash
pip install websockets             # 仅弹幕需要
python selftest.py                 # 全接口自检 (31 项)
python douyu_api.py                # 演示 1/2/3/4 四项
python danmaku_check.py 24422 30   # 弹幕连通性检查
python douyu_danmaku.py 24422 60   # 实时弹幕 60 秒
```

```python
import douyu_api as d

d.get_home_recommend()          # 1. 首页推荐
d.search_show("cs2")            # 2. 搜索直播间
d.get_cate_rooms(2, 6)          # 3. CS2 分区房间
d.get_stream_urls(24422)        # 4. 全清晰度播放地址
d.watch_danmaku(24422, print, 60)  # 5. 弹幕
```

---

## 需求 1：首页推荐

斗鱼首页是 **Next.js App Router 服务端渲染**，推荐位数据**没有公开 JSON 接口**
（`/japi/webHome/*`、`/wbapi/web/homepage/*`、`/wgapi/livenc/liveweb/homeRecommend*`
等几十个猜测路径全部 404）。数据藏在 HTML 的 RSC 流里。

```python
d.get_home_recommend()   # -> list[dict]，每张卡片
```

**逆向原理**：HTML 里有 60+ 个 `self.__next_f.push([1,"..."])` 分片，
把它们拼起来 → 反转义 → 找 `"recommendCards":[` → 括号配对取出数组 → `json.loads`。

卡片结构（实测 18 张：17 直播 + 1 广告）：

```jsonc
{
  "type": 1,                    // 1=直播间, 4=广告
  "cardId": "...",
  "live": {
    "rid": 4349563,
    "roomName": "...", "anchorName": "...", "anchorUid": 123,
    "anchorAvatar": "https://...",
    "cate2Id": 270, "cate2Name": "热门游戏", "cate2Url": "/g_...",
    "hot": 123456, "userCnt": 123, "watchUv": 456, "realHotValue": 789,
    "cover": {"picUrl": "https://...", "coverType": 1, "coverId": 232},
    "showId": 437850481, "tags": [...]
  },
  "dot": {"_rt": "...", "_rank": 1, "_rec_pos": 0}   // 埋点/推荐位信息
}
```

**替代方案**：`get_hot_rooms()` → `mixList/0_0/1`，全站最热 120 间，纯 JSON，更适合程序使用。

---

## 需求 2：搜索

| 接口 | 方法 | 返回 |
|---|---|---|
| `/japi/search/api/searchShow` | `search_show(kw, page, page_size)` | 直播间/主播 |
| `/japi/search/api/searchUser` | `search_user(kw, page, page_size)` | 用户 |
| `/japi/search/api/searchVideo` | `search_video(kw, page, page_size)` | 视频 |
| `/japi/search/api/searchTopic` | `search_topic(kw)` | 话题 |
| `/japi/search/api/getSearchRec` | `search_rec(kw)` | 分类直达（如 cs2 → 射击游戏） |
| `/japi/search/api/hotRankV1` | `hot_rank()` | 主播热度榜 50 条 |
| `/wgapi/livenc/search/overallSearchV8` | `search_all(kw)` | **聚合**：直播/用户/分类/视频/赛事/话题 |
| `/wgapi/livenc/search/searchWordDefault` | `search_hot_words()` | 热词 30 条 |
| `/wgapi/livenc/search/searchWordRec` | `search_word_rec(kw)` | 下拉联想 |

```python
r = d.search_show("cs2")["relateShow"][0]
# {"rid":6830632, "nickName":"完美世界电竞频道2", "roomName":"【重播】PGL...",
#  "roomSrc":"https://rpic...", "cateName":"CS2", "cid":6,
#  "hot":"65.5万", "isLive":1, "avatar":"...", "followStatus":0,
#  "url":"douyuapp://room?..."}
```

### ⚠️ 搜索接口的 IP 级风控

`searchShow` / `searchUser` / `searchVideo` / `overallSearchV8` 调用频率一高就会返回：

```json
{"error": 8, "msg": "您的行为可能存在风险, 请完成验证"}
{"error": 9, "msg": "搜索行为异常"}
```

实测**换设备号（`dy_did`）、换 Cookie、加 `X-Requested-With`、换 Referer 均无效**，
是按出口 IP 限流的，冷却时间数分钟以上。封装里已统一处理：

```python
try:
    r = d.search_show("cs2")
except d.DouyuRiskControl:
    r = d.search_rooms_by_cate("cs2")   # 兜底：分类映射 + 标题过滤
```

`search_rooms_by_cate(kw)` 不碰搜索接口：`getSearchRec` 拿到分类 cid → 拉该分区
房间 → 按房间标题/主播名过滤。风控期间仍然可用（实测 `cs2` 能筛出 2 个正在播的 CS2 房间）。

不受风控影响的搜索相关接口：`getSearchRec`、`hotRankV1`、`searchWordRec`、`searchTopic`。

`overallSearchV8` 的 `data` 结构：
`{relateShow{total,list}, relateUser{total,list}, relateCate, relateVideo,
relateMatch, relateTopic, relateActivity, relateToken, total, sort[7],
guessIntention, redirect, matchTheme, flowContent, version}`

---

## 需求 3：分类与二级子菜单

```python
nav = d.get_cate_nav()      # 一级 5 个 + 二级 55 个
d.get_cate_rooms(2, 6)      # CS2 分区
d.get_cate_rooms_all(6)     # 自动翻页
```

`GET /wgapi/live/liveweb/getLeftNav` → `data.cateList`：

```jsonc
{"id": 4, "cn1": "网游竞技", "stn1": "PCgame", "relId": 1, "isCate1": 1,
 "list": [{"cid1": 4, "cid2": 6, "cn2": "CS2", "stn2": "CounterStrike",
           "url": "/g_CounterStrike"}, ...]}
```

五个一级分类：网游竞技(4) / 单机热游(5) / 手游休闲(6) / 娱乐(20) / 正能量(12)。

### ⚠ 最关键的一条规则

房间列表接口是 `GET /gapi/rkc/directory/mixList/{cid1}_{cid2}/{page}`，
但**路径里的 cid1 恒为 `2`，不是 `getLeftNav` 里那个 cid1**：

```
mixList/2_6/1    → 59 间   ✅ CS2
mixList/4_6/1    → 0 间    ❌ 用 getLeftNav 的 cid1 会空
mixList/0_0/1    → 120 间  全站最热
```

55 个二级分区用 `2_{cid2}` 全部验证通过。

房间字段：`rid, rn(标题), nn(主播), uid, av(头像), ol(热度), cid1, cid2, cid3,
c2name, c2url, rs1/rs16(封面), utag, roomLabel, type, url, authInfo, ...`
分页：`data.pgcnt` 为总页数。

实测房间数：英雄联盟 112 / 热门游戏 102 / 三角洲行动 98 / CS2 59 / 炉石 28 /
王者荣耀 120(pgcnt=2) / 星秀 120(pgcnt=2) / 主机游戏 120(pgcnt=4)。

---

## 需求 4：直播流地址（多清晰度）

### 签名算法（核心）

```
1. GET /wgapi/livenc/liveweb/websec/getEncryption?did={did}
   → {key, rand_str, enc_time, expire_at, enc_data, cpp:{danmu,heartbeat}}

2. f = rand_str
   for _ in range(enc_time):  f = md5(f + key)
   auth = md5(f + key + str(rid) + str(ts))

3. POST /lapi/live/getH5PlayV1/{rid}   (form-urlencoded)
   enc_data, tt=ts, did, auth, cdn, rate, ver, iar, ive, prev=1, bs=2
```

播放地址 = `data.rtmp_url + "/" + data.rtmp_live`。

### 多清晰度的关键参数

| 参数 | 作用 |
|---|---|
| **`iar=0`** | **服务端才真正遵守 `rate`**。`iar=1` 永远返回最高清晰度 |
| `rate` | 目标档位：0=原画, 4=蓝光4M, 3=超清, 2=高清（**每间不同，以 multirates 为准**） |
| `ive=1` | 强制降级到最低档 |
| `cdn` | 线路代码：`hw-h5`（线路7）/ `hs-h5`（线路13） |
| `ver` | `Douyu_224011102` 或 `Douyu_new`（JS 里真实常量是后者） |

### 用法

```python
s = d.get_stream_urls(24422)
# {"room_id": 24422,
#  "rates": [{"name":"原画1080P60","rate":0,"bit":14218,"actual_rate":4,
#             "cdn":"hs-h5","url":"https://huos1a.douyucdn2.cn/live/24422rykeUuFd2TN_4000.flv?wsAuth=..."},
#            {"name":"蓝光4M","rate":4,...},
#            {"name":"超清","rate":3,...},
#            {"name":"高清","rate":2,...}],
#  "multirates": [...], "cdns": [...], "p2p": {...}}
```

`get_stream_urls` 的实现：先请求一次拿 `multirates`（该房间真实支持的档位表），
再对每个 `rate` 各请求一次（`iar=0`），得到各自签名的地址。

实测（rid 24422）：rate 0/4/3/2 → `_4000.flv` / `_4000.flv` / `_2000.flv` / `_900.flv`，
**四个地址全部 HTTP 200 `video/x-flv`，可直接 ffplay/VLC 播放**。

### ⚠ 两个坑

1. **不能改后缀复用签名**。把 `_4000` 手动改成 `_900` 而沿用同一个 `wsAuth`，
   会返回 **403 Forbidden** —— 签名与档位绑定，每个档位必须单独请求。
2. **原画可能别名到蓝光**。部分房间（如 24422）`multirates` 列了"原画1080P60"，
   但请求 `rate=0` 返回的仍是 `_4000`（`actual_rate=4`）；只有 249813 / 67554 这类
   房间 `rate=0` 才真正返回无后缀的原画流。

### 其它流形态

`data` 里还带 P2P/H265 信息：
`p2pMeta{pcdn_api_domain, xp2p_api_domain, xp2p_unity_api_domain, stream_props[{sid,txSecret}],
stun, xp2p_txSecret, xp2p_txTime}`，`p2pCid`，`av1_url`，`rtc_stream_url`，`h265_p2p`。

P2P 切片地址实测：
- `https://sdkapi-unity.douyucdn.cn/{sid}.xs` → 200（194B JSON）
- `https://dyp2p-hw.douyucdn.cn/{sid}.xs` → 200（73B JSON）
- `https://dy-ss.douyucdn.cn/live/{sid}.xs` → 403

---

## 需求 5：直播弹幕

```bash
python douyu_danmaku.py 24422 60
```

```python
from douyu_danmaku import DouyuDanmaku
import asyncio

async def main():
    async def on_msg(m):
        if m.get("type") == "chatmsg":
            print(m["nn"], ":", m["txt"])
    await DouyuDanmaku(24422, on_msg).run()

asyncio.run(main())
```

### 协议要点

**二进制帧**（不是文本帧！）：

```
<u32 len><u32 len><i16 689><u8 0><u8 0><utf8 payload><0x00>
len = 8 + len(payload 含结尾 NUL)
```

**STT 序列化**：`k@=v/k@=v/`，转义 `@`→`@A`、`/`→`@S`。
列表值被二次转义（`@AA=` / `@AS`），需解两层转义后按 `//` 分割。

**两个 socket**：

1. 网关 `wss://wsproxy.douyu.com:{6671..6676}/`（来自 `/lapi/live/gateway/web/{rid}?isH5=1` 的 `data.wss`）
2. 弹幕 `wss://danmuproxy.douyu.com:{8501..8506}/`（来自网关下发的 `msgrepeaterproxylist`）

**网关登录**：`type=loginreq` + `roomid/username=""/password=""/ltkid=""/biz=""/stk=""/
devid/ct=0/pt=2/cvr=0/tvr=7/apd=""/jwt=""/rt/vk/ver=20190610/aver=218101901/dmbt/dmbv/er=1`，
其中 `vk = md5(rt + "r5*^5;}2#${XF[h+;'./.Q'1;,-]f'p[" + devid)`。

**匿名游客登录可用**：返回 `userid` 与 `username=visitorXXXXXXX`，能收到全部弹幕，无需任何账号。

**TLS 坑**：`wsproxy.douyu.com` 拒绝 SNI（`SSLV3_ALERT_HANDSHAKE_FAILURE`），
必须 `server_hostname=None` + `ctx.set_ciphers("DEFAULT:@SECLEVEL=0")` + `CERT_NONE`。

**弹幕消息字段**：`nn`(昵称) `txt`(内容) `level` `col` `cst`(时间戳) `uid` `rid`
`ic`(头像) `bnn`(粉丝牌) `bl` `rg`。

消息类型：`chatmsg`(弹幕) `uenter`(进场) `dgb`(礼物) `loginres` `setmsggroup`
`msgrepeaterproxylist` `memberinfores` `blst` `ctl` `ittl` `fdm` 等。

**心跳**：网关每 ~45s 发 `{type:"keeplive", vbw:<已发送字节数>, cdn:"", tick:<ts>, kd:<服务端下发>}`，
弹幕 socket 发 `{type:"mrkl"}`。

**客户端实现要点**（`douyu_danmaku.py`）：
网关与弹幕两条 socket 用独立 asyncio task 并发收包（早期版本在网关循环里顺带
`recv` 弹幕，会因网关消息稀疏而漏收）；`msgrepeaterproxylist` 的 5 个主机按顺序
故障切换；登录成功后起独立心跳 task。

---

## 需求 6：其它可用接口清单

### 房间相关

| 接口 | 说明 |
|---|---|
| `GET /betard/{rid}` | 房间完整信息（108 字段，107KB） |
| `GET /lapi/live/gateway/web/{rid}?isH5=1` | 弹幕网关 + wss 列表 |
| `GET /wgapi/live/liveweb/roomapi/biz/getSwitch?rid=` | 房间开关/弹幕等级限制 |
| `GET /wgapi/live/liveweb/getRoomLoopInfo?rid=` | 轮播/回放信息 |
| `GET /swf_api/getRoomCloseVod/{rid}` | 相似推荐房间列表 |
| `POST /gapi/live/web/autoswitch/v1/{rid}?client_sys=web_h5` | 自动切流（需 enc 签名，实测报"时间戳错误"，未攻克） |
| `POST /gapi/live/web/super/stream/v1/{rid}` | 超管专用流（需 isSuperManager，返回"鉴权失败"） |

`betard` 房间字段（108 个）摘录：`room_id, room_name, nickname, owner_uid, avatar{big,mid,small},
cate1_id, cate2_id, cate3_id, cate_id, child_id, show_id, status, show_status, videoLoop,
chat_level, chat_group, room_src, bgimg_src, coverSrc, is_vr, isVertical, tags, close_notice,
video_high_quality_resolution(=1440), multirates, nobleConfig, giftActivity, levelInfo,
can_send_gift, speakSet, simplifyBulletScreen, p2p_setting, room_biz_all, share{...},
up_id, yuba_jump_url` 等。

### 语音房（yuba 语聊）`/wgapi/audio/v1/*`

约 24 个接口：`mic/{seatList,joinChat,quitChat,optMic,optVideoMic,userCard,switchJoinChat,
joinList,inviteJoinChat,handleJoinChat,handleInviteJoinChat,cancelJoinChat,cleanAll}`、
`pk/{info,joinTeam,endPK,addTime,honorList,cross/{punishmentInfo,operateRoomMute,
operateInviteRoomPK,inviteRoomPK,endRoomPK}}`、`decoration/{all,batch}`、
`admin/getMyPermission`、`voiceRoom/{sendEmoji,bannedGuest,hotScore/clear,hotScore/batchClear}`。

实测可用（GET）：`mic/seatList?rid=`、`decoration/all?rid=`（370KB）、`admin/getMyPermission?rid=`。

### 搜索/榜单

见需求 2 表格。

### 杂项

| 接口 | 返回 |
|---|---|
| `GET /api/v1/timestamp` | 服务器时间戳 |
| `GET /wgapi/livenc/release/pc/latestVersion` | 客户端最新版本 |
| `GET /japi/weblist/apinc/getUserCustomConfigCate` | 定制分区（匿名 `[]`） |
| `GET /japi/home/getAdsInfo?posid=1` | 首页广告位（**posid 必传**，否则 400；匿名返回空 `{}`） |
| `GET /wgapi/activity/gametask/config` | 游戏任务活动配置 |
| `GET /lapi/member/game/getGameList` | 游戏列表 |
| `GET /wgapi/live/match/baike/videos?rid=` | 赛事百科视频（参数不全时报错） |
| `GET /wgapi/live/match/vod/leagueDetailReplay?rid=` | 赛事回放 |
| `POST /lapi/sign/web/rtpv`、`POST /lapi/sign/web/click` | 广告埋点 |
| `POST /japi/sign/web/getinfo` | 广告位信息 |
| `GET msg.douyu.com/wbapi/web/emotion` | **全站表情包 80KB**（可用） |
| `GET /wgapi/livenc/search/searchWordDefault` | 搜索热词 |

### 需登录（带 cookie 才可用）

`/wgapi/livenc/liveweb/follow/{top3,list,add,rm}`、`/wgapi/livenc/liveweb/csrfApi/getCsrfCookie`、
`/web/member/panel/teenInfo/apinc/query`、`/japi/carnivalApi/nc/sign/getStatus`、
`msg.douyu.com` 的 `/v3/login/getusersig`、`/v1.3/robot/allHash`、`/v1.2/switch`、
`/v3/user/official`、`/mgapi/v2.4/user/role`、`/wgapi/yubanc/api/user/blacklist`
（匿名时均返回 `未登录` / `请提供token` / `Unauthenticated request`）。

### 开放 API（`open.douyucdn.cn/api/RoomApi`）— 老版公开接口，仍在服务

| 接口 | 返回 |
|---|---|
| `GET /game` | **全部分类 3222 个**（cate_id, game_name, short_name, game_url, game_src, game_icon） |
| `GET /live/{cid}?limit=&page=` | 分区直播列表（**每页最多 30 条**），字段 room_id, room_src, room_name, owner_uid, online, hn, nickname, url |
| `GET /live?limit=&page=` | 全站直播列表 |
| `GET /room/{rid}` | 房间信息 + **完整礼物表 151 条**（id, name, pc=价格, gx=经验, mimg/himg） |

```python
d.open_games()          # 3222 个分类
d.open_live(6)          # CS2 直播 30 条
d.open_room(24422)      # 房间 + 151 个礼物
d.open_room_gifts(24422)
```

优点：结构简单、无签名。缺点：每页固定最多 30 条（`limit` 传 120/200 无效）、无多清晰度流地址。
**web 端唯一拿不到的就是礼物列表，这里能拿到**（`betard` 里的 `cfmGiftList` 是空数组）。

---

## 逆向方法记录

1. **抓 JS bundle**：斗鱼的 chunk 不在 `www.douyu.com/_next/static/`（404），
   而在 CDN `https://shark2.douyucdn.cn/front-publish/douyu-web-master/_next/static/chunks/`。
   `grab_page_js.py <页面URL> <输出目录>` 自动提取并下载（39 个 chunk / 页）。
2. **提接口路径**：正则 `["'](/(?:wgapi|japi|lapi|gapi|api|www|web|swf_api|mock|inner)[\w\-/{}.$]*?)["']`
   扫 bundle，得到 67 个候选路径，再逐个用 `selftest` 式探针验证。
3. **找签名逻辑**：`js_room/web-encrypt-*.js` 里有完整 signer；`js_room/7730-*.js`
   里能看到 `getH5PlayV1` 与 `super/stream/v1` 的分支和全部参数拼装。
4. **常量位置**：`ver` 常量 `Douyu_new` 导出为 `d.Hk`，定义在
   `js_room/7310-c395c7027f6620c5.js` 的 module `40519`。
5. **浏览器抓包**：用 browser-skill 插件连真实 Chrome，`bsk_inspect debug start` 后
   `bsk_inspect network` 过滤 url，`bsk_inspect debug request <id> part=request` 看原始请求体，
   用来逐字节比对签名结果。

---

## 已知限制

- 首页推荐没有 JSON 接口，只能解析 HTML（HTML 结构一变就需调整）
- 礼物/榜单/关注/历史 这些接口**不在 web bundle 里**，需登录态且路径未知；
  礼物列表可用开放 API `open_room()` 替代
- `autoswitch`（自动切流）与 `super/stream`（超管流）未完全攻克
- 流地址带 `wsAuth` 签名，有时效性，需现取现用
- 混合流（`is_mixed`）、H265、AV1 房间的流地址字段不同，`av1_url`/`rtc_stream_url`
  在普通房间为空

---

## 免责

本项目仅用于技术研究与学习，接口来自公开网页，请勿用于商业用途或大规模抓取，
遵守斗鱼用户协议与 robots 规则。
