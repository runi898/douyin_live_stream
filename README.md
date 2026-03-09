# 🎬 抖音直播源获取工具

零依赖的抖音直播流地址提取工具，提供 **命令行 (CLI)** 和 **Web 界面** 两种使用方式。

## ✨ 功能特点

- **多画质支持**：自动提取原画 (OR4)、超清 (UHD)、高清 (HD)、标清 (SD)、流畅 (LD) 等多种画质
- **双协议输出**：同时提取 FLV 和 HLS (m3u8) 两种流媒体协议地址
- **画质排序**：输出结果按清晰度从高到低排列，方便快速选择最佳画质
- **多种输入方式**：支持直播间链接、短链接、房间号等多种输入格式
- **Web 版支持 Docker 部署**：提供精美的 Web 界面，点击画质卡片即可一键复制流地址
- **CLI 版零依赖**：命令行版仅使用 Python 标准库，无需 `pip install`

---

## �️ 方式一：命令行版（零依赖）

### 环境要求

- **Python 3.6+**（推荐 3.8 及以上）
- 无需安装任何第三方依赖

### 使用方法

```bash
python douyin_live_stream.py
```

运行后根据提示输入直播间链接或房间号即可：

```
  请输入直播间链接或房间号 (q 退出): https://live.douyin.com/123456789
```

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

---

## 🌐 方式二：Web 版（Docker 部署）

提供精美的暗色主题 Web 界面，粘贴直播间链接后自动解析，**点击任意画质卡片即可一键复制对应的流地址**。

### 快速部署

```bash
# 克隆项目
git clone https://github.com/runi898/douyin_live_stream.git
cd douyin_live_stream

# Docker Compose 一键启动
docker compose up -d
```

启动后访问 **http://localhost:5000** 即可使用。

### 手动构建

```bash
# 构建镜像
docker build -t douyin-live-web .

# 运行容器
docker run -d -p 5000:5000 --name douyin-live-web douyin-live-web
```

### 支持的输入格式

| 格式 | 示例 |
|------|------|
| 房间号 | `123456789` |
| 直播间链接 | `https://live.douyin.com/123456789` |
| 短链接 | `https://v.douyin.com/xxxxx/` |

---

## 📁 项目结构

```
├── douyin_live_stream.py   # CLI 命令行版（零依赖）
├── app.py                  # Web 版 Flask 服务
├── static/
│   └── index.html          # Web 界面
├── Dockerfile              # Docker 镜像配置
├── docker-compose.yml      # Docker Compose 配置
├── requirements.txt        # Web 版 Python 依赖
└── README.md
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
