"""
文件处理器 —— 上传、解析、验证数据文件（CSV / Excel / JSON / Parquet）。
"""

import io
import os
import json
from typing import Optional

import pandas as pd

import config


class FileHandler:
    """
    统一文件入口：
    - validate(): 校验文件存在性与大小
    - load():     将文件加载为 pandas DataFrame
    - inspect():  返回 df.info() / df.describe() / 前 N 行
    """

    SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".parquet"}

    @staticmethod
    def validate(file_path: str) -> tuple[bool, Optional[str]]:
        """
        校验文件是否可读。

        Returns:
            (is_valid, error_message)
        """
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in FileHandler.SUPPORTED_EXTENSIONS:
            return False, f"不支持的文件类型: {ext}，支持: {FileHandler.SUPPORTED_EXTENSIONS}"

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > config.MAX_FILE_SIZE_MB:
            return False, f"文件过大 ({size_mb:.1f}MB)，上限 {config.MAX_FILE_SIZE_MB}MB"

        return True, None

    @staticmethod
    def load(file_path: str) -> tuple[Optional[pd.DataFrame], Optional[str], dict]:
        """
        加载文件为 DataFrame。

        Returns:
            (df, error, metadata)
        """
        ext = os.path.splitext(file_path)[1].lower()
        metadata = {"file_path": file_path, "extension": ext, "file_size_mb": 0}

        try:
            metadata["file_size_mb"] = round(os.path.getsize(file_path) / (1024 * 1024), 2)
        except OSError:
            pass

        try:
            if ext == ".csv":
                df = pd.read_csv(file_path)
            elif ext == ".tsv":
                df = pd.read_csv(file_path, sep="\t")
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(file_path)
            elif ext == ".json":
                df = pd.read_json(file_path)
            elif ext == ".parquet":
                df = pd.read_parquet(file_path)
            else:
                return None, f"不支持的文件类型: {ext}", metadata

            metadata["rows"] = len(df)
            metadata["columns"] = len(df.columns)
            metadata["column_names"] = list(df.columns)
            metadata["dtypes"] = {col: str(dt) for col, dt in df.dtypes.items()}
            metadata["memory_usage_mb"] = round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)

            return df, None, metadata

        except Exception as e:
            return None, str(e), metadata

    @staticmethod
    def inspect(df: pd.DataFrame) -> str:
        """
        生成数据摘要文本：info + describe + 前 N 行预览。
        """
        buf = io.StringIO()

        # info
        buf.write("=" * 60 + "\n")
        buf.write("📊 数据信息 (df.info())\n")
        buf.write("=" * 60 + "\n")
        df.info(buf=buf)
        buf.write("\n")

        # describe
        buf.write("=" * 60 + "\n")
        buf.write("📈 描述统计 (df.describe())\n")
        buf.write("=" * 60 + "\n")
        desc = df.describe(include="all")
        buf.write(desc.to_string(max_rows=config.MAX_ROWS_DISPLAY,
                                  max_cols=config.MAX_COLS_DISPLAY))
        buf.write("\n\n")

        # head
        buf.write("=" * 60 + "\n")
        buf.write(f"👀 前 {config.MAX_ROWS_DISPLAY} 行预览\n")
        buf.write("=" * 60 + "\n")
        buf.write(df.head(config.MAX_ROWS_DISPLAY).to_string(
            max_cols=config.MAX_COLS_DISPLAY))
        buf.write("\n")

        return buf.getvalue()
