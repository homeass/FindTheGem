# -*- coding: utf-8 -*-
"""
Find the Gem - AI Research Platform
Agent-Reach 기반 자료 조사 플랫폼

Streamlit app for research with progressive progress bars
"""

import streamlit as st
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.parse

import sys
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config
st.set_page_config(
    page_title="Find the Gem - AI Research Platform",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .main-header h1 {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    .main-header p {
        font-size: 1.1rem;
        opacity: 0.9;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    .platform-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #667eea;
    }
    .result-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border: 1px solid #e9ecef;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #667eea;
    }
    .metric-label {
        color: #6c757d;
        font-size: 0.9rem;
    }
    .step-indicator {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        margin: 0.25rem;
    }
    .step-pending { background: #e9ecef; color: #6c757d; }
    .step-running { background: #fff3cd; color: #856404; }
    .step-completed { background: #d4edda; color: #155724; }
    .step-failed { background: #f8d7da; color: #721c24; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'research_history' not in st.session_state:
    st.session_state.research_history = []
if 'current_results' not in st.session_state:
    st.session_state.current_results = []
if 'pipeline_status' not in st.session_state:
    st.session_state.pipeline_status = {}


class ResearchPipeline:
    """Research pipeline with progress tracking"""
    
    def __init__(self):
        self.steps = []
        self.current_step = 0
        self.total_steps = 0
        
    def add_step(self, name: str, platform: str):
        self.steps.append({
            'name': name,
            'platform': platform,
            'status': 'pending',
            'result': None,
            'start_time': None,
            'end_time': None,
            'error': None
        })
        self.total_steps = len(self.steps)
        
    def start_step(self, index: int):
        if index < len(self.steps):
            self.steps[index]['status'] = 'running'
            self.steps[index]['start_time'] = time.time()
            self.current_step = index
            
    def complete_step(self, index: int, result: Any = None):
        if index < len(self.steps):
            self.steps[index]['status'] = 'completed'
            self.steps[index]['result'] = result
            self.steps[index]['end_time'] = time.time()
            
    def fail_step(self, index: int, error: str = None):
        if index < len(self.steps):
            self.steps[index]['status'] = 'failed'
            self.steps[index]['error'] = error
            self.steps[index]['end_time'] = time.time()
    
    def get_duration(self, index: int) -> float:
        if index < len(self.steps):
            step = self.steps[index]
            if step['start_time'] and step['end_time']:
                return step['end_time'] - step['start_time']
        return 0


def search_youtube_ytdlp(query: str, max_results: int = 5) -> List[Dict]:
    try:
        cmd = [
            "yt-dlp",
            f"ytsearch{max_results}:{query}",
            "--flat-playlist",
            "--dump-json",
            "--no-download"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        results = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)
                    results.append({
                        'title': data.get('title', 'Untitled'),
                        'url': data.get('url', data.get('webpage_url', '')),
                        'snippet': data.get('description', '')[:200],
                        'platform': 'YouTube',
                        'duration': data.get('duration_string', ''),
                        'view_count': data.get('view_count', 0),
                        'uploader': data.get('uploader', 'Unknown')
                    })
                except json.JSONDecodeError:
                    continue
        
        return results
    except Exception as e:
        st.error(f"YouTube search error: {e}")
        return []


def search_jina_reader(url: str) -> str:
    try:
        jina_url = f"https://r.jina.ai/{url}"
        req = urllib.request.Request(
            jina_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/plain"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')
            return content[:2000]
    except Exception as e:
        return f"Error reading page: {e}"


def search_web_google(query: str, num_results: int = 5) -> List[Dict]:
    results = []
    
    try:
        search_url = f"https://s.jina.ai/{urllib.parse.quote(query)}"
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
            if 'results' in data:
                for item in data['results'][:num_results]:
                    results.append({
                        'title': item.get('title', 'Untitled'),
                        'url': item.get('url', ''),
                        'snippet': item.get('snippet', item.get('content', ''))[:200],
                        'platform': 'Web'
                    })
    except Exception as e:
        st.warning(f"Web search limited: {e}")
    
    return results


def search_rss_feeds(feeds: List[str]) -> List[Dict]:
    results = []
    try:
        import feedparser
    except ImportError:
        st.error("feedparser not installed. Run: pip install feedparser")
        return results
    
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                results.append({
                    'title': entry.get('title', 'Untitled'),
                    'url': entry.get('link', ''),
                    'snippet': entry.get('summary', '')[:200],
                    'platform': 'RSS',
                    'feed_name': feed.feed.get('title', feed_url)
                })
        except Exception as e:
            st.warning(f"RSS error for {feed_url}: {e}")
    
    return results


def run_research_pipeline(
    query: str,
    platforms: List[str],
    rss_feeds: List[str] = None
) -> tuple[List[Dict], ResearchPipeline]:
    """Execute research pipeline with progress tracking"""
    
    pipeline = ResearchPipeline()
    
    # Add steps based on selected platforms
    if "📺 YouTube" in platforms:
        pipeline.add_step("YouTube Search", "youtube")
    if "🌐 Web Search" in platforms:
        pipeline.add_step("Web Search", "web")
    if "📡 RSS Feeds" in platforms and rss_feeds:
        pipeline.add_step("RSS Feed Parsing", "rss")
    
    all_results = []
    
    for i, step in enumerate(pipeline.steps):
        pipeline.start_step(i)
        
        try:
            if step['platform'] == 'youtube':
                results = search_youtube_ytdlp(query, max_results=5)
                all_results.extend(results)
                pipeline.complete_step(i, results)
                
            elif step['platform'] == 'web':
                results = search_web_google(query, num_results=5)
                all_results.extend(results)
                pipeline.complete_step(i, results)
                
            elif step['platform'] == 'rss' and rss_feeds:
                results = search_rss_feeds(rss_feeds)
                all_results.extend(results)
                pipeline.complete_step(i, results)
                
        except Exception as e:
            pipeline.fail_step(i, str(e))
        
        time.sleep(0.3)
    
    return all_results, pipeline


def format_results_markdown(results: List[Dict], query: str) -> str:
    """Format results as downloadable markdown"""
    
    md = f"# 💎 Find the Gem Research Report\n\n"
    md += f"**Query:** {query}\n\n"
    md += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += f"**Total Results:** {len(results)}\n\n"
    md += "---\n\n"
    
    platforms = {}
    for r in results:
        platform = r.get('platform', 'Unknown')
        if platform not in platforms:
            platforms[platform] = []
        platforms[platform].append(r)
    
    for platform, platform_results in platforms.items():
        md += f"## {platform}\n\n"
        for i, result in enumerate(platform_results, 1):
            title = result.get('title', 'Untitled')
            url = result.get('url', '')
            snippet = result.get('snippet', result.get('content', 'No content'))
            
            md += f"### {i}. {title}\n\n"
            if url:
                md += f"**URL:** [{url}]({url})\n\n"
            md += f"{snippet}\n\n"
            md += "---\n\n"
    
    return md


def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>💎 Find the Gem</h1>
        <p>AI-Powered Research Platform | Powered by Agent-Reach</p>
        <p style="font-size: 0.9rem; margin-top: 0.5rem;">
            Search YouTube, Web, and RSS feeds with progressive progress tracking
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Research Settings")
        
        st.subheader("🔍 Platforms")
        platforms = st.multiselect(
            "Select platforms to search:",
            ["📺 YouTube", "🌐 Web Search", "📡 RSS Feeds"],
            default=["📺 YouTube", "🌐 Web Search"]
        )
        
        st.subheader("📡 RSS Feeds")
        default_feeds = "https://news.ycombinator.com/rss\nhttps://www.reddit.com/r/technology/.rss"
        rss_feeds_text = st.text_area(
            "RSS Feed URLs (one per line):",
            value=default_feeds,
            height=100
        )
        rss_feeds = [f.strip() for f in rss_feeds_text.split('\n') if f.strip()]
        
        st.subheader("📊 History")
        if st.session_state.research_history:
            for i, research in enumerate(reversed(st.session_state.research_history[-5:])):
                query_preview = research['query'][:40] + "..." if len(research['query']) > 40 else research['query']
                if st.button(f"📋 {query_preview}", key=f"history_{i}", use_container_width=True):
                    st.session_state.current_results = research['results']
                    st.rerun()
        else:
            st.info("No research history yet")
    
    # Main content
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("🔍 Research Query")
        with st.form("research_form", enter_to_submit=True):
            query = st.text_input(
                "Enter your research question:",
                placeholder="例: What are the latest developments in AI agents?",
            )
            submitted = st.form_submit_button("🚀 Start Research", type="primary", use_container_width=True)

        if submitted:
            if not query:
                st.error("Please enter a research question")
                return

            progress_container = st.container()
            status_container = st.container()

            with progress_container:
                progress_bar = st.progress(0)
                status_text = st.empty()

            with st.spinner("Researching across platforms..."):
                results, pipeline = run_research_pipeline(
                    query, platforms, rss_feeds
                )

                for i, step in enumerate(pipeline.steps):
                    progress = (i + 1) / len(pipeline.steps)
                    progress_bar.progress(progress)
                    status_text.text(f"✅ {step['name']} complete!" if step['status'] == 'completed' else f"❌ {step['name']} failed")
                    time.sleep(0.2)

            st.session_state.current_results = results
            st.session_state.pipeline_status = {
                'steps': pipeline.steps,
                'total_results': len(results),
                'query': query
            }
            st.session_state.research_history.append({
                'query': query,
                'results': results,
                'timestamp': datetime.now().isoformat()
            })

            st.success(f"✨ Research complete! Found {len(results)} results.")
    
    with col2:
        st.subheader("📈 Results Summary")
        if st.session_state.current_results:
            results = st.session_state.current_results
            
            # Platform breakdown
            platform_counts = {}
            for r in results:
                platform = r.get('platform', 'Unknown')
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            for platform, count in platform_counts.items():
                st.metric(label=platform, value=count)
            
            st.metric(label="📊 Total Results", value=len(results))
        else:
            st.info("Start a research query to see results!")
    
    if st.session_state.pipeline_status:
        st.header("📊 Pipeline Status")
        steps = st.session_state.pipeline_status.get('steps', [])
        
        cols = st.columns(len(steps) if steps else 1)
        for i, step in enumerate(steps):
            with cols[i] if i < len(cols) else cols[0]:
                status_icon = "✅" if step['status'] == 'completed' else "❌" if step['status'] == 'failed' else "⏳"
                st.metric(
                    label=f"{status_icon} {step['name']}",
                    value=step['status'].upper()
                )
    
    if st.session_state.current_results:
        st.header("🎯 Research Results")

        results = st.session_state.current_results

        for i, result in enumerate(results, 1):
            with st.expander(f"{i}. {result.get('title', 'Untitled')}", expanded=False):
                st.write(f"**Platform:** {result.get('platform', 'Unknown')}")
                if result.get('url'):
                    st.write(f"**URL:** [{result['url'][:60]}...]({result['url']})")
                if result.get('duration'):
                    st.write(f"**Duration:** {result['duration']}")
                if result.get('view_count'):
                    st.write(f"**Views:** {result['view_count']:,}")
                st.write(result.get('snippet', result.get('content', 'No content')))

        st.divider()

        st.subheader("📥 Download Results")
        md_content = format_results_markdown(results, st.session_state.pipeline_status.get('query', ''))
        json_content = json.dumps(results, indent=2, ensure_ascii=False)
        txt_content = "\n\n".join([
            f"Title: {r.get('title', 'Untitled')}\n"
            f"URL: {r.get('url', 'N/A')}\n"
            f"Platform: {r.get('platform', 'Unknown')}\n"
            f"Content: {r.get('content', r.get('snippet', 'N/A'))}\n"
            for r in results
        ])
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                label="📄 Markdown",
                data=md_content,
                file_name=f"research_{ts}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with dl2:
            st.download_button(
                label="📊 JSON",
                data=json_content,
                file_name=f"research_{ts}.json",
                mime="application/json",
                use_container_width=True
            )
        with dl3:
            st.download_button(
                label="📝 Text",
                data=txt_content,
                file_name=f"research_{ts}.txt",
                mime="text/plain",
                use_container_width=True
            )
    
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #6c757d; padding: 1rem;">
        <p>💎 Find the Gem | Powered by <a href="https://github.com/Panniantong/Agent-Reach">Agent-Reach</a></p>
        <p style="font-size: 0.8rem;">AI-Powered Research Platform</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
