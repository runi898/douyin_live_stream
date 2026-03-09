"""
抖音直播源获取工具 (Python 版) — 零依赖版本
使用 Python 内置的 urllib 库，无需安装任何第三方包。
搜索 ld.flv? / sd.flv? / hd.flv? / or4.flv? 四种画质地址。

使用方式:
  python douyin_live_stream.py
  然后输入直播间链接或房间号即可。
"""

import re
import json
import sys
import ssl
import gzip
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPSHandler
from urllib.parse import unquote, urlparse, urlencode
from http.cookiejar import CookieJar


#硬编码的四种 FLV 画质后缀
FLV_QUALITIES = {
    'or4.flv': '原画 (OR4)',
    'hd.flv':  '高清 (HD)',
    'sd.flv':  '标清 (SD)',
    'ld.flv':  '流畅 (LD)',
}

# 对应的 HLS (m3u8) 画质后缀
HLS_QUALITIES = {
    'or4.m3u8': '原画 (OR4)',
    'hd.m3u8':  '高清 (HD)',
    'sd.m3u8':  '标清 (SD)',
    'ld.m3u8':  '流畅 (LD)',
}


class DouyinLiveExtractor:
    """抖音直播流地址提取器"""

    def __init__(self):
        self.cookie_jar = CookieJar()
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self.opener = build_opener(
            HTTPSHandler(context=ssl_ctx),
            HTTPCookieProcessor(self.cookie_jar)
        )
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        self._init_cookies()

    def _request(self, url, headers=None, data=None, timeout=15):
        """发送 HTTP 请求"""
        hdrs = dict(self.headers)
        if headers:
            hdrs.update(headers)
        req = Request(url, data=data, headers=hdrs)
        if data:
            req.add_header("Content-Type", "application/json")
        resp = self.opener.open(req, timeout=timeout)
        body = resp.read()
        if resp.headers.get('Content-Encoding') == 'gzip':
            body = gzip.decompress(body)
        return body.decode('utf-8', errors='replace'), resp

    def _init_cookies(self):
        """自动获取 ttwid Cookie）"""
        try:
            self._request("https://live.douyin.com/", timeout=10)
            if self._has_cookie('ttwid'):
                print("[✓] 已自动获取 ttwid Cookie")
                return
            # 备用方式
            payload = json.dumps({
                "region": "cn", "aid": 1768, "needFid": False,
                "service": "www.ixigua.com",
                "migrate_info": {"ticket": "", "source": "node"},
                "cbUrlProtocol": "https", "union": True,
            }).encode('utf-8')
            self._request("https://ttwid.bytedance.com/ttwid/union/register/",
                          data=payload, timeout=10)
            if self._has_cookie('ttwid'):
                print("[✓] 已通过备用接口获取 ttwid Cookie")
                return
            print("[!] 未能自动获取 ttwid，继续尝试...")
        except Exception as e:
            print(f"[!] Cookie 初始化: {e}，继续运行...")

    def _has_cookie(self, name):
        return any(c.name == name for c in self.cookie_jar)

    def _parse_room_id(self, user_input: str) -> str:
        """从用户输入中解析房间号"""
        user_input = user_input.strip()
        if user_input.isdigit():
            return user_input

        # 短链接跳转
        if 'v.douyin.com' in user_input:
            try:
                _, resp = self._request(user_input, timeout=10)
                user_input = resp.url
            except:
                pass

        for pattern in [r'live\.douyin\.com/(\d+)', r'/live/(\d+)', r'room_id=(\d+)']:
            match = re.search(pattern, user_input)
            if match:
                return match.group(1)

        parsed = urlparse(user_input if '://' in user_input else 'https://' + user_input)
        parts = parsed.path.strip('/').split('/')
        if parts and parts[-1].isdigit():
            return parts[-1]
        return user_input

    # ============================================================
    #  核心提取逻辑
    # ============================================================

    def _extract_by_suffix(self, text: str) -> dict:
        """
        【核心逻辑】
        通过在页面文本中搜索包含特定后缀的完整 URL 来提取。
        FLV: ld.flv? / sd.flv? / hd.flv? / or4.flv?
        HLS: ld.m3u8? / sd.m3u8? / hd.m3u8? / or4.m3u8?
        """
        flv_results = {}
        hls_results = {}

        # 先统一解码各种转义
        text = text.replace('\\u002F', '/')
        text = text.replace('\\u0026', '&')
        text = text.replace('\\/', '/')
        text = text.replace('\\"', '"')
        text = text.replace('&amp;', '&')
        text = text.replace('&quot;', '"')

        # 搜索 FLV 流
        for suffix, quality_name in FLV_QUALITIES.items():
            pattern = rf'(https?://[^\s"\'<>,\{{\}}\\]+?{re.escape(suffix)}\?[^\s"\'<>,\{{\}}\\]*)'
            matches = re.findall(pattern, text)
            if matches:
                url = matches[-1].rstrip('"\')}]')
                flv_results[quality_name] = url

        # 搜索 HLS/m3u8 流
        for suffix, quality_name in HLS_QUALITIES.items():
            pattern = rf'(https?://[^\s"\'<>,\{{\}}\\]+?{re.escape(suffix)}\?[^\s"\'<>,\{{\}}\\]*)'
            matches = re.findall(pattern, text)
            if matches:
                url = matches[-1].rstrip('"\')}]')
                hls_results[quality_name] = url

        return flv_results, hls_results

    def _extract_from_render_data(self, html: str) -> dict:
        """从 RENDER_DATA JSON 中提取流地址"""
        results = {"flv": {}, "hls": {}}

        # 提取 RENDER_DATA
        match = re.search(
            r'<script\s+id="RENDER_DATA"\s+type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        json_text = None
        if match:
            json_text = unquote(match.group(1))
        else:
            match = re.search(
                r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
                html, re.DOTALL
            )
            if match:
                json_text = match.group(1)

        if not json_text:
            return results

        try:
            data = json.loads(json_text)
        except:
            # JSON 解析失败，直接对原始文本搜索
            flv_r, hls_r = self._extract_by_suffix(json_text)
            results["flv"] = flv_r
            results["hls"] = hls_r
            return results

        # 方式A: 递归查找 flv_pull_url / hls_pull_url_map 字段（结构化）
        self._recursive_find(data, results)

        # 方式B: 文本搜索补充（FLV + HLS）
        if len(results["flv"]) < 4 or len(results["hls"]) < 4:
            flv_r, hls_r = self._extract_by_suffix(json_text)
            for q, url in flv_r.items():
                if q not in results["flv"]:
                    results["flv"][q] = url
            for q, url in hls_r.items():
                if q not in results["hls"]:
                    results["hls"][q] = url

        return results

    def _recursive_find(self, data, results):
        """递归搜索 JSON 中的 flv_pull_url / hls_pull_url_map 字段"""
        if isinstance(data, dict):
            if "flv_pull_url" in data:
                val = data["flv_pull_url"]
                if isinstance(val, dict):
                    for key, url in val.items():
                        quality = self._classify_quality(key)
                        if quality not in results["flv"]:  # 不覆盖已有结果
                            results["flv"][quality] = url
                elif isinstance(val, str) and val.startswith("http"):
                    quality = self._classify_quality(val)
                    if quality not in results["flv"]:
                        results["flv"][quality] = val

            if "hls_pull_url_map" in data:
                val = data["hls_pull_url_map"]
                if isinstance(val, dict):
                    for key, url in val.items():
                        quality = self._classify_quality(key)
                        if quality not in results["hls"]:
                            results["hls"][quality] = url

            if "hls_pull_url" in data and isinstance(data["hls_pull_url"], str):
                url = data["hls_pull_url"]
                if url.startswith("http") and "HLS" not in results["hls"]:
                    results["hls"]["HLS"] = url

            # 递归子对象（跳过已处理的 key）
            skip = {"flv_pull_url", "hls_pull_url_map", "hls_pull_url"}
            for k, v in data.items():
                if k not in skip:
                    self._recursive_find(v, results)

        elif isinstance(data, list):
            for item in data:
                self._recursive_find(item, results)

    def _classify_quality(self, text: str) -> str:
        """通过文本中的关键字判断画质"""
        text_lower = text.lower()
        # 精确匹配四种后缀
        for suffix, name in FLV_QUALITIES.items():
            if suffix in text_lower:
                return name
        # 扩展匹配
        checks = [
            ('_uhd', '超清 (UHD)'), ('uhd', '超清 (UHD)'),
            ('_origin', '原画 (OR4)'), ('origin', '原画 (OR4)'),
            ('_or4', '原画 (OR4)'), ('_or', '原画 (OR4)'),
            ('_hd', '高清 (HD)'), ('_sd', '标清 (SD)'), ('_ld', '流畅 (LD)'),
            ('_ao', '仅音频 (AO)'),
        ]
        for kw, name in checks:
            if kw in text_lower:
                return name
        return '默认'

    def _try_webcast_api(self, web_rid: str) -> dict:
        """Webcast API 备用方案"""
        results = {"flv": {}, "hls": {}}
        params = urlencode({
            "aid": "6383", "app_name": "douyin_web", "live_id": "1",
            "device_platform": "web", "language": "zh-CN",
            "browser_language": "zh-CN", "browser_platform": "Win32",
            "browser_name": "Chrome", "browser_version": "131.0.0.0",
            "web_rid": web_rid,
        })
        url = f"https://live.douyin.com/webcast/room/web/enter/?{params}"
        try:
            body, _ = self._request(url, headers={"Referer": "https://live.douyin.com/"})
            data = json.loads(body)
            if data.get("status_code") == 0 and data.get("data"):
                # 结构化提取
                self._recursive_find(data["data"], results)
                # 文本搜索补充（FLV + HLS）
                if len(results["flv"]) < 4 or len(results["hls"]) < 4:
                    flv_r, hls_r = self._extract_by_suffix(body)
                    for q, u in flv_r.items():
                        if q not in results["flv"]:
                            results["flv"][q] = u
                    for q, u in hls_r.items():
                        if q not in results["hls"]:
                            results["hls"][q] = u
        except Exception as e:
            print(f"  [!] Webcast API: {e}")
        return results

    def get_streams(self, user_input: str) -> dict:
        """主方法：获取直播流地址"""
        room_id = self._parse_room_id(user_input)
        print(f"\n[INFO] 房间号: {room_id}")

        url = f"https://live.douyin.com/{room_id}"
        print(f"[INFO] 请求: {url}")

        try:
            html, _ = self._request(url, headers={"Referer": "https://live.douyin.com/"})
        except Exception as e:
            print(f"[ERROR] 请求失败: {e}")
            return {"flv": {}, "hls": {}}

        print(f"[INFO] 页面大小: {len(html)} 字符")

        if '主播暂未开播' in html or '直播已结束' in html:
            print("[!] 该主播当前未开播或直播已结束")

        # 策略1: RENDER_DATA 结构化 + 文本搜索
        results = self._extract_from_render_data(html)

        # 策略2: 对整个 HTML 进行文本搜索补充（FLV + HLS）
        if len(results.get("flv", {})) < 4 or len(results.get("hls", {})) < 4:
            print("[INFO] 对整页进行文本搜索补充...")
            flv_r, hls_r = self._extract_by_suffix(html)
            for q, u in flv_r.items():
                if q not in results.get("flv", {}):
                    results.setdefault("flv", {})[q] = u
            for q, u in hls_r.items():
                if q not in results.get("hls", {}):
                    results.setdefault("hls", {})[q] = u

        # 策略3: Webcast API
        if not results.get("flv"):
            print("[INFO] 尝试 Webcast API...")
            results = self._try_webcast_api(room_id)

        # 最终报告
        flv_count = len(results.get("flv", {}))
        hls_count = len(results.get("hls", {}))
        print(f"[INFO] 共找到 {flv_count} 个 FLV + {hls_count} 个 HLS 画质地址")

        return results

    @staticmethod
    def display(results: dict):
        """格式化显示"""
        has_any = bool(results.get("flv") or results.get("hls"))
        if not has_any:
            print("\n  ✗ 未提取到flv地址，重新复制链接")
            print("    可能原因: 直播间不存在 / 未开播 / 链接有误")
            return False

        # 固定顺序
        quality_order = ['原画 (OR4)', '超清 (UHD)', '高清 (HD)', '标清 (SD)', '流畅 (LD)']

        if results.get("flv"):
            print("\n╔══════════════════════════════════════════════╗")
            print("║           🎬 FLV 直播流地址                  ║")
            print("╚══════════════════════════════════════════════╝")
            # 先按固定顺序打印
            for q in quality_order:
                if q in results["flv"]:
                    print(f"\n  ▶ {q}")
                    print(f"    {results['flv'][q]}")
            # 再打印其他
            for q, url in results["flv"].items():
                if q not in quality_order:
                    print(f"\n  ▶ {q}")
                    print(f"    {url}")

        if results.get("hls"):
            print("\n╔══════════════════════════════════════════════╗")
            print("║         📺 HLS(.m3u8)直播流地址              ║")
            print("╚══════════════════════════════════════════════╝")
            for q in quality_order:
                if q in results["hls"]:
                    print(f"\n  ▶ {q}")
                    print(f"    {results['hls'][q]}")
            for q, url in results["hls"].items():
                if q not in quality_order:
                    print(f"\n  ▶ {q}")
                    print(f"    {url}")

        return True

    @staticmethod
    def copy_to_clipboard(results: dict):
        """复制到剪贴板"""
        lines = []
        for st in ("flv", "hls"):
            for q, url in results.get(st, {}).items():
                lines.append(f"[{q}] {url}")
        if lines:
            text = "\n".join(lines)
            try:
                import subprocess
                p = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
                p.communicate(text.encode('utf-8'))
                print(f"\n  [✓] 已复制 {len(lines)} 条到剪贴板!")
            except:
                pass


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║          🎬 抖音直播源获取工具 (Python 版)                ║
║                   无需第三方依赖                          ║
╚═══════════════════════════════════════════════════════════╝
    """)

    extractor = DouyinLiveExtractor()

    while True:
        print("\n" + "─" * 60)
        try:
            user_input = input("  请输入直播间链接或房间号 (q 退出): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见!")
            break

        if user_input.lower() in ('q', 'quit', 'exit'):
            print("  再见!")
            break
        if not user_input:
            continue

        results = extractor.get_streams(user_input)
        if extractor.display(results):
            extractor.copy_to_clipboard(results)


if __name__ == "__main__":
    main()
