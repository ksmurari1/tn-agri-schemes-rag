from __future__ import annotations

import hashlib
import html
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion import ingest_uploaded_file, ingest_url, source_rows, init_registry
from src.qa import answer_question
from src.voice import transcribe_audio
from guardrails import check_question
from src.source_catalogue import GOS_URL, fetch_gos_catalogue, load_catalogue, save_catalogue

load_dotenv(ROOT / ".env")
st.set_page_config(
    page_title="வயல்வழி AI | Agriculture Guide", page_icon="🌾", layout="wide",
    initial_sidebar_state="auto",
)

# Deployment fix: if the key exists only in Streamlit secrets, expose it to guardrails.py / qa.py / voice.py,
# which read the OPENAI_API_KEY environment variable. No effect when the key is already in .env.
if not os.getenv("OPENAI_API_KEY"):
    try:
        _secret_key = st.secrets.get("OPENAI_API_KEY", "")
        if _secret_key:
            os.environ["OPENAI_API_KEY"] = _secret_key
    except Exception:
        pass

CATALOGUE_DIR = ROOT / "data" / "source_catalogue"
CATALOGUE_JSON = CATALOGUE_DIR / "gos_links.json"
CATALOGUE_CSV = CATALOGUE_DIR / "gos_links.csv"
CATALOGUE_DIR.mkdir(parents=True, exist_ok=True)
init_registry()

def get_embeddings():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        try:
            api_key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            api_key = ""
    if not api_key:
        return None
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        api_key=api_key,
    )

def require_embeddings():
    embeddings = get_embeddings()
    if embeddings is None:
        st.error("OPENAI_API_KEY is missing. Copy .env.example to .env and add your key.")
    return embeddings


# ---------------------------------------------------------------------------
# Presentation layer. All ingestion / retrieval / guardrail / QA calls are the same
# calls the original app made; this file only changes layout, navigation and styling.
# ---------------------------------------------------------------------------
PAGE_HOME = "🏠 Home"
PAGE_ASK = "💬 Ask AI Assistant"
PAGE_SOURCES = "📚 Sources & Ingestion"
PAGE_STATUS = "📊 Knowledge Base Status"
PAGES = [PAGE_HOME, PAGE_ASK, PAGE_SOURCES, PAGE_STATUS]

RETRIEVAL_LABELS = ["Hybrid (recommended)", "Vector only", "BM25 keyword only"]
RETRIEVAL_MODES = {"Vector only": "vector", "BM25 keyword only": "bm25", "Hybrid (recommended)": "hybrid"}

# Suggested topics taken from the indexed budget speech / policy documents. Clicking one asks a normal,
# fully self-contained question; the answer still comes only from the vector database.
SCHEME_TOPICS = [
    ("Velaan e-Sevai Maiyam", "One-stop farmer service centres (ATMA)", "What is the Velaan e-Sevai Maiyam scheme?"),
    ("Tamil Nadu Millet Mission", "Millet production and consumption", "What is the Tamil Nadu Millet Mission?"),
    ("Mannuyir Kaathu Mannuyir Kaappom", "Soil health and organic farming", "What is the Chief Minister's Mannuyir Kaathu Mannuyir Kaappom Scheme?"),
    ("Farmers Service Centres", "Input and advisory centres for farmers", "What is the Chief Minister's 1000 Farmers Service Centres Scheme?"),
    ("Micro Irrigation Scheme", "Subsidised micro-irrigation systems", "What subsidy is available under the Micro Irrigation Scheme?"),
    ("Kuruvai Special Package", "Support for Kuruvai paddy cultivation", "What is the Kuruvai Special Package Scheme?"),
    ("Traditional Paddy Mission", "Conserving traditional paddy varieties", "What is Nel Jayaraman's Traditional Paddy Varieties Conservation Mission?"),
    ("Crop Insurance", "Premium subsidy and crop-loss compensation", "How does crop insurance work for farmers in Tamil Nadu?"),
]
FOLLOW_UP_QUESTIONS = [
    "What documents are required to apply for a subsidy?",
    "Which schemes are available for small and marginal farmers?",
    "What support is available for millet cultivation?",
]

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = PAGE_HOME
# After an answer is stored, the question box is emptied here, before the widget is created.
if st.session_state.pop("_clear_question", False):
    st.session_state["farmer_question"] = ""


def _open_page(page: str) -> None:
    st.session_state["nav_page"] = page


def _ask_now(question: str) -> None:
    """Button callback: jump to the Ask page and answer a ready-made question."""
    st.session_state["nav_page"] = PAGE_ASK
    st.session_state["farmer_question"] = question
    st.session_state["_autorun"] = True


def _clear_chat() -> None:
    st.session_state["chat_history"] = []


def kb_stats() -> dict:
    records = source_rows()
    indexed = [r for r in records if r.get("status") == "indexed"]
    return {
        "sources": len(indexed),
        "chunks": sum(int(r.get("chunk_count") or 0) for r in indexed),
        "latest": max((str(r.get("ingested_at_utc") or "") for r in indexed), default="")[:10],
    }


STATS = kb_stats()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Tamil:wght@400;500;600;700&display=swap');
:root {
  --g950:#0A2A1B; --g900:#0F3B27; --g800:#165233; --g700:#1F6F43; --g600:#2A8553; --g500:#4C9A5F; --g200:#C9E2C8; --g100:#E3EFDF; --g50:#F1F6EC;
  --gold:#E0A526; --ink:#1B2A22; --muted:#5E6F64; --line:#DCE6D6; --card:#FFFFFF;
}
html, body, [class*="css"], .stMarkdown, .stTextArea textarea, button {
  font-family: 'Inter','Noto Sans Tamil',system-ui,-apple-system,'Segoe UI',sans-serif !important;
}
[data-testid="stAppViewContainer"] {background: linear-gradient(180deg,#F7F6EF 0%,#F1F6EC 100%);}
[data-testid="stHeader"] {background: transparent;}
footer {visibility:hidden;}
.block-container {padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1240px;}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {background: linear-gradient(180deg,#EEF5EA 0%,#E3EFDF 100%); border-right:1px solid var(--line);}
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] {padding-top: 1.2rem;}
.brand {display:flex; align-items:center; gap:.7rem; margin:.2rem 0 1.1rem 0;}
.brand-logo {width:2.7rem; height:2.7rem; border-radius:50%; background:linear-gradient(135deg,var(--g700),var(--g500)); display:flex; align-items:center; justify-content:center; font-size:1.4rem; box-shadow:0 4px 12px rgba(31,111,67,.35);}
.brand-name {font-size:1.25rem; font-weight:800; color:var(--g900); line-height:1.1;}
.brand-tag {font-size:.74rem; color:var(--muted); margin-top:.1rem;}
[data-testid="stSidebar"] [role="radiogroup"] {gap:.3rem;}
[data-testid="stSidebar"] [role="radiogroup"] label {width:100%; padding:.62rem .85rem; border-radius:12px; cursor:pointer; transition:all .15s ease; border:1px solid transparent;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:rgba(255,255,255,.65);}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {display:none;}
[data-testid="stSidebar"] [role="radiogroup"] label p {font-weight:600; font-size:.95rem; color:var(--g900); margin:0;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked), [data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {background: linear-gradient(120deg,var(--g700),var(--g600)); box-shadow:0 6px 14px rgba(31,111,67,.28);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p, [data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {color:#fff;}
.side-card {margin-top:1.2rem; padding:.9rem 1rem; border-radius:14px; background:rgba(255,255,255,.7); border:1px solid var(--line); font-size:.84rem; color:var(--ink);}
.side-card b {color:var(--g800);}
.side-stat {display:flex; justify-content:space-between; padding:.18rem 0;}
.side-art {margin-top:1rem; border-radius:14px; overflow:hidden; line-height:0;}

/* ---------- Hero: compact and responsive ---------- */
.hero {position:relative; overflow:hidden; padding: 1.7rem 2rem 1.5rem; border-radius: 24px; color:#fff;
  min-height: 0;
  background: radial-gradient(900px 320px at 90% -20%, rgba(224,165,38,.35), transparent 60%),
              linear-gradient(115deg, var(--g950) 0%, var(--g800) 45%, #3F8A4F 100%);
  box-shadow: 0 14px 36px rgba(10,42,27,.24); margin-bottom: .85rem;}
.hero .eyebrow {display:inline-block; font-size:.7rem; letter-spacing:.13em; text-transform:uppercase; color:#F7E3A6; font-weight:700; margin-bottom:.4rem;}
.hero h1 {color:#fff; margin:0 0 .5rem 0; font-size: clamp(1.55rem, 2.7vw, 2.2rem); line-height:1.12; font-weight:800; max-width: 32rem;}
.hero p {color:#E4F3E6; margin:0; font-size:.96rem; max-width: 32rem; line-height:1.42;}
.hero-art {position:absolute; right:0; bottom:0; width:43%; height:70%; opacity:.92; pointer-events:none; z-index:0;
  -webkit-mask-image: linear-gradient(to right, transparent 0%, #000 38%); mask-image: linear-gradient(to right, transparent 0%, #000 38%);}
.hero > *:not(.hero-art) {position:relative; z-index:1;}
.chips {margin-top:.8rem; display:flex; flex-wrap:wrap; gap:.4rem; max-width: 36rem;}
.chip {display:inline-flex; align-items:center; gap:.35rem; padding:.25rem .65rem; border-radius:999px; font-size:.76rem; font-weight:500;
  background: rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.3); color:#fff;}
.chip b {color:#FFE9A8; font-weight:700;}

/* Short laptop viewports: trim vertical spacing without hiding content. */
@media (max-height: 850px) and (min-width: 761px) {
  .hero {padding-top:1.35rem; padding-bottom:1.2rem;}
  .hero h1 {font-size:clamp(1.5rem, 2.45vw, 2rem); margin-bottom:.4rem;}
  .hero p {font-size:.92rem; line-height:1.38;}
  .chips {margin-top:.65rem; gap:.35rem;}
  .chip {padding:.22rem .58rem; font-size:.73rem;}
}
@media (max-width: 760px) {
  .hero {padding:1.35rem 1.15rem 1.2rem; border-radius:18px;}
  .hero h1 {font-size:clamp(1.5rem, 6vw, 2rem); max-width:100%;}
  .hero p {font-size:.92rem; max-width:100%;}
  .hero-art {opacity:.28; width:100%; height:65%;}
  .chips {margin-top:.75rem; gap:.35rem;}
  .chip {font-size:.72rem; padding:.22rem .55rem;}
}

/* ---------- Feature cards ---------- */
.fcard {border-radius:18px; padding:1.1rem 1.1rem .9rem; border:1px solid rgba(0,0,0,.05); height:12rem; overflow:hidden; box-shadow:0 2px 10px rgba(15,59,39,.05);}
.fcard .ico {width:2.5rem; height:2.5rem; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:1.25rem; background:rgba(255,255,255,.85); margin-bottom:.6rem;}
.fcard h4 {margin:0 0 .25rem 0; font-size:1.02rem; font-weight:700; color:var(--ink);}
.fcard p {margin:0; font-size:.84rem; color:var(--muted); line-height:1.4;}
.fc-green {background:#E8F4E6;} .fc-blue {background:#E5EEFB;} .fc-amber {background:#FDF1D8;} .fc-purple {background:#EEE8FA;}

/* ---------- Generic cards ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"] .card-marker) {
  background: var(--card); border:1px solid var(--line); box-shadow: 0 2px 10px rgba(15,59,39,.05); padding: .35rem .5rem;}
.sec-head {display:flex; align-items:center; gap:.65rem; margin:.15rem 0 .35rem 0;}
.sec-num {display:inline-flex; align-items:center; justify-content:center; width:1.9rem; height:1.9rem; border-radius:50%; background: var(--g700); color:#fff; font-weight:700; font-size:.95rem; flex:none;}
.sec-title {font-size:1.12rem; font-weight:700; color: var(--g900);}
.sec-sub {color: var(--muted); font-size:.92rem; margin:0 0 .6rem 0;}
.panel-title {font-size:1.05rem; font-weight:700; color:var(--g900); margin:.1rem 0 .55rem 0; display:flex; align-items:center; gap:.45rem;}
.step {display:flex; gap:.7rem; margin-bottom:.75rem; font-size:.92rem; color: var(--ink);}
.step i {font-style:normal; flex:none; width:1.65rem; height:1.65rem; border-radius:50%; background: var(--g100); color: var(--g700); font-weight:700; display:flex; align-items:center; justify-content:center; font-size:.82rem;}
.note {margin-top:.4rem; padding:.65rem .8rem; border-radius:12px; background:#FBF0CF; color:#6B4E05; font-size:.84rem;}
.stat-tile {background:var(--card); border:1px solid var(--line); border-radius:16px; padding:.9rem 1.1rem; box-shadow:0 1px 4px rgba(15,59,39,.05);}
.stat-tile .v {font-size:1.55rem; white-space:nowrap; font-weight:800; color:var(--g700); line-height:1.1;}
.stat-tile .l {font-size:.8rem; color:var(--muted); font-weight:600; margin-top:.15rem;}

/* ---------- Inputs & buttons ---------- */
.stTextArea textarea {border-radius:14px; border:1.5px solid var(--line); font-size:1rem; background:#FFFEFB;}
.stTextArea textarea:focus {border-color: var(--g500); box-shadow: 0 0 0 3px rgba(76,154,95,.18);}
div.stButton > button {border-radius:12px; font-weight:600; border:1.5px solid var(--line); transition: all .15s ease;}
div.stButton > button:hover {border-color: var(--g500); color: var(--g700); transform: translateY(-1px); box-shadow:0 4px 12px rgba(31,111,67,.12);}
div.stButton > button[kind="primary"] {background: linear-gradient(120deg, var(--g700), #2E8B57); color:#fff; border:none; padding:.55rem 1rem;}
div.stButton > button[kind="primary"]:hover {color:#fff; box-shadow:0 6px 16px rgba(31,111,67,.32);}
div.stButton > button[kind="secondary"] {background:#FBFDF9; font-weight:500; min-height:3rem; height:auto; padding:.5rem .8rem;}
div.stButton > button p {white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height:1.35; margin:0;}
[data-testid="stFileUploader"] section {border-radius:14px; border:1.5px dashed var(--g500); background: var(--g50);}
[data-testid="stAudioInput"] {border-radius:14px;}

/* ---------- Scheme list buttons ---------- */
[class*="st-key-home_scheme_"] button, [class*="st-key-ask_scheme_"] button {justify-content:flex-start !important; text-align:left !important; min-height:3.2rem; background:#fff; border:1px solid var(--line); border-radius:14px;}
[class*="st-key-home_scheme_"] button p, [class*="st-key-ask_scheme_"] button p {text-align:left !important; font-size:.9rem;}
[class*="st-key-home_scheme_"] button:hover, [class*="st-key-ask_scheme_"] button:hover {background:var(--g50);}

/* ---------- Metrics ---------- */
div[data-testid="stMetric"] {background: var(--card); padding: .9rem 1rem; border-radius: 14px; border: 1px solid var(--line); box-shadow:0 1px 4px rgba(15,59,39,.05);}
div[data-testid="stMetricValue"] {color: var(--g700); font-weight:700;}
div[data-testid="stMetricLabel"] p {color: var(--muted); font-weight:600;}

/* ---------- Chat ---------- */
[data-testid="stChatMessage"] {border-radius:18px; padding:.85rem 1rem; margin-bottom:.7rem; border:1px solid var(--line); background: var(--card); box-shadow:0 1px 6px rgba(15,59,39,.05);}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {background: #E6F3E3; border-color:#CFE5CB; width:88%; margin-left:auto;}
.evidence {color: var(--muted); font-size:.84rem; margin:.1rem 0 .5rem 0;}
.src-badges {display:flex; gap:.4rem; flex-wrap:wrap; margin:.1rem 0 .55rem 0;}
.badge {font-size:.74rem; font-weight:600; padding:.18rem .55rem; border-radius:8px; background: var(--g100); color: var(--g900);}
.badge.gold {background:#FBF0CF; color:#7A5A06;}
.badge.grounded {background:var(--g700); color:#fff;}
[data-testid="stExpander"] {border-radius:12px; border:1px solid var(--line); background: var(--card); margin-bottom:.4rem;}
[data-testid="stExpander"] summary {font-weight:600;}
.composer-title {font-weight:700; color:var(--g900); margin:.2rem 0 .3rem 0;}

.footer-note {text-align:center; color: var(--muted); font-size:.82rem; margin-top:1.6rem;}
</style>
""", unsafe_allow_html=True)

_FIELD_SVG = (
    '<svg viewBox="0 0 600 260" preserveAspectRatio="xMidYMax slice" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="470" cy="78" r="40" fill="#FFE9A8" opacity=".92"/>'
    '<circle cx="470" cy="78" r="62" fill="#FFE9A8" opacity=".14"/>'
    '<path d="M0 185 C90 140 190 178 290 150 C390 122 500 170 600 140 L600 260 L0 260Z" fill="#5BA467" opacity=".55"/>'
    '<path d="M0 215 C120 178 220 220 330 190 C440 160 520 210 600 183 L600 260 L0 260Z" fill="#2F7A4C" opacity=".8"/>'
    '<path d="M0 240 C150 214 260 246 380 228 C480 212 540 240 600 230 L600 260 L0 260Z" fill="#0F3B27"/>'
    '<g stroke="#8CCB7E" stroke-width="2" opacity=".55" fill="none">'
    '<path d="M40 250 C120 230 200 244 280 238"/><path d="M300 252 C380 232 460 246 560 236"/></g>'
    '<g fill="#F2D675"><circle cx="120" cy="206" r="3"/><circle cx="150" cy="212" r="3"/><circle cx="410" cy="196" r="3"/><circle cx="440" cy="203" r="3"/></g>'
    '</svg>'
)


def section_head(num: int, title: str, sub: str = "") -> None:
    st.markdown(
        f'<span class="card-marker"></span><div class="sec-head"><span class="sec-num">{num}</span>'
        f'<span class="sec-title">{html.escape(title)}</span></div>'
        + (f'<p class="sec-sub">{html.escape(sub)}</p>' if sub else ""),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-logo">🌾</div><div>'
        '<div class="brand-name">SmartAgri AI</div>'
        '<div class="brand-tag">வயல்வழி AI · Smart schemes. Better farms.</div></div></div>',
        unsafe_allow_html=True,
    )
    page = st.radio("Navigate", PAGES, key="nav_page", label_visibility="collapsed")
    st.markdown(
        f'<div class="side-card"><b>Knowledge base</b>'
        f'<div class="side-stat"><span>📄 Sources</span><b>{STATS["sources"]}</b></div>'
        f'<div class="side-stat"><span>🧩 Passages</span><b>{STATS["chunks"]:,}</b></div>'
        f'<div style="margin-top:.4rem;color:#5E6F64">Answers come only from indexed official documents. No live web search.</div></div>'
        f'<div class="side-art"><svg viewBox="0 40 600 220" preserveAspectRatio="xMidYMax slice" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto"><rect y="40" width="600" height="220" fill="#D9ECD6"/>' + _FIELD_SVG.split('xmlns="http://www.w3.org/2000/svg">')[1].replace('</svg>', '') + '</svg></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
def render_home_page() -> None:
    st.markdown(f"""
    <div class="hero">
      <svg class="hero-art" viewBox="0 0 600 260" preserveAspectRatio="xMaxYMax slice" xmlns="http://www.w3.org/2000/svg">{_FIELD_SVG.split('xmlns="http://www.w3.org/2000/svg">')[1].replace('</svg>', '')}</svg>
      <span class="eyebrow">Tamil Nadu · Agriculture Schemes Assistant</span>
      <h1>AI-powered guidance on Tamil Nadu agriculture schemes</h1>
      <p>அரசு ஆவணங்களின் அடிப்படையில் வேளாண்மைத் தகவல்கள் — ask about schemes, subsidies and Government Orders, in Tamil or English, by typing or by voice.</p>
      <div class="chips">
        <span class="chip">📄 <b>{STATS['sources']}</b> sources indexed</span>
        <span class="chip">🧩 <b>{STATS['chunks']:,}</b> passages searchable</span>
        <span class="chip">🎙️ Voice questions</span>
        <span class="chip">🛡️ Safety checks on</span>
        <span class="chip">🚫 No live web search</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    b1, b2, _spacer = st.columns([1.2, 1.2, 3])
    b1.button("💬 Ask AI Assistant", type="primary", use_container_width=True, key="home_cta_ask", on_click=_open_page, args=(PAGE_ASK,))
    b2.button("🎙️ Ask by voice", use_container_width=True, key="home_cta_voice", on_click=_open_page, args=(PAGE_ASK,))

    st.write("")
    cards = [
        ("fc-green", "💬", "AI Assistant", "Ask in Tamil or English and get answers with cited sources.", "Chat now →", PAGE_ASK, "home_card_ask"),
        ("fc-blue", "🎙️", "Voice Question", "Speak your question — it is transcribed so you can review it.", "Ask by voice →", PAGE_ASK, "home_card_voice"),
        ("fc-amber", "📚", "Add Sources", "Upload PDFs, web pages and Government Orders to the knowledge base.", "Manage sources →", PAGE_SOURCES, "home_card_sources"),
        ("fc-purple", "📊", "Knowledge Base", "See what is indexed, with counts and an exportable registry.", "View status →", PAGE_STATUS, "home_card_status"),
    ]
    for col, (css, icon, title, text, cta, target, key) in zip(st.columns(4, gap="medium"), cards):
        with col:
            st.markdown(f'<div class="fcard {css}"><div class="ico">{icon}</div><h4>{html.escape(title)}</h4><p>{html.escape(text)}</p></div>', unsafe_allow_html=True)
            st.button(cta, key=key, use_container_width=True, on_click=_open_page, args=(target,))

    st.write("")
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        with st.container(border=True):
            st.markdown('<span class="card-marker"></span><div class="panel-title">How your answer is made</div>', unsafe_allow_html=True)
            st.markdown("""
            <div class="step"><i>1</i><div><b>Safety check</b><br>Your question (typed or spoken) is screened before anything else.</div></div>
            <div class="step"><i>2</i><div><b>Search official documents</b><br>Only the pre-indexed Government documents are searched: keyword, semantic, or both.</div></div>
            <div class="step"><i>3</i><div><b>Cited answer</b><br>The answer quotes its sources, or says clearly when the evidence is missing.</div></div>
            <div class="note">ℹ️ Always confirm eligibility, amounts and deadlines with your local agriculture office.</div>
            """, unsafe_allow_html=True)
        t1, t2, t3 = st.columns(3)
        t1.markdown(f'<div class="stat-tile"><div class="v">{STATS["sources"]}</div><div class="l">Sources indexed</div></div>', unsafe_allow_html=True)
        t2.markdown(f'<div class="stat-tile"><div class="v">{STATS["chunks"]:,}</div><div class="l">Searchable passages</div></div>', unsafe_allow_html=True)
        t3.markdown(f'<div class="stat-tile"><div class="v">{html.escape(STATS["latest"] or "—")}</div><div class="l">Last updated</div></div>', unsafe_allow_html=True)
    with right:
        render_scheme_panel(prefix="home")


def render_scheme_panel(prefix: str) -> None:
    with st.container(border=True):
        st.markdown('<span class="card-marker"></span><div class="panel-title">⭐ Schemes you can ask about</div>', unsafe_allow_html=True)
        st.caption("Suggested topics. Answers appear only if the relevant document has been indexed.")
        st.markdown('<div class="scheme-list">', unsafe_allow_html=True)
        for idx, (name, blurb, question) in enumerate(SCHEME_TOPICS):
            st.button(f"{name} — {blurb}", key=f"{prefix}_scheme_{idx}", use_container_width=True, on_click=_ask_now, args=(question,))
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Ask (chat)
# ---------------------------------------------------------------------------
def process_question(question: str, retrieval_mode: str, retrieval_mode_label: str) -> bool:
    """Same sequence as the original app: guardrail check -> embeddings -> answer_question."""
    entry = {"q": question, "mode": retrieval_mode_label}
    with st.spinner("Running safety check..."):
        safety = check_question(question)
    if not safety.allowed:
        entry.update(kind="blocked", message=safety.message)
    else:
        embeddings = require_embeddings()
        if not embeddings:
            return False
        with st.spinner("Searching the indexed knowledge base..."):
            try:
                result = answer_question(
                    question, embeddings, os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
                    retrieval_mode=retrieval_mode,
                )
                entry.update(kind="answer", answer=result["answer"], sources=result["sources"])
            except Exception as exc:
                entry.update(kind="error", message=f"Could not answer the question: {exc}")
    st.session_state["chat_history"] = (st.session_state["chat_history"] + [entry])[-20:]
    if entry["kind"] in {"answer", "blocked"}:
        st.session_state["_clear_question"] = True
    return True


def render_sources(sources: list[dict]) -> None:
    st.markdown("**📄 ஆதார ஆவணங்கள் | Retrieved sources**")
    for i, source in enumerate(sources, start=1):
        label = source["title"]
        if source.get("page"):
            label += f" — page {source['page']}"
        with st.expander(f"{i}. {label}"):
            badges = ""
            if source.get("source_type"):
                badges += f'<span class="badge">{html.escape(str(source["source_type"]).upper())}</span>'
            if source.get("page"):
                badges += f'<span class="badge gold">Page {html.escape(str(source["page"]))}</span>'
            if badges:
                st.markdown(f'<div class="src-badges">{badges}</div>', unsafe_allow_html=True)
            st.write(source["excerpt"])
            if source.get("url"):
                st.markdown(f"[Open source document]({source['url']})")


def render_history(box) -> None:
    history = st.session_state["chat_history"]
    with box:
        with st.chat_message("assistant", avatar="🌾"):
            st.markdown(
                "**வணக்கம்!** நான் வயல்வழி AI. அரசு ஆவணங்களின் அடிப்படையில் வேளாண் திட்டங்கள் பற்றி பதில் அளிக்கிறேன்.\n\n"
                "Hello! Ask me about Tamil Nadu agriculture schemes, in Tamil or English. Type below, or tap the microphone."
            )
        for turn in history:
            with st.chat_message("user", avatar="🧑‍🌾"):
                st.markdown(turn["q"])
            with st.chat_message("assistant", avatar="🌾"):
                if turn["kind"] == "blocked":
                    st.warning(turn["message"])
                    st.caption("Safety guardrail stopped this request before document retrieval or answer generation.")
                elif turn["kind"] == "error":
                    st.error(turn["message"])
                else:
                    sources = turn.get("sources") or []
                    if sources:
                        n_docs = len({s["title"] for s in sources})
                        st.markdown(
                            f'<div class="evidence"><span class="badge grounded">Grounded answer</span> '
                            f'Based on {len(sources)} retrieved passage(s) from {n_docs} document(s) · mode: {html.escape(turn["mode"])}</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(turn["answer"])
                    if sources:
                        render_sources(sources)
        if history and history[-1]["kind"] == "answer":
            st.caption("Try asking")
            for col, text in zip(st.columns(len(FOLLOW_UP_QUESTIONS)), FOLLOW_UP_QUESTIONS):
                col.button(text, key=f"chip_{len(history)}_{FOLLOW_UP_QUESTIONS.index(text)}", use_container_width=True, on_click=_ask_now, args=(text,))


def render_ask_page() -> None:
    main_col, side_col = st.columns([2.2, 1], gap="large")
    with side_col:
        render_scheme_panel(prefix="ask")
    with main_col:
        st.markdown(  '<div class="sec-title" style="font-size:1.45rem">'    '💬 Your Agricultural Questions, Answered</div>',    unsafe_allow_html=True,)
        st.caption(    "Get AI-powered answers about Tamil Nadu agricultural schemes, "    "subsidies, farmer services, and government initiatives. "    "Ask in English or Tamil.")
        history_box = st.container()
        has_history = bool(st.session_state["chat_history"])

        # Sample questions (same questions and the same prefill behaviour as the original app).
        if not has_history:
            st.markdown("**Try a sample question**")
            sample_questions = [
                "வேளான் இ-சேவை மையத்தில் இலவசமாக வழங்கப்படும் சேவைகள் என்னென்ன?",
                "What is the Velaan e-Sevai Maiyam scheme?",
                "What is the current application deadline for an agriculture subsidy in December 2026?",
            ]
            for idx, (col, sample) in enumerate(zip(st.columns(3), sample_questions)):
                with col:
                    if st.button(sample, key=f"sample_{idx}", use_container_width=True):
                        st.session_state["farmer_question"] = sample

        st.markdown('<div class="composer-title">Your question / உங்கள் கேள்வி</div>', unsafe_allow_html=True)
        textarea_box = st.container()
        voice_box = st.container()

        # Voice: transcribe BEFORE the text area is created so the transcript can fill it (editable before sending).
        with voice_box:
            audio = st.audio_input(
                "🎙️ Ask by voice — Tamil or English",
                key=f"voice_input_{st.session_state.get('_voice_nonce', 0)}",
            )
            if audio is not None:
                audio_bytes = audio.getvalue()
                digest = hashlib.sha256(audio_bytes).hexdigest()
                if st.session_state.get("_voice_digest") != digest:
                    st.session_state["_voice_digest"] = digest
                    try:
                        with st.spinner("Transcribing your voice question..."):
                            transcript = transcribe_audio(audio_bytes, getattr(audio, "name", None) or "question.wav")
                        if transcript:
                            st.session_state["farmer_question"] = transcript
                            st.session_state["_voice_note"] = "Transcribed from your voice — please check the text, edit if needed, then press Send."
                        else:
                            st.session_state["_voice_note"] = "I could not hear a question in that recording. Please try again."
                    except Exception as exc:
                        st.session_state["_voice_note"] = f"Voice transcription failed: {exc}"
            if st.session_state.get("_voice_note"):
                st.caption(st.session_state["_voice_note"])

        with textarea_box:
            question = st.text_area(
                "Farmer question / விவசாயியின் கேள்வி",
                placeholder="Example: What documents are required to apply for a subsidy? / மானியம் பெற என்ன ஆவணங்கள் தேவை?",
                height=105,
                key="farmer_question",
                label_visibility="collapsed",
            )
        with st.expander("⚙️ Advanced: retrieval mode"):
            retrieval_mode_label = st.selectbox(
                "Retrieval mode",
                RETRIEVAL_LABELS,
                index=0,
                help="Hybrid combines semantic and keyword retrieval. Farmer questions never trigger live web search.",
            )
        retrieval_mode = RETRIEVAL_MODES[retrieval_mode_label]

        send_col, clear_col = st.columns([4, 1])
        send = send_col.button("🔎 Find answer / பதிலைக் காண்க", type="primary", disabled=not question.strip(), use_container_width=True)
        if has_history:
            clear_col.button("🗑️ Clear chat", key="clear_chat", use_container_width=True, on_click=_clear_chat)

        autorun = st.session_state.pop("_autorun", False)
        if (send or autorun) and question.strip():
            st.session_state["_voice_note"] = ""
            if process_question(question, retrieval_mode, retrieval_mode_label):
                st.session_state["_voice_nonce"] = st.session_state.get("_voice_nonce", 0) + 1  # reset the recorder
                st.rerun()

        render_history(history_box)


# ---------------------------------------------------------------------------
# Sources & Ingestion (admin) and Status — widgets, keys and handlers unchanged from the original app
# ---------------------------------------------------------------------------
def render_sources_page() -> None:
    st.caption("Administrator workspace — documents added here become searchable in the Ask tab. Farmer questions never trigger live web search.")
    with st.container(border=True):
        section_head(1, "Upload official PDFs", "Upload policy notes, scheme guidelines, Government Orders, and other approved documents.")
        uploads = st.file_uploader("Choose one or more PDF files", type=["pdf"], accept_multiple_files=True, key="pdf_uploads")
        if st.button("Ingest uploaded PDFs", type="primary", disabled=not uploads):
            embeddings = require_embeddings()
            if embeddings:
                progress = st.progress(0)
                for i, uploaded in enumerate(uploads, start=1):
                    try:
                        result = ingest_uploaded_file(uploaded, embeddings)
                        if result["status"] == "indexed":
                            st.success(f"{uploaded.name}: {result['message']}")
                        else:
                            st.info(f"{uploaded.name}: {result['message']}")
                    except Exception as exc:
                        st.error(f"{uploaded.name}: {exc}")
                    progress.progress(i / len(uploads))

    with st.container(border=True):
        section_head(2, "Load URL sources", "Add readable web pages or direct PDF links.")
        urls_text = st.text_area(
            "Enter one URL per line (HTML page or direct PDF URL)",
            placeholder="https://example.gov.in/scheme-guidelines.pdf\nhttps://example.gov.in/scheme-details.html",
            height=110,
        )
        if st.button("Ingest URL sources", type="primary", disabled=not urls_text.strip()):
            embeddings = require_embeddings()
            if embeddings:
                urls = list(dict.fromkeys(line.strip() for line in urls_text.splitlines() if line.strip()))
                for url in urls:
                    try:
                        result = ingest_url(url, embeddings)
                        st.success(f"{url} — {result['message']}")
                    except Exception as exc:
                        st.error(f"{url} — {exc}")

    with st.container(border=True):
        section_head(3, "Government Orders catalogue", "Fetch the current GO table into JSON and CSV. This refreshes the source list; it does not automatically download or index every listed PDF.")
        st.code(GOS_URL, language="text")
        if st.button("🔄 Refresh GO catalogue from source website"):
            with st.spinner("Opening the official GO page and extracting table rows..."):
                try:
                    rows, method = fetch_gos_catalogue(GOS_URL)
                    save_catalogue(rows, CATALOGUE_JSON, CATALOGUE_CSV)
                    st.success(f"Refreshed {len(rows)} unique records using {method}.")
                    st.download_button("Download refreshed JSON", CATALOGUE_JSON.read_bytes(), "gos_links.json", "application/json")
                    st.download_button("Download refreshed CSV", CATALOGUE_CSV.read_bytes(), "gos_links.csv", "text/csv")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                except Exception as exc:
                    st.error(str(exc))
                    st.info("If Playwright is being used for the first time, run: python -m playwright install chromium")

        # Catalogue preview and controlled ingestion of selected GO PDFs.
        rows = load_catalogue(CATALOGUE_JSON)
        if rows:
            st.caption(f"Catalogue currently contains {len(rows)} unique records.")
            shortlist_path = CATALOGUE_DIR / "gos_shortlist.csv"
            approved_urls = set()
            if shortlist_path.exists():
                try:
                    shortlist_df = pd.read_csv(shortlist_path).fillna("")
                    url_col = "url" if "url" in shortlist_df.columns else "PDF URL"
                    keep_col = "keep" if "keep" in shortlist_df.columns else "Keep? (Y/N)"
                    if url_col in shortlist_df.columns and keep_col in shortlist_df.columns:
                        approved_urls = set(shortlist_df.loc[shortlist_df[keep_col].astype(str).str.upper().eq("Y"), url_col].astype(str))
                except Exception:
                    approved_urls = set()

            selection_rows = []
            for row in rows:
                selection_rows.append({
                    "Select for ingestion": bool(row.get("url") in approved_urls),
                    "Department": row.get("dept", ""),
                    "GO Number": row.get("go_no", ""),
                    "Year": row.get("year", ""),
                    "Date": row.get("date", ""),
                    "Subject": row.get("subject", ""),
                    "Section": row.get("section", ""),
                    "PDF URL": row.get("url", ""),
                })
            st.write("Review the catalogue below. The supplied shortlist preselects records marked Y; newly discovered records remain unselected by default.")
            edited = st.data_editor(
                pd.DataFrame(selection_rows),
                use_container_width=True,
                hide_index=True,
                height=350,
                key="gos_catalogue_editor",
                disabled=["Department", "GO Number", "Year", "Date", "Subject", "Section", "PDF URL"],
                column_config={
                    "Select for ingestion": st.column_config.CheckboxColumn("Select for ingestion", default=False),
                    "PDF URL": st.column_config.LinkColumn("PDF URL", display_text="Open PDF"),
                },
            )
            selected_rows = edited[edited["Select for ingestion"] == True]
            st.caption(f"Selected for ingestion: {len(selected_rows)} record(s). Selecting a row downloads and indexes its PDF; review old GOs before selecting them.")
            if st.button("Ingest selected Government Order PDFs", type="primary", disabled=selected_rows.empty):
                embeddings = require_embeddings()
                if embeddings:
                    progress = st.progress(0)
                    for i, (_, selected_row) in enumerate(selected_rows.iterrows(), start=1):
                        url = str(selected_row.get("PDF URL", "")).strip()
                        title = f"{selected_row.get('GO Number', '')} — {selected_row.get('Subject', '')}".strip(" —")
                        try:
                            result = ingest_url(url, embeddings)
                            st.success(f"{title}: {result['message']}")
                        except Exception as exc:
                            st.error(f"{title or url}: {exc}")
                        progress.progress(i / len(selected_rows))


def render_status_page() -> None:
    st.markdown('<div class="sec-title" style="font-size:1.25rem; margin-bottom:.6rem">Ingestion registry</div>', unsafe_allow_html=True)
    records = source_rows()
    if records:
        df = pd.DataFrame(records)
        m1, m2, m3 = st.columns(3)
        m1.metric("Sources recorded", len(df))
        m2.metric("Successfully indexed", int((df["status"] == "indexed").sum()))
        m3.metric("Passages indexed", int(df.loc[df["status"] == "indexed", "chunk_count"].sum()))
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Export source registry CSV", df.to_csv(index=False).encode("utf-8-sig"), "source_registry.csv", "text/csv")
    else:
        st.info("No sources have been indexed yet.")
    st.caption("Duplicate files/content are skipped using SHA-256. Changed content is recorded as a new version. Exact content hashes are checked before creating embeddings.")


if page == PAGE_HOME:
    render_home_page()
elif page == PAGE_ASK:
    render_ask_page()
elif page == PAGE_SOURCES:
    render_sources_page()
else:
    render_status_page()

st.markdown('<div class="footer-note">வயல்வழி AI · Answers come only from indexed official documents · No live web search</div>', unsafe_allow_html=True)
