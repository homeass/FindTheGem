"""
ProteusP Streamlit GUI
태블릿에서 실행되는 RAG 파이프라인 모니터링 및 제어 인터페이스
"""

import json
import os
import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# Ensure proteusp package is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from proteusp.config import ProteusPConfig, get_config
from proteusp.pipeline import ProteusPPipeline, get_pipeline, reset_pipeline
from proteusp.telegram_bridge import (
    get_config_status,
    load_telegram_config,
    save_telegram_config,
    send_file_via_telegram,
    send_telegram_message,
    validate_bot_token,
)
from proteusp.generate_docs import generate_docs

# ──────────── Page Config ────────────
st.set_page_config(
    page_title="ProteusP Tablet Edition",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────── Session State ────────────
if "pipeline" not in st.session_state:
    st.session_state.pipeline = get_pipeline()
if "index_result" not in st.session_state:
    st.session_state.index_result = None
if "search_result" not in st.session_state:
    st.session_state.search_result = None
if "query_result" not in st.session_state:
    st.session_state.query_result = None
if "progress_messages" not in st.session_state:
    st.session_state.progress_messages = []
if "watching" not in st.session_state:
    st.session_state.watching = False
if "ollama_status" not in st.session_state:
    st.session_state.ollama_status = None
if "telegram_setup_done" not in st.session_state:
    # Check if telegram is already configured
    tg = load_telegram_config()
    st.session_state.telegram_setup_done = tg is not None
if "docs_path" not in st.session_state:
    st.session_state.docs_path = None

# ──────────── Callbacks ────────────
def progress_callback(message: str, progress: float = 0):
    """Callback for pipeline progress updates."""
    st.session_state.progress_messages.append((message, progress, time.time()))

def run_index(full_rebuild: bool = False):
    """Run indexing in a background thread."""
    pipeline = st.session_state.pipeline
    pipeline.set_progress_callback(progress_callback)
    
    with st.spinner("📂 인덱싱 진행 중..."):
        result = pipeline.index_vault(full_rebuild=full_rebuild)
        st.session_state.index_result = result
    
    # Check Ollama after indexing
    st.session_state.ollama_status = pipeline.llm.check_availability()
    st.rerun()

# ──────────── Sidebar ────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/brain.png", width=64)
    st.markdown("## ProteusP")
    st.caption("Tablet Edition v1.0.0")
    st.divider()
    
    # Quick status
    pipeline = st.session_state.pipeline
    status = pipeline.get_status()
    
    st.markdown("### 시스템 상태")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("문서", status["status"]["documents"])
    with col2:
        st.metric("청크", status["status"]["chunks"])
    
    st.metric("벡터", status["status"]["vectors"])
    
    # Ollama status indicator
    ollama_ok = status.get("ollama", {}).get("available", False)
    if ollama_ok:
        st.success(f"🤖 Ollama: 연결됨")
    else:
        st.warning("🤖 Ollama: 연결 안됨")
    
    # Telegram status
    tg_status = get_config_status()
    if tg_status.get("configured"):
        st.info(f"📨 텔레그램: 설정됨")
    else:
        st.info("📨 텔레그램: 설정 필요")
    
    st.divider()
    
    # Navigation
    st.markdown("### 메뉴")
    page = st.radio(
        "페이지 선택",
        ["🏠 대시보드", "🔍 검색", "⚙️ 설정", "📡 파일 감시", "📨 텔레그램"],
        label_visibility="collapsed",
    )
    
    st.divider()
    st.caption("Lenovo Legion Y705 | Termux-Ubuntu")

# ──────────── Main Content ────────────

# ─── TELEGRAM SETUP MODAL (first run) ───
if not st.session_state.telegram_setup_done:
    with st.container():
        st.markdown("## 📨 텔레그램 봇 설정")
        st.markdown(
            "ProteusP가 인덱싱 완료 알림과 문서(DOCX 가이드)를 전송할 "
            "텔레그램 봇을 설정합니다."
        )
        st.divider()
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("### BotFather에서 봇 생성하기")
            st.markdown(
                "1. Telegram에서 [@BotFather](https://t.me/BotFather)를 찾으세요.\n"
                "2. `/newbot` 명령으로 새 봇을 만드세요.\n"
                "3. 봇 이름과 사용자명을 입력하세요.\n"
                "4. 발급된 HTTP API 토큰을 아래에 붙여넣으세요.\n\n"
                "예시 토큰: `1234567890:ABCdefGHIjklmNOPqrSTUvwxYZ`"
            )
        
        with col2:
            bot_token = st.text_input(
                "봇 토큰 (Bot Token)",
                type="password",
                placeholder="1234567890:ABCdefGHIjklmNOPqrSTUvwxYZ",
                help="BotFather에서 받은 HTTP API 토큰을 입력하세요",
            )
            
            chat_id = st.text_input(
                "채팅 ID (선택)",
                placeholder="예: 123456789",
                help="비워두면 첫 메시지 전송 후 자동 감지됩니다. "
                     "봇과의 채팅방에서 /start를 먼저 보내세요.",
            )
            
            if st.button("✅ 토큰 확인 및 저장", type="primary", use_container_width=True):
                if not bot_token:
                    st.error("봇 토큰을 입력하세요.")
                else:
                    is_valid, msg = validate_bot_token(bot_token)
                    if is_valid:
                        cids = []
                        if chat_id:
                            try:
                                cids.append(int(chat_id))
                            except ValueError:
                                st.error("채팅 ID는 숫자여야 합니다.")
                        
                        success = save_telegram_config(bot_token, cids)
                        if success:
                            st.success(f"✅ 설정 완료! {msg}")
                            st.session_state.telegram_setup_done = True
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("설정 파일 저장에 실패했습니다.")
                    else:
                        st.error(f"토큰 확인 실패: {msg}")
        
        st.divider()
        st.markdown("### ⏭️ 나중에 설정하기")
        if st.button("나중에 설정", use_container_width=True):
            st.session_state.telegram_setup_done = True
            st.rerun()

# ─── MAIN INTERFACE ───
elif page == "🏠 대시보드":
    st.markdown("# 🧠 ProteusP 대시보드")
    st.markdown("### Obsidian RAG Pipeline — Tablet Edition")
    st.divider()
    
    # Status cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "📄 문서 수",
            status["status"]["documents"],
            help="Obsidian Vault에서 파싱된 마크다운 문서 수",
        )
    with col2:
        st.metric(
            "🧩 청크 수",
            status["status"]["chunks"],
            help="분할된 텍스트 청크 수",
        )
    with col3:
        st.metric(
            "📊 벡터 수",
            status["status"]["vectors"],
            help="벡터 DB에 저장된 임베딩 수",
        )
    with col4:
        last_idx = status["status"]["last_index"]
        st.metric(
            "⏱️ 마지막 인덱싱",
            last_idx,
            help="마지막 전체 인덱싱 시간",
        )
    
    st.divider()
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 인덱싱 시작", type="primary", use_container_width=True):
            run_index(full_rebuild=False)
    with col2:
        if st.button("🔄 전체 재구축", use_container_width=True):
            run_index(full_rebuild=True)
    
    # Show index result
    if st.session_state.index_result:
        result = st.session_state.index_result
        if result.get("status") == "success":
            st.success(
                f"✅ 인덱싱 완료! "
                f"{result['documents']}개 문서 → {result['chunks']}개 청크 → "
                f"{result['upserted']}개 벡터 저장 "
                f"({result['time_seconds']}초)"
            )
        elif result.get("status") == "error":
            st.error(f"❌ 인덱싱 실패: {result.get('message', '알 수 없는 오류')}")
    
    # Recent messages
    st.divider()
    st.markdown("### 📋 최근 활동")
    messages = pipeline.status.messages[-10:] if pipeline.status.messages else ["아직 활동이 없습니다."]
    for msg in reversed(messages):
        st.caption(msg)
    
    # Pipeline errors (if any)
    if pipeline.status.errors:
        st.divider()
        st.markdown("### ⚠️ 오류 내역")
        for err in pipeline.status.errors[-3:]:
            st.error(err)

elif page == "🔍 검색":
    st.markdown("# 🔍 Obsidian 검색")
    st.markdown("### 하이브리드 검색 (BM25 + Vector) + RAG")
    st.divider()
    
    # Search options
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        query = st.text_input(
            "질문을 입력하세요",
            placeholder="예: 프로젝트 일정이 어떻게 되나요?",
            label_visibility="collapsed",
        )
    with col2:
        top_k = st.number_input("검색 결과 수", min_value=1, max_value=20, value=5)
    with col3:
        use_rerank = st.checkbox("Rerank 사용", value=True)
    
    # Search button
    search_clicked = st.button("🔍 검색", type="primary", use_container_width=True)
    
    if search_clicked and query:
        with st.spinner("검색 중..."):
            # Check vector DB has data
            if pipeline.vector_store.count() == 0:
                st.warning("⚠️ 벡터 DB가 비어 있습니다. 먼저 인덱싱을 실행하세요.")
            else:
                # Ensure BM25 is built
                if not pipeline.searcher.bm25_ready:
                    with st.spinner("BM25 인덱스 구축 중..."):
                        pipeline.searcher.build_bm25_index()
                
                # Execute search
                search_result = pipeline.search(query, top_k=top_k, rerank=use_rerank)
                st.session_state.search_result = search_result
                
                # Execute RAG query
                with st.spinner("🤖 LLM 응답 생성 중..."):
                    query_result = pipeline.query(query, top_k=top_k)
                    st.session_state.query_result = query_result
                
                st.rerun()
    
    # Display results
    if st.session_state.query_result:
        qr = st.session_state.query_result
        
        # LLM Answer
        st.divider()
        st.markdown("### 🤖 답변")
        
        response = qr.get("response", "응답을 생성할 수 없습니다.")
        st.markdown(response)
        
        # Source info
        sources = qr.get("sources", [])
        if sources:
            st.divider()
            st.markdown("### 📚 참고 출처")
            for src in sources:
                file_info = src.get("file_name", "알 수 없음")
                header_info = src.get("header", "")
                excerpt = src.get("excerpt", "")[:100]
                
                with st.expander(f"📄 {file_info}" + (f" > {header_info[:40]}" if header_info else "")):
                    st.caption(f"출처: {src.get('source', '')}")
                    st.text(excerpt)
        
        # Usage info
        usage = qr.get("usage", {})
        if usage:
            st.divider()
            st.caption(
                f"토큰: 입력 {usage.get('prompt_tokens', 0):,} | "
                f"출력 {usage.get('completion_tokens', 0):,} | "
                f"시간: {usage.get('time_seconds', 0):.1f}초"
            )
    
    # Search results (raw)
    if st.session_state.search_result:
        sr = st.session_state.search_result
        with st.expander("🔎 원본 검색 결과 보기"):
            st.caption(
                f"검색 시간: {sr.get('time', 0):.2f}초 | "
                f"벡터: {sr.get('vector_count', 0)}건 | "
                f"BM25: {sr.get('bm25_count', 0)}건"
            )
            for i, r in enumerate(sr.get("results", [])):
                st.markdown(f"**{i+1}. {r.get('id', 'N/A')}** (score: {r.get('score', 0):.3f})")
                st.caption(r.get("document", "")[:300])
                st.divider()

elif page == "⚙️ 설정":
    st.markdown("# ⚙️ 설정")
    st.markdown("### ProteusP 파이프라인 설정")
    st.divider()
    
    cfg = pipeline.config
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📂 Obsidian Vault")
        vault_path = st.text_input(
            "Vault 경로",
            value=cfg.vault_path,
            help="Obsidian Vault가 위치한 폴더 경로",
        )
        
        st.markdown("#### ✂️ 청킹 설정")
        chunk_size = st.number_input(
            "청크 크기 (문자 수)",
            min_value=64, max_value=2048, value=cfg.chunk_size,
        )
        chunk_overlap = st.number_input(
            "청크 중복 (문자 수)",
            min_value=0, max_value=512, value=cfg.chunk_overlap,
        )
    
    with col2:
        st.markdown("#### 🤖 Ollama")
        ollama_host = st.text_input(
            "Ollama 호스트",
            value=cfg.ollama_host,
            help="Ollama 서버 주소 (기본: http://localhost:11434)",
        )
        llm_model = st.text_input(
            "LLM 모델",
            value=cfg.llm_model,
            help="Ollama에 설치된 모델명",
        )
        
        st.markdown("#### 🧠 임베딩")
        embedding_model = st.text_input(
            "임베딩 모델",
            value=cfg.embedding_model,
            help="HuggingFace 임베딩 모델명",
        )
    
    # Apply settings
    if st.button("💾 설정 저장 및 적용", type="primary", use_container_width=True):
        cfg.vault_path = vault_path
        cfg.chunk_size = chunk_size
        cfg.chunk_overlap = chunk_overlap
        cfg.ollama_host = ollama_host
        cfg.llm_model = llm_model
        cfg.embedding_model = embedding_model
        cfg.save()
        
        # Reset pipeline so it picks up new config
        reset_pipeline()
        st.session_state.pipeline = get_pipeline()
        
        st.success("✅ 설정이 저장되었습니다. 변경된 설정을 적용하려면 인덱싱을 다시 실행하세요.")
        time.sleep(0.5)
        st.rerun()
    
    st.divider()
    
    # Available Ollama models
    st.markdown("#### 사용 가능한 Ollama 모델")
    if st.button("🔄 모델 목록 새로고침"):
        models = pipeline.llm.list_models()
        if models:
            for m in models:
                st.code(m)
        else:
            st.warning("Ollama 서버에 연결할 수 없거나 모델이 없습니다.")
    
    st.divider()
    
    # Config file location
    st.caption(f"설정 파일 위치: ~/.proteusp/config.json")

elif page == "📡 파일 감시":
    st.markdown("# 📡 파일 감시")
    st.markdown("### Obsidian Vault 실시간 동기화")
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Watchdog 파일 감시")
        st.markdown(
            "Obsidian Vault의 파일 변경을 실시간으로 감지하여 "
            "자동으로 벡터 DB를 업데이트합니다."
        )
        
        if not st.session_state.watching:
            if st.button("🔍 파일 감시 시작", type="primary", use_container_width=True):
                pipeline.start_watching()
                st.session_state.watching = True
                st.rerun()
        else:
            st.success("✅ 파일 감시 활성화됨")
            if st.button("⏹️ 파일 감시 중지", use_container_width=True):
                pipeline.stop_watching()
                st.session_state.watching = False
                st.rerun()
        
        st.info(
            f"감시 경로: {pipeline.config.vault_path}\n"
            f"지연 시간: {pipeline.config.vault_watch_debounce_seconds}초"
        )
    
    with col2:
        st.markdown("#### Git 동기화")
        st.markdown(
            "Obsidian Vault를 Git 저장소로 관리하여 원격과 동기화합니다."
        )
        
        git_enabled = st.checkbox("Git 동기화 사용", value=pipeline.config.git_enabled)
        if git_enabled:
            git_url = st.text_input(
                "Git 원격 URL",
                value=pipeline.config.git_remote_url,
                placeholder="https://github.com/user/vault.git",
            )
            git_branch = st.text_input("브랜치", value=pipeline.config.git_branch)
            git_interval = st.number_input(
                "동기화 주기 (분)",
                min_value=1, max_value=60, value=pipeline.config.git_poll_interval_minutes,
            )
            
            if st.button("🔄 Git 동기화 설정 저장"):
                pipeline.config.git_enabled = True
                pipeline.config.git_remote_url = git_url
                pipeline.config.git_branch = git_branch
                pipeline.config.git_poll_interval_minutes = git_interval
                pipeline.config.save()
                st.success("Git 설정이 저장되었습니다.")
    
    st.divider()
    
    # Manual sync button
    st.markdown("#### 수동 동기화")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📂 수동으로 Vault 다시 읽기", use_container_width=True):
            with st.spinner("Vault 스캔 중..."):
                from proteusp.parser import parse_vault
                docs = parse_vault(pipeline.config.vault_path)
                st.success(f"Vault에서 {len(docs)}개 문서를 찾았습니다.")

elif page == "📨 텔레그램":
    st.markdown("# 📨 텔레그램 설정")
    st.divider()
    
    tg_status = get_config_status()
    
    if tg_status.get("configured"):
        st.success("✅ 텔레그램 봇이 설정되어 있습니다.")
        st.markdown(f"**봇 토큰:** {tg_status['bot_token']}")
        st.markdown(f"**채팅 ID:** {tg_status['chat_ids']}")
        st.markdown(f"**설정 파일:** {tg_status['path']}")
        
        st.divider()
        
        # Test message
        test_msg = st.text_area(
            "테스트 메시지",
            value="🧪 ProteusP Tablet Edition 테스트 메시지입니다.",
        )
        if st.button("📤 테스트 메시지 전송", use_container_width=True):
            success, msg = send_telegram_message(test_msg)
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
        
        # Send docs
        st.divider()
        st.markdown("#### 📄 문서 전송")
        if st.button("📄 DOCX 가이드 생성 및 전송", type="primary", use_container_width=True):
            with st.spinner("문서 생성 중..."):
                docs_path = generate_docs()
                st.session_state.docs_path = docs_path
            st.success(f"✅ 문서 생성 완료: {docs_path}")
            
            with st.spinner("텔레그램으로 전송 중..."):
                success, msg = send_file_via_telegram(
                    docs_path,
                    caption="📘 ProteusP Tablet Edition — 설치 및 사용 가이드 v1.0.0",
                )
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
        
        st.divider()
        
        # Reset config
        st.markdown("#### 설정 초기화")
        if st.button("🗑️ 텔레그램 설정 초기화", type="secondary"):
            import os
            os.remove(str(Path.home() / ".codex" / "telegram-bridge.json"))
            st.session_state.telegram_setup_done = False
            st.success("설정이 초기화되었습니다.")
            time.sleep(1)
            st.rerun()
    
    else:
        st.info("텔레그램 봇이 설정되지 않았습니다.")
        st.markdown(
            "**BotFather에서 봇 생성 방법:**\n"
            "1. Telegram에서 @BotFather 검색\n"
            "2. `/newbot` 명령으로 새 봇 생성\n"
            "3. 봇 이름과 사용자명 설정\n"
            "4. 발급된 토큰을 아래에 입력"
        )
        
        bot_token = st.text_input(
            "봇 토큰",
            type="password",
            placeholder="1234567890:ABCdefGHIjklmNOPqrSTUvwxYZ",
        )
        chat_id_input = st.text_input(
            "채팅 ID (선택)",
            placeholder="예: 123456789",
            help="비워두면 /start 후 자동 감지",
        )
        
        if st.button("💾 저장", type="primary"):
            if not bot_token:
                st.error("봇 토큰을 입력하세요.")
            else:
                is_valid, msg = validate_bot_token(bot_token)
                if is_valid:
                    cids = []
                    if chat_id_input:
                        try:
                            cids.append(int(chat_id_input))
                        except ValueError:
                            st.error("채팅 ID는 숫자여야 합니다.")
                    success = save_telegram_config(bot_token, cids)
                    if success:
                        st.success(f"✅ 저장 완료! {msg}")
                        st.session_state.telegram_setup_done = True
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error(msg)

# ──────────── Footer ────────────
st.divider()
st.caption(
    "ProteusP Tablet Edition v1.0.0 | "
    "Lenovo Legion Y705 | "
    "Termux-Ubuntu | "
    f"Python {sys.version.split()[0]}"
)
