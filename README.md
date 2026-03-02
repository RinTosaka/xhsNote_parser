# xhsnote-parser

一个面向小红书（Xiaohongshu）笔记页面的解析工具：

- 从页面 HTML 中提取 `window.__INITIAL_STATE__`
- 解析出 `noteDetail` 并输出为 JSON
- 额外生成图片/视频的去水印直链字段（`urlNoWatermark`）
- 提供 Windows 友好的 CLI、FastAPI 后端，以及可选的 Web UI

> 说明：此项目仅用于学习/自用调试。目标站点可能随时变更页面结构或访问策略；请遵守当地法律法规与站点条款。

## 目录结构

- `main.py`：CLI 入口（委托 `xhsnote_parser.cli`）
- `main_api.py`：API 入口（启动 `xhsnote_parser.api:app`）
- `xhsnote_parser/`：核心解析/存储/API 代码
- `docs/quickstart.md`：API + Web 快速开始
- `web/`：Vite 前端（可选）

## 安装（推荐 uv）

要求：Python `>= 3.12`

```bash
uv sync
```

## CLI 使用

解析单条笔记：

```bash
uv run python main.py https://www.xiaohongshu.com/explore/<note_id>
```

查看 CLI 帮助（等价入口）：

```bash
uv run python -m xhsnote_parser.cli --help
```

解析多条（命令行直接传多个 URL）：

```bash
uv run python main.py https://www.xiaohongshu.com/explore/1 https://www.xiaohongshu.com/explore/2
```

从文件读取 URL（支持空行与 `#` 注释）：

```bash
uv run python main.py -f notes_url.txt
```

常用参数：

```bash
uv run python main.py https://www.xiaohongshu.com/explore/<note_id> --timeout 20 --user-agent "Mozilla/5.0 ..." --log-level DEBUG --save-log --log-dir logs --save-initial-state -o output
```

### CLI 配置（.env 文件）

CLI 支持通过 `.env`（默认读取当前目录的 `.env`）或 `--env-file` 覆盖配置：

```bash
uv run python main.py --env-file .env -f notes_url.txt
```

可用键（见 `.env.example`）：

- `XHSNOTE_TIMEOUT`
- `XHSNOTE_USER_AGENT`
- `XHSNOTE_OUTPUT_DIR`
- `XHSNOTE_LOG_LEVEL`
- `XHSNOTE_SAVE_LOG`
- `XHSNOTE_LOG_DIR`
- `XHSNOTE_INPUT_FILE`

## API（FastAPI）

启动后端：

```bash
uv sync
uv run python main_api.py
```

默认监听：`http://127.0.0.1:8000`

主要接口：

- `GET /api/health`
- `POST /api/parse`
- `POST /api/parse/batch`
- `GET /api/outputs`
- `GET /api/outputs/{relative_path}`

### PowerShell 调用示例

单条解析：

```powershell
$body = @{
  url = "https://www.xiaohongshu.com/explore/<note_id>"
  options = @{
    timeout = 20
    user_agent = "Mozilla/5.0 ..."
    cookie = "a=1; b=2"   # 可选：需要登录/反爬时使用
    save = $true
    save_initial_state = $false
  }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/parse" -ContentType "application/json" -Body $body
```

批量解析：

```powershell
$body = @{
  urls = @(
    "https://www.xiaohongshu.com/explore/1",
    "https://www.xiaohongshu.com/explore/2"
  )
  concurrency = 3
  dedupe = $true
  options = @{ save = $true }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/parse/batch" -ContentType "application/json" -Body $body
```

### API 环境变量

API 从进程环境变量读取配置（不会自动加载 `.env`）。见 `.env.example`：

- `XHSNOTE_TIMEOUT`
- `XHSNOTE_OUTPUT_DIR`
- `XHSNOTE_LOG_LEVEL`
- `XHSNOTE_SAVE_LOG`
- `XHSNOTE_LOG_DIR`
- `XHSNOTE_API_HOST`
- `XHSNOTE_API_PORT`
- `XHSNOTE_API_RELOAD`
- `XHSNOTE_API_CORS_ORIGINS`（逗号分隔；或 `*` 允许所有来源）
- `XHSNOTE_API_ENABLE_STATIC`（是否挂载静态站点）
- `XHSNOTE_API_STATIC_DIR`（静态目录，默认 `web/dist`）

## Web UI（可选）

见 `docs/quickstart.md`。

开发模式：

```bash
cd web
npm install
npm run dev
```

默认前端请求后端：`http://127.0.0.1:8000`；可通过 `web/.env` 设置 `VITE_API_BASE` 覆盖。

生产构建后（`web/dist` 存在且启用静态服务），FastAPI 会把前端挂载在 `/`。

## 输出说明

默认输出目录：`output/`（可通过 CLI `-o/--output` 或 `XHSNOTE_OUTPUT_DIR` 调整）。

输出文件名规则（大致）：

- `output/<author>_notes/<title>_<noteId>_noteDetail.json`
- `output/<author>_notes/<title>_<noteId>_initial_state.json`（开启保存时）

## 常见问题

- **403 / 需要登录**：尝试设置 `User-Agent`；API 可在 `options.cookie` 传入 Cookie（注意不要把 Cookie 写入仓库）。
- **提示找不到 `window.__INITIAL_STATE__`**：页面结构可能变更或返回了非笔记 HTML（如风控/跳转页）；建议打开 `--log-level DEBUG` 并抓取返回内容排查。

## 开发与测试

```bash
uv run pytest -q
```

## 部署到服务器（Linux 示例）

下面以「后端 API +（可选）Web UI」为目标，给出一套最小可用的部署方式。生产环境建议使用反向代理（Nginx/Caddy）并关闭热重载。

### 1）准备环境

- Python `>=3.12`
- Node.js（仅在需要构建 `web/` 时需要）
- `uv`（推荐）

```bash
# 安装/更新依赖（在项目目录）
uv sync
```

### 2）配置环境变量

API 不会自动加载 `.env` 文件（只读取进程环境变量），生产环境建议通过 systemd 的 `EnvironmentFile` 或导出环境变量注入。

关键变量（见 `.env.example`）：

- `XHSNOTE_OUTPUT_DIR`：输出目录（建议指向持久化路径）
- `XHSNOTE_TIMEOUT`：请求超时
- `XHSNOTE_SAVE_LOG` / `XHSNOTE_LOG_DIR`：日志开关与目录
- `XHSNOTE_API_HOST`：生产环境通常用 `0.0.0.0`
- `XHSNOTE_API_PORT`：端口
- `XHSNOTE_API_RELOAD`：生产环境建议 `false`
- `XHSNOTE_API_CORS_ORIGINS`：前端域名白名单（逗号分隔；或 `*`）
- `XHSNOTE_API_ENABLE_STATIC` / `XHSNOTE_API_STATIC_DIR`：是否挂载静态站点（`web/dist`）

> 如需 Cookie / UA，请通过环境变量/部署配置注入，避免写入仓库。

### 3）启动后端（不含 Web UI）

```bash
export XHSNOTE_API_HOST=0.0.0.0
export XHSNOTE_API_PORT=8000
export XHSNOTE_API_RELOAD=false
uv run python main_api.py
```

验证：

```bash
curl http://127.0.0.1:8000/api/health
```

### 4）（可选）构建并部署 Web UI（由后端静态托管）

在服务器上构建：

```bash
cd web
npm install
npm run build
```

然后确保：

- `web/dist` 存在
- `XHSNOTE_API_ENABLE_STATIC=true`（或不设置，默认开启）
- `XHSNOTE_API_STATIC_DIR` 不设置时默认指向 `web/dist`

此时 FastAPI 会把静态站点挂载在 `/`，API 仍在 `/api/*`。

### 5）systemd 守护（推荐）

示例：`/etc/systemd/system/xhsnote-parser.service`

```ini
[Unit]
Description=xhsnote-parser API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/xhsnote-parser
EnvironmentFile=/opt/xhsnote-parser/.env
ExecStart=/usr/bin/env uv run python main_api.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now xhsnote-parser
sudo systemctl status xhsnote-parser
```

### 6）Nginx 反向代理（示例）

将外网 `80/443` 转发到本机 `8000`：

```nginx
server {
  listen 80;
  server_name your.domain.com;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

如果前端与后端分开部署（不同域名/端口），前端构建时可在 `web/.env` 设置 `VITE_API_BASE` 指向后端的 `/api` 根路径，并同步配置 `XHSNOTE_API_CORS_ORIGINS`。
