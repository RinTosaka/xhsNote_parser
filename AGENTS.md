# Repository Guidelines

## 项目结构与模块组织
- `main.py`：提供 Windows 友好的 CLI 启动入口，底层委托 `xhsnote_parser.cli`.
- `xhsnote_parser/cli.py`：命令解析与日志开关；调用 `service.parse_note`。
- `xhsnote_parser/http_client.py` 与 `note_detail.py`：前者封装 `requests.Session` 请求，后者负责解析 `window.__INITIAL_STATE__`、格式化时间与图片去水印。
- `xhsnote_parser/service.py`、`storage.py`、`logging_utils.py`：组合流程、写入 JSON 以及统一日志。
- 根目录下的 `pyproject.toml`、`uv.lock` 记录依赖，仅包含 `requests`，方便被嵌入到其它项目；`README.md` 提供使用示例。

## 构建、测试与开发命令
- `uv sync`：读取 `pyproject.toml` 与 `uv.lock`，生成/刷新虚拟环境并安装锁定依赖。
- `uv run python main.py https://www.xiaohongshu.com/explore/<id> --timeout 15 -o noteDetail.json`：标准解析命令，`--user-agent` 与 `--log-level DEBUG` 用于排查网络或页面差异。
- `uv run python -m xhsnote_parser.cli --help`：查看 CLI 参数以验证新增开关。
- `uv run pytest tests -q`：运行单元及端到端测试，提交前请附带命令输出，必要时追加 `-vv` 帮助排障。

## 编码风格与命名约定
遵循 PEP 8 与 4 空格缩进，保持 `snake_case` 函数/变量命名以及 `CapWords` 类名；公共 API 须补全类型注解与 docstring。解析逻辑应以纯函数实现，便于复用；网络错误统一在 `http_client.py` 中转换为 `RuntimeError` 并记录日志，避免泄露底层实现细节。新增模块须在 `__init__.py` 导出对外可见符号。

## 测试指南
当前仓库尚无正式测试目录，新贡献需在 `tests/` 下创建 `test_<module>.py`，优先覆盖 `note_detail` 的解析分支以及 CLI 参数矩阵。默认使用 `pytest`，命名遵循 `test_function_behaviour`，并借助 `requests-mock` 或离线 HTML 固定输入，目标覆盖率不低于 80%。提交前请运行 `pytest -k note_detail -vv` 与一次真实 CLI 演练，确保 `noteDetail.json` 成功写入。

## 提交与 Pull Request 指南
目前 `main` 还没有历史提交，请自觉遵循 Conventional Commits（示例：`feat(cli): 支持批量解析`）。提交信息需说明动机与影响面，PR 描述中附上：变更摘要、测试命令输出、关联 issue/任务编号，以及必要的日志/截图。变更触及网络或存储层时，请解释超时、UA 或 headers 的修改理由，并 @ 审阅者确认。保持 PR 专注单一范围，优先补文档与类型注释。

## 安全与配置提示
解析小红书需要自定义 `Cookie`/`User-Agent` 时，请通过环境变量或本地配置文件注入，严禁写入仓库。默认 `requests` 会跟随重定向，涉及公司代理或自建调试代理时，可注入 `session` 但需在描述中说明。输出 JSON 包含用户生成内容，请勿在公共渠道共享真实数据样例，示例可改写或脱敏处理。
