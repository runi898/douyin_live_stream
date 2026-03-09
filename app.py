"""
抖音直播源获取工具 — Web 版
基于 Flask，复用 douyin_live_stream.py 中的提取逻辑。
"""

import logging
from flask import Flask, send_from_directory, request, jsonify
from douyin_live_stream import DouyinLiveExtractor

app = Flask(__name__)
extractor = DouyinLiveExtractor()

# 配置日志等级
app.logger.setLevel(logging.INFO)

# 画质排序（从高到低）
QUALITY_ORDER = ['原画 (OR4)', '超清 (UHD)', '高清 (HD)', '标清 (SD)', '流畅 (LD)']


def sort_by_quality(stream_dict: dict) -> list:
    """将流地址字典按画质从高到低排序，返回列表"""
    sorted_list = []
    # 先按固定顺序
    for q in QUALITY_ORDER:
        if q in stream_dict:
            sorted_list.append({"quality": q, "url": stream_dict[q]})
    # 再追加其他
    for q, url in stream_dict.items():
        if q not in QUALITY_ORDER:
            sorted_list.append({"quality": q, "url": url})
    return sorted_list


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/extract", methods=["POST"])
def api_extract():
    """API: 提取直播流地址"""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    
    # 获取真实IP，考虑常见的反向代理透传头
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    # 若有多个 IP 取第一个
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    app.logger.info(f"收到提取请求 - IP: {client_ip} | URL: {url}")

    if not url:
        return jsonify({"success": False, "message": "请输入直播间链接或房间号"}), 400

    try:
        results = extractor.get_streams(url)
    except Exception as e:
        return jsonify({"success": False, "message": f"提取失败: {e}"}), 500

    flv_list = sort_by_quality(results.get("flv", {}))
    hls_list = sort_by_quality(results.get("hls", {}))

    if not flv_list and not hls_list:
        return jsonify({
            "success": False,
            "message": "未提取到直播流地址，可能原因：直播间不存在 / 未开播 / 链接有误"
        })

    return jsonify({
        "success": True,
        "flv": flv_list,
        "hls": hls_list,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
