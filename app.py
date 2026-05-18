"""
Citation Annotator: full app, with theme switcher.

Themes:
  - editorial : warm cream, serif, terracotta accent (academic journal)
  - modern    : white, sans-serif, indigo accent (Linear/Notion vibe)
  - terminal  : dark background, monospace, green accent (developer tool)
  - print     : narrow column, large serif (book-like)
  - default   : minimal Streamlit defaults
"""

import random
import secrets
import string
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st
from supabase import create_client

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
RESEND_API_KEY = st.secrets["RESEND_API_KEY"]
RESEND_FROM = st.secrets.get("RESEND_FROM", "onboarding@resend.dev")

CODE_LENGTH = 6
CODE_TTL_MINUTES = 10
SESSION_TTL_DAYS = 30
ASSIGNMENT_TTL_HOURS = 24
CITATION_CAP = 10
MAX_IN_PROGRESS_PER_USER = 3
TEST_EMAIL = "test@test.com"
SUPPORT_EMAIL = "sinaalemohammad@gmail.com"

CONSENT_TEXT = f"""
Thanks for participating. Your responses (which papers you would cite for each
prompt) will be used in a research paper comparing human and LLM citation
patterns. Your individual responses will be aggregated; we will not identify
you personally in the paper unless we ask permission.

You can stop at any time, and you can request that your data be deleted by
emailing **{SUPPORT_EMAIL}**.
"""

CAREER_STAGES = [
    "Undergraduate",
    "Master's student",
    "PhD student",
    "Postdoctoral researcher",
    "Industry researcher / engineer",
    "Faculty",
    "Other",
]

KD_FAMILIARITY_OPTIONS = [
    "I have published on knowledge distillation",
    "I have read papers on knowledge distillation but not published in the area",
    "I'm new to this literature",
]


# ----------------------------------------------------------------------------
# Themes
# ----------------------------------------------------------------------------

THEMES = {
    "editorial": {
        "label": "Journal",
        "css": """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --bg: #FAF8F3;
    --bg-card: #FFFFFF;
    --ink: #1A1A1A;
    --ink-soft: #3A3530;
    --muted: #6B6560;
    --border: #E8E2D5;
    --border-strong: #D4CCB8;
    --accent: #A33B20;
    --accent-bg: #F5E8E0;
    --success: #2E6B3E;
    --warning: #B5811D;
    --danger: #A33B20;
    --display-font: 'Fraunces', serif;
    --body-font: 'IBM Plex Sans', sans-serif;
    --mono-font: 'IBM Plex Mono', monospace;
}
.stApp { background: var(--bg); color: var(--ink); font-family: var(--body-font); }
h1, h2, h3, h4 { font-family: var(--display-font) !important; font-weight: 500 !important; color: var(--ink) !important; letter-spacing: -0.01em; }
h1 { font-size: 2.5rem !important; line-height: 1.15; }
h2 { font-size: 1.75rem !important; }
h3 { font-size: 1.3rem !important; }
.brand-mark { font-family: var(--display-font); font-weight: 600; color: var(--accent); }
.instruction-card { font-family: var(--display-font); border-left: 3px solid var(--accent); background: var(--bg-card); }
.candidate-title { font-family: var(--display-font); }
""",
    },
    "modern": {
        "label": "Clean",
        "css": """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg: #FFFFFF;
    --bg-card: #FAFBFC;
    --ink: #0E0E10;
    --ink-soft: #383844;
    --muted: #7A7B85;
    --border: #EBEBEF;
    --border-strong: #D8D8DD;
    --accent: #5E5CE6;
    --accent-bg: #EEEDFE;
    --success: #0F7B3A;
    --warning: #B5811D;
    --danger: #D13438;
    --display-font: 'Inter', sans-serif;
    --body-font: 'Inter', sans-serif;
    --mono-font: 'JetBrains Mono', monospace;
}
.stApp { background: var(--bg); color: var(--ink); font-family: var(--body-font); }
h1, h2, h3, h4 { font-family: var(--display-font) !important; font-weight: 600 !important; color: var(--ink) !important; letter-spacing: -0.02em; }
h1 { font-size: 2.25rem !important; line-height: 1.1; }
h2 { font-size: 1.5rem !important; }
h3 { font-size: 1.15rem !important; }
.brand-mark { font-family: var(--display-font); font-weight: 700; color: var(--accent); letter-spacing: -0.02em; }
.instruction-card { border-left: 3px solid var(--accent); background: var(--accent-bg); font-weight: 500; }
.candidate-title { font-family: var(--display-font); font-weight: 600; }
""",
    },
    "terminal": {
        "label": "Dark",
        "css": """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
    --bg: #0D1117;
    --bg-card: #161B22;
    --ink: #E6EDF3;
    --ink-soft: #C9D1D9;
    --muted: #7D8590;
    --border: #30363D;
    --border-strong: #484F58;
    --accent: #7EE787;
    --accent-bg: #1A2F1F;
    --success: #3FB950;
    --warning: #D29922;
    --danger: #F85149;
    --display-font: 'JetBrains Mono', monospace;
    --body-font: 'IBM Plex Sans', sans-serif;
    --mono-font: 'JetBrains Mono', monospace;
}
.stApp { background: var(--bg); color: var(--ink); font-family: var(--body-font); }
h1, h2, h3, h4 { font-family: var(--display-font) !important; font-weight: 600 !important; color: var(--ink) !important; }
h1 { font-size: 2rem !important; line-height: 1.15; }
h1::before { content: '> '; color: var(--accent); }
h2 { font-size: 1.4rem !important; }
h3 { font-size: 1.15rem !important; }
.brand-mark { font-family: var(--display-font); font-weight: 700; color: var(--accent); }
.brand-mark::before { content: '$ '; opacity: 0.6; }
.instruction-card { border-left: 3px solid var(--accent); background: var(--bg-card); font-family: var(--body-font); }
.candidate-title { font-family: var(--body-font); font-weight: 600; color: var(--ink); }
.stApp p, .stApp label, .stApp div, .stMarkdown p { color: var(--ink-soft); }
""",
    },
    "print": {
        "label": "Book",
        "css": """
@import url('https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600&display=swap');

:root {
    --bg: #F9F6EE;
    --bg-card: #FFFFFE;
    --ink: #1C1815;
    --ink-soft: #2E2926;
    --muted: #65605A;
    --border: #DDD6C5;
    --border-strong: #C8BFA8;
    --accent: #5A341C;
    --accent-bg: #EDE3D2;
    --success: #2D5938;
    --warning: #8A6A1A;
    --danger: #7A2B1B;
    --display-font: 'Spectral', serif;
    --body-font: 'Spectral', serif;
    --mono-font: 'Inter', sans-serif;
}
.stApp { background: var(--bg); color: var(--ink); font-family: var(--body-font); }
[data-testid="stMainBlockContainer"] { max-width: 640px !important; }
h1, h2, h3, h4 { font-family: var(--display-font) !important; font-weight: 500 !important; color: var(--ink) !important; }
h1 { font-size: 2.75rem !important; line-height: 1.1; font-style: italic; font-weight: 400 !important; }
h2 { font-size: 1.8rem !important; }
h3 { font-size: 1.35rem !important; }
.brand-mark { font-family: var(--display-font); font-style: italic; font-weight: 500; color: var(--ink); }
.instruction-card { font-family: var(--display-font); border-left: 2px solid var(--accent); font-size: 1.2rem !important; font-style: italic; background: transparent; }
.candidate-title { font-family: var(--display-font); font-size: 1.15rem; font-weight: 500; }
.stApp p, .stMarkdown p { font-size: 1.05rem; line-height: 1.7; }
""",
    },
    "default": {
        "label": "Plain",
        "css": """
:root {
    --bg: #FFFFFF;
    --bg-card: #FFFFFF;
    --ink: #262730;
    --ink-soft: #262730;
    --muted: #808495;
    --border: #E0E0E0;
    --border-strong: #C0C0C0;
    --accent: #FF4B4B;
    --accent-bg: #FFE5E5;
    --success: #21BA45;
    --warning: #F2C037;
    --danger: #FF4B4B;
    --display-font: 'Source Sans 3', sans-serif;
    --body-font: 'Source Sans 3', sans-serif;
    --mono-font: monospace;
}
""",
    },
}

DEFAULT_THEME = "editorial"


# Universal CSS that applies on top of every theme.
UNIVERSAL_CSS = """
/* --- Hide Streamlit chrome --- */
#MainMenu { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.stApp [data-testid="stSidebar"] { display: none; }

/* --- Main container --- */
[data-testid="stMainBlockContainer"] {
    max-width: 760px;
    padding-top: 2.5rem;
    padding-bottom: 6rem;
}

/* --- Theme switcher --- */
.theme-switcher {
    display: flex;
    gap: 0.4rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}

/* --- Brand strip --- */
.brand-strip {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    padding-bottom: 1rem;
    margin-bottom: 2.5rem;
    border-bottom: 1px solid var(--border);
}
.brand-mark {
    font-size: 1.15rem;
    letter-spacing: 0.01em;
}
.brand-meta {
    font-family: var(--mono-font);
    font-size: 0.78rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* --- Eyebrow --- */
.eyebrow {
    font-family: var(--mono-font);
    font-size: 0.72rem;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.15em;
    font-weight: 500;
    margin-bottom: 0.75rem;
}

/* --- Body --- */
.stApp p, .stMarkdown p { font-size: 1rem; line-height: 1.65; color: var(--ink-soft); }
code, .stMarkdown code {
    font-family: var(--mono-font) !important;
    background: var(--accent-bg) !important;
    color: var(--accent) !important;
    padding: 0.1em 0.4em !important;
    border-radius: 3px !important;
    font-size: 0.92em !important;
}

/* --- Buttons --- */
.stButton > button {
    font-family: var(--body-font) !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    border-radius: 4px !important;
    padding: 0.5rem 1.1rem !important;
    transition: all 0.15s ease !important;
    border: 1px solid var(--border-strong) !important;
    background: var(--bg-card) !important;
    color: var(--ink) !important;
    box-shadow: none !important;
}
.stButton > button:hover {
    border-color: var(--ink) !important;
    background: var(--ink) !important;
    color: var(--bg) !important;
}
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: var(--bg-card) !important;
    border-color: var(--accent) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--ink) !important;
    border-color: var(--ink) !important;
    color: var(--bg) !important;
}
.stButton > button:disabled {
    background: var(--border) !important;
    color: var(--muted) !important;
    border-color: var(--border) !important;
    cursor: not-allowed !important;
}

/* --- Inputs --- */
.stTextInput > div > div > input,
.stSelectbox > div > div {
    font-family: var(--body-font) !important;
    border-radius: 4px !important;
    border: 1px solid var(--border-strong) !important;
    background: var(--bg-card) !important;
    font-size: 1rem !important;
    color: var(--ink) !important;
}
.stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }
.stTextInput > label, .stSelectbox > label { font-family: var(--body-font) !important; font-size: 0.9rem !important; color: var(--ink-soft) !important; font-weight: 500 !important; }

/* --- Metrics --- */
[data-testid="stMetric"] { background: var(--bg-card); border: 1px solid var(--border); padding: 1.25rem 1.5rem; border-radius: 4px; }
[data-testid="stMetricLabel"] { font-family: var(--mono-font) !important; font-size: 0.72rem !important; color: var(--muted) !important; text-transform: uppercase !important; letter-spacing: 0.1em !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { font-family: var(--display-font) !important; font-weight: 600 !important; color: var(--ink) !important; }

/* --- Alerts --- */
div[data-testid="stAlertContainer"] {
    border-radius: 4px !important;
    border-left: 3px solid var(--accent) !important;
    font-family: var(--body-font) !important;
    background: var(--accent-bg) !important;
    color: var(--ink) !important;
}
div[data-testid="stAlertContainer"] * { color: var(--ink) !important; }

/* --- Candidate elements --- */
.candidate-title {
    font-size: 1.05rem;
    color: var(--ink);
    line-height: 1.35;
    margin-bottom: 0.35rem;
}
.candidate-position {
    font-family: var(--mono-font);
    font-size: 0.7rem;
    color: var(--muted);
    margin-bottom: 0.3rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* --- Expanders --- */
[data-testid="stExpander"] { border: none !important; background: transparent !important; box-shadow: none !important; }
[data-testid="stExpander"] > details > summary { background: transparent !important; padding: 0.3rem 0 !important; font-family: var(--mono-font) !important; font-size: 0.78rem !important; color: var(--muted) !important; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500 !important; }
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p { font-size: 0.92rem; color: var(--ink-soft); line-height: 1.55; margin: 0.5rem 0 0 0; }

/* --- Divider --- */
hr { border: none !important; border-top: 1px solid var(--border) !important; margin: 2rem 0 !important; }

/* --- Status badges --- */
.status-badge {
    display: inline-block;
    font-family: var(--mono-font);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-weight: 500;
}
.status-in-progress { background: var(--accent-bg); color: var(--warning); border: 1px solid var(--border-strong); }
.status-completed { background: var(--accent-bg); color: var(--success); border: 1px solid var(--border-strong); }
.status-expired { background: var(--accent-bg); color: var(--danger); border: 1px solid var(--border-strong); }
.status-abandoned { background: var(--border); color: var(--muted); }

/* --- Test mode banner --- */
.test-banner {
    background: var(--accent-bg);
    border-left: 3px solid var(--warning);
    color: var(--warning) !important;
    padding: 0.7rem 1rem;
    margin-bottom: 1.5rem;
    font-family: var(--mono-font);
    font-size: 0.85rem;
    border-radius: 4px;
}
.test-banner * { color: var(--warning) !important; }

/* --- Selection counter --- */
.selection-counter {
    display: inline-block;
    background: var(--ink);
    color: var(--bg) !important;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-family: var(--mono-font);
    font-size: 0.85rem;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
    font-weight: 500;
}
.selection-counter * { color: var(--bg) !important; }
.selection-counter-warn { background: var(--warning); }
.selection-counter-warn, .selection-counter-warn * { color: var(--bg) !important; }
.selection-counter-danger { background: var(--danger); }
.selection-counter-danger, .selection-counter-danger * { color: var(--bg) !important; }

/* --- Instruction card --- */
.instruction-card {
    padding: 1.25rem 1.5rem;
    margin: 1.25rem 0 2rem 0;
    font-size: 1.1rem;
    line-height: 1.5;
    color: var(--ink);
    border-radius: 4px;
}

/* --- Assignment row --- */
.assignment-id {
    font-family: var(--mono-font);
    font-size: 0.95rem;
    color: var(--ink);
    font-weight: 500;
}
.assignment-time {
    font-family: var(--mono-font);
    font-size: 0.78rem;
    color: var(--muted);
}

/* --- Theme switcher buttons (rendered as small buttons) --- */
.theme-switcher-label {
    font-family: var(--mono-font);
    font-size: 0.7rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-right: 0.4rem;
    margin-bottom: 0.5rem;
}

/* Theme switcher buttons: single line, smaller padding, tight */
button[data-testid="stBaseButton-secondary"][kind="secondary"],
button[data-testid="stBaseButton-primary"][kind="primary"] {
    white-space: nowrap !important;
}
[data-testid="stHorizontalBlock"] button {
    white-space: nowrap !important;
}
/* Make the theme switcher row visually distinct, like a segmented bar */
.stApp [data-testid="stHorizontalBlock"]:has(button[data-testid*="theme_btn"]) {
    margin-bottom: 1rem;
    padding: 0.5rem 0;
}
button[data-testid*="theme_btn"] {
    padding: 0.4rem 0.8rem !important;
    font-size: 0.82rem !important;
    min-width: 0 !important;
}
"""


# ----------------------------------------------------------------------------
# Supabase
# ----------------------------------------------------------------------------

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

sb = get_supabase()


# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------

def now_utc():
    return datetime.now(timezone.utc)


def generate_code():
    return "".join(secrets.choice(string.digits) for _ in range(CODE_LENGTH))


def generate_session_token():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def parse_ts(s):
    return datetime.fromisoformat(s)


def humanize_remaining(expires_at):
    remaining = expires_at - now_utc()
    if remaining.total_seconds() <= 0:
        return "expired"
    total_minutes = int(remaining.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def is_test_mode():
    return st.session_state.get("email") == TEST_EMAIL


def get_current_theme():
    """Theme from URL param or session state, falling back to default."""
    # Priority: URL param > session state > default
    theme_from_url = st.query_params.get("theme")
    if theme_from_url and theme_from_url in THEMES:
        st.session_state.theme = theme_from_url
        return theme_from_url
    if "theme" in st.session_state and st.session_state.theme in THEMES:
        return st.session_state.theme
    return DEFAULT_THEME


def set_theme(theme_name):
    if theme_name in THEMES:
        st.session_state.theme = theme_name
        st.query_params["theme"] = theme_name


def inject_theme_css():
    theme = get_current_theme()
    theme_css = THEMES[theme]["css"]
    full_css = f"<style>{theme_css}\n{UNIVERSAL_CSS}</style>"
    st.markdown(full_css, unsafe_allow_html=True)


def render_theme_switcher():
    """Render a compact inline theme switcher."""
    current = get_current_theme()
    theme_names = list(THEMES.keys())

    # Use generous column widths: label gets 2, each button gets 2, then padding
    n = len(theme_names)
    col_widths = [1.4] + [1.5] * n + [3.0]
    cols = st.columns(col_widths)
    with cols[0]:
        st.markdown(
            '<div class="theme-switcher-label" style="padding-top: 0.55rem; text-align: right;">THEME</div>',
            unsafe_allow_html=True,
        )
    for i, name in enumerate(theme_names):
        with cols[i + 1]:
            label = THEMES[name]["label"]
            is_current = (name == current)
            if st.button(
                label,
                key=f"theme_btn_{name}",
                disabled=is_current,
                type="primary" if is_current else "secondary",
                use_container_width=True,
            ):
                set_theme(name)
                st.rerun()


def render_brand_strip(extra=""):
    st.markdown(
        f"""
        <div class="brand-strip">
            <span class="brand-mark">Citation Annotator</span>
            <span class="brand-meta">{extra}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------------

def send_code_email(to_email, code):
    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": f"Your verification code: {code}",
            "html": f"""
                <p>Hello,</p>
                <p>Your verification code for the Citation Annotator study is:</p>
                <h2 style="font-family: monospace; letter-spacing: 4px;">{code}</h2>
                <p>This code is valid for {CODE_TTL_MINUTES} minutes.</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
            """,
        },
        timeout=10,
    )
    if r.status_code >= 400:
        st.error(f"Email send failed: {r.text}")
        return False
    return True


def store_verification_code(email, code):
    sb.table("verification_codes").delete().eq("email", email).execute()
    sb.table("verification_codes").insert({
        "email": email,
        "code": code,
        "expires_at": (now_utc() + timedelta(minutes=CODE_TTL_MINUTES)).isoformat(),
    }).execute()


def verify_code(email, code):
    res = sb.table("verification_codes").select("*").eq("email", email).eq("code", code).execute()
    if not res.data:
        return False
    if parse_ts(res.data[0]["expires_at"]) < now_utc():
        return False
    sb.table("verification_codes").delete().eq("email", email).execute()
    return True


def create_session(email):
    token = generate_session_token()
    sb.table("sessions").insert({
        "token": token,
        "email": email,
        "expires_at": (now_utc() + timedelta(days=SESSION_TTL_DAYS)).isoformat(),
    }).execute()
    return token


def lookup_session(token):
    res = sb.table("sessions").select("*").eq("token", token).execute()
    if not res.data:
        return None
    row = res.data[0]
    if parse_ts(row["expires_at"]) < now_utc():
        return None
    return row["email"]


def end_session(token):
    sb.table("sessions").delete().eq("token", token).execute()


def restore_session_from_url():
    if "email" in st.session_state:
        return
    token = st.query_params.get("session")
    if not token:
        return
    email = lookup_session(token)
    if email:
        st.session_state.email = email
        st.session_state.session_token = token


def log_in(email):
    token = create_session(email)
    st.session_state.email = email
    st.session_state.session_token = token
    st.query_params["session"] = token


def log_out():
    token = st.session_state.get("session_token")
    if token:
        end_session(token)
    # Preserve theme on logout
    saved_theme = st.session_state.get("theme")
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    if saved_theme:
        st.session_state.theme = saved_theme
    st.query_params.clear()
    if saved_theme:
        st.query_params["theme"] = saved_theme


# ----------------------------------------------------------------------------
# Onboarding
# ----------------------------------------------------------------------------

def is_onboarded(email):
    if email == TEST_EMAIL:
        return True
    res = sb.table("annotators").select("email").eq("email", email).execute()
    return bool(res.data)


def save_onboarding(email, data):
    sb.table("annotators").insert({
        "email": email,
        "full_name": data.get("full_name") or None,
        "affiliation": data["affiliation"],
        "career_stage": data["career_stage"],
        "research_area": data["research_area"],
        "kd_familiarity": data["kd_familiarity"],
    }).execute()


# ----------------------------------------------------------------------------
# Queue
# ----------------------------------------------------------------------------

def expire_overdue_assignments():
    sb.table("assignments").update({"status": "expired"}) \
        .eq("status", "in_progress") \
        .lt("expires_at", now_utc().isoformat()) \
        .execute()


def get_my_assignments(email):
    expire_overdue_assignments()
    res = sb.table("assignments").select("*").eq("annotator_email", email).order("assigned_at", desc=True).execute()
    return res.data


def count_in_progress(email):
    expire_overdue_assignments()
    res = sb.table("assignments").select("prompt_id", count="exact").eq("annotator_email", email).eq("status", "in_progress").execute()
    return res.count or 0


def find_available_prompt():
    expire_overdue_assignments()
    used = sb.table("assignments").select("prompt_id").in_("status", ["in_progress", "completed"]).execute()
    used_ids = {row["prompt_id"] for row in used.data}
    all_prompts = sb.table("prompts").select("id").execute()
    available = [row["id"] for row in all_prompts.data if row["id"] not in used_ids]
    if not available:
        return None
    return random.choice(available)


def request_new_prompt(email):
    if count_in_progress(email) >= MAX_IN_PROGRESS_PER_USER:
        return None, f"You already have {MAX_IN_PROGRESS_PER_USER} prompts in progress. Complete or abandon one first."
    prompt_id = find_available_prompt()
    if prompt_id is None:
        return None, "No prompts available right now. Please check back later."
    expires_at = now_utc() + timedelta(hours=ASSIGNMENT_TTL_HOURS)
    sb.table("assignments").insert({
        "annotator_email": email,
        "prompt_id": prompt_id,
        "assigned_at": now_utc().isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "in_progress",
    }).execute()
    return prompt_id, None


def abandon_assignment(email, prompt_id):
    sb.table("assignments").delete().eq("annotator_email", email).eq("prompt_id", prompt_id).execute()


def submit_response(email, prompt_id, cited_paper_ids):
    cands = sb.table("prompt_candidates").select("paper_id").eq("prompt_id", prompt_id).execute()
    cited_set = set(cited_paper_ids)
    rows = []
    for c in cands.data:
        pid = c["paper_id"]
        rows.append({
            "annotator_email": email,
            "prompt_id": prompt_id,
            "paper_id": pid,
            "cited": 1 if pid in cited_set else 0,
        })
    sb.table("responses").upsert(rows, on_conflict="annotator_email,prompt_id,paper_id").execute()
    sb.table("assignments").update({"status": "completed"}).eq("annotator_email", email).eq("prompt_id", prompt_id).execute()


def load_prompt(prompt_id):
    p = sb.table("prompts").select("*").eq("id", prompt_id).execute()
    if not p.data:
        return None
    prompt = p.data[0]
    cands = sb.table("prompt_candidates").select("position, paper_id, papers(id, title, abstract)").eq("prompt_id", prompt_id).order("position").execute()
    prompt["candidates"] = cands.data
    return prompt


def load_response(email, prompt_id):
    res = sb.table("responses").select("paper_id, cited").eq("annotator_email", email).eq("prompt_id", prompt_id).execute()
    return {r["paper_id"] for r in res.data if r["cited"] == 1}


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------

def login_page():
    render_theme_switcher()
    render_brand_strip("a study of citation patterns")
    st.markdown('<div class="eyebrow">SIGN IN</div>', unsafe_allow_html=True)
    st.markdown("# Welcome.")
    st.markdown("Enter your email to receive a 6-digit login code. Once verified, you'll stay signed in for 30 days on this browser.")
    st.markdown("<br>", unsafe_allow_html=True)

    if "pending_email" not in st.session_state:
        email = st.text_input("Email address", key="email_input").strip().lower()
        if st.button("Send code", type="primary", disabled=not email):
            if email == TEST_EMAIL:
                log_in(email)
                st.rerun()
                return
            code = generate_code()
            store_verification_code(email, code)
            if send_code_email(email, code):
                st.session_state.pending_email = email
                st.rerun()
        return

    pending_email = st.session_state.pending_email
    st.info(f"Code sent to **{pending_email}**. Check your inbox (and spam).")
    code = st.text_input("6-digit code", max_chars=6, key="code_input").strip()
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Verify", type="primary", disabled=len(code) != CODE_LENGTH):
            if verify_code(pending_email, code):
                log_in(pending_email)
                del st.session_state.pending_email
                st.rerun()
            else:
                st.error("Invalid or expired code. Try again or request a new one.")
    with col2:
        if st.button("Use a different email"):
            del st.session_state.pending_email
            st.rerun()


def consent_page():
    render_theme_switcher()
    render_brand_strip("before we begin")
    st.markdown('<div class="eyebrow">CONSENT</div>', unsafe_allow_html=True)
    st.markdown("# Welcome to the study.")
    st.markdown(CONSENT_TEXT)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("I understand, let's continue", type="primary"):
        st.session_state.consent_given = True
        st.rerun()


def onboarding_page():
    render_theme_switcher()
    render_brand_strip("step 2 of 2")
    st.markdown('<div class="eyebrow">YOUR BACKGROUND</div>', unsafe_allow_html=True)
    st.markdown("# A few quick questions.")
    st.markdown("This helps us describe the participant pool in aggregate when we write up the results. Never tied to individuals.")
    st.markdown("<br>", unsafe_allow_html=True)

    full_name = st.text_input("Full name (optional)")
    affiliation = st.text_input("Affiliation (institution or company)")
    career_stage = st.selectbox("Career stage", [""] + CAREER_STAGES)
    research_area = st.text_input("Primary research area (e.g., ML, NLP, vision)")
    kd_familiarity = st.selectbox("Familiarity with knowledge distillation literature", [""] + KD_FAMILIARITY_OPTIONS)

    required = [affiliation, career_stage, research_area, kd_familiarity]
    can_submit = all(x for x in required)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Continue to the study", type="primary", disabled=not can_submit):
        save_onboarding(st.session_state.email, {
            "full_name": full_name.strip(),
            "affiliation": affiliation.strip(),
            "career_stage": career_stage,
            "research_area": research_area.strip(),
            "kd_familiarity": kd_familiarity,
        })
        st.rerun()


def _get_sample_prompt_id():
    res = sb.table("prompts").select("id").limit(1).execute()
    return res.data[0]["id"] if res.data else None


def dashboard_page():
    email = st.session_state.email
    test = is_test_mode()

    render_theme_switcher()
    render_brand_strip(email)

    if test:
        st.markdown('<div class="test-banner">TEST MODE — co-author preview. No data is saved.</div>', unsafe_allow_html=True)

    st.markdown('<div class="eyebrow">DASHBOARD</div>', unsafe_allow_html=True)
    st.markdown("# Your work.")

    cols = st.columns([4, 1])
    with cols[1]:
        if st.button("Log out"):
            log_out()
            st.rerun()

    if test:
        st.markdown("---")
        st.markdown("Preview the annotation interface with a sample prompt.")
        sample_id = _get_sample_prompt_id()
        if sample_id and st.button("Open sample prompt", type="primary"):
            st.session_state.current_prompt_id = sample_id
            st.rerun()
        return

    assignments = get_my_assignments(email)
    in_progress_count = sum(1 for a in assignments if a["status"] == "in_progress")
    completed_count = sum(1 for a in assignments if a["status"] == "completed")

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("Completed", completed_count)
    col2.metric("In progress", in_progress_count)
    col3.metric("Maximum at once", MAX_IN_PROGRESS_PER_USER)

    st.markdown("<br>", unsafe_allow_html=True)
    request_disabled = in_progress_count >= MAX_IN_PROGRESS_PER_USER
    if st.button("Request a new prompt", type="primary", disabled=request_disabled):
        prompt_id, err = request_new_prompt(email)
        if err:
            st.error(err)
        else:
            st.session_state.current_prompt_id = prompt_id
            st.rerun()

    if request_disabled:
        st.caption(f"You have the maximum {MAX_IN_PROGRESS_PER_USER} prompts in progress. Complete or abandon one to get more.")

    st.markdown("---")
    st.markdown('<div class="eyebrow">YOUR PROMPTS</div>', unsafe_allow_html=True)
    st.markdown("### Recent activity")

    if not assignments:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("No prompts yet. Click 'Request a new prompt' above to get started.")
        return

    status_order = {"in_progress": 0, "completed": 1, "expired": 2, "abandoned": 3}
    assignments_sorted = sorted(assignments, key=lambda a: (status_order.get(a["status"], 99), a["assigned_at"]))

    for a in assignments_sorted:
        status = a["status"]
        prompt_id = a["prompt_id"]
        if status == "in_progress":
            expires_at = parse_ts(a["expires_at"])
            time_text = humanize_remaining(expires_at) + " remaining"
            badge_cls, badge_text = "status-in-progress", "IN PROGRESS"
        elif status == "completed":
            time_text = "Submitted"
            badge_cls, badge_text = "status-completed", "COMPLETED"
        elif status == "expired":
            time_text = "Lease expired"
            badge_cls, badge_text = "status-expired", "EXPIRED"
        else:
            time_text = "Abandoned"
            badge_cls, badge_text = "status-abandoned", "ABANDONED"

        c1, c2, c3 = st.columns([2, 3, 1])
        with c1:
            st.markdown(
                f'<div class="assignment-id">{prompt_id}</div>'
                f'<div><span class="status-badge {badge_cls}">{badge_text}</span></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f'<div class="assignment-time" style="padding-top: 0.4rem;">{time_text}</div>', unsafe_allow_html=True)
        with c3:
            if status in ("in_progress", "completed"):
                btn_label = "Review →" if status == "completed" else "Open →"
                if st.button(btn_label, key=f"open_{prompt_id}"):
                    st.session_state.current_prompt_id = prompt_id
                    st.rerun()
        st.markdown('<div style="border-bottom: 1px solid var(--border); margin: 0.5rem 0;"></div>', unsafe_allow_html=True)


def annotation_page():
    email = st.session_state.email
    test = is_test_mode()
    prompt_id = st.session_state.current_prompt_id

    prompt = load_prompt(prompt_id)
    if not prompt:
        st.error("Prompt not found.")
        if st.button("Back to dashboard"):
            del st.session_state.current_prompt_id
            st.rerun()
        return

    assignment = None
    if not test:
        res = sb.table("assignments").select("*").eq("annotator_email", email).eq("prompt_id", prompt_id).execute()
        if res.data:
            assignment = res.data[0]

    read_only = (assignment is not None and assignment["status"] != "in_progress")
    expired = (assignment is not None and assignment["status"] == "expired")

    time_meta = ""
    if assignment and assignment["status"] == "in_progress":
        time_meta = humanize_remaining(parse_ts(assignment['expires_at'])) + " remaining"
    elif read_only:
        time_meta = "review mode"

    render_theme_switcher()
    render_brand_strip(f"{prompt_id} — {time_meta}" if time_meta else prompt_id)

    if test:
        st.markdown('<div class="test-banner">TEST MODE — nothing will be saved.</div>', unsafe_allow_html=True)

    if st.button("← Back to dashboard"):
        del st.session_state.current_prompt_id
        for k in list(st.session_state.keys()):
            if k.startswith(f"sel_{prompt_id}_") or k == f"selected_{prompt_id}":
                del st.session_state[k]
        st.rerun()

    st.markdown('<div class="eyebrow">YOUR TASK</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="instruction-card">{prompt["instruction"]}</div>', unsafe_allow_html=True)

    sel_key = f"selected_{prompt_id}"
    pre_cited = set()
    if read_only:
        pre_cited = load_response(email, prompt_id)
    if sel_key not in st.session_state:
        st.session_state[sel_key] = set(pre_cited) if read_only else set()
    selected = st.session_state[sel_key]

    n_selected = len(selected)
    if n_selected > CITATION_CAP:
        st.markdown(
            f'<div class="selection-counter selection-counter-danger">'
            f'<span style="color: inherit;">{n_selected} / {CITATION_CAP} — reduce to {CITATION_CAP} or fewer</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif n_selected == CITATION_CAP:
        st.markdown(
            f'<div class="selection-counter selection-counter-warn">'
            f'<span style="color: inherit;">{n_selected} / {CITATION_CAP} — cap reached</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="selection-counter">'
            f'<span style="color: inherit;">SELECTED &nbsp; {n_selected} / {CITATION_CAP}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if expired:
        st.error("This assignment has expired. You can no longer submit.")
    elif read_only:
        st.success("This prompt was already completed — viewing in read-only mode.")

    seed_str = f"{email}_{prompt_id}"
    rng = random.Random(hash(seed_str) % (2**32))
    candidates = list(prompt["candidates"])
    rng.shuffle(candidates)

    st.markdown('<div class="eyebrow">CANDIDATE PAPERS</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    for idx, c in enumerate(candidates):
        paper = c["papers"]
        paper_id = paper["id"]
        title = paper["title"]
        abstract = paper["abstract"]
        is_selected = paper_id in selected

        cols = st.columns([1, 20])
        with cols[0]:
            cb_key = f"cb_{prompt_id}_{paper_id}"
            checked = st.checkbox(
                "Cite", key=cb_key, value=is_selected,
                label_visibility="collapsed",
                disabled=read_only or expired,
            )
            if not read_only and not expired:
                if checked:
                    selected.add(paper_id)
                else:
                    selected.discard(paper_id)
        with cols[1]:
            st.markdown(
                f'<div class="candidate-position">№ {idx + 1:02d}</div>'
                f'<div class="candidate-title">{title}</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Read abstract"):
                st.markdown(abstract)
        st.markdown('<div style="margin-bottom: 0.4rem;"></div>', unsafe_allow_html=True)

    st.session_state[sel_key] = selected

    if read_only or expired:
        return

    st.markdown("---")
    n_selected = len(selected)
    can_submit = (1 <= n_selected <= CITATION_CAP)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Submit", type="primary", disabled=not can_submit):
            if test:
                st.success("Submission previewed (test mode — nothing saved).")
                st.balloons()
            else:
                submit_response(email, prompt_id, list(selected))
                st.success("Submitted. Returning to dashboard.")
                del st.session_state.current_prompt_id
                del st.session_state[sel_key]
                st.rerun()
    with col2:
        if not test:
            if st.button("Abandon this prompt"):
                if st.session_state.get(f"confirm_abandon_{prompt_id}"):
                    abandon_assignment(email, prompt_id)
                    del st.session_state.current_prompt_id
                    if sel_key in st.session_state:
                        del st.session_state[sel_key]
                    st.session_state.pop(f"confirm_abandon_{prompt_id}", None)
                    st.rerun()
                else:
                    st.session_state[f"confirm_abandon_{prompt_id}"] = True
                    st.warning("Click 'Abandon this prompt' again to confirm.")


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Citation Annotator",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    inject_theme_css()
    restore_session_from_url()

    if "email" not in st.session_state:
        login_page()
        return

    email = st.session_state.email
    test = is_test_mode()

    if test:
        if "current_prompt_id" in st.session_state:
            annotation_page()
        else:
            dashboard_page()
        return

    if not is_onboarded(email):
        if not st.session_state.get("consent_given"):
            consent_page()
            return
        onboarding_page()
        return

    if "current_prompt_id" in st.session_state:
        annotation_page()
    else:
        dashboard_page()


if __name__ == "__main__":
    main()
