import json
from netschoolpy import NetSchool


def test_extract_access_token_from_session_store():
    payload = [
        {
            "active": True,
            "accessToken": "token-123",
        }
    ]
    session_store = json.dumps(payload)
    token = NetSchool._extract_access_token_from_session_store(session_store)
    assert token == "token-123"


def test_extract_access_token_from_session_store_stringified():
    payload = [
        {
            "active": True,
            "accessToken": "token-456",
        }
    ]
    session_store = json.dumps(json.dumps(payload))
    token = NetSchool._extract_access_token_from_session_store(session_store)
    assert token == "token-456"
