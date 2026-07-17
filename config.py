"""
ProteusP Configuration Module
환경 변수 및 설정 파일 기반 구성 관리
"""

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Default paths for Termux-Ubuntu on Android tablet
DEFAULT_HOME = Path.home()
DEFAULT_VAULT_PATH = os.environ.get(
    "PROTEUSP_VAULT_PATH",
    str(DEFAULT_HOME / "storage" / "shared" / "Obsidian" / "Vault")
)
DEFAULT_DB_PATH = os.environ.get(
    "PROTEUSP_DB_PATH",
    str(DEFAULT_HOME / ".proteusp" / "chroma_db")
)
DEFAULT_CONFIG_PATH = os.environ.get(
    "PROTEUSP_CONFIG_PATH",
    str(DEFAULT_HOME / ".proteusp" / "config.json")
)
DEFAULT_LOG_PATH = os.environ.get(
    "PROTEUSP_LOG_PATH",
    str(DEFAULT_HOME / ".proteusp" / "logs")
)
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_TELEGRAM_CONFIG = os.environ.get(
    "PROTEUSP_TELEGRAM_CONFIG",
    str(Path.home() / ".codex" / "telegram-bridge.json")
)


@dataclass
class ProteusPConfig:
    """Unified configuration for ProteusP pipeline."""

    # --- Obsidian Vault ---
    vault_path: str = DEFAULT_VAULT_PATH
    vault_watch_recursive: bool = True
    vault_watch_debounce_seconds: int = 5

    # --- Git Sync ---
    git_enabled: bool = False
    git_remote_url: str = ""
    git_poll_interval_minutes: int = 5
    git_branch: str = "main"

    # --- Chunking ---
    chunk_size: int = 512
    chunk_overlap: int = 64

    # --- Embedding ---
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"  # cpu (no GPU on typical tablet)
    embedding_batch_size: int = 16
    embedding_normalize: bool = True

    # --- Vector DB ---
    vector_db_path: str = DEFAULT_DB_PATH
    vector_db_collection: str = "obsidian_vault"

    # --- Search ---
    search_hybrid_top_k: int = 20
    search_rerank_top_k: int = 5
    search_bm25_weight: float = 0.3
    search_vector_weight: float = 0.7
    reranker_model: str = "ms-marco-MiniLM-L-12-v2"  # FlashRank compatible

    # --- LLM (Ollama) ---
    ollama_host: str = DEFAULT_OLLAMA_HOST
    llm_model: str = "timHan/llama3.2korean3B"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    llm_system_prompt: str = (
        "당신은 Obsidian 노트를 기반으로 질문에 답변하는 ProteusP AI 어시스턴트입니다. "
        "주어진 컨텍스트(검색된 노트 조각)를 바탕으로 정확하고 간결하게 답변하세요. "
        "컨텍스트에 없는 내용은 추측하지 말고 모른다고 말하세요. "
        "한국어로 자연스럽게 답변하며, 필요시 출처 파일명을 함께 제공하세요."
    )

    # --- Logging ---
    log_path: str = DEFAULT_LOG_PATH
    log_level: str = "INFO"

    # --- Telegram ---
    telegram_config_path: str = DEFAULT_TELEGRAM_CONFIG
    telegram_notify_on_index: bool = False
    telegram_notify_on_error: bool = True

    # --- Pipeline ---
    auto_index_on_start: bool = True
    incremental_update: bool = True

    def save(self, path: Optional[str] = None) -> None:
        """Save configuration to JSON file."""
        save_path = Path(path or DEFAULT_CONFIG_PATH)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def to_dict(self) -> dict:
        """Convert config to dictionary (excluding internal fields)."""
        return {
            "vault_path": self.vault_path,
            "vault_watch_recursive": self.vault_watch_recursive,
            "vault_watch_debounce_seconds": self.vault_watch_debounce_seconds,
            "git_enabled": self.git_enabled,
            "git_remote_url": self.git_remote_url,
            "git_poll_interval_minutes": self.git_poll_interval_minutes,
            "git_branch": self.git_branch,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "embedding_model": self.embedding_model,
            "embedding_device": self.embedding_device,
            "embedding_batch_size": self.embedding_batch_size,
            "vector_db_path": self.vector_db_path,
            "vector_db_collection": self.vector_db_collection,
            "search_hybrid_top_k": self.search_hybrid_top_k,
            "search_rerank_top_k": self.search_rerank_top_k,
            "search_bm25_weight": self.search_bm25_weight,
            "search_vector_weight": self.search_vector_weight,
            "reranker_model": self.reranker_model,
            "ollama_host": self.ollama_host,
            "llm_model": self.llm_model,
            "llm_temperature": self.llm_temperature,
            "llm_max_tokens": self.llm_max_tokens,
            "log_path": self.log_path,
            "log_level": self.log_level,
            "telegram_config_path": self.telegram_config_path,
            "telegram_notify_on_index": self.telegram_notify_on_index,
            "telegram_notify_on_error": self.telegram_notify_on_error,
            "auto_index_on_start": self.auto_index_on_start,
            "incremental_update": self.incremental_update,
        }

    @classmethod
    def load(cls, path: Optional[str] = None) -> "ProteusPConfig":
        """Load configuration from JSON file or return defaults."""
        load_path = Path(path or DEFAULT_CONFIG_PATH)
        if not load_path.exists():
            return cls()
        try:
            with open(load_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = cls()
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            return config
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load config from {load_path}: {e}")
            return cls()

    @classmethod
    def from_env(cls) -> "ProteusPConfig":
        """Load config from environment variables (overrides file)."""
        config = cls.load()
        # Environment overrides
        env_map = {
            "PROTEUSP_VAULT_PATH": "vault_path",
            "PROTEUSP_DB_PATH": "vector_db_path",
            "OLLAMA_HOST": "ollama_host",
            "PROTEUSP_LLM_MODEL": "llm_model",
            "PROTEUSP_CHUNK_SIZE": "chunk_size",
            "PROTEUSP_CHUNK_OVERLAP": "chunk_overlap",
            "PROTEUSP_LOG_LEVEL": "log_level",
        }
        for env_var, attr in env_map.items():
            val = os.environ.get(env_var)
            if val is not None:
                if attr in ("chunk_size", "chunk_overlap"):
                    val = int(val)
                setattr(config, attr, val)
        return config


# Singleton
_config: Optional[ProteusPConfig] = None


def get_config() -> ProteusPConfig:
    """Get global configuration singleton."""
    global _config
    if _config is None:
        _config = ProteusPConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset configuration singleton (useful for tests)."""
    global _config
    _config = None
