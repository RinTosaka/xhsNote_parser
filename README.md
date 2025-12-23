# xhsNote Parser

一个专注于解析小红书图文/视频笔记详情页并导出结构化 JSON 的轻量级工具集。项目提供 Windows 友好的 CLI、可复用的 `parse_note` API 以及最小依赖（仅 `requests`），既能直接在终端使用，也能方便地嵌入到其它 Python 项目中。

## 功能特性
- **网络请求封装**：`http_client.fetch_note_page` 统一了 `requests.Session`、默认 User-Agent、超时与异常转换，所有底层网络异常都会被包装为 `RuntimeError` 并带有日志，避免泄露实现细节。
- **批量解析与进度日志**：CLI 支持一次传入多个 URL 或通过文件批量输入，并在日志中输出 `[当前/总数]` 进度，便于大批量任务监控。
- **可选的本地日志文件**：可通过 `--save-log` 开启日志写盘，默认写入 `logs/xhsnote_parser.log`，方便留存排障信息（可用 `--log-dir` 调整目录）。
- **`__INITIAL_STATE__` 解析**：`note_detail.extract_note_data` 精确定位页面中的 `window.__INITIAL_STATE__` JSON，自动处理 `undefined`、时间戳格式化以及图片 traceId 提取，保证解析出的字段可直接用于业务。
- **去水印与视频地址补全**：`note_detail.build_note_detail` 会根据图片/视频 `urlDefault` 推导出无水印地址 (`urlNoWatermark`)，并保留原始 traceId 方便排错。
- **安全的文件命名**：CLI 端借助 `_sanitize_segment` 自动对标题、作者 ID、noteId 做非法字符替换与裁剪，生成路径形如 `output/<作者>_notes/<标题>_<noteId>_noteDetail.json`，可避免跨平台文件名冲突。
- **可选的持久化流程**：`parse_note` 默认会调用 `storage.save_note_detail` 写入 JSON；若以库形式调用，可通过 `output_path=None` 禁止写盘，仅返回内存对象。

## 仓库结构
```
xhsNote_parser/
├── main.py                 # Windows 入口脚本，委托 xhsnote_parser.cli
├── xhsnote_parser/
│   ├── cli.py              # CLI 参数解析、日志开关与输出路径组织
│   ├── http_client.py      # requests.Session 封装与默认头
│   ├── logging_utils.py    # logging basicConfig 与等级解析
│   ├── note_detail.py      # HTML 解析、时间格式化、去水印逻辑
│   ├── service.py          # 业务编排 parse_note
│   ├── storage.py          # JSON 写盘
│   └── __init__.py         # 导出公共 API
├── pyproject.toml / uv.lock# 仅锁定 requests 依赖
└── output/                 # CLI 运行后的示例输出
```

## 环境准备
1. 安装 Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)（`pip install uv`）。
2. 在仓库根目录执行：
   ```bash
   uv sync                # 创建虚拟环境并根据 uv.lock 安装依赖
   uv run python -m pip list  # 可选：确认虚拟环境可用
   ```
3. 如需在非网络环境使用，可提前配置系统代理或在运行前导出所需 Cookie/User-Agent 至环境变量，再通过 CLI 参数注入。

## CLI 使用
### 最简示例
```bash
uv run python main.py https://www.xiaohongshu.com/explore/<note_id> \
    --timeout 15 \
    --user-agent "自定义UA" \
    --log-level DEBUG \
    -o my_exports
```

### 参数说明
| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `urls` | 必填 | 位置参数，可提供 1..N 个小红书 URL，按输入顺序依次解析。 |
| `-f/--input-file` | 无 | 指向 UTF-8 文本文件，每行一个 URL（支持 `#` 注释），会与位置参数合并并自动去重。 |
| `--env-file` | `.env` | 指定额外的环境配置文件路径，默认自动查找当前目录下的 `.env`。 |
| `-o/--output` | `output` | JSON 根目录，可在 `.env` 中通过 `XHSNOTE_OUTPUT_DIR` 预设。 |
| `--timeout` | `15` | HTTP 请求超时（秒），同样支持 `.env` 中的 `XHSNOTE_TIMEOUT`。 |
| `--user-agent` | 内置浏览器 UA | 覆盖默认 UA，可结合 `.env` 持久化自定义值。 |
| `--log-level` | `INFO` | 日志等级，支持 `DEBUG/INFO/WARNING/ERROR`，亦可由 `XHSNOTE_LOG_LEVEL` 控制。 |
| `--save-log`/`--no-save-log` | `False` | 控制是否写入日志文件，`.env` 中的 `XHSNOTE_SAVE_LOG` 可设置默认值。 |
| `--log-dir` | `logs` | 日志目录，仅在写文件日志时生效，可使用 `XHSNOTE_LOG_DIR` 预配。 |

### 使用 .env 管理默认配置
- CLI 参数 > `.env` > 内置默认值，若命令行中未显式传入，才会回退到 `.env`。
- 默认会读取工程根目录下的 `.env`，也可以通过 `--env-file` 指向其它路径；参考仓库附带的 `.env.example`。
- 支持的键值：
  - `XHSNOTE_TIMEOUT`：请求超时秒数。
  - `XHSNOTE_USER_AGENT`：自定义 UA 字符串。
  - `XHSNOTE_OUTPUT_DIR`：导出 JSON 根目录。
  - `XHSNOTE_LOG_LEVEL`：`DEBUG/INFO/WARNING/ERROR` 其一。
  - `XHSNOTE_SAVE_LOG`：`true/false`，控制是否落盘日志。
  - `XHSNOTE_LOG_DIR`：日志文件目录。
  - `XHSNOTE_INPUT_FILE`：需要预置的 URL 列表文件（等价于 `--input-file`）。
- `.env` 写法示例：

```dotenv
XHSNOTE_TIMEOUT=20
XHSNOTE_USER_AGENT="Mozilla/5.0 ..."
XHSNOTE_OUTPUT_DIR=output
XHSNOTE_LOG_LEVEL=INFO
XHSNOTE_SAVE_LOG=true
XHSNOTE_LOG_DIR=logs
# XHSNOTE_INPUT_FILE=notes_url.txt
```

### 批量解析示例
```bash
# urls.txt 中每行一个链接，可穿插 # 注释或空行
uv run python main.py https://www.xiaohongshu.com/explore/<note_a> \
    https://www.xiaohongshu.com/explore/<note_b> \
    -f urls.txt \
    --log-level INFO \
    -o batched_output
```

运行过程中会输出 `[当前/总数]` 进度与每个笔记的目标路径，失败条目会继续记录，所有任务完成后若存在失败则返回非 0 状态码。

若启用 `--save-log`，日志会在控制台输出的同时写入 `logs/xhsnote_parser.log`（或指定目录），方便长时间批量任务排查。

CLI 成功后会在 `output/<作者>_notes/<标题>_<noteId>_noteDetail.json` 写出完整解析结果，包含时间戳（`time`、`lastUpdateTime`）与 `urlNoWatermark` 等精选字段。

## 输出与文件命名策略
- `_sanitize_segment` 会移除 `<>:"/\\|?*`、控制字符与路径尾部的空格/点，保证在 Windows/macOS/Linux 都能正常保存。
- 若解析不到作者昵称/标题，将退回 `unknown_author`、`untitled`，确保 CLI 不会因为空值而异常。
- 可手动通过 `-o` 指定一个绝对或相对路径，命令会自动创建缺失的父目录。

## Python API 调用
```python
from pathlib import Path
from xhsnote_parser import parse_note, configure_logging, DEFAULT_TIMEOUT

configure_logging()  # 可按需传入 logging.DEBUG
detail = parse_note(
    "https://www.xiaohongshu.com/explore/<note_id>",
    headers={"Cookie": "...", "User-Agent": "..."},
    timeout=DEFAULT_TIMEOUT,
    output_path=Path("my_note.json"),  # 传 None 可跳过写盘
)
print(detail["title"], detail["imageList"][0]["urlNoWatermark"])
```

返回的 `detail` 字典会附加：
- `noteUrl`：原始输入 URL（便于后续回溯）。
- `imageList[].urlNoWatermark` / `video.urlNoWatermark`：基于 CDN 规则推导出的无水印直链。
- `time`、`lastUpdateTime`：统一格式化为 `YYYY-mm-dd HH:MM:SS`。

## 内部处理流程
1. `cli.main` 接收命令行参数，初始化日志与目标输出路径。
2. `service.parse_note` 调用 `http_client.fetch_note_page` 拉取 HTML，并将网络异常转换为 `RuntimeError`，由 CLI 捕获并打印中文提示。
3. `note_detail.extract_note_data` 定位 `window.__INITIAL_STATE__`，提取 `noteDetailMap` 并选择第一条笔记。
4. `note_detail.build_note_detail` 富化字段：图片/视频去水印、traceId、时间戳格式化、附加 `noteUrl`。
5. `storage.save_note_detail` 以 `ensure_ascii=False` 写盘，保留原文内容。

了解此流程有助于在自定义脚本中插入调试逻辑或覆写 `requests.Session` 以支持代理/重试。

## 调试与常见问题
- **日志**：传入 `--log-level DEBUG` 或调用 `configure_logging(logging.DEBUG)` 可输出网络请求与解析细节。
- **被风控/403**：多数情况下需要自备账号 Cookie，将其放入 `headers` 或 CLI 参数 `--user-agent`/`--cookie`（可通过 `envsubst` 注入）。
- **长标题导致路径过长**：可手动使用 `-o` 将输出目录设置为较短路径，或自行修改 `_sanitize_segment` 逻辑。
- **测试建议**：运行 `uv run pytest tests -q`（若存在测试）或至少执行一次真实 CLI 命令，确认 `noteDetail.json` 成功写入。

## 后续规划
- 支持失败重试与可配置并发度，进一步提升批量任务表现。
- 完善 `tests/`，覆盖 `note_detail` 的异常分支及 CLI 参数矩阵。
- 考虑新增导出选项（如单独下载图片/视频）与更丰富的日志/重试策略。
- 考虑引入 API 服务形态（如 FastAPI/Flask），对外暴露 RESTful 接口，方便上层系统以 HTTP 方式集成。
