"""Smoke test: python -m pytest test_app.py  (or just: python test_app.py)"""
from streamlit.testing.v1 import AppTest


def test_app_runs():
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert not at.exception, at.exception
    assert at.metric[0].value == "40"


if __name__ == "__main__":
    test_app_runs()
    print("ok")
