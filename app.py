"""
Minimal Streamlit app. Sole purpose: confirm the GitHub -> Streamlit Cloud
deployment pipeline works end-to-end. Once this is live, we replace the
contents of this file with the real annotation app.
"""

import streamlit as st

st.title("Hello from Sina's citation study")

st.write("If you're seeing this, the deployment works. 🎉")

st.write("This is a placeholder. The real annotation interface will go here next.")

name = st.text_input("What's your name?")
if name:
    st.success(f"Nice to meet you, {name}.")
