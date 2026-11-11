# -*- coding: utf-8 -*-
"""配置：只从环境变量 / .env 读取；不得把 key 写入代码或日志。"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM providers（OpenAI-compatible） ---
    deepseek_base_url: str = ""
    deepseek_api_key: str = ""
    deepseek_reader_model: str = ""
    deepseek_judge_model: str = ""

    siliconflow_base_url: str = ""
    siliconflow_api_key: str = ""
    siliconflow_embedding_model: str = ""
    siliconflow_rerank_model: str = ""

    minimax_base_url: str = ""
    minimax_api_key: str = ""
    minimax_model: str = ""

    # --- MySQL 8 ---
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "anchorline"
    mysql_user: str = "anchorline"
    mysql_password: str = ""

    # --- LanceDB ---
    lancedb_uri: str = "./data/lancedb"

    # --- eval ---
    eval_budget_tokens: int = 4000
    eval_judge_prompt_sha256: str = ""

    # --- memory lifecycle ---
    # 每个实体最多保留多少条「当前值」；超出时自动把最旧/最低置信度的值标记失效（归档可追溯）
    memory_max_current_per_entity: int = 200

    # --- reliability ---
    llm_max_retries: int = 3
    llm_retry_base_delay_s: float = 0.5
    llm_timeout_s: float = 120.0

    # --- optional API token (off by default; set API_TOKEN to require it) ---
    api_token: str = ""

    # --- optional knowledge base (LoreKeeper bridge) ---
    # 打开后聊天 agent 多一个 kb_search 工具，查 LoreKeeper 的 chunk 索引；记忆仍走 memory_*
    lorekeeper_enabled: bool = True
    lorekeeper_lance_dir: str = ""  # 由 LOREKEEPER_LANCE_DIR 提供；空 = 知识库未配置
    lorekeeper_embed_model: str = "BAAI/bge-m3"

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    def safe_dsn(self) -> str:
        """脱敏 DSN：只给日志/诊断用，**永不包含密码**。"""
        return (
            f"mysql+pymysql://{self.mysql_user}:***"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    def redacted(self) -> dict[str, str]:
        """安全打印：key 一律变成 ***。"""
        data = self.model_dump()
        for k in list(data):
            if k.endswith("_api_key"):
                data[k] = "***" if data[k] else ""
        return data
