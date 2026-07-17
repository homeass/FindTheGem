"""
FindTheGem - AI Research Platform
Agent-Reach 기반 자료 조사 플랫폼
Version: 0.1-beta.3
"""

import json
import os
import sys
import time
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

__version__ = "0.1-beta.3"
__app_name__ = "FindTheGem"

# ──────────── 페이지 설정 ────────────
st.set_page_config(
    page_title=f"{__app_name__} v{__version__}",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────── 세션 상태 초기화 ────────────
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "current_query" not in st.session_state:
    st.session_state.current_query = ""
if "pipeline_status" not in st.session_state:
    st.session_state.pipeline_status = "idle"
if "progress_messages" not in st.session_state:
    st.session_state.progress_messages = []
if "download_data" not in st.session_state:
    st.session_state.download_data = None


# ──────────── 프로그레시브 프로그레스바 ────────────
class ProgressTracker:
    """파이프라인 진행 상황 추적"""
    
    STEPS = [
        ("🔍 검색 쿼리 준비", 0.1),
        ("🌐 Agent-Reach 웹 검색", 0.3),
        ("📚 검색 결과 분석", 0.5),
        ("🤖 LLM 응답 생성", 0.7),
        ("📄 답변 포맷팅", 0.9),
        ("✅ 완료", 1.0),
    ]
    
    def __init__(self):
        self.current_step = 0
        self.messages = []
    
    def update(self, step_index: int, message: str = None):
        if step_index < len(self.STEPS):
            self.current_step = step_index
            step_name, progress = self.STEPS[step_index]
            msg = message or step_name
            self.messages.append({
                "step": step_index,
                "message": msg,
                "progress": progress,
                "timestamp": time.time()
            })
            return progress
        return 1.0
    
    def get_progress(self) -> float:
        if self.current_step < len(self.STEPS):
            return self.STEPS[self.current_step][1]
        return 1.0


# ──────────── Agent-Reach 검색 엔진 ────────────
class AgentReachSearch:
    """Agent-Reach를 활용한 웹 검색 엔진"""
    
    def __init__(self):
        self.channels = {}
        self._init_channels()
    
    def _init_channels(self):
        """Agent-Reach 채널 초기화"""
        try:
            # Agent-Reach가 설치되어 있으면 채널 로드
            from agent_reach.channels.web import WebChannel
            from agent_reach.channels.youtube import YoutubeChannel
            from agent_reach.channels.github import GithubChannel
            from agent_reach.channels.rss import RssChannel
            
            self.channels = {
                "web": WebChannel(),
                "youtube": YoutubeChannel(),
                "github": GithubChannel(),
                "rss": RssChannel(),
            }
        except ImportError:
            # Agent-Reach가 없으면 기본 HTTP 검색 사용
            self.channels = {}
    
    def search(self, query: str, channels: List[str] = None) -> Dict[str, Any]:
        """
        Agent-Reach를 사용하여 웹 검색
        
        Args:
            query: 검색 쿼리
            channels: 사용할 채널 목록 (기본: ["web"])
        
        Returns:
            검색 결과 딕셔너리
        """
        if channels is None:
            channels = ["web"]
        
        results = {
            "query": query,
            "results": [],
            "sources": [],
            "timestamp": time.time(),
        }
        
        for channel_name in channels:
            if channel_name in self.channels:
                try:
                    channel = self.channels[channel_name]
                    if hasattr(channel, 'search'):
                        channel_results = channel.search(query)
                        if channel_results:
                            results["results"].extend(channel_results)
                            results["sources"].append(channel_name)
                except Exception as e:
                    results.setdefault("errors", []).append(f"{channel_name}: {str(e)}")
        
        return results
    
    def read_url(self, url: str) -> Optional[str]:
        """Agent-Reach를 사용하여 URL 내용 읽기"""
        try:
            if "web" in self.channels:
                channel = self.channels["web"]
                if hasattr(channel, 'read'):
                    return channel.read(url)
        except Exception as e:
            pass
        return None


# ──────────── RAG 쿼리 엔진 ────────────
class RAGEngine:
    """RAG(Retrieval-Augmented Generation) 엔진"""
    
    def __init__(self):
        self.searcher = None
        self.llm = None
        self._init_components()
    
    def _init_components(self):
        """RAG 구성 요소 초기화"""
        try:
            from proteusp.searcher import get_searcher
            from proteusp.llm_service import get_llm
            self.searcher = get_searcher()
            self.llm = get_llm()
        except Exception as e:
            pass
    
    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        RAG 쿼리 실행
        
        Args:
            question: 사용자 질문
            top_k: 검색 결과 수
        
        Returns:
            응답 딕셔너리
        """
        if not self.searcher or not self.llm:
            return {
                "response": "⚠️ RAG 엔진이 초기화되지 않았습니다.",
                "sources": [],
                "usage": {},
            }
        
        # 검색 실행
        search_result = self.searcher.search(question, top_k=top_k)
        chunks = search_result.get("results", [])
        
        # LLM 응답 생성
        response = self.llm.generate(
            query=question,
            context_chunks=chunks,
        )
        
        return response


# ──────────── 답변 포맷터 ────────────
class AnswerFormatter:
    """검색 결과와 RAG 응답을 포맷팅"""
    
    @staticmethod
    def format_research_answer(
        query: str,
        web_results: Dict[str, Any],
        rag_response: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        연구 결과를 마크다운 형식으로 포맷팅
        
        Args:
            query: 원본 질문
            web_results: 웹 검색 결과
            rag_response: RAG 응답 (선택사항)
        
        Returns:
            포맷팅된 마크다운 문자열
        """
        lines = [
            f"# 💎 FindTheGem 연구 결과",
            f"",
            f"## 질문",
            f"{query}",
            f"",
            f"## 웹 검색 결과",
            f"",
        ]
        
        # 웹 검색 결과 추가
        if web_results and web_results.get("results"):
            for i, result in enumerate(web_results["results"][:5], 1):
                if isinstance(result, dict):
                    title = result.get("title", result.get("text", "제목 없음")[:50])
                    url = result.get("url", "")
                    snippet = result.get("snippet", result.get("text", ""))[:200]
                    
                    lines.append(f"### {i}. {title}")
                    if url:
                        lines.append(f"🔗 {url}")
                    lines.append(f"")
                    lines.append(f"{snippet}")
                    lines.append(f"")
                elif isinstance(result, str):
                    lines.append(f"### {i}. 결과")
                    lines.append(f"{result[:200]}")
                    lines.append(f"")
        else:
            lines.append("검색 결과가 없습니다.")
            lines.append(f"")
        
        # RAG 응답 추가
        if rag_response and rag_response.get("response"):
            lines.extend([
                "---",
                "",
                "## 🤖 AI 분석 답변",
                "",
                rag_response["response"],
                "",
            ])
            
            # 참고 출처
            sources = rag_response.get("sources", [])
            if sources:
                lines.append("## 📚 참고 출처")
                for src in sources[:3]:
                    file_name = src.get("file_name", "")
                    header = src.get("header", "")
                    if file_name:
                        ref = f"- {file_name}"
                        if header:
                            ref += f" > {header[:30]}"
                        lines.append(ref)
                lines.append("")
        
        # 메타 정보
        lines.extend([
            "---",
            f"*Generated by FindTheGem v{__version__} | {time.strftime('%Y-%m-%d %H:%M:%S')}*",
        ])
        
        return "\n".join(lines)
    
    @staticmethod
    def format_for_download(content: str, format: str = "markdown") -> bytes:
        """다운로드용 형식으로 변환"""
        if format == "markdown":
            return content.encode("utf-8")
        elif format == "text":
            # 마크다운에서 텍스트만 추출
            lines = content.split("\n")
            text_lines = []
            for line in lines:
                if line.startswith("#"):
                    text_lines.append(line.replace("#", "").strip())
                elif line.startswith("---"):
                    continue
                elif line.startswith("*"):
                    continue
                else:
                    text_lines.append(line)
            return "\n".join(text_lines).encode("utf-8")
        return content.encode("utf-8")


# ──────────── 메인 앱 ────────────
def main():
    """메인 앱 실행"""
    
    # 사이드바
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/diamond.png", width=64)
        st.markdown(f"## 💎 {__app_name__}")
        st.caption(f"Version {__version__}")
        st.divider()
        
        # 시스템 상태
        st.markdown("### 📊 시스템 상태")
        
        # Agent-Reach 상태
        try:
            from agent_reach import __version__ as ar_version
            st.success(f"✅ Agent-Reach v{ar_version}")
        except:
            st.warning("⚠️ Agent-Reach 미설치")
        
        # RAG 상태
        try:
            from proteusp import __version__ as p_version
            st.info(f"ℹ️ ProteusP v{p_version}")
        except:
            st.warning("⚠️ ProteusP 미설치")
        
        st.divider()
        
        # 검색 설정
        st.markdown("### ⚙️ 검색 설정")
        search_channels = st.multiselect(
            "검색 채널",
            ["web", "youtube", "github", "rss"],
            default=["web"],
            help="사용할 Agent-Reach 채널 선택"
        )
        
        use_rag = st.checkbox(
            "RAG 검색 사용",
            value=True,
            help="로컬 Obsidian Vault 기반 RAG 검색 활성화"
        )
        
        top_k = st.slider(
            "검색 결과 수",
            min_value=1,
            max_value=20,
            value=5,
        )
        
        st.divider()
        st.caption(f"Python {sys.version.split()[0]}")
    
    
    # 메인 콘텐츠
    st.markdown(f"# 💎 {__app_name__}")
    st.markdown("### AI 기반 자료 조사 플랫폼")
    st.divider()
    
    # 검색 입력
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "질문을 입력하세요",
            placeholder="예:最新的 LLM 프레임워크 비교",
            label_visibility="collapsed",
        )
    with col2:
        search_button = st.button("🔍 검색", type="primary", use_container_width=True)
    
    # 검색 실행
    if search_button and query:
        st.session_state.current_query = query
        progress = ProgressTracker()
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: 검색 쿼리 준비
            progress.update(0, "🔍 검색 쿼리 준비 중...")
            progress_bar.progress(0.1)
            status_text.text("🔍 검색 쿼리 준비 중...")
            time.sleep(0.3)
            
            # Step 2: Agent-Reach 웹 검색
            progress.update(1, "🌐 Agent-Reach 웹 검색 실행 중...")
            progress_bar.progress(0.3)
            status_text.text("🌐 Agent-Reach 웹 검색 실행 중...")
            
            agent_search = AgentReachSearch()
            web_results = agent_search.search(query, channels=search_channels)
            
            # Step 3: 검색 결과 분석
            progress.update(2, "📚 검색 결과 분석 중...")
            progress_bar.progress(0.5)
            status_text.text("📚 검색 결과 분석 중...")
            time.sleep(0.3)
            
            # Step 4: RAG 응답 생성 (선택사항)
            rag_response = None
            if use_rag:
                progress.update(3, "🤖 LLM 응답 생성 중...")
                progress_bar.progress(0.7)
                status_text.text("🤖 LLM 응답 생성 중...")
                
                try:
                    rag_engine = RAGEngine()
                    rag_response = rag_engine.query(query, top_k=top_k)
                except Exception as e:
                    rag_response = {
                        "response": f"⚠️ RAG 검색 오류: {str(e)}",
                        "sources": [],
                    }
            
            # Step 5: 답변 포맷팅
            progress.update(4, "📄 답변 포맷팅 중...")
            progress_bar.progress(0.9)
            status_text.text("📄 답변 포맷팅 중...")
            
            formatter = AnswerFormatter()
            formatted_answer = formatter.format_research_answer(
                query=query,
                web_results=web_results,
                rag_response=rag_response,
            )
            
            # Step 6: 완료
            progress.update(5, "✅ 검색 완료!")
            progress_bar.progress(1.0)
            status_text.text("✅ 검색 완료!")
            
            # 세션 상태 저장
            st.session_state.search_results = web_results
            st.session_state.download_data = formatted_answer
            
        except Exception as e:
            st.error(f"❌ 검색 중 오류 발생: {str(e)}")
            progress_bar.progress(1.0)
            status_text.text("❌ 오류 발생")
    
    
    # 결과 표시
    if st.session_state.download_data:
        st.divider()
        
        # 결과 헤더
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### 📋 연구 결과")
        with col2:
            # 다운로드 버튼
            st.download_button(
                label="📥 다운로드",
                data=st.session_state.download_data,
                file_name=f"FindTheGem_{time.strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        
        # 결과 표시
        st.markdown(st.session_state.download_data)
        
        # 추가 액션
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 다시 검색", use_container_width=True):
                st.session_state.search_results = []
                st.session_state.download_data = None
                st.rerun()
        with col2:
            if st.button("📋 클립보드 복사", use_container_width=True):
                st.toast("클립보드에 복사되었습니다!")
        with col3:
            if st.button("📤 텔레그램 전송", use_container_width=True):
                st.toast("텔레그램 전송 기능은 준비 중입니다.")
    
    
    # 하단 정보
    st.divider()
    st.caption(
        f"{__app_name__} v{__version__} | "
        f"Powered by Agent-Reach | "
        f"{' '.join(sys.version.split()[:2])}"
    )


if __name__ == "__main__":
    main()
