import argparse
import json
import sys

from douyin_live_stream import DouyinLiveExtractor


def safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve a Douyin identifier or URL to the current live room."
    )
    parser.add_argument("input", nargs="?", help="Douyin ID, share URL, profile URL, or live URL.")
    args = parser.parse_args()

    user_input = args.input or input("请输入抖音号、主页链接、分享链接或直播链接: ").strip()
    extractor = DouyinLiveExtractor()

    try:
        result = extractor.resolve_live_room(user_input)
    except RuntimeError as exc:
        print(f"Resolve failed: {exc}")
        return

    stream_type, stream_code = extractor.pick_best_stream(result.get("streams", {}))

    print(f"Input: {result['input']}")
    print(f"Resolved candidate: {result.get('candidate') or 'N/A'}")
    print(f"Anchor nickname: {result.get('nickname') or 'N/A'}")
    print(f"web_rid: {result.get('web_rid') or 'N/A'}")
    print(f"room_id: {result.get('room_id') or 'N/A'}")
    print(f"Live status: {'LIVE' if result.get('is_live') else 'NOT_LIVE'}")
    if stream_code:
        print(f"Best stream ({stream_type}): {stream_code}")

    print("\nJSON:")
    safe_print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
