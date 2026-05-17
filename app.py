"""
Minimal test: connect Streamlit to Supabase.
"""

import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_client()

st.title("Supabase test")
st.write("Type your name and submit. We'll store it in Supabase and show all submissions below.")

name = st.text_input("Your name")

if st.button("Submit", type="primary", disabled=not name):
    supabase.table("submissions").insert({"name": name}).execute()
    st.success(f"Saved '{name}' to Supabase.")
    st.rerun()

st.markdown("---")
st.subheader("All submissions so far")

result = supabase.table("submissions").select("*").order("submitted_at", desc=True).execute()
rows = result.data

if not rows:
    st.info("No submissions yet. Be the first.")
else:
    for row in rows:
        st.write(f"- **{row['name']}**  ·  {row['submitted_at']}")
