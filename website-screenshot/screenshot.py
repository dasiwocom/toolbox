#!/usr/bin/env python3
"""website-screenshot v1.1.0

网页截图工具：等待页面完全加载后截图，支持全屏/视口模式。

用法:
    python3 screenshot.py                    # 视口截图（默认）
    python3 screenshot.py --full-page        # 整个页面截图
    python3 screenshot.py --wait-ms 3000     # 加载完成后额外等 3 秒
    python3 screenshot.py --timeout-ms 45000 # 加载超时 45 秒
"""
import os
import sys
import argparse
from datetime import datetime

INPUT = "urls.txt"
OUTPUT_DIR = "screenshots"
LOG_DIR = "log"

bad_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]


def safe_filename(url: str) -> str:
    # 只取域名部分作为文件名（如 https://www.dasiwo.com/path/a → www_dasiwo_com.png）
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc or url
        name = netloc
    except Exception:
        name = url.replace("https://", "").replace("http://", "")
    for c in bad_chars:
        name = name.replace(c, "_")
    name = name.replace(".", "_")
    return name + ".png"


def main():
    parser = argparse.ArgumentParser(description="网页截图工具")
    parser.add_argument("--full-page", action="store_true",
                        help="截取整个页面（默认只截视口）")
    parser.add_argument("--headful", action="store_true",
                        help="用有头模式（真实浏览器窗口，配合 xvfb-run 可绕过部分反爬）")
    parser.add_argument("--address-bar", action="store_true",
                        help="截图顶部显示模拟浏览器地址栏（红黄绿圆点 + 网址）")
    parser.add_argument("--wait-ms", type=int, default=1200,
                        help="页面加载完成后额外等待的毫秒数（默认 1200，等懒加载/字体渲染）")
    parser.add_argument("--timeout-ms", type=int, default=20000,
                        help="页面加载超时毫秒数（默认 20000）")
    parser.add_argument("--workers", type=int, default=1,
                        help="并发截图数（默认 1；2-3 更快，多占内存）")
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    log_name = datetime.now().strftime("%Y%m%d_%H%M%S.log")
    log_path = os.path.join(LOG_DIR, log_name)

    class Logger:
        def __init__(self, logfile):
            self.logfile = open(logfile, "a", encoding="utf-8")

        def write(self, s):
            sys.__stdout__.write(s)
            self.logfile.write(s)
            self.logfile.flush()

        def flush(self):
            sys.__stdout__.flush()
            self.logfile.flush()

    logger = Logger(log_path)
    sys.stdout = logger
    sys.stderr = logger

    mode = "整页" if args.full_page else "视口"
    print(f"===== 任务开始 {datetime.now()} | 模式: {mode} | 等待: {args.wait_ms}ms =====")

    if not os.path.exists(INPUT):
        print(f"错误：找不到 {INPUT}")
        logger.logfile.close()
        return

    with open(INPUT, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    if not urls:
        print("urls.txt 为空")
        logger.logfile.close()
        return

    from playwright.sync_api import sync_playwright
    import concurrent.futures

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

    def shot_one(url, args, output_dir):
        """单个 worker：独立浏览器截一个 URL（支持并发）"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=not args.headful, args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ])
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent=UA,
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                )
                context.add_init_script("""
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en']});
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = { runtime: {} };
                """)
                page = context.new_page()
                try:
                    # 保险等待：先等 networkidle（上限 8 秒），超时降级 load
                    try:
                        page.goto(url, timeout=8000, wait_until="networkidle")
                    except Exception:
                        print(f"  networkidle 超时，降级为 load 等待…")
                        try:
                            page.goto(url, timeout=12000, wait_until="load")
                        except Exception:
                            print(f"  加载被跳转打断/超时，直接截当前状态…")
                    page.wait_for_timeout(args.wait_ms)

                    # 模拟浏览器地址栏（可选）
                    if args.address_bar:
                        page.add_style_tag(content="""
                            .wmm-addrbar{position:fixed;top:0;left:0;right:0;height:38px;background:#edeef1;border-bottom:1px solid #d3d6db;display:flex;align-items:center;padding:0 12px;z-index:999999;font-family:Arial,sans-serif}
                            .wmm-addrbar .wmm-dots{display:flex;gap:6px;margin-right:12px}
                            .wmm-addrbar .wmm-dot{width:10px;height:10px;border-radius:50%}
                            .wmm-addrbar .wmm-url{flex:1;background:#fff;border:1px solid #d3d6db;border-radius:16px;padding:5px 14px;font-size:12px;color:#444;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
                            body{padding-top:38px !important}
                        """)
                        page.evaluate("""
                            (function(){
                                if(document.querySelector('.wmm-addrbar')) return;
                                var d=document.createElement('div');
                                d.className='wmm-addrbar';
                                d.innerHTML='<div class="wmm-dots"><span class="wmm-dot" style="background:#ff5f57"></span><span class="wmm-dot" style="background:#febc2e"></span><span class="wmm-dot" style="background:#28c840"></span></div><div class="wmm-url">'+location.href+'</div>';
                                document.body.prepend(d);
                            })();
                        """)
                        page.wait_for_timeout(300)

                    fn = safe_filename(url)
                    out_path = os.path.join(output_dir, fn)
                    page.screenshot(path=out_path, full_page=args.full_page, timeout=8000)
                    print(f"✅截图完成：{url} -> {fn}")
                except Exception as e:
                    print(f"❌失败 {url} : {e}")
                browser.close()
        except Exception as e:
            print(f"❌worker 异常 {url} : {e}")

    workers = max(1, min(args.workers, len(urls)))
    print(f"并发数: {workers}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda u: shot_one(u, args, OUTPUT_DIR), urls))

    print(f"===== 任务结束 {datetime.now()} =====")
    logger.logfile.close()


if __name__ == "__main__":
    main()
