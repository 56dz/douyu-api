"""从斗鱼首页 Next.js RSC 流中提取首页推荐卡片 (无需浏览器)。"""
import re, json, sys

def load_pushes(html):
    return re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)

def unescape(js):
    # RSC chunk 是 JS 字符串字面量内容, 只需处理 \" \n \\ \uXXXX
    out = []
    i, n = 0, len(js)
    while i < n:
        c = js[i]
        if c == "\\" and i + 1 < n:
            d = js[i+1]
            if d == "n": out.append("\n"); i += 2; continue
            if d == "t": out.append("\t"); i += 2; continue
            if d == "r": out.append("\r"); i += 2; continue
            if d == '"': out.append('"'); i += 2; continue
            if d == "\\": out.append("\\"); i += 2; continue
            if d == "u":
                out.append(chr(int(js[i+2:i+6], 16))); i += 6; continue
            if d == "/": out.append("/"); i += 2; continue
        out.append(c)
        i += 1
    return "".join(out)

def extract_json_array(txt, key):
    i = txt.find('"%s":' % key)
    if i < 0:
        return None
    start = txt.index("[", i)
    depth = 0
    instr = False
    esc = False
    for j in range(start, len(txt)):
        ch = txt[j]
        if instr:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': instr = False
            continue
        if ch == '"': instr = True
        elif ch == "[": depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return txt[start:j+1]
    return None

def main(path=None):
    if path:
        html = open(path, encoding="utf-8").read()
    else:
        import urllib.request
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")
        req = urllib.request.Request("https://www.douyu.com/", headers={"User-Agent": ua})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    txt = unescape("".join(load_pushes(html)))
    arr = extract_json_array(txt, "recommendCards")
    if not arr:
        print("recommendCards not found"); return
    data = json.loads(arr)
    print("共 %d 张推荐卡片" % len(data))
    from collections import Counter
    print("卡片类型分布:", Counter(c.get("type") for c in data if isinstance(c, dict)))
    for c in data:
        if not isinstance(c, dict):
            continue
        live = c.get("live") or {}
        if live:
            print("  [直播] rid=%s 主播=%s 标题=%s 分类=%s 热度=%s 封面=%s"
                  % (live.get("rid"), live.get("anchorName"), live.get("roomName"),
                     live.get("cate2Name"), live.get("hot"), live.get("cover", {}).get("picUrl")))
        else:
            print("  [type=%s] %s" % (c.get("type"), json.dumps(c, ensure_ascii=False)[:160]))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
