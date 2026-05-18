"""
Citation Annotator: full app.

Flow:
  1. Login (email + OTP via Resend)        -- existing
  2. Consent screen (first visit only)     -- new
  3. Onboarding survey (first visit only)  -- new
  4. Dashboard (list of assignments)       -- new
  5. Annotation page (per prompt)          -- new

Test mode (test@test.com): skip auth, skip consent, skip onboarding,
show a yellow "test mode" banner, do not save anything to assignments/responses.
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
    """Convert a future timestamp into 'Xh Ym left'."""
    remaining = expires_at - now_utc()
    if remaining.total_seconds() <= 0:
        return "expired"
    total_minutes = int(remaining.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m left"
    return f"{minutes}m left"


def is_test_mode() -> bool:
    return st.session_state.get("email") == TEST_EMAIL


# ----------------------------------------------------------------------------
# Auth (email OTP)
# ----------------------------------------------------------------------------

def send_code_email(to_email: str, code: str) -> bool:
    """Send the OTP code via Resend."""
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
    """Flip any in_progress assignments past their expires_at to 'expired'."""
    sb.table("assignments").update({"status": "expired"}) \
        .eq("status", "in_progress") \
        .lt("expires_at", now_utc().isoformat()) \
        .execute()


def get_my_assignments(email: str):
    """Return the user's assignments with status, ordered by recent first."""
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


def find_available_prompt() -> str | None:
    """Find a prompt nobody has in-progress or completed. Returns prompt_id or None."""
    expire_overdue_assignments()
    # Get all prompts that are NOT in the unavailable set.
    # "Unavailable" = at least one in_progress or completed assignment exists.
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


def request_new_prompt(email: str) -> tuple[str | None, str | None]:
    """Assign a new prompt to the user. Returns (prompt_id, error_message)."""
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
    """Delete the assignment so the prompt goes back to the pool."""
    sb.table("assignments").delete() \
        .eq("annotator_email", email) \
        .eq("prompt_id", prompt_id) \
        .execute()


def submit_response(email: str, prompt_id: str, cited_paper_ids: list):
    """Write 30 rows to responses (one per candidate), flip assignment to completed."""
    # First, load the 30 candidate paper IDs for this prompt
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
    # Upsert (in case of accidental resubmit)
    sb.table("responses").upsert(rows, on_conflict="annotator_email,prompt_id,paper_id").execute()
    sb.table("assignments").update({"status": "completed"}) \
        .eq("annotator_email", email) \
        .eq("prompt_id", prompt_id) \
        .execute()


def load_prompt(prompt_id: str):
    """Load a prompt and its 30 candidates with paper details."""
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
    """Return set of paper_ids the user cited on this prompt (for review)."""
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
    st.title("Citation Annotator")
    st.markdown(
        "Welcome. Enter your email to receive a 6-digit login code. "
        "Once verified, you'll stay logged in for 30 days on this browser."
    )

    if "pending_email" not in st.session_state:
        email = st.text_input("Email", key="email_input").strip().lower()
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
    st.title("Welcome")
    st.markdown(CONSENT_TEXT)
    st.markdown("---")
    if st.button("I understand, let's continue", type="primary"):
        st.session_state.consent_given = True
        st.rerun()


# ----------------------------------------------------------------------------
# UI: Onboarding page
# ----------------------------------------------------------------------------

def onboarding_page():
    st.title("A few quick questions")
    st.markdown("This information helps us describe the participant pool in the paper. Aggregate only, never tied to individuals.")
    st.markdown("---")

    full_name = st.text_input("Full name (optional)")
    affiliation = st.text_input("Affiliation (institution or company) *")
    career_stage = st.selectbox("Career stage *", [""] + CAREER_STAGES)
    research_area = st.text_input("Primary research area * (e.g., ML, NLP, vision)")
    kd_familiarity = st.selectbox("Familiarity with knowledge distillation literature *", [""] + KD_FAMILIARITY_OPTIONS)

    required = [affiliation, career_stage, research_area, kd_familiarity]
    can_submit = all(x for x in required)

    if st.button("Continue", type="primary", disabled=not can_submit):
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

def dashboard_page():
    email = st.session_state.email
    test = is_test_mode()

    st.title("Citation Annotator")
    if test:
        st.warning("🧪 **Test mode.** This is a preview for co-authors. Nothing is saved.")

    cols = st.columns([4, 1])
    with cols[0]:
        st.markdown(f"Logged in as **{email}**")
    with cols[1]:
        if st.button("Log out"):
            log_out()
            st.rerun()

    st.markdown("---")

    if test:
        # In test mode, give a fixed sample prompt to look at
        st.subheader("Sample prompt (test mode)")
        st.markdown("Click below to preview the annotation page with a sample prompt.")
        sample_id = _get_sample_prompt_id()
        if sample_id and st.button("Open sample prompt", type="primary"):
            st.session_state.current_prompt_id = sample_id
            st.rerun()
        return

    # Real mode
    assignments = get_my_assignments(email)
    in_progress_count = sum(1 for a in assignments if a["status"] == "in_progress")
    completed_count = sum(1 for a in assignments if a["status"] == "completed")

    col1, col2, col3 = st.columns(3)
    col1.metric("Completed", completed_count)
    col2.metric("In progress", in_progress_count)
    col3.metric("Max in progress", MAX_IN_PROGRESS_PER_USER)

    st.markdown("---")

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
    st.subheader("Your prompts")

    if not assignments:
        st.info("No prompts assigned yet. Click 'Request a new prompt' to start.")
        return

    # Sort: in_progress first, then completed, then expired/abandoned
    status_order = {"in_progress": 0, "completed": 1, "expired": 2, "abandoned": 3}
    assignments_sorted = sorted(assignments, key=lambda a: (status_order.get(a["status"], 99), a["assigned_at"]))

    for a in assignments_sorted:
        status = a["status"]
        prompt_id = a["prompt_id"]
        if status == "in_progress":
            expires_at = parse_ts(a["expires_at"])
            label = f"🟡 In progress — {humanize_remaining(expires_at)}"
        elif status == "completed":
            label = "🟢 Completed"
        elif status == "expired":
            label = "🔴 Expired"
        else:
            label = "⚪ Abandoned"

        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{prompt_id}** — {label}")
        with c2:
            btn_label = "Review" if status == "completed" else ("Open" if status == "in_progress" else "View")
            if status in ("in_progress", "completed"):
                if st.button(btn_label, key=f"open_{prompt_id}"):
                    st.session_state.current_prompt_id = prompt_id
                    st.rerun()


# ----------------------------------------------------------------------------
# UI: Annotation page
# ----------------------------------------------------------------------------

def _get_sample_prompt_id() -> str | None:
    """For test mode: just grab a deterministic prompt to preview."""
    res = sb.table("prompts").select("id").limit(1).execute()
    return res.data[0]["id"] if res.data else None


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

    # Determine if read-only (completed or test mode is preview-only on submit)
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

    # Header
    if test:
        st.warning("🧪 **Test mode.** Submissions will not be saved.")
    if st.button("← Back to dashboard"):
        del st.session_state.current_prompt_id
        # Clear the selection state for this prompt too
        for k in list(st.session_state.keys()):
            if k.startswith(f"sel_{prompt_id}_") or k == f"selected_{prompt_id}":
                del st.session_state[k]
        st.rerun()

    st.markdown("---")
    st.subheader(f"Prompt {prompt_id}")
    st.info(prompt["instruction"])

    if assignment and assignment["status"] == "in_progress":
        st.caption(f"⏱ {humanize_remaining(parse_ts(assignment['expires_at']))}")

    # Load existing response if completed
    pre_cited = set()
    if read_only:
        pre_cited = load_response(email, prompt_id)

    # Randomize candidate order deterministically per (annotator, prompt)
    seed_str = f"{email}_{prompt_id}"
    rng = random.Random(hash(seed_str) % (2**32))
    candidates = list(prompt["candidates"])
    rng.shuffle(candidates)

    # Selection state in session_state
    sel_key = f"selected_{prompt_id}"
    if sel_key not in st.session_state:
        if read_only:
            st.session_state[sel_key] = set(pre_cited)
        else:
            st.session_state[sel_key] = set()
    selected = st.session_state[sel_key]

    # Counter at the top
    n_selected = len(selected)
    if n_selected > CITATION_CAP:
        st.error(f"You have selected {n_selected} papers. Reduce to {CITATION_CAP} or fewer before submitting.")
    elif n_selected == CITATION_CAP:
        st.warning(f"Selected {n_selected} / {CITATION_CAP} (cap reached).")
    else:
        st.markdown(f"**Selected: {n_selected} / {CITATION_CAP}**")

    if expired:
        st.error("This assignment has expired. You can no longer submit.")
    elif read_only:
        st.success("This prompt was already completed (read-only view).")

    st.markdown("---")

    # Render candidates
    for c in candidates:
        paper = c["papers"]
        paper_id = paper["id"]
        title = paper["title"]
        abstract = paper["abstract"]

        cb_key = f"cb_{prompt_id}_{paper_id}"
        cols = st.columns([1, 20])
        with cols[0]:
            checked = st.checkbox(
                "Cite",
                key=cb_key,
                value=paper_id in selected,
                label_visibility="collapsed",
                disabled=read_only or expired,
            )
            if not read_only and not expired:
                if checked:
                    selected.add(paper_id)
                else:
                    selected.discard(paper_id)
        with cols[1]:
            st.markdown(f"**{title}**")
            with st.expander("Abstract", expanded=False):
                st.markdown(abstract)
        st.markdown("---")

    st.session_state[sel_key] = selected

    # Submit / Abandon
    if read_only or expired:
        return

    n_selected = len(selected)
    can_submit = (1 <= n_selected <= CITATION_CAP)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Submit this prompt", type="primary", disabled=not can_submit):
            if test:
                st.success("✅ (Test mode) Submission previewed — nothing saved.")
                st.balloons()
            else:
                submit_response(email, prompt_id, list(selected))
                st.success("Submitted! Returning to dashboard...")
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
    st.set_page_config(page_title="Citation Annotator", layout="centered")
    restore_session_from_url()

    if "email" not in st.session_state:
        login_page()
        return

    email = st.session_state.email
    test = is_test_mode()

    # Test mode skips consent + onboarding
    if test:
        if "current_prompt_id" in st.session_state:
            annotation_page()
        else:
            dashboard_page()
        return

    # Consent gate (one-time per browser session)
    if not is_onboarded(email):
        if not st.session_state.get("consent_given"):
            consent_page()
            return
        onboarding_page()
        return

    # Normal flow
    if "current_prompt_id" in st.session_state:
        annotation_page()
    else:
        dashboard_page()


if __name__ == "__main__":
    main()
