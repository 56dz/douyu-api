# 斗鱼接口速查表

标注说明：✅ 实测可用（匿名） · 🔒 需登录 cookie · ⚠️ 参数未完全攻克 · ❌ 已确认 404/失效

所有 GET 请求建议带：`User-Agent: <Chrome UA>` + `Referer: https://www.douyu.com/`
除特别说明外，base = `https://www.douyu.com`

---

## A. 首页 / 推荐

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `GET /`（解析 RSC） | 首页推荐位，`recommendCards`，18 张卡片 |
| ✅ | `GET /gapi/rkc/directory/mixList/0_0/{page}` | 全站最热 120 间/页，pgcnt=37 |
| ❌ | `/japi/webHome/getHomePageData` 等 | 全部 404，不存在公开 JSON 推荐接口 |
| ✅ | `GET /japi/home/getAdsInfo?posid=1` | 广告位（posid 必传，匿名返回 `{}`） |

## B. 搜索

| 状态 | 接口 | 说明 |
|---|---|---|
| ⚠️ | `GET /japi/search/api/searchShow?kw=&page=&pageSize=` | 直播间/主播（IP 风控 error=8） |
| ⚠️ | `GET /japi/search/api/searchUser?kw=&page=&pageSize=` | 用户（同上） |
| ⚠️ | `GET /japi/search/api/searchVideo?kw=&page=&pageSize=` | 视频（同上） |
| ✅ | `GET /japi/search/api/searchTopic?kw=` | 话题（不受风控） |
| ✅ | `GET /japi/search/api/getSearchRec?kw=` | 分类直达（不受风控） |
| ✅ | `GET /japi/search/api/hotRankV1` | 主播热度榜 50 条 |
| ⚠️ | `GET /wgapi/livenc/search/overallSearchV8?kw=&page=&pageSize=` | 聚合搜索（风控最严 error=9） |
| ✅ | `GET /wgapi/livenc/search/searchWordDefault` | 热词 30 条 |
| ✅ | `GET /wgapi/livenc/search/searchWordRec?kw=` | 下拉联想 |

> ⚠️ = 接口本身完全可用，但按**出口 IP** 限流。高频调用后返回
> `{"error":8,"msg":"您的行为可能存在风险, 请完成验证"}`；换 did / Cookie / Referer
> 都绕不过，需等数分钟冷却。代码里捕获 `douyu_api.DouyuRiskControl`，
> 用 `search_rooms_by_cate(kw)` 兜底。

## C. 分类

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `GET /wgapi/live/liveweb/getLeftNav` | 一级 5 + 二级 55 分类树 |
| ✅ | `GET /gapi/rkc/directory/mixList/2_{cid2}/{page}` | **分区房间列表（cid1 恒为 2）** |
| ✅ | `GET /gapi/rkc/directory/mixList/0_0/{page}` | 全站 |
| ✅ | `GET /japi/weblist/apinc/getUserCustomConfigCate` | 定制分区（匿名 `[]`） |
| ✅ | `GET open.douyucdn.cn/api/RoomApi/game` | 3222 个分类全表 |
| ✅ | `GET open.douyucdn.cn/api/RoomApi/live/{cid}?page=` | 分区直播（30 条/页） |

## D. 直播流

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `GET /wgapi/livenc/liveweb/websec/getEncryption?did=` | 签名密钥 |
| ✅ | `POST /lapi/live/getH5PlayV1/{rid}` | **播放信息（多清晰度）** |
| ⚠️ | `POST /gapi/live/web/autoswitch/v1/{rid}?client_sys=web_h5` | 自动切流，报"时间戳错误" |
| ⚠️ | `POST /gapi/live/web/super/stream/v1/{rid}` | 超管流，报"鉴权失败" |
| ✅ | `GET /lapi/live/gateway/web/{rid}?isH5=1` | 弹幕网关 + wss 列表 |
| ✅ | `GET /api/v1/timestamp` | 服务器时间 |

## E. 房间

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `GET /betard/{rid}` | 房间全量信息 108 字段 |
| ✅ | `GET /wgapi/live/liveweb/roomapi/biz/getSwitch?rid=` | 弹幕等级/开关 |
| ✅ | `GET /wgapi/live/liveweb/getRoomLoopInfo?rid=` | 轮播/回放 |
| ✅ | `GET /swf_api/getRoomCloseVod/{rid}` | 相似推荐房间 |
| ✅ | `GET open.douyucdn.cn/api/RoomApi/room/{rid}` | 房间信息 + **151 个礼物** |
| ❌ | `/wgapi/livenc/liveweb/rank/*`、`/gift/*` 等 40+ 猜测路径 | 全部 404，web bundle 里没有 |

## F. 弹幕（WebSocket）

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `wss://wsproxy.douyu.com:{6671-6676}/` | 网关（需 server_hostname=None） |
| ✅ | `wss://danmuproxy.douyu.com:{8501-8506}/` | 弹幕 |
| ✅ | `GET msg.douyu.com/wbapi/web/emotion` | 全站表情包 80KB |
| 🔒 | `msg.douyu.com/v3/login/getusersig`、`/v1.3/robot/allHash`、`/v1.2/switch`、`/v3/user/official`、`/mgapi/v2.4/user/role`、`/wgapi/yubanc/api/user/blacklist` | 需 token |
| ✅ | `GET /wgapi/live/liveweb/roomapi/biz/getSwitch` | 弹幕发送权限 |

## G. 语音房 / 语聊

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `GET /wgapi/audio/v1/mic/seatList?rid=` | 麦位列表 |
| ✅ | `GET /wgapi/audio/v1/decoration/all?rid=` | 装饰 370KB |
| ✅ | `GET /wgapi/audio/v1/admin/getMyPermission?rid=` | 权限（匿名 null） |
| 🔒 | `mic/{joinChat,quitChat,optMic,optVideoMic,userCard,switchJoinChat,joinList,inviteJoinChat,handleJoinChat,handleInviteJoinChat,cancelJoinChat,cleanAll}` | 需登录 |
| 🔒 | `pk/{info,joinTeam,endPK,addTime,honorList,cross/*}` | 需登录 |
| 🔒 | `decoration/batch`、`voiceRoom/{sendEmoji,bannedGuest,hotScore/clear,hotScore/batchClear}` | 需登录 |

## H. 用户 / 关注

| 状态 | 接口 | 说明 |
|---|---|---|
| 🔒 | `GET /wgapi/livenc/liveweb/follow/top3` | 关注 Top3 |
| 🔒 | `GET /wgapi/livenc/liveweb/follow/list?page=` | 关注列表 |
| 🔒 | `POST /wgapi/livenc/liveweb/follow/add` / `rm` | 关注/取关 |
| 🔒 | `GET /wgapi/livenc/liveweb/csrfApi/getCsrfCookie` | csrf token |
| 🔒 | `GET /web/member/panel/teenInfo/apinc/query` | 青少年模式 |
| 🔒 | `GET /japi/carnivalApi/nc/sign/getStatus` | 签到状态 |

## I. 活动 / 任务

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `GET /wgapi/activity/gametask/config` | 任务活动配置 |
| 🔒 | `POST /wgapi/activitync/gametask/taskStatus`、`/viewStatus` | 任务进度 |
| 🔒 | `GET /wgapi/activitync/redeemPoints/panel`、`/eggTwistMachinePanel`、`POST /batchBagInfos` | 积分/扭蛋 |
| ✅ | `GET /lapi/member/game/getGameList` | 游戏列表 |

## J. 赛事

| 状态 | 接口 | 说明 |
|---|---|---|
| ⚠️ | `GET /wgapi/live/match/baike/videos?rid=` | 需完整参数 |
| ⚠️ | `GET /wgapi/live/match/vod/leagueDetailReplay?rid=` | 需赛事 ID |
| ❌ | `/wgapi/live/match/baike/league-options` | 404 |

## K. 埋点 / 广告 / 杂项

| 状态 | 接口 | 说明 |
|---|---|---|
| ✅ | `POST /lapi/sign/web/rtpv` | 曝光埋点 |
| ✅ | `POST /lapi/sign/web/click` | 点击埋点 |
| ✅ | `POST /japi/sign/web/getinfo` | 广告位信息 |
| ✅ | `GET rtbapi.douyucdn.cn/japi/sign/web/getconfig?posid=&roomid=&cate1=&cate2=` | 广告配置 |
| ✅ | `GET /wgapi/livenc/release/pc/latestVersion` | 客户端版本 |
| ✅ | `GET wconf.douyucdn.cn/resource/common/property_info_22.json` | 配置 |
| ✅ | `GET wconf.douyucdn.cn/resource/common/home_top_activity_info.json` | 首页活动 |
| ✅ | `GET webconf.douyucdn.cn/package/live_room_flash.json` | 房间 flash 配置 |
| ✅ | `POST streamdot.douyucdn.cn/tianshu/access/gate/nreport/{30,305}` | 播放埋点 |
| ✅ | `GET uact.douyucdn.cn/uact.do` | 活动（无参返回 400，需带业务参数） |

---

## 统计

- 实测可用（匿名）：**40+**
- 需登录：**约 20**
- 参数未攻克：**4**（autoswitch、super/stream、baike/videos、leagueDetailReplay）
- 已确认失效：**60+**（主要是不存在的礼物/榜单/历史接口）

---

## 两套编号系统

| | web 端 | 开放 API |
|---|---|---|
| 分类 id | `cid2`（CS2=6, LOL=1, 热门游戏=270, 王者荣耀=181, 星秀=1008） | `cate_id`（**数值完全相同**：CS2=6, LOL=1, 热门游戏=270, 王者荣耀=181, 星秀=1008） |
| 房间列表 | `mixList/2_{cid2}/{page}`，120 条/页，pgcnt 可翻页 | `RoomApi/live/{cid}?page=`，**固定 30 条/页** |
| 直播流 | `getH5PlayV1`，多清晰度 | 无 |
| 礼物 | 无 | `RoomApi/room/{rid}` 里 151 个 |

好消息：两套的分类 id 数值一致，`getLeftNav` 拿到的 `cid2` 可直接喂给
`open_live(cid)`；但 web 端路径里必须写 `2_{cid2}`，不能写 `{cid1}_{cid2}`。
