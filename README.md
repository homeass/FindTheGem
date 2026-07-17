# 💎 Find the Gem

AI-Powered Research Platform — YouTube, Web, RSS를 하나의 검색으로 통합 조사

<p align="center">
  <img src="docs/icon.png" width="120" alt="Find the Gem Icon">
</p>

<p align="center">
  <a href="https://github.com/homeass/FindTheGem/releases/latest"><img src="https://img.shields.io/github/v/release/homeass/FindTheGem?style=for-badge&label=Beta" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-badge" alt="MIT License"></a>
  <a href="#"><img src="https://img.shields.io/badge/Platform-Mac%20%7C%20Android-green.svg?style=for-badge" alt="Platform"></a>
</p>

---

## 이 앱은 무엇인가?

**Find the Gem**은 AI 에이전트가 YouTube, 웹 검색, RSS 피드를 동시에 조사하고 결과를 정리해주는 리서치 플랫폼입니다.

- 🔍 하나의 검색어로 **YouTube + 웹 + RSS** 동시 검색
- 📊 플랫폼별 결과 분류 및 통계
- 📥 결과를 **Markdown / JSON / Text**로 다운로드
- 🤖 Agent-Reach 기반 — 13개 인터넷 플랫폼 확장 가능

### 지원 플랫폼

| 플랫폼 | 기능 | 설정 |
|--------|------|------|
| 📺 YouTube | 영상 검색 + 메타데이터 | 불필요 |
| 🌐 Web | Jina Search API 기반 웹 검색 | 불필요 |
| 📡 RSS | RSS/Atom 피드 파싱 | 불필요 |

---

## 📥 다운로드

### Mac (macOS)

> Apple Silicon (M1/M2/M3/M4) 및 Intel Mac 모두 지원

1. **[최신 릴리스 페이지](https://github.com/homeass/FindTheGem/releases)** 접속
2. `FindTheGem-darwin-arm64.zip` (Apple Silicon) 또는 `FindTheGem-darwin-x64.zip` (Intel) 다운로드
3. 압축 해제 → `FindTheGem.app`을 Applications 폴더로 드래그
4. 첫 실행 시: **마우스 오른쪽 클릭 → 열기** (macOS 보안 경고 우회)

> ⚠️ macOS가 "확인되지 않은 개발자" 경고가 뜨면:
> ```bash
> xattr -cr /Applications/FindTheGem.app
> ```

### Android

> Android 8.0 (API 26) 이상, 약 100MB 여유 공간 필요

1. **[최신 릴리스 페이지](https://github.com/homeass/FindTheGem/releases)** 접속
2. `FindTheGem.apk` 다운로드
3. APK 파일 열기 → **"이 소스에서 설치 허용"** 활성화
4. 설치 완료 후 앱 열기

#### ⚡ 첫 실행 설정 (Android)

Android 버전은 Termux를 사용하여 로컬에서 Streamlit 서버를 실행합니다. **최초 1회만** 아래 설정이 필요합니다:

1. 앱을 열면 **"Setup Instructions"** 화면이 표시됩니다
2. **Termux 앱을 열기** 버튼을 눌러 Termux를 실행합니다
3. Termux에서 아래 명령어를 **복사하여 붙여넣기** 합니다:

```bash
bash /storage/emulated/0/Documents/FindTheGem/bootstrap.sh
```

4. "Installation complete!" 메시지가 뜨면 앱으로 돌아가기
5. 서버가 자동으로 시작되고 리서치 화면으로 전환됩니다

> 💡 이후 실행부터는 앱이 자동으로 서버를 시작하므로 추가 설정 불필요

#### 📋 Android 설정 요약

```
최초 실행
  ├── Termux 열기
  ├── bootstrap.sh 실행 (1회)
  └── 앱으로 돌아가기 → 자동 서버 시작
  
이후 실행
  └── 앱 열기 → 자동으로 서버 시작 → 바로 리서치
```

---

## 🚀 사용법

### 검색

1. 플랫폼 선택 (기본: YouTube + Web)
2. 검색어 입력
3. **Start Research** 클릭 또는 **엔터** 키 누르기
4. 진행률 표시와 함께 결과가 실시간으로 표시됨

### 결과 다운로드

검색 왼쪽 하단에 다운로드 버튼이 표시됩니다:
- 📄 **Markdown** — 리서치 보고서 형식
- 📊 **JSON** — 구조화된 데이터
- 📝 **Text** — 일반 텍스트

### RSS 피드 설정

사이드바에서 RSS 피드 URL을 추가할 수 있습니다 (기본값 포함):
```
https://news.ycombinator.com/rss
https://www.reddit.com/r/technology/.rss
```

---

## 🔧 소스 코드 빌드

### Mac (Electron)

```bash
cd mac/findthegem-electron
npm install
npm start          # 개발 모드
npm run make       # 빌드 (.app 생성)
```

### Android

```bash
cd android/findthegem-android
./gradlew assembleDebug    # 디버그 APK 빌드
```

빌드 결과물:
- Mac: `mac/findthegem-electron/out/` 디렉토리
- Android: `android/findthegem-android/app/build/outputs/apk/debug/app-debug.apk`

---

## 📁 프로젝트 구조

```
FindTheGem/
├── README.md
├── LICENSE
├── mac/
│   └── findthegem-electron/    # macOS Electron 앱
│       ├── main.js
│       ├── preload.js
│       ├── package.json
│       └── assets/
├── android/
│   ├── FindTheGem.apk          # 배포용 APK
│   └── findthegem-android/     # Android 소스
│       ├── app/src/main/
│       │   ├── java/.../
│       │   │   ├── MainActivity.java
│       │   │   ├── SplashActivity.java
│       │   │   ├── SettingsActivity.java
│       │   │   └── TermuxManager.java
│       │   ├── assets/findthegem/
│       │   │   ├── findthegem_app.py   # Streamlit 메인 앱
│       │   │   ├── setup.sh
│       │   │   ├── start_server.sh
│       │   │   ├── stop_server.sh
│       │   │   └── requirements.txt
│       │   └── AndroidManifest.xml
│       └── build.gradle
└── docs/
```

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────┐
│           Find the Gem UI               │
│  ┌──────────┐  ┌──────────┐             │
│  │   Mac    │  │ Android  │             │
│  │ Electron │  │ WebView  │             │
│  └────┬─────┘  └────┬─────┘             │
│       │              │                   │
│       ▼              ▼                   │
│  ┌─────────────────────────┐            │
│  │   Streamlit Server      │            │
│  │   (localhost:8501)      │            │
│  └───────────┬─────────────┘            │
│              │                           │
│       ┌──────┼──────┐                   │
│       ▼      ▼      ▼                   │
│   ┌──────┐┌──────┐┌──────┐             │
│   │YouTube││ Web  ││ RSS  │             │
│   │yt-dlp ││ Jina ││feed- │             │
│   │       ││Reader││parser│             │
│   └──────┘└──────┘└──────┘             │
└─────────────────────────────────────────┘
```

### 핵심 컴포넌트

| 컴포넌트 | 역할 | 기술 스택 |
|----------|------|----------|
| **Streamlit App** | UI + 리서치 파이프라인 | Python, Streamlit |
| **Mac App** | 네이티브 래퍼 | Electron, Node.js |
| **Android App** | 네이티브 래퍼 + Termux 서버 | Kotlin, Android WebView |
| **YouTube 검색** | yt-dlp 기반 | yt-dlp CLI |
| **웹 검색** | Jina Search API | HTTP API (무료) |
| **RSS 파싱** | feedparser | Python feedparser |

---

## ❓ 자주 묻는 질문

### Q: 서버가 시작되지 않아요 (Android)
**A:** Termux에서 bootstrap.sh를 실행했는지 확인하세요:
```bash
bash /storage/emulated/0/Documents/FindTheGem/bootstrap.sh
```

### Q: "확인되지 않은 개발자" 경고가 뜹니다 (Mac)
**A:** 터미널에서 실행:
```bash
xattr -cr /Applications/FindTheGem.app
```

### Q: 검색 결과가 없어요
**A:** 인터넷 연결을 확인하세요. Jina Search API는 무료이지만 인터넷 연결이 필요합니다.

### Q: APK 설치가 차단됩니다 (Android)
**A:** 설정 → 보안 → "출처 불명 앱 허용"에서 해당 브라우저/파일 매니저를 허용하세요.

---

## 📄 라이선스

MIT License - 상업적 사용, 수정, 배포 자유롭게 가능

## 🤝 기여

버그 리포트나 기능 요청은 [Issues](https://github.com/homeass/FindTheGem/issues)에 등록해주세요.

## 🙏 감사

- [Agent-Reach](https://github.com/Panniantong/Agent-Reach) — 13개 플랫폼 접근성 레이어
- [Streamlit](https://streamlit.io) — 빠른 프로토타이핑
- [Electron](https://www.electronjs.org) — 크로스 플랫폼 데스크톱
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube 데이터 추출
- [Jina AI](https://jina.ai) — 웹 검색 API
- [Termux](https://termux.dev) — Android 터미널 에뮬레이터
