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
    include_initial_state = $false
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
