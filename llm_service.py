"""
ProteusP LLM Service (Ollama)
로컬 Ollama LLM과 연동하여 RAG 답변 생성
"""

import json
import time
from typing import Any, Dict, Generator, List, Optional

import httpx

from proteusp.config import ProteusPConfig, get_config


class LLMService:
    """
    Ollama API와 통신하는 LLM 서비스.
    로컬에서 실행 중인 Ollama 인스턴스와 HTTP 통신.
    """

    def __init__(self, config: Optional[ProteusPConfig] = None):
        self.config = config or get_config()
        self._base_url = self.config.ollama_host.rstrip("/")
        self._model = self.config.llm_model
        self._available = False
        self._generation_stats = {"total_calls": 0, "total_tokens": 0}

    def check_availability(self) -> Dict[str, Any]:
        """
        Check if Ollama server is running and the model is available.
        Returns status dict.
        """
        try:
            # Check server health
            resp = httpx.get(
                f"{self._base_url}/api/tags",
                timeout=5.0,
            )
            if resp.status_code != 200:
                return {"available": False, "error": "Server not responding"}

            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]

            # Check if our model is available
            model_available = any(
                self._model in m_name for m_name in model_names
            )

            self._available = model_available

            return {
                "available": model_available,
                "server": "ok",
                "model": self._model,
                "model_found": model_available,
                "available_models": model_names[:5],
            }
        except httpx.ConnectError:
            return {
                "available": False,
                "error": f"Cannot connect to Ollama at {self._base_url}",
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def list_models(self) -> List[str]:
        """List all available models in Ollama."""
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
            return []
        except Exception:
            return []

    def generate(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a response using RAG context.
        
        Args:
            query: User's question
            context_chunks: List of retrieved context chunks (with 'document' key)
            system_prompt: Optional system prompt override
            stream: Whether to stream the response

        Returns:
            Dict with 'response', 'sources', 'usage' keys
        """
        if not self._available:
            status = self.check_availability()
            if not status.get("available"):
                return {
                    "response": f"⚠️ Ollama 서버에 연결할 수 없습니다.\n"
                                f"- 호스트: {self._base_url}\n"
                                f"- 모델: {self._model}\n"
                                f"- 오류: {status.get('error', '알 수 없는 오류')}\n\n"
                                f"터미널에서 'ollama serve'를 실행했는지 확인하세요.",
                    "sources": [],
                    "usage": {},
                    "error": status.get("error", ""),
                }

        # Build context string from chunks
        context_parts = []
        sources = []
        for i, chunk in enumerate(context_chunks[:5]):
            text = chunk.get("document", chunk.get("text", ""))
            source = chunk.get("metadata", {}).get("source", "알 수 없음")
            header = chunk.get("metadata", {}).get("header", "")
            file_name = chunk.get("metadata", {}).get("file_name", "")

            # Compact source reference
            source_ref = file_name or source.split("/")[-1].replace(".md", "")
            if header:
                source_ref += f" > {header[:50]}"

            context_parts.append(f"[출처 {i+1}: {source_ref}]\n{text}")
            sources.append({
                "index": i,
                "source": source,
                "file_name": file_name or Path(source).stem,
                "header": header,
                "excerpt": text[:150] + "..." if len(text) > 150 else text,
            })

        context_text = "\n\n---\n\n".join(context_parts)
        sys_prompt = system_prompt or self.config.llm_system_prompt

        # Build the full prompt
        full_prompt = f"""{sys_prompt}

# 검색된 컨텍스트 (Obsidian 노트):
{context_text}

# 사용자 질문:
{query}

# 답변:
"""

        # Call Ollama API
        try:
            t0 = time.time()
            response = self._call_ollama(full_prompt, stream=stream)

            elapsed = time.time() - t0
            self._generation_stats["total_calls"] += 1
            self._generation_stats["total_tokens"] += response.get("eval_count", 0)

            return {
                "response": response.get("response", ""),
                "sources": sources,
                "usage": {
                    "prompt_tokens": response.get("prompt_eval_count", 0),
                    "completion_tokens": response.get("eval_count", 0),
                    "total_tokens": (response.get("prompt_eval_count", 0)
                                     + response.get("eval_count", 0)),
                    "time_seconds": round(elapsed, 2),
                },
            }
        except Exception as e:
            return {
                "response": f"⚠️ LLM 응답 생성 중 오류 발생: {e}",
                "sources": sources,
                "usage": {},
                "error": str(e),
            }

    def _call_ollama(
        self,
        prompt: str,
        stream: bool = False,
    ) -> dict:
        """Execute the actual Ollama API call."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": self.config.llm_temperature,
                "num_predict": self.config.llm_max_tokens,
            },
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()

            if stream:
                # Accumulate streaming response
                full_response = ""
                for line in resp.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            full_response += data.get("response", "")
                            if data.get("done"):
                                data["response"] = full_response
                                return data
                        except json.JSONDecodeError:
                            continue
                return {"response": full_response}
            else:
                return resp.json()

    def generate_stream(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Stream response tokens from the LLM.
        Yields response text chunks and final metadata.
        """
        if not self._available:
            self.check_availability()

        # Build context (same as generate)
        context_parts = []
        sources = []
        for i, chunk in enumerate(context_chunks[:5]):
            text = chunk.get("document", chunk.get("text", ""))
            source = chunk.get("metadata", {}).get("source", "알 수 없음")
            header = chunk.get("metadata", {}).get("header", "")
            file_name = chunk.get("metadata", {}).get("file_name", "")
            source_ref = file_name or source.split("/")[-1].replace(".md", "")
            if header:
                source_ref += f" > {header[:50]}"
            context_parts.append(f"[출처 {i+1}: {source_ref}]\n{text}")
            sources.append({
                "source": source,
                "file_name": file_name or Path(source).stem,
                "header": header,
            })

        context_text = "\n\n---\n\n".join(context_parts)
        sys_prompt = system_prompt or self.config.llm_system_prompt

        full_prompt = f"""{sys_prompt}

# 검색된 컨텍스트:
{context_text}

# 사용자 질문:
{query}

# 답변:
"""

        try:
            payload = {
                "model": self._model,
                "prompt": full_prompt,
                "stream": True,
                "options": {
                    "temperature": self.config.llm_temperature,
                    "num_predict": self.config.llm_max_tokens,
                },
            }

            with httpx.Client(timeout=120.0) as client:
                with client.stream(
                    "POST", f"{self._base_url}/api/generate", json=payload
                ) as resp:
                    for line in resp.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"\n\n[오류: {e}]"


# Helper
from pathlib import Path  # noqa: E402


# Singleton
_llm: Optional[LLMService] = None


def get_llm(config: Optional[ProteusPConfig] = None) -> LLMService:
    """Get or create global LLM service singleton."""
    global _llm
    if _llm is None:
        _llm = LLMService(config or get_config())
    return _llm


def reset_llm() -> None:
    """Reset LLM singleton."""
    global _llm
    _llm = None
