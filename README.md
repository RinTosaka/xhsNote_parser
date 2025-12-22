# xhsNote Parser

一个用于抓取并解析小红书笔记详情的轻量化工具集。项目将页面请求、JSON 解析、图片去水印处理以及数据落盘进行模块化封装，可直接通过命令行脚本使用，也可以在其他 Python 项目中以库的形式复用。

## 功能特点
- **HTTP 请求模块化**：可自定义 `User-Agent`、超时与 `requests.Session`，方便注入代理、Cookie 等扩展能力。
- **结构化数据解析**：自动从 `window.__INITIAL_STATE__` 中提取笔记数据，补充图片 `traceId` 与无水印链接，并格式化时间字段。
- **日志与 CLI 支持**：内置日志等级控制与命令行参数解析，出错时能获得清晰的诊断信息。
- **JSON 导出**：默认会将解析结果写入 `output/<作者昵称>_notes/{title}_{noteId}_noteDetail.json`，并可借由 `-o/--output` 指定不同的根目录。

## 环境要求
- Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)（可先执行 `pip install uv` 获取），统一由 uv 管理依赖。
- 依赖由 `pyproject.toml` + `uv.lock` 锁定，当前只包含 `requests`。

使用 uv 同步依赖并验证环境：

```bash
uv sync
uv run python -m pip list  # 确认环境安装成功
```

## 命令行使用

```bash
uv run python main.py <note_url> \
    --timeout 15 \
    --user-agent "自定义 UA" \
    --log-level DEBUG \
    -o my_exports
```

参数说明：
- `url`：必填，小红书笔记 URL。
- `-o / --output`：输出 JSON 根目录，默认 `output`，实际文件按 `{作者昵称}_notes/{title}_{noteId}_noteDetail.json` 组织。
- `--timeout`：HTTP 请求超时时间（秒），默认 15。
- `--user-agent`：覆盖默认 UA。
- `--log-level`：日志等级，支持 `DEBUG/INFO/WARNING/ERROR`。

脚本运行成功后，会在指定或默认目录下生成 `{作者昵称}_notes/{title}_{noteId}_noteDetail.json`。

## 作为库调用

```python
from pathlib import Path
from xhsnote_parser import parse_note, configure_logging

configure_logging()  # 可选
detail = parse_note(
    "https://www.xiaohongshu.com/explore/xxx",
    headers={"Cookie": "..."},
    timeout=20,
    output_path=Path("my_note.json"),
)
print(detail["title"])
```

`parse_note` 返回完整的笔记详情字典，包含图片去水印后的 `urlNoWatermark`、格式化的 `time/lastUpdateTime` 以及原笔记链接等字段。

## 项目结构

```
xhsnote_parser/
├── cli.py             # 命令行入口与参数解析
├── http_client.py     # 请求封装与默认头部
├── logging_utils.py   # 日志配置工具
├── note_detail.py     # HTML 解析、数据补全逻辑
├── service.py         # 对外提供的 parse_note API
└── storage.py         # JSON 写入
main.py               # CLI 启动脚本
```

## 后续规划
- 支持批量解析多条笔记。
- 新增单元测试覆盖核心解析逻辑。
- 提供更丰富的 CLI 选项，例如代理设置、并发下载图片等。
