# FindTheGem v0.1-beta.3 - 설치 및 사용 가이드

## 📋 개요

FindTheGem은 Agent-Reach 오픈소스를 기반으로 한 AI 자료 조사 플랫폼입니다.
질문을 입력하면 웹 검색과 RAG를 통해 답변을 생성하고 다운로드할 수 있습니다.

**버전:** 0.1-beta.3  
**날짜:** 2026-07-17  
**플랫폼:** Android (Termux), Web

---

## 🚀 빠른 시작

### 1. 사전 요구사항

- **Android:** Termux 앱 설치 (F-Droid에서 다운로드)
- **Python:** 3.10 이상
- **메모리:** 최소 2GB RAM 권장
- **저장 공간:** 최소 1GB 여유 공간

### 2. 설치 방법

#### Termux에서 직접 설치

```bash
# 1. 저장소 접근 권한 설정
termux-setup-storage

# 2. 패키지 업데이트
pkg update && pkg upgrade

# 3. Python 설치
pkg install python

# 4. pip 업그레이드
pip install --upgrade pip

# 5. Agent-Reach 클론 및 설치
cd ~/work
git clone https://github.com/homeass/Agent-Reach.git
cd Agent-Reach
pip install -e .

# 6. FindTheGem 프로젝트 클론
cd ~/work
git clone https://github.com/homeass/FindTheGem.git
cd FindTheGem

# 7. 의존성 설치
pip install streamlit httpx rank-bm25

# 8. 앱 실행
streamlit run findthegem_app.py --server.port 8501
```

### 3. 앱 실행

```bash
# 앱 실행
streamlit run findthegem_app.py --server.port 8501

# 백그라운드 실행 (선택사항)
nohup streamlit run findthegem_app.py --server.port 8501 > findthegem.log 2>&1 &
```

실행 후 브라우저에서 `http://localhost:8501`로 접속하세요.

---

## 📱 Android 앱 설정

### Termux 바로가기 생성

1. Termux에서 다음 명령어 실행:
```bash
# 바로가기 스크립트 생성
cat > ~/.shortcuts/findthegem.sh << 'EOF'
#!/bin/bash
cd ~/work/FindTheGem
streamlit run findthegem_app.py --server.port 8501 --server.headless true
EOF

# 실행 권한 부여
chmod +x ~/.shortcuts/findthegem.sh
```

2. Termux 위젯 설치 (F-Droid)
3. 홈 화면에 Termux 위젯 추가
4. 위젯을 탭하여 FindTheGem 실행

### 브라우저 바로가기 설정

1. Chrome 브라우저 열기
2. `http://localhost:8501` 접속
3. 메뉴 → "홈 화면에 추가" 선택
4. 이름: "FindTheGem" 입력

---

## 🔧 설정 및 구성

### Agent-Reach 채널 설정

FindTheGem은 Agent-Reach의 다음 채널을 지원합니다:

| 채널 | 설명 | 설정 필요 |
|------|------|-----------|
| web | 웹페이지 검색 | ❌ 불필요 |
| youtube | YouTube 검색 | ❌ 불필요 |
| github | GitHub 저장소 검색 | ❌ 불필요 |
| rss | RSS 피드 검색 | ❌ 불필요 |
| twitter | Twitter/X 검색 | ✅ 쿠키 필요 |
| reddit | Reddit 검색 | ✅ 로그인 필요 |

### RAG 설정 (선택사항)

로컬 Obsidian Vault가 있다면 RAG 검색을 활성화할 수 있습니다:

```bash
# 설정 파일 생성
mkdir -p ~/.proteusp
cat > ~/.proteusp/config.json << 'EOF'
{
  "vault_path": "/storage/emulated/0/Obsidian/Vault",
  "llm_model": "timHan/llama3.2korean3B",
  "embedding_model": "BAAI/bge-m3"
}
EOF
```

---

## 🎯 사용법

### 기본 검색

1. 메인 페이지의 검색창에 질문 입력
2. "검색" 버튼 클릭
3. 프로그레시브 프로그레스바로 진행 상황 확인
4. 검색 결과 확인 및 다운로드

### 검색 옵션

- **검색 채널:** 웹, YouTube, GitHub, RSS 중 선택
- **RAG 검색:** 로컬 문서 기반 검색 활성화
- **검색 결과 수:** 1-20개 조정

### 다운로드 형식

- **마크다운 (.md):** 서식이 포함된 문서
- **텍스트 (.txt):** 일반 텍스트 형식

---

## 🐛 문제 해결

### 흔한 오류 및 해결법

| 오류 | 원인 | 해결법 |
|------|------|--------|
| `ModuleNotFoundError: No module named 'streamlit'` | Streamlit 미설치 | `pip install streamlit` |
| `ConnectionRefused` | 서버 미실행 | `streamlit run findthegem_app.py` |
| `MemoryError` | 메모리 부족 | 다른 앱 종료 후 재시도 |
| `Permission denied` | 저장소 권한 미부여 | `termux-setup-storage` |

### 로그 확인

```bash
# 앱 로그 확인
tail -f findthegem.log

# Agent-Reach 상태 확인
agent-reach doctor
```

---

## 🔄 업데이트

```bash
# FindTheGem 업데이트
cd ~/work/FindTheGem
git pull origin main

# Agent-Reach 업데이트
cd ~/work/Agent-Reach
git pull origin main
pip install -e .
```

---

## 📞 지원

- **GitHub:** https://github.com/homeass/FindTheGem
- **Issues:** https://github.com/homeass/FindTheGem/issues

---

## 📄 라이선스

MIT License

---

*FindTheGem v0.1-beta.3 | Generated: 2026-07-17*
