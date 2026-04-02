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
        results = extractor.get_streams(raw_input)
    except Exception as exc:
        return jsonify({"success": False, "message": f"提取失败: {exc}"}), 500

    flv_list = sort_by_quality(results.get("flv", {}))
    hls_list = sort_by_quality(results.get("hls", {}))

    if not flv_list and not hls_list:
        return jsonify({
            "success": False,
            "message": "未提取到直播流地址，可能原因：主播未开播 / 链接有误 / 当前输入未能解析到直播间",
        })

    return jsonify({
        "success": True,
        "flv": flv_list,
        "hls": hls_list,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
