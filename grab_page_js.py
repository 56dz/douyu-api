"""下载某个斗鱼页面引用的全部 Next.js JS chunk (走 shark2 CDN)。"""
import re, os, sys, gzip, ssl, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


def fetch(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.douyu.com/"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            b = gzip.decompress(b)
        return b if raw else b.decode("utf-8", "replace")


def main(page, outdir):
    os.makedirs(outdir, exist_ok=True)
    html = fetch(page)
    urls = sorted(set(re.findall(r'src="(https://shark2\.douyucdn\.cn/[^"]+\.js[^"]*)"', html)))
    print("chunks:", len(urls))

    def dl(u):
        name = os.path.join(outdir, u.rsplit("/", 1)[-1])
        if os.path.exists(name) and os.path.getsize(name) > 0:
            return
        try:
            open(name, "wb").write(fetch(u, raw=True))
        except Exception as e:
            print("ERR", u.rsplit("/", 1)[-1], e)

    with ThreadPoolExecutor(10) as ex:
        list(ex.map(dl, urls))
    print("done", len(os.listdir(outdir)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
