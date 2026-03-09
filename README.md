# 🎬 抖音直播源获取工具（Python 版）

零依赖的抖音直播流地址提取工具，使用 Python 内置标准库实现，无需安装任何第三方包。

## ✨ 功能特点

- **零依赖**：仅使用 Python 标准库（`urllib`、`ssl`、`json`、`re`、`gzip`），无需 `pip install`
- **多画质支持**：自动提取原画 (OR4)、超清 (UHD)、高清 (HD)、标清 (SD)、流畅 (LD) 等多种画质
- **双协议输出**：同时提取 FLV 和 HLS (m3u8) 两种流媒体协议地址
- **画质排序**：输出结果按清晰度从高到低排列，方便快速选择最佳画质
- **多种输入方式**：支持直播间链接、短链接、房间号等多种输入格式
- **自动剪贴板**：提取成功后自动复制到系统剪贴板（Windows）

## 📋 环境要求

- **Python 3.6+**（推荐 3.8 及以上）
- 无需安装任何第三方依赖

## 🚀 使用方法

```bash
python douyin_live_stream.py
```

运行后根据提示输入直播间链接或房间号即可：

```
  请输入直播间链接或房间号 (q 退出): https://live.douyin.com/123456789
```

### 支持的输入格式

| 格式 | 示例 |
|------|------|
| 房间号 | `123456789` |
| 直播间链接 | `https://live.douyin.com/123456789` |
| 短链接 | `https://v.douyin.com/xxxxx/` |

### 输出示例

```
╔══════════════════════════════════════════════╗
║           🎬 FLV 直播流地址                  ║
╚══════════════════════════════════════════════╝

  ▶ 原画 (OR4)
    https://pull-xxx.douyincdn.com/...or4.flv?...

  ▶ 高清 (HD)
    https://pull-xxx.douyincdn.com/...hd.flv?...

  ▶ 标清 (SD)
    https://pull-xxx.douyincdn.com/...sd.flv?...

  ▶ 流畅 (LD)
    https://pull-xxx.douyincdn.com/...ld.flv?...
```

## 🔧 提取策略

工具使用三级提取策略，确保最大成功率：

1. **RENDER_DATA 结构化提取**：优先从页面嵌入的 JSON 数据中解析 `flv_pull_url` / `hls_pull_url_map` 字段
2. **全页面文本搜索**：通过正则匹配页面中的 `ld.flv` / `sd.flv` / `hd.flv` / `or4.flv` 等后缀 URL
3. **Webcast API 备用方案**：当前两种方式失败时，通过抖音 Webcast API 获取

## ⚠️ 注意事项

- 需确保网络能正常访问抖音直播页面
- 仅在主播**正在直播**时才能获取到流地址
- 本工具仅供学习研究使用

## 📄 License

MIT
