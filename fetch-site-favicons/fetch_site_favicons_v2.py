import os
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import sys
# 强制终端输出utf‑8
sys.stdout.reconfigure(encoding='utf-8')
# ========== 配置区 ==========
INPUT_TXT = "sites.txt"
OUTPUT_FOLDER = "site_favicons_v2"
TIMEOUT_SEC = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"
}
# =============================
def domain_to_safe_name(domain: str):
    return domain.replace(".", "_")

def save_http_file(url: str, out_path: str):
    if os.path.exists(out_path):
        print("  [skip] 跳过已存在: %s" % os.path.basename(out_path))
        return True
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SEC, stream=True)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print("  [ok] 下载成功 %s" % os.path.basename(out_path))
        return True
    except Exception as err:
        print("  [fail] 下载失败 %s | %s" % (url, str(err)[:80]))
        return False

def main():
    if not os.path.isfile(INPUT_TXT):
        print("\n错误：找不到 %s！" % INPUT_TXT)
        print("请新建 sites.txt，一行一个网站地址")
        return

    # 只创建这一个总文件夹，不再创建每个站点的子目录
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    with open(INPUT_TXT, "r", encoding="utf-8") as f:
        url_lines = [x.strip() for x in f.readlines() if x.strip()]
    print("一共读取 %d 个站点，开始抓取图标\n" % len(url_lines))

    for one_site in url_lines:
        print("\n处理站点 %s" % one_site)
        p = urlparse(one_site)
        domain_str = p.netloc
        safe_dom = domain_to_safe_name(domain_str)
        base_url = f"{p.scheme}://{p.netloc}"

        # ---------- 1.根路径 favicon.ico (浏览器标签图标) ----------
        favicon_url = urljoin(base_url, "/favicon.ico")
        ext1 = os.path.splitext(urlparse(favicon_url).path)[1]
        if not ext1 or len(ext1) >8:
            ext1 = ".ico"
        fn1 = f"{safe_dom}_link{ext1}"
        save_http_file(favicon_url, os.path.join(OUTPUT_FOLDER, fn1))

        # ---------- 2.解析页面 head 里面的图标 ----------
        html_icon_list = []
        manifest_icon_list = []
        try:
            resp = requests.get(one_site, headers=HEADERS, timeout=TIMEOUT_SEC)
            soup = BeautifulSoup(resp.text, "html.parser")
            for link_tag in soup.find_all("link"):
                rel_raw = link_tag.get("rel", "")
                if isinstance(rel_raw, list):
                    rel_raw = " ".join(rel_raw)
                rel_raw = rel_raw.lower()
                if any(k in rel_raw for k in ["icon", "shortcut", "apple-touch-icon", "mask-icon"]):
                    href = link_tag.get("href")
                    if href:
                        full = urljoin(one_site, href)
                        html_icon_list.append(full)
            # manifest
            manifest_link = soup.find("link", {"rel": "manifest"})
            if manifest_link:
                m_href = manifest_link.get("href")
                manifest_url = urljoin(one_site, m_href)
                m_resp = requests.get(manifest_url, headers=HEADERS, timeout=TIMEOUT_SEC)
                manifest_json = m_resp.json()
                if "icons" in manifest_json:
                    for entry in manifest_json["icons"]:
                        src = entry.get("src")
                        if src:
                            manifest_icon_list.append(urljoin(manifest_url, src))
        except Exception as e:
            print("  [warn]页面解析出错 %s" % str(e)[:70])

        # 保存 html head 的图标，直接放进总文件夹
        for idx, icon_url in enumerate(html_icon_list):
            ext = os.path.splitext(urlparse(icon_url).path)[1]
            if not ext or len(ext)>8:
                ext = ".png"
            fn = f"{safe_dom}_link_{idx}{ext}"
            save_http_file(icon_url, os.path.join(OUTPUT_FOLDER, fn))

        # 保存 manifest PWA图标，直接放进总文件夹
        for idx, icon_url in enumerate(manifest_icon_list):
            ext = os.path.splitext(urlparse(icon_url).path)[1]
            if not ext or len(ext)>8:
                ext = ".png"
            fn = f"{safe_dom}_link_{idx}{ext}"
            save_http_file(icon_url, os.path.join(OUTPUT_FOLDER, fn))

    print("\n====全部任务结束====")
    print(f"目录说明：全部图标统一存放于 {OUTPUT_FOLDER}")
    print("同一个网站的文件拥有相同文件名前缀，文件管理器排序会聚集在一起")

if __name__ == "__main__":
    main()
