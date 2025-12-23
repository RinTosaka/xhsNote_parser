from pathlib import Path

import pytest

from xhsnote_parser import cli


def test_collect_input_urls_merges_cli_and_file(tmp_path: Path) -> None:
    file_path = tmp_path / "urls.txt"
    file_path.write_text(
        "https://www.xiaohongshu.com/explore/1\n"
        "# comment line\n"
        "   \n"
        "https://www.xiaohongshu.com/explore/2  \n",
        encoding="utf-8",
    )

    urls = cli._collect_input_urls(
        [
            " https://www.xiaohongshu.com/explore/1 ",
            "",
            "https://www.xiaohongshu.com/explore/3",
        ],
        file_path,
    )

    assert urls == [
        "https://www.xiaohongshu.com/explore/1",
        "https://www.xiaohongshu.com/explore/3",
        "https://www.xiaohongshu.com/explore/2",
    ]


def test_collect_input_urls_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.txt"

    with pytest.raises(ValueError) as excinfo:
        cli._collect_input_urls([], missing_path)

    assert str(excinfo.value).startswith("输入文件不存在")
