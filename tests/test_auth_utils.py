import unittest

from auth_utils import read_admin_auth_state, save_admin_auth_state


class DummyCookieManager:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, **kwargs):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


class AdminAuthStateTests(unittest.TestCase):
    def test_save_admin_auth_state_persists_in_session_and_cookie(self):
        cookie_manager = DummyCookieManager()
        state = {}

        save_admin_auth_state(state, cookie_manager, "admin01")

        self.assertTrue(state["admin_logged_in"])
        self.assertEqual(state["admin_username"], "admin01")
        self.assertEqual(cookie_manager.get("admin_logged_in"), "true")
        self.assertEqual(cookie_manager.get("admin_username"), "admin01")

    def test_read_admin_auth_state_from_cookie_when_session_is_empty(self):
        cookie_manager = DummyCookieManager()
        cookie_manager.set("admin_logged_in", "true")
        cookie_manager.set("admin_username", "admin01")
        state = {}

        result = read_admin_auth_state(state, cookie_manager)

        self.assertTrue(result["admin_logged_in"])
        self.assertEqual(result["admin_username"], "admin01")


if __name__ == "__main__":
    unittest.main()
