"""
Douyin live stream extractor.

Supports:
- Douyin ID / web_rid
- Live page URLs
- Share URLs
- Profile URLs
"""

from __future__ import annotations

import gzip
import json
import re
import ssl
import subprocess
from http.client import InvalidURL
from http.cookiejar import CookieJar
from typing import Dict, List, Optional, Tuple
from urllib import error as urllib_error
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency at runtime
    sync_playwright = None


FLV_QUALITIES = {
    "or4.flv": "原画 (OR4)",
    "hd.flv": "高清 (HD)",
    "sd.flv": "标清 (SD)",
    "ld.flv": "流畅 (LD)",
}

HLS_QUALITIES = {
    "or4.m3u8": "原画 (OR4)",
    "hd.m3u8": "高清 (HD)",
    "sd.m3u8": "标清 (SD)",
    "ld.m3u8": "流畅 (LD)",
}

HLS_INDEX_QUALITIES = {
    "or4": "原画 (OR4)",
    "uhd": "超清 (UHD)",
    "hd": "高清 (HD)",
    "sd": "标清 (SD)",
    "ld": "流畅 (LD)",
    "md": "流畅 (LD)",
}

QUALITY_ORDER = ["原画 (OR4)", "超清 (UHD)", "高清 (HD)", "标清 (SD)", "流畅 (LD)"]


class DouyinLiveExtractor:
    """Resolve Douyin live rooms and extract stream URLs."""

    def __init__(self) -> None:
        self.cookie_jar = CookieJar()
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self.opener = build_opener(
            HTTPSHandler(context=ssl_ctx),
            HTTPCookieProcessor(self.cookie_jar),
        )
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        self._init_cookies()

    def _request(self, url: str, headers: Optional[dict] = None, data=None, timeout: int = 15):
        hdrs = dict(self.headers)
        if headers:
            hdrs.update(headers)
        req = Request(url, data=data, headers=hdrs)
        if data:
            req.add_header("Content-Type", "application/json")
        resp = self.opener.open(req, timeout=timeout)
        body = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body.decode("utf-8", errors="replace"), resp

    def _init_cookies(self) -> None:
        try:
            self._request("https://live.douyin.com/", timeout=10)
            if self._has_cookie("ttwid"):
                print("[OK] auto loaded ttwid cookie")
                return

            payload = json.dumps(
                {
                    "region": "cn",
                    "aid": 1768,
                    "needFid": False,
                    "service": "www.ixigua.com",
                    "migrate_info": {"ticket": "", "source": "node"},
                    "cbUrlProtocol": "https",
                    "union": True,
                }
            ).encode("utf-8")
            self._request(
                "https://ttwid.bytedance.com/ttwid/union/register/",
                data=payload,
                timeout=10,
            )
            if self._has_cookie("ttwid"):
                print("[OK] loaded ttwid cookie from fallback endpoint")
                return
            print("[WARN] unable to confirm ttwid cookie, continuing anyway")
        except Exception as exc:
            print(f"[WARN] cookie bootstrap failed: {exc}; continuing")

    def _has_cookie(self, name: str) -> bool:
        return any(cookie.name == name for cookie in self.cookie_jar)

    def _normalize_input(self, user_input: str) -> str:
        text = user_input.strip()
        embedded_url = re.search(r"(https?://[^\s]+)", text)
        if embedded_url:
            text = embedded_url.group(1)
        return text.strip().rstrip("/")

    def _parse_room_id(self, user_input: str) -> str:
        user_input = user_input.strip()

        short_link_match = re.search(r"(https?://v\.douyin\.com/[a-zA-Z0-9]+)", user_input)
        if short_link_match:
            try:
                html, resp = self._request(short_link_match.group(1), timeout=10)
                for pattern in (
                    r'"roomId"\s*:\s*"(\d+)"',
                    r'\\*"webRid\\*"\s*:\s*\\*"(\d+)\\*"',
                    r"room_id=(\d+)",
                ):
                    match = re.search(pattern, html) or re.search(pattern, resp.url)
                    if match:
                        return match.group(1)
                user_input = resp.url
            except Exception:
                pass

        for pattern in (
            r"live\.douyin\.com/([^/?#]+)",
            r"/live/(\d+)",
            r"room_id=(\d+)",
        ):
            match = re.search(pattern, user_input)
            if match:
                return match.group(1)

        parsed = urlparse(user_input if "://" in user_input else "https://" + user_input)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if parts:
            return parts[-1]
        return user_input

    def _extract_candidates_from_text(self, text: str) -> List[str]:
        values: List[str] = []
        raw = text.strip()
        if not raw:
            return values

        if raw.startswith("http://") or raw.startswith("https://"):
            parsed = urlparse(raw)
            query = parse_qs(parsed.query)

            sec_uid = query.get("sec_uid", [None])[0]
            if sec_uid:
                values.append(sec_uid)

            user_match = re.search(r"(?:douyin\.com|iesdouyin\.com)/user/([^/?#]+)", raw)
            if user_match:
                values.append(user_match.group(1))

            share_user_match = re.search(r"iesdouyin\.com/share/user/([^/?#]+)", raw)
            if share_user_match:
                values.append(share_user_match.group(1))

            live_match = re.search(r"live\.douyin\.com/([^/?#]+)", raw)
            if live_match:
                values.append(live_match.group(1))
        else:
            values.append(raw)

        values.append(raw)
        return values

    def _extract_candidates_with_browser(self, user_input: str) -> List[str]:
        if sync_playwright is None:
            return []

        if not any(domain in user_input for domain in ("v.douyin.com", "douyin.com/user", "iesdouyin.com/share/user")):
            return []

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(user_input, wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(8000)
                payload = page.evaluate(
                    """() => {
                        const bodyText = document.body ? document.body.innerText : "";
                        return {
                            url: location.href,
                            bodyText,
                            html: document.documentElement ? document.documentElement.outerHTML : ""
                        };
                    }"""
                )
                browser.close()
        except Exception:
            return []

        candidates: List[str] = []
        candidates.extend(self._extract_candidates_from_text(payload.get("url") or ""))

        html = payload.get("html") or ""
        for pattern in (
            r'https?://www\.douyin\.com/user/[^"\s<>]+',
            r'https?://live\.douyin\.com/[^"\s<>]+',
            r'sec_uid=([^&"\']+)',
            r'"uniqueId":"([^"]+)"',
            r'"web_rid":"([^"]+)"',
        ):
            matches = re.findall(pattern, html)
            for match in matches:
                candidates.append(match if isinstance(match, str) else match[0])

        body_text = payload.get("bodyText") or ""
        douyin_id_match = re.search(r"抖音号[:：]\s*([A-Za-z0-9._-]+)", body_text)
        if douyin_id_match:
            candidates.append(douyin_id_match.group(1))

        return candidates

    def _is_viable_candidate(self, value: str) -> bool:
        if not value:
            return False
        if any(char.isspace() for char in value):
            return False
        if len(value) > 512:
            return False
        return True

    def _build_candidates(self, user_input: str) -> List[str]:
        normalized = self._normalize_input(user_input)
        candidates: List[str] = []

        if "v.douyin.com" in normalized or "live.douyin.com" in normalized:
            parsed = self._parse_room_id(normalized)
            if parsed:
                candidates.extend(self._extract_candidates_from_text(parsed))

        candidates.extend(self._extract_candidates_from_text(normalized))
        candidates.extend(self._extract_candidates_with_browser(normalized))

        clean: List[str] = []
        seen = set()
        for candidate in candidates:
            value = candidate.strip().strip("/")
            if value in seen or not self._is_viable_candidate(value):
                continue
            clean.append(value)
            seen.add(value)
        return clean

    def _extract_by_suffix(self, text: str) -> Tuple[dict, dict]:
        flv_results = {}
        hls_results = {}

        text = text.replace("\\u002F", "/")
        text = text.replace("\\u0026", "&")
        text = text.replace("\\/", "/")
        text = text.replace('\\"', '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&quot;", '"')

        for suffix, quality_name in FLV_QUALITIES.items():
            pattern = rf'(https?://[^\s"\'<>,\{{\}}\\]+?{re.escape(suffix)}\?[^\s"\'<>,\{{\}}\\]*)'
            matches = re.findall(pattern, text)
            if matches:
                flv_results[quality_name] = matches[-1].rstrip('"\')}]')

        for suffix, quality_name in HLS_QUALITIES.items():
            pattern = rf'(https?://[^\s"\'<>,\{{\}}\\]+?{re.escape(suffix)}\?[^\s"\'<>,\{{\}}\\]*)'
            matches = re.findall(pattern, text)
            if matches:
                hls_results[quality_name] = matches[-1].rstrip('"\')}]')

        # Some pages expose HLS as ..._hd/index.m3u8 instead of ...hd.m3u8.
        index_pattern = r'(https?://[^\s"\'<>,\{\}\\]+?_((?:or4|uhd|hd|sd|ld|md))/index\.m3u8\?[^\s"\'<>,\{\}\\]*)'
        for url, quality_key in re.findall(index_pattern, text, re.IGNORECASE):
            quality_name = HLS_INDEX_QUALITIES.get(quality_key.lower())
            if quality_name:
                hls_results[quality_name] = url.rstrip('"\')}]')

        return flv_results, hls_results

    def _extract_from_render_data(self, html: str) -> dict:
        results = {"flv": {}, "hls": {}}

        match = re.search(
            r'<script\s+id="RENDER_DATA"\s+type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        json_text = None
        if match:
            json_text = unquote(match.group(1))
        else:
            match = re.search(
                r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
                html,
                re.DOTALL,
            )
            if match:
                json_text = match.group(1)

        if not json_text:
            return results

        try:
            data = json.loads(json_text)
        except Exception:
            flv_r, hls_r = self._extract_by_suffix(json_text)
            results["flv"] = flv_r
            results["hls"] = hls_r
            return results

        self._recursive_find(data, results)

        if len(results["flv"]) < 4 or len(results["hls"]) < 4:
            flv_r, hls_r = self._extract_by_suffix(json_text)
            for quality, url in flv_r.items():
                results["flv"].setdefault(quality, url)
            for quality, url in hls_r.items():
                results["hls"].setdefault(quality, url)

        return results

    def _recursive_find(self, data, results: dict) -> None:
        if isinstance(data, dict):
            if "flv_pull_url" in data:
                value = data["flv_pull_url"]
                if isinstance(value, dict):
                    for key, url in value.items():
                        results["flv"].setdefault(self._classify_quality(key), url)
                elif isinstance(value, str) and value.startswith("http"):
                    results["flv"].setdefault(self._classify_quality(value), value)

            if "hls_pull_url_map" in data and isinstance(data["hls_pull_url_map"], dict):
                for key, url in data["hls_pull_url_map"].items():
                    results["hls"].setdefault(self._classify_quality(key), url)

            if "hls_pull_url" in data and isinstance(data["hls_pull_url"], str):
                url = data["hls_pull_url"]
                if url.startswith("http"):
                    results["hls"].setdefault("HLS", url)

            skip_keys = {"flv_pull_url", "hls_pull_url_map", "hls_pull_url"}
            for key, value in data.items():
                if key not in skip_keys:
                    self._recursive_find(value, results)

        elif isinstance(data, list):
            for item in data:
                self._recursive_find(item, results)

    def _classify_quality(self, text: str) -> str:
        text_lower = text.lower()
        for suffix, name in FLV_QUALITIES.items():
            if suffix in text_lower:
                return name

        checks = [
            ("full_hd1", "原画 (OR4)"),
            ("fullhd1", "原画 (OR4)"),
            ("uhd", "超清 (UHD)"),
            ("hd1", "高清 (HD)"),
            ("sd1", "流畅 (LD)"),
            ("sd2", "标清 (SD)"),
            ("_uhd", "超清 (UHD)"),
            ("_origin", "原画 (OR4)"),
            ("origin", "原画 (OR4)"),
            ("_or4", "原画 (OR4)"),
            ("_or", "原画 (OR4)"),
            ("_hd", "高清 (HD)"),
            ("_sd", "标清 (SD)"),
            ("_ld", "流畅 (LD)"),
            ("_ao", "仅音频 (AO)"),
        ]
        for keyword, name in checks:
            if keyword in text_lower:
                return name
        return "默认"

    def _try_webcast_api(self, web_rid: str) -> dict:
        results = {"flv": {}, "hls": {}}
        params = urlencode(
            {
                "aid": "6383",
                "app_name": "douyin_web",
                "live_id": "1",
                "device_platform": "web",
                "language": "zh-CN",
                "browser_language": "zh-CN",
                "browser_platform": "Win32",
                "browser_name": "Chrome",
                "browser_version": "131.0.0.0",
                "web_rid": web_rid,
            }
        )
        url = f"https://live.douyin.com/webcast/room/web/enter/?{params}"
        try:
            body, _ = self._request(url, headers={"Referer": "https://live.douyin.com/"})
            data = json.loads(body)
            if data.get("status_code") == 0 and data.get("data"):
                self._recursive_find(data["data"], results)
                if len(results["flv"]) < 4 or len(results["hls"]) < 4:
                    flv_r, hls_r = self._extract_by_suffix(body)
                    for quality, url in flv_r.items():
                        results["flv"].setdefault(quality, url)
                    for quality, url in hls_r.items():
                        results["hls"].setdefault(quality, url)
        except Exception:
            pass
        return results

    def _extract_room_info(self, html: str) -> Optional[Dict[str, object]]:
        room_block = re.search(
            r'roomStore\\":\{\\"roomInfo\\":\{\\"room\\":\{'
            r'\\"id_str\\":\\"(?P<room_id>\d+)\\".*?'
            r'\\"status\\":(?P<status>\d+).*?'
            r'\\"title\\":\\"(?P<title>.*?)\\".*?'
            r'\\"user_count_str\\":\\"(?P<user_count>.*?)\\"',
            html,
            re.DOTALL,
        )
        owner_block = re.search(
            r'owner\\":\{\\"id_str\\":\\"(?P<anchor_id>[^"]+)\\".*?'
            r'\\"sec_uid\\":\\"(?P<sec_uid>[^"]*)\\".*?'
            r'\\"nickname\\":\\"(?P<nickname>.*?)\\"',
            html,
            re.DOTALL,
        )
        anchor_block = re.search(
            r'anchor\\":\{\\"id_str\\":\\"(?P<anchor_id>[^"]+)\\".*?'
            r'\\"sec_uid\\":\\"(?P<sec_uid>[^"]*)\\".*?'
            r'\\"nickname\\":\\"(?P<nickname>.*?)\\"',
            html,
            re.DOTALL,
        )

        room_id_match = re.findall(r'roomId\\":\\"(\d+)\\"', html)
        web_rid_match = re.findall(r'web_rid\\":\\"([^"]+)\\"', html)
        empty_room_info = 'roomInfo\\":{}' in html or 'web_stream_url\\":null' in html
        owner_data = owner_block or anchor_block

        if not room_block and not room_id_match and not web_rid_match:
            return None

        return {
            "room_id": room_block.group("room_id") if room_block else (room_id_match[-1] if room_id_match else None),
            "web_rid": web_rid_match[-1] if web_rid_match else None,
            "status": int(room_block.group("status")) if room_block else (4 if empty_room_info else None),
            "title": self._decode_text(room_block.group("title")) if room_block else "",
            "user_count": self._decode_text(room_block.group("user_count")) if room_block else "",
            "anchor_id": owner_data.group("anchor_id") if owner_data else None,
            "sec_uid": owner_data.group("sec_uid") if owner_data else None,
            "nickname": self._decode_text(owner_data.group("nickname")) if owner_data else "",
        }

    @staticmethod
    def _decode_text(value: Optional[str]) -> str:
        if value is None:
            return ""
        return json.loads(f'"{value}"')

    def _resolve_candidate(self, candidate: str) -> Optional[Dict[str, object]]:
        live_url = f"https://live.douyin.com/{candidate}"
        try:
            html, response = self._request(live_url, headers={"Referer": "https://live.douyin.com/"})
        except (urllib_error.HTTPError, InvalidURL, ValueError):
            return None

        room = self._extract_room_info(html)
        if not room:
            return None

        streams = {"flv": {}, "hls": {}}
        if room.get("room_id"):
            streams = self._extract_from_render_data(html)
            if not streams.get("flv") and not streams.get("hls"):
                flv_streams, hls_streams = self._extract_by_suffix(html)
                streams = {"flv": flv_streams, "hls": hls_streams}

        if (
            room.get("room_id")
            and (not streams.get("flv") or not streams.get("hls"))
            and room.get("web_rid")
            and str(room["web_rid"]).isdigit()
        ):
            api_streams = self._try_webcast_api(str(room["web_rid"]))
            for stream_type in ("flv", "hls"):
                merged = dict(streams.get(stream_type, {}))
                for quality, url in api_streams.get(stream_type, {}).items():
                    merged.setdefault(quality, url)
                streams[stream_type] = merged

        room["candidate"] = candidate
        room["live_url"] = response.geturl()
        room["streams"] = streams
        room["is_live"] = room.get("status") == 2
        return room

    def resolve_live_room(self, user_input: str) -> Dict[str, object]:
        normalized = self._normalize_input(user_input)
        candidates = self._build_candidates(normalized)
        attempts: List[str] = []
        best_effort: Optional[Dict[str, object]] = None
        best_score: Optional[Tuple[int, int, int, int]] = None

        for candidate in candidates:
            attempts.append(candidate)
            result = self._resolve_candidate(candidate)
            if not result:
                continue

            score = self._score_result(result)
            if best_effort is None or best_score is None or score > best_score:
                best_effort = result
                best_score = score

        if best_effort:
            best_effort["input"] = user_input
            best_effort["normalized"] = normalized
            best_effort["attempts"] = attempts
            return best_effort

        raise RuntimeError(
            "Unable to resolve a live room from the provided input. "
            "The anchor may be offline, the identifier may be invalid, or Douyin changed the page structure."
        )

    @staticmethod
    def pick_best_stream(streams: Dict[str, Dict[str, str]]) -> Tuple[Optional[str], Optional[str]]:
        for stream_type in ("flv", "hls"):
            stream_map = streams.get(stream_type, {})
            for quality in QUALITY_ORDER:
                if quality in stream_map:
                    return stream_type, stream_map[quality]
            if stream_map:
                _, url = next(iter(stream_map.items()))
                return stream_type, url
        return None, None

    @staticmethod
    def _score_result(result: Dict[str, object]) -> Tuple[int, int, int, int]:
        streams = result.get("streams", {})
        flv_count = len(streams.get("flv", {}))
        hls_count = len(streams.get("hls", {}))
        web_rid = str(result.get("web_rid") or "")
        return (
            1 if result.get("is_live") else 0,
            hls_count,
            flv_count,
            1 if web_rid.isdigit() else 0,
        )

    def get_streams(self, user_input: str) -> dict:
        result = self.resolve_live_room(user_input)
        return result.get("streams", {"flv": {}, "hls": {}})

    @staticmethod
    def display(results: dict) -> bool:
        has_any = bool(results.get("flv") or results.get("hls"))
        if not has_any:
            print("\n未提取到直播地址，请确认主播正在直播且输入有效。")
            return False

        if results.get("flv"):
            print("\n" + "=" * 68)
            print("FLV 直播流地址")
            print("=" * 68)
            for quality in QUALITY_ORDER:
                if quality in results["flv"]:
                    print(f"\n[{quality}]")
                    print(results["flv"][quality])
            for quality, url in results["flv"].items():
                if quality not in QUALITY_ORDER:
                    print(f"\n[{quality}]")
                    print(url)

        if results.get("hls"):
            print("\n" + "=" * 68)
            print("HLS / M3U8 直播流地址")
            print("=" * 68)
            for quality in QUALITY_ORDER:
                if quality in results["hls"]:
                    print(f"\n[{quality}]")
                    print(results["hls"][quality])
            for quality, url in results["hls"].items():
                if quality not in QUALITY_ORDER:
                    print(f"\n[{quality}]")
                    print(url)
        return True

    @staticmethod
    def copy_to_clipboard(results: dict) -> None:
        lines = []
        for stream_type in ("flv", "hls"):
            for quality, url in results.get(stream_type, {}).items():
                lines.append(f"[{quality}] {url}")
        if not lines:
            return
        text = "\n".join(lines)
        try:
            process = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            process.communicate(text.encode("utf-8"))
            print(f"\n[OK] copied {len(lines)} stream URLs to clipboard")
        except Exception:
            pass


def main() -> None:
    extractor = DouyinLiveExtractor()

    while True:
        print("\n" + "-" * 60)
        try:
            user_input = input("请输入抖音号、分享链接、直播链接或主页链接 (q 退出): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见")
            break

        if user_input.lower() in {"q", "quit", "exit"}:
            print("再见")
            break
        if not user_input:
            continue

        try:
            resolved = extractor.resolve_live_room(user_input)
        except RuntimeError as exc:
            print(f"[ERROR] {exc}")
            continue

        print(f"[INFO] candidate: {resolved.get('candidate') or 'N/A'}")
        print(f"[INFO] nickname: {resolved.get('nickname') or 'N/A'}")
        print(f"[INFO] web_rid: {resolved.get('web_rid') or 'N/A'}")
        print(f"[INFO] room_id: {resolved.get('room_id') or 'N/A'}")
        print(f"[INFO] live_url: {resolved.get('live_url') or 'N/A'}")
        print(f"[INFO] title: {resolved.get('title') or 'N/A'}")
        print(f"[INFO] status: {'LIVE' if resolved.get('is_live') else 'NOT_LIVE'}")

        streams = resolved.get("streams", {"flv": {}, "hls": {}})
        if extractor.display(streams):
            extractor.copy_to_clipboard(streams)


if __name__ == "__main__":
    main()
