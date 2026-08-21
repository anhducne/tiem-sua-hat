from __future__ import annotations

from datetime import datetime, timedelta


def _get_cookie_expiry(days: int = 7):
    return datetime.utcnow() + timedelta(days=days)


def get_cookie_manager():
    try:
        import streamlit as st
    except Exception:
        return None

    if hasattr(st, "cookies"):
        return st.cookies

    if hasattr(st, "experimental_get_cookie") and hasattr(st, "experimental_set_cookie"):
        class LegacyCookieManager:
            def get(self, key, default=None):
                value = st.experimental_get_cookie(key)
                return value if value is not None else default

            def set(self, key, value, **kwargs):
                try:
                    st.experimental_set_cookie(key, value, **kwargs)
                except TypeError:
                    st.experimental_set_cookie(key, value)

            def delete(self, key):
                if hasattr(st, "experimental_delete_cookie"):
                    st.experimental_delete_cookie(key)

        return LegacyCookieManager()

    return None


def read_admin_auth_state(session_state, cookie_manager=None):
    if cookie_manager is None:
        cookie_manager = get_cookie_manager()

    saved_login = bool(session_state.get("admin_logged_in", False))
    saved_username = str(session_state.get("admin_username", "")).strip()

    if cookie_manager is not None and not saved_login:
        cookie_login = str(cookie_manager.get("admin_logged_in", "false")).strip().lower()
        if cookie_login == "true":
            saved_username = str(cookie_manager.get("admin_username", "")).strip()
            saved_login = bool(saved_username)

    session_state["admin_logged_in"] = saved_login
    session_state["admin_username"] = saved_username
    return session_state


def save_admin_auth_state(session_state, cookie_manager=None, username=""):
    if cookie_manager is None:
        cookie_manager = get_cookie_manager()

    username = str(username or session_state.get("admin_username", "")).strip()
    session_state["admin_logged_in"] = bool(username)
    session_state["admin_username"] = username

    if cookie_manager is not None and username:
        expiry = _get_cookie_expiry(7)
        try:
            cookie_manager.set("admin_logged_in", "true", expires_at=expiry)
            cookie_manager.set("admin_username", username, expires_at=expiry)
        except TypeError:
            cookie_manager.set("admin_logged_in", "true")
            cookie_manager.set("admin_username", username)

    return session_state


def clear_admin_auth_state(session_state, cookie_manager=None):
    if cookie_manager is None:
        cookie_manager = get_cookie_manager()

    session_state["admin_logged_in"] = False
    session_state["admin_username"] = ""

    if cookie_manager is not None:
        try:
            cookie_manager.delete("admin_logged_in")
        except Exception:
            pass
        try:
            cookie_manager.delete("admin_username")
        except Exception:
            pass

    return session_state
