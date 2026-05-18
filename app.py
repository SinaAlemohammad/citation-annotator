"""
Citation Annotator: full app, styled.

Flow:
  1. Login (email + OTP via Resend)
  2. Consent screen (first visit only)
  3. Onboarding survey (first visit only)
  4. Dashboard (list of assignments)
  5. Annotation page (per prompt)

Test mode (test@test.com): skip auth, skip consent, skip onboarding,
show a test-mode banner, do not save anything.
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
# Custom styling
# ----------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --bg: #FAF8F3;
    --bg-card: #FFFFFF;
    --ink: #1A1A1A;
    --ink-soft: #3A3530;
    --muted: #6B6560;
    --border: #E8E2D5;
    --border-strong: #D4CCB8;
    --accent: #A33B20;
    --accent-soft: #C25A3D;
    --accent-bg: #F5E8E0;
    --success: #2E6B3E;
    --warning: #B5811D;
    --danger: #A33B20;
}

/* --- Base --- */
.stApp {
    background: var(--bg);
    color: var(--ink);
    font-family: 'IBM Plex Sans', sans-serif;
}

.stApp [data-testid="stSidebar"] { display: none; }

/* Main container */
[data-testid="stMainBlockContainer"] {
    max-width: 760px;
    padding-top: 3rem;
    padding-bottom: 6rem;
}

/* --- Typography --- */
.stApp, .stApp p, .stApp label, .stApp div {
    font-family: 'IBM Plex Sans', sans-serif;
    color: var(--ink);
}

h1, h2, h3, h4 {
    font-family: 'Fraunces', serif !important;
    font-weight: 500 !important;
    color: var(--ink) !important;
    letter-spacing: -0.01em;
}

h1 { font-size: 2.5rem !important; line-height: 1.15; margin-bottom: 0.5rem !important; }
h2 { font-size: 1.75rem !important; line-height: 1.2; }
h3 { font-size: 1.3rem !important; }

/* Body text */
p, .stMarkdown p {
    font-size: 1rem;
    line-height: 1.65;
    color: var(--ink-soft);
}

code, .stMarkdown code {
    font-family: 'IBM Plex Mono', monospace !important;
    background: var(--accent-bg) !important;
    color: var(--accent) !important;
    padding: 0.1em 0.4em !important;
    border-radius: 3px !important;
    font-size: 0.92em !important;
}

/* --- Header brand strip --- */
.brand-strip {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    padding-bottom: 1rem;
    margin-bottom: 2.5rem;
    border-bottom: 1px solid var(--border);
}
.brand-mark {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 1.15rem;
    color: var(--accent);
    letter-spacing: 0.02em;
}
.brand-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* --- Eyebrow label --- */
.eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.15em;
    font-weight: 500;
    margin-bottom: 0.75rem;
}

/* --- Buttons --- */
.stButton > button {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    border-radius: 2px !important;
    padding: 0.6rem 1.5rem !important;
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
    font-family: 'IBM Plex Sans', sans-serif !important;
    border-radius: 2px !important;
    border: 1px solid var(--border-strong) !important;
    background: var(--bg-card) !important;
    font-size: 1rem !important;
    color: var(--ink) !important;
}

.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}

.stTextInput > label, .stSelectbox > label {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.9rem !important;
    color: var(--ink-soft) !important;
    font-weight: 500 !important;
}

/* --- Metrics --- */
[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 1.25rem 1.5rem;
    border-radius: 2px;
}
[data-testid="stMetricLabel"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.72rem !important;
    color: var(--muted) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Fraunces', serif !important;
    font-weight: 500 !important;
    color: var(--ink) !important;
}

/* --- Info / warning / error / success boxes --- */
div[data-testid="stAlertContainer"] {
    border-radius: 2px !important;
    border-left: 3px solid var(--accent) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
}

/* Hide default streamlit chrome */
#MainMenu { visibility: hidden; }
header[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* --- Candidate card --- */
.candidate-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 1.1rem 1.25rem;
    margin-bottom: 0.6rem;
    transition: border-color 0.15s ease;
}
.candidate-card:hover {
    border-color: var(--border-strong);
}
.candidate-card-selected {
    border-color: var(--accent) !important;
    background: var(--accent-bg);
}
.candidate-title {
    font-family: 'Fraunces', serif;
    font-weight: 500;
    font-size: 1.05rem;
    color: var(--ink);
    line-height: 1.35;
    margin-bottom: 0.35rem;
}
.candidate-position {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: var(--muted);
    margin-bottom: 0.3rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* Streamlit checkbox restyle */
.stCheckbox > label {
    font-family: 'IBM Plex Sans', sans-serif !important;
}
.stCheckbox > label > div[data-testid="stMarkdownContainer"] {
    display: none;
}

/* Expander for abstracts */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.85rem !important;
    color: var(--muted) !important;
    font-weight: 400 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
[data-testid="stExpander"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stExpander"] > details {
    background: transparent;
    border: none;
}
[data-testid="stExpander"] > details > summary {
    background: transparent !important;
    padding: 0.3rem 0 !important;
}
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.92rem;
    color: var(--ink-soft);
    line-height: 1.55;
    margin: 0.5rem 0 0 0;
}

/* Section divider */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 2rem 0 !important;
}

/* --- Status badges --- */
.status-badge {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.2rem 0.5rem;
    border-radius: 2px;
    font-weight: 500;
}
.status-in-progress { background: #FFF4E0; color: var(--warning); border: 1px solid #F0DBB0; }
.status-completed { background: #E5F0E8; color: var(--success); border: 1px solid #C5DCCC; }
.status-expired { background: #F2DDD7; color: var(--danger); border: 1px solid #DDB8AC; }
.status-abandoned { background: var(--border); color: var(--muted); }

/* --- Test mode banner --- */
.test-banner {
    background: #FFF4E0;
    border: 1px solid #F0DBB0;
    border-left: 3px solid var(--warning);
    color: var(--warning);
    padding: 0.7rem 1rem;
    margin-bottom: 1.5rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    border-radius: 2px;
}

/* --- Selected counter pill --- */
.selection-counter {
    display: inline-block;
    background: var(--ink);
    color: var(--bg);
    padding: 0.5rem 1rem;
    border-radius: 2px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
}
.selection-counter-warn { background: var(--warning); }
.selection-counter-danger { background: var(--danger); }

/* --- Assignment row --- */
.assignment-row {
    padding: 1rem 0;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.assignment-id {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.95rem;
    color: var(--ink);
    font-weight: 500;
}
.assignment-time {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: var(--muted);
}

/* --- Prompt instruction card --- */
.instruction-card {
    background: var(--bg-card);
    border-left: 3px solid var(--accent);
    padding: 1.25rem 1.5rem;
    margin: 1.5rem 0 2rem 0;
    font-family: 'Fraunces', serif;
    font-size: 1.1rem;
    line-height: 1.5;
    color: var(--ink);
}

/* Small caps */
.small-caps {
    font-variant: small-caps;
    letter-spacing: 0.05em;
}
</style>
"""


# ----------------------------------------------------------------------------
# Supabase client
# ----------------------------------------------------------------------------

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

sb = get_supabase()

# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def generate_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(CODE_LENGTH))


def generate_session_token() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def humanize_remaining(expires_at: datetime) -> str:
    remaining = expires_at - now_utc()
    if remaining.total_seconds() <= 0:
        return "expired"
    total_minutes = int(remaining.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def is_test_mode() -> bool:
    return st.session_state.get("email") == TEST_EMAIL


def render_brand_strip(extra: str = ""):
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
# Auth (email OTP)
# ----------------------------------------------------------------------------

def send_code_email(to_email: str, code: str) -> bool:
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


def store_verification_code(email: str, code: str):
    sb.table("verification_codes").delete().eq("email", email).execute()
    sb.table("verification_codes").insert({
        "email": email,
        "code": code,
        "expires_at": (now_utc() + timedelta(minutes=CODE_TTL_MINUTES)).isoformat(),
    }).execute()


def verify_code(email: str, code: str) -> bool:
    res = (sb.table("verification_codes")
             .select("*")
             .eq("email", email)
             .eq("code", code)
             .execute())
    if not res.data:
        return False
    if parse_ts(res.data[0]["expires_at"]) < now_utc():
        return False
    sb.table("verification_codes").delete().eq("email", email).execute()
    return True


def create_session(email: str) -> str:
    token = generate_session_token()
    sb.table("sessions").insert({
        "token": token,
        "email": email,
        "expires_at": (now_utc() + timedelta(days=SESSION_TTL_DAYS)).isoformat(),
    }).execute()
    return token


def lookup_session(token: str):
    res = sb.table("sessions").select("*").eq("token", token).execute()
    if not res.data:
        return None
    row = res.data[0]
    if parse_ts(row["expires_at"]) < now_utc():
        return None
    return row["email"]


def end_session(token: str):
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


def log_in(email: str):
    token = create_session(email)
    st.session_state.email = email
    st.session_state.session_token = token
    st.query_params["session"] = token


def log_out():
    token = st.session_state.get("session_token")
    if token:
        end_session(token)
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.query_params.clear()


# ----------------------------------------------------------------------------
# Onboarding
# ----------------------------------------------------------------------------

def is_onboarded(email: str) -> bool:
    if email == TEST_EMAIL:
        return True
    res = sb.table("annotators").select("email").eq("email", email).execute()
    return bool(res.data)


def save_onboarding(email: str, data: dict):
    sb.table("annotators").insert({
        "email": email,
        "full_name": data.get("full_name") or None,
        "affiliation": data["affiliation"],
        "career_stage": data["career_stage"],
        "research_area": data["research_area"],
        "kd_familiarity": data["kd_familiarity"],
    }).execute()


# ----------------------------------------------------------------------------
# Queue / lease logic
# ----------------------------------------------------------------------------

def expire_overdue_assignments():
    sb.table("assignments").update({"status": "expired"}) \
        .eq("status", "in_progress") \
        .lt("expires_at", now_utc().isoformat()) \
        .execute()


def get_my_assignments(email: str):
    expire_overdue_assignments()
    res = (sb.table("assignments")
             .select("*")
             .eq("annotator_email", email)
             .order("assigned_at", desc=True)
             .execute())
    return res.data


def count_in_progress(email: str) -> int:
    expire_overdue_assignments()
    res = (sb.table("assignments")
             .select("prompt_id", count="exact")
             .eq("annotator_email", email)
             .eq("status", "in_progress")
             .execute())
    return res.count or 0


def find_available_prompt():
    expire_overdue_assignments()
    used = (sb.table("assignments")
              .select("prompt_id")
              .in_("status", ["in_progress", "completed"])
              .execute())
    used_ids = {row["prompt_id"] for row in used.data}

    all_prompts = sb.table("prompts").select("id").execute()
    available = [row["id"] for row in all_prompts.data if row["id"] not in used_ids]

    if not available:
        return None
    return random.choice(available)


def request_new_prompt(email: str):
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


def abandon_assignment(email: str, prompt_id: str):
    sb.table("assignments").delete() \
        .eq("annotator_email", email) \
        .eq("prompt_id", prompt_id) \
        .execute()


def submit_response(email: str, prompt_id: str, cited_paper_ids: list):
    cands = (sb.table("prompt_candidates")
               .select("paper_id")
               .eq("prompt_id", prompt_id)
               .execute())
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
    sb.table("assignments").update({"status": "completed"}) \
        .eq("annotator_email", email) \
        .eq("prompt_id", prompt_id) \
        .execute()


def load_prompt(prompt_id: str):
    p = sb.table("prompts").select("*").eq("id", prompt_id).execute()
    if not p.data:
        return None
    prompt = p.data[0]
    cands = (sb.table("prompt_candidates")
               .select("position, paper_id, papers(id, title, abstract)")
               .eq("prompt_id", prompt_id)
               .order("position")
               .execute())
    prompt["candidates"] = cands.data
    return prompt


def load_response(email: str, prompt_id: str) -> set:
    res = (sb.table("responses")
             .select("paper_id, cited")
             .eq("annotator_email", email)
             .eq("prompt_id", prompt_id)
             .execute())
    return {r["paper_id"] for r in res.data if r["cited"] == 1}


# ----------------------------------------------------------------------------
# UI: Login page
# ----------------------------------------------------------------------------

def login_page():
    render_brand_strip("a study of citation patterns")

    st.markdown('<div class="eyebrow">SIGN IN</div>', unsafe_allow_html=True)
    st.markdown("# Welcome.")
    st.markdown(
        "Enter your email to receive a 6-digit login code. Once verified, "
        "you'll stay signed in for 30 days on this browser."
    )

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


# ----------------------------------------------------------------------------
# UI: Consent page
# ----------------------------------------------------------------------------

def consent_page():
    render_brand_strip("before we begin")
    st.markdown('<div class="eyebrow">CONSENT</div>', unsafe_allow_html=True)
    st.markdown("# Welcome to the study.")
    st.markdown(CONSENT_TEXT)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("I understand, let's continue", type="primary"):
        st.session_state.consent_given = True
        st.rerun()


# ----------------------------------------------------------------------------
# UI: Onboarding page
# ----------------------------------------------------------------------------

def onboarding_page():
    render_brand_strip("step 2 of 2")
    st.markdown('<div class="eyebrow">YOUR BACKGROUND</div>', unsafe_allow_html=True)
    st.markdown("# A few quick questions.")
    st.markdown(
        "This helps us describe the participant pool in aggregate when we "
        "write up the results. Never tied to individuals."
    )
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


# ----------------------------------------------------------------------------
# UI: Dashboard
# ----------------------------------------------------------------------------

def _get_sample_prompt_id():
    res = sb.table("prompts").select("id").limit(1).execute()
    return res.data[0]["id"] if res.data else None


def dashboard_page():
    email = st.session_state.email
    test = is_test_mode()

    render_brand_strip(email)

    if test:
        st.markdown(
            '<div class="test-banner">TEST MODE — co-author preview. No data is saved.</div>',
            unsafe_allow_html=True,
        )

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

    # Real mode
    assignments = get_my_assignments(email)
    in_progress_count = sum(1 for a in assignments if a["status"] == "in_progress")
    completed_count = sum(1 for a in assignments if a["status"] == "completed")

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("Completed", completed_count)
    col2.metric("In progress", in_progress_count)
    col3.metric("Maximum at once", MAX_IN_PROGRESS_PER_USER)

    st.markdown("<br>", unsafe_allow_html=True)

    # Request a new prompt
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
    assignments_sorted = sorted(
        assignments, key=lambda a: (status_order.get(a["status"], 99), a["assigned_at"])
    )

    for a in assignments_sorted:
        status = a["status"]
        prompt_id = a["prompt_id"]
        if status == "in_progress":
            expires_at = parse_ts(a["expires_at"])
            time_text = humanize_remaining(expires_at) + " remaining"
            badge_cls = "status-in-progress"
            badge_text = "IN PROGRESS"
        elif status == "completed":
            time_text = "Submitted"
            badge_cls = "status-completed"
            badge_text = "COMPLETED"
        elif status == "expired":
            time_text = "Lease expired"
            badge_cls = "status-expired"
            badge_text = "EXPIRED"
        else:
            time_text = "Abandoned"
            badge_cls = "status-abandoned"
            badge_text = "ABANDONED"

        c1, c2, c3 = st.columns([2, 3, 1])
        with c1:
            st.markdown(
                f'<div class="assignment-id">{prompt_id}</div>'
                f'<div><span class="status-badge {badge_cls}">{badge_text}</span></div>',
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f'<div class="assignment-time" style="padding-top: 0.4rem;">{time_text}</div>',
                unsafe_allow_html=True,
            )
        with c3:
            if status in ("in_progress", "completed"):
                btn_label = "Review →" if status == "completed" else "Open →"
                if st.button(btn_label, key=f"open_{prompt_id}"):
                    st.session_state.current_prompt_id = prompt_id
                    st.rerun()
        st.markdown('<div style="border-bottom: 1px solid var(--border); margin: 0.5rem 0;"></div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# UI: Annotation page
# ----------------------------------------------------------------------------

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
        res = (sb.table("assignments")
                 .select("*")
                 .eq("annotator_email", email)
                 .eq("prompt_id", prompt_id)
                 .execute())
        if res.data:
            assignment = res.data[0]

    read_only = (assignment is not None and assignment["status"] != "in_progress")
    expired = (assignment is not None and assignment["status"] == "expired")

    # Header strip
    time_meta = ""
    if assignment and assignment["status"] == "in_progress":
        time_meta = humanize_remaining(parse_ts(assignment['expires_at'])) + " remaining"
    elif read_only:
        time_meta = "review mode"

    render_brand_strip(f"{prompt_id} — {time_meta}" if time_meta else prompt_id)

    if test:
        st.markdown(
            '<div class="test-banner">TEST MODE — nothing will be saved.</div>',
            unsafe_allow_html=True,
        )

    if st.button("← Back to dashboard"):
        del st.session_state.current_prompt_id
        for k in list(st.session_state.keys()):
            if k.startswith(f"sel_{prompt_id}_") or k == f"selected_{prompt_id}":
                del st.session_state[k]
        st.rerun()

    # Instruction card
    st.markdown('<div class="eyebrow">YOUR TASK</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="instruction-card">{prompt["instruction"]}</div>',
        unsafe_allow_html=True,
    )

    # Selection state
    sel_key = f"selected_{prompt_id}"
    pre_cited = set()
    if read_only:
        pre_cited = load_response(email, prompt_id)
    if sel_key not in st.session_state:
        st.session_state[sel_key] = set(pre_cited) if read_only else set()
    selected = st.session_state[sel_key]

    # Counter
    n_selected = len(selected)
    if n_selected > CITATION_CAP:
        st.markdown(
            f'<div class="selection-counter selection-counter-danger">'
            f'{n_selected} / {CITATION_CAP} — reduce to {CITATION_CAP} or fewer'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif n_selected == CITATION_CAP:
        st.markdown(
            f'<div class="selection-counter selection-counter-warn">'
            f'{n_selected} / {CITATION_CAP} — cap reached'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="selection-counter">SELECTED &nbsp; {n_selected} / {CITATION_CAP}</div>',
            unsafe_allow_html=True,
        )

    if expired:
        st.error("This assignment has expired. You can no longer submit.")
    elif read_only:
        st.success("This prompt was already completed — viewing in read-only mode.")

    # Candidates
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
        card_class = "candidate-card-selected" if is_selected else ""

        cols = st.columns([1, 20])
        with cols[0]:
            cb_key = f"cb_{prompt_id}_{paper_id}"
            checked = st.checkbox(
                "Cite",
                key=cb_key,
                value=is_selected,
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
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
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
