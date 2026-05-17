"""
Citation Annotator — login flow with email OTP verification.

This is the auth-only test. Once login works end-to-end, we add the prompt
assignment, dashboard, and annotation pages on top.

Login flow:
  1. User enters email -> we generate a 6-digit code, store it in Supabase
     with a 10-minute expiry, and send it via Resend.
  2. User pastes the code -> we verify it matches and isn't expired.
  3. On success: we create a 30-day session token stored in the browser via
     query params, and the user is "logged in" for that period.
  4. test@test.com bypasses verification entirely (for co-author demos).
"""

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
TEST_EMAIL = "test@test.com"

# ----------------------------------------------------------------------------
# Supabase client
# ----------------------------------------------------------------------------

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# ----------------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def generate_code() -> str:
    """6-digit numeric code."""
    return "".join(secrets.choice(string.digits) for _ in range(CODE_LENGTH))


def generate_session_token() -> str:
    """A long random token used as the session ID. Stored in URL query params."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))


def send_code_email(to_email: str, code: str) -> bool:
    """Send the OTP code via Resend. Returns True on success."""
    response = requests.post(
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
    if response.status_code >= 400:
        st.error(f"Email send failed: {response.text}")
        return False
    return True


# ----------------------------------------------------------------------------
# Supabase data operations
# ----------------------------------------------------------------------------

def store_verification_code(email: str, code: str) -> None:
    """Save the code with an expiry; delete any older codes for this email first."""
    supabase.table("verification_codes").delete().eq("email", email).execute()
    supabase.table("verification_codes").insert({
        "email": email,
        "code": code,
        "expires_at": (now_utc() + timedelta(minutes=CODE_TTL_MINUTES)).isoformat(),
    }).execute()


def verify_code(email: str, code: str) -> bool:
    """Check whether the code matches and isn't expired."""
    result = (
        supabase.table("verification_codes")
        .select("*")
        .eq("email", email)
        .eq("code", code)
        .execute()
    )
    if not result.data:
        return False
    row = result.data[0]
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < now_utc():
        return False
    # Code is valid; delete it so it can't be reused.
    supabase.table("verification_codes").delete().eq("email", email).execute()
    return True


def create_session(email: str) -> str:
    """Create a session row in Supabase and return the token."""
    token = generate_session_token()
    supabase.table("sessions").insert({
        "token": token,
        "email": email,
        "expires_at": (now_utc() + timedelta(days=SESSION_TTL_DAYS)).isoformat(),
    }).execute()
    return token


def lookup_session(token: str) -> str | None:
    """Given a token from the URL, return the email if the session is valid, else None."""
    result = (
        supabase.table("sessions")
        .select("*")
        .eq("token", token)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < now_utc():
        return None
    return row["email"]


def end_session(token: str) -> None:
    supabase.table("sessions").delete().eq("token", token).execute()


# ----------------------------------------------------------------------------
# Session state helpers
# ----------------------------------------------------------------------------

def restore_session_from_url() -> None:
    """If the URL has a ?session=... param, try to restore the user's session."""
    if "email" in st.session_state:
        return  # already logged in this session
    token = st.query_params.get("session")
    if not token:
        return
    email = lookup_session(token)
    if email:
        st.session_state.email = email
        st.session_state.session_token = token


def log_in(email: str) -> None:
    token = create_session(email)
    st.session_state.email = email
    st.session_state.session_token = token
    st.query_params["session"] = token


def log_out() -> None:
    token = st.session_state.get("session_token")
    if token:
        end_session(token)
    for k in ["email", "session_token", "pending_email"]:
        if k in st.session_state:
            del st.session_state[k]
    st.query_params.clear()


# ----------------------------------------------------------------------------
# UI: Login page
# ----------------------------------------------------------------------------

def login_page() -> None:
    st.title("Citation Annotator")
    st.markdown(
        "Welcome. Enter your email to receive a 6-digit login code. "
        "Once verified, you'll stay logged in for 30 days on this browser."
    )

    # Step 1: ask for email
    if "pending_email" not in st.session_state:
        email = st.text_input("Email", key="email_input").strip().lower()
        if st.button("Send code", type="primary", disabled=not email):
            if email == TEST_EMAIL:
                # Test mode: skip verification, log in immediately.
                log_in(email)
                st.rerun()
                return
            code = generate_code()
            store_verification_code(email, code)
            if send_code_email(email, code):
                st.session_state.pending_email = email
                st.rerun()
        return

    # Step 2: ask for the code they received via email
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
                st.error("Invalid or expired code. Try again, or request a new one.")
    with col2:
        if st.button("Use a different email"):
            del st.session_state.pending_email
            st.rerun()


# ----------------------------------------------------------------------------
# UI: Home (logged in)
# ----------------------------------------------------------------------------

def home_page() -> None:
    email = st.session_state.email
    is_test = email == TEST_EMAIL

    st.title("Citation Annotator")

    if is_test:
        st.warning(
            "🧪 **Test mode.** This is a preview for co-authors. No data is saved. "
            "Real annotators will see their assigned prompts here."
        )
    else:
        st.success(f"Logged in as **{email}**.")

    st.markdown("---")

    st.markdown(
        """
        ### What goes here next

        - Your assigned prompts (with status: completed, in-progress with timer, etc.)
        - A "Request a new prompt" button
        - Click into a prompt to make citation selections
        """
    )

    st.markdown("---")
    if st.button("Log out"):
        log_out()
        st.rerun()


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Citation Annotator", layout="centered")
    restore_session_from_url()

    if "email" in st.session_state:
        home_page()
    else:
        login_page()


if __name__ == "__main__":
    main()
