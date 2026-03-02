# xhsnote-parser

一个面向小红书（Xiaohongshu）笔记页面的解析工具：

- 从页面 HTML 中提取 `window.__INITIAL_STATE__`
- 解析出 `noteDetail` 并输出为 JSON
- 额外生成图片/视频的去水印直链字段（`urlNoWatermark`）
- 提供 Windows 友好的 CLI、FastAPI 后端，以及可选的 Web UI

> 说明：本项目仅用于学习/自用调试。目标站点可能随时变更页面结构或访问策略；请遵守当地法律法规与站点条款。

## 目录结构

- `main.py`：CLI 入口（委托 `xhsnote_parser.cli`）
- `main_api.py`：API 入口（启动 `xhsnote_parser.api:app`）
- `xhsnote_parser/`：核心解析/存储/API 代码
- `web/`：Vite + React 前端（可选）
- `docs/quickstart.md`：API + Web 快速开始

## 环境要求

- Python `>= 3.12`（见 `.python-version` 与 `pyproject.toml`）
- Node.js（仅在需要构建 `web/` 时需要；建议 18+）
- 推荐使用：
  - `uv` 管理 Python 版本/依赖与运行（锁文件 `uv.lock`）
  - `nvm` 管理 Node.js 版本（前端构建用）

## 安装（uv）

在项目根目录：

```bash
uv sync
```

> 生产环境建议：使用 `uv sync --frozen` 以严格按 `uv.lock` 安装。

## CLI 使用

解析单条笔记：

```bash
uv run python main.py https://www.xiaohongshu.com/explore/<note_id>
```

查看 CLI 帮助：

```bash
uv run python -m xhsnote_parser.cli --help
```

从文件读取 URL（支持空行与 `#` 注释）：

```bash
uv run python main.py -f notes_url.txt
```

### CLI 配置（.env）

CLI 支持读取当前目录 `.env`，也可以用 `--env-file` 指定：

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

### API 环境变量

API 从“进程环境变量”读取配置（直接运行时不会自动加载 `.env`）。推荐在 systemd 中用 `EnvironmentFile` 注入，或在 shell 中 `source .env` 后启动。

见 `.env.example`：

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

> 说明：API 请求的 `options.user_agent` / `options.cookie` 由调用方在请求体里传入；不会自动从 `.env` 填充（CLI 才会使用 `.env` 作为默认值）。

## Web UI（可选）

开发模式：

```bash
cd web
npm ci
npm run dev
```

生产构建：

```bash
cd web
npm ci
npm run build
```

构建后会生成 `web/dist`。若 `web/dist` 存在且启用静态挂载（默认开启），后端会把它托管在 `/`，API 仍在 `/api/*`。

如需修改 API 地址，可在前端构建时通过 `web/.env` 设置 `VITE_API_BASE`（默认 `"/api"`）。

## 部署到服务器（Linux）

下面以“后端 API +（可选）Web UI，使用 Nginx 反代 + systemd 守护”为目标，给出一套常用部署流程。建议后端只监听本机回环地址，通过 Nginx 对外提供 `80/443`。

### 1）拉代码到服务器

```bash
mkdir -p ~/github
cd ~/github
git clone https://github.com/RinTosaka/xhsNote_parser
cd xhsnote-parser
```

### 2）用 uv 管理 Python（建议）

安装uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装依赖（生产环境建议加 `--frozen`）：

```bash
uv sync --frozen
```

### 3）用 nvm 管理 Node.js（仅用于构建 Web）

安装 nvm（按官方方式安装后，重新登录或手动加载 nvm 环境）

```
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash
```

然后安装 Node.js LTS：

```bash
nvm install --lts
nvm use --lts
node -v
npm -v
```

构建前端：

```bash
cd web
npm ci
npm run build
```

> 运行期不需要 Node.js；只要 `web/dist` 已构建好即可。

### 4）配置环境变量（.env）

```bash
cp .env.example .env
chmod 600 .env
```

生产环境建议至少调整：

- `XHSNOTE_API_HOST=127.0.0.1`（由 Nginx 对外暴露）
- `XHSNOTE_API_PORT=8000`
- `XHSNOTE_API_RELOAD=false`
- `XHSNOTE_API_CORS_ORIGINS=https://your.domain.com`
- `XHSNOTE_OUTPUT_DIR=/home/<user>/xhsNote-output`（确保可写、可持久化）
- 若要后端托管前端静态：`XHSNOTE_API_ENABLE_STATIC=true`

### 5）systemd 守护后端

创建 service：`/etc/systemd/system/xhsnote_parser.service`（把路径与用户名改成你的）

```ini
[Unit]
Description=xhsnote-parser (FastAPI)
After=network.target

[Service]
Type=simple
User=<user>
WorkingDirectory=/home/<user>/github/xhsNote_parser
EnvironmentFile=/home/<user>/github/xhsNote_parser/.env
ExecStart=/home/<user>/.local/bin/uv run python main_api.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now xhsnote_parser
sudo systemctl status xhsnote_parser
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

查看日志：

```bash
journalctl -u xhsnote-parser -f
```

### 6）Nginx 反向代理（建议）

示例配置（将域名改成你的）：

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

如前后端分开部署（不同域名/端口），前端构建时可在 `web/.env` 设置 `VITE_API_BASE` 指向后端 `/api`；同时按需配置 `XHSNOTE_API_CORS_ORIGINS`。

## 安全提示

- 不要把 Cookie / UA 写入仓库；建议仅通过 `.env`/systemd 环境变量在服务器注入。
- 输出 JSON 可能包含用户生成内容，请避免公开分享真实数据样例。
