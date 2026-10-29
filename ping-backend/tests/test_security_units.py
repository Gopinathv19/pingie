import uuid

import pytest

from app.core.errors import AuthenticationError
from app.core.security import (
    conversation_from_token,
    create_conversation_token,
    create_session_token,
    session_user_id,
)


def test_session_round_trip():
    uid = uuid.uuid4()
    assert session_user_id(create_session_token(uid, "a@b.com")) == uid


def test_conversation_token_is_bound_to_its_bot_and_type():
    cid, bot = uuid.uuid4(), uuid.uuid4()
    token = create_conversation_token(cid, bot)
    assert conversation_from_token(token, bot) == cid
    with pytest.raises(AuthenticationError):
        conversation_from_token(token, uuid.uuid4())
    # A conversation token is not a session, and vice versa.
    with pytest.raises(AuthenticationError):
        session_user_id(token)
    with pytest.raises(AuthenticationError):
        conversation_from_token(create_session_token(cid, "x@y.z"), bot)
