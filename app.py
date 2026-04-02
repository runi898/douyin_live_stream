import logging

from flask import Flask, jsonify, request, send_from_directory

from douyin_live_stream import DouyinLiveExtractor, QUALITY_ORDER

app = Flask(__name__)
extractor = DouyinLiveExtractor()
app.logger.setLevel(logging.INFO)


def sort_by_quality(stream_dict: dict) -> list:
    sorted_list = []
    for quality in QUALITY_ORDER:
        if quality in stream_dict:
            sorted_list.append({"quality": quality, "url": stream_dict[quality]})
    for quality, url in stream_dict.items():
        if quality not in QUALITY_ORDER:
            sorted_list.append({"quality": quality, "url": url})
    return sorted_list


def build_stream_log_lines(protocol: str, items: list[dict]) -> list[str]:
    if not items:
        return [f"  {protocol:<4}: none"]

    lines = [f"  {protocol:<4}: {len(items)} route(s)"]
    for item in items:
        lines.append(f"    - {item['quality']}: {item['url']}")
    return lines


def build_extract_log_block(
    status: str,
    client_ip: str | None,
    raw_input: str,
    resolved: dict | None = None,
    flv_list: list[dict] | None = None,
    hls_list: list[dict] | None = None,
    error: str | None = None,
) -> str:
    resolved = resolved or {}
    flv_list = flv_list or []
    hls_list = hls_list or []

    lines = [
        "",
        "=" * 72,
        f"[{status}]",
        f"  IP      : {client_ip or 'N/A'}",
        f"  Input   : {raw_input or 'N/A'}",
    ]

    if resolved:
        lines.extend([
            f"  Candidate: {resolved.get('candidate') or 'N/A'}",
            f"  Nickname : {resolved.get('nickname') or 'N/A'}",
            f"  Web RID  : {resolved.get('web_rid') or 'N/A'}",
            f"  Room ID  : {resolved.get('room_id') or 'N/A'}",
            f"  Title    : {resolved.get('title') or 'N/A'}",
            f"  Status   : {'LIVE' if resolved.get('is_live') else 'NOT_LIVE'}",
        ])

    if error:
        lines.append(f"  Error    : {error}")

    if flv_list or hls_list:
        lines.append("-" * 72)
        lines.extend(build_stream_log_lines("FLV", flv_list))
        lines.extend(build_stream_log_lines("HLS", hls_list))

    lines.append("=" * 72)
    return "\n".join(lines)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(silent=True) or {}
    raw_input = data.get("url", "").strip()

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    app.logger.info("extract request - IP: %s | input: %s", client_ip, raw_input)

    if not raw_input:
        return jsonify({"success": False, "message": "请输入抖音号、主页链接、分享链接、直播链接或房间号"}), 400

    try:
        resolved = extractor.resolve_live_room(raw_input)
    except Exception as exc:
        app.logger.exception(build_extract_log_block(
            status="EXTRACT FAILED",
            client_ip=client_ip,
            raw_input=raw_input,
            error=str(exc),
        ))
        return jsonify({"success": False, "message": f"提取失败: {exc}"}), 500

    results = resolved.get("streams", {"flv": {}, "hls": {}})
    flv_list = sort_by_quality(results.get("flv", {}))
    hls_list = sort_by_quality(results.get("hls", {}))

    if not flv_list and not hls_list:
        app.logger.warning(build_extract_log_block(
            status="EXTRACT EMPTY",
            client_ip=client_ip,
            raw_input=raw_input,
            resolved=resolved,
        ))
        return jsonify({
            "success": False,
            "message": "未提取到直播流地址，可能原因：主播未开播 / 链接有误 / 当前输入未能解析到直播间",
        })

    app.logger.info(build_extract_log_block(
        status="EXTRACT SUCCESS",
        client_ip=client_ip,
        raw_input=raw_input,
        resolved=resolved,
        flv_list=flv_list,
        hls_list=hls_list,
    ))

    return jsonify({
        "success": True,
        "flv": flv_list,
        "hls": hls_list,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
