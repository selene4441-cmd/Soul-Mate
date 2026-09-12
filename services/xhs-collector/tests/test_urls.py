from app.urls import profile_url_for


def test_profile_url_for():
    assert profile_url_for("61b46d790000000010008153") == "https://www.xiaohongshu.com/user/profile/61b46d790000000010008153"


def test_profile_url_for_empty():
    assert profile_url_for(None) is None
    assert profile_url_for("") is None
