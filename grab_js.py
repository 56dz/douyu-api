import os, re, urllib.request, ssl, json, sys
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.douyu.com/"})
        with urllib.request.urlopen(r, timeout=30, context=ctx) as resp:
            return resp.read()
    except Exception as e:
        print("ERR", url, e, file=sys.stderr)
        return b""

def main():
    os.makedirs("js", exist_ok=True)
    html = open("home.html", encoding="utf-8", errors="replace").read()
    urls = sorted(set(re.findall(r'src="(https://shark2\.douyucdn\.cn/[^"]+\.js[^"]*)"', html)))
    print("chunks:", len(urls))
    def dl(u):
        name = "js/" + u.rsplit("/", 1)[-1]
        if os.path.exists(name) and os.path.getsize(name) > 0:
            return
        b = fetch(u)
        if b:
            open(name, "wb").write(b)
    with ThreadPoolExecutor(10) as ex:
        list(ex.map(dl, urls))
    print("done", len(os.listdir("js")))

if __name__ == "__main__":
    main()
