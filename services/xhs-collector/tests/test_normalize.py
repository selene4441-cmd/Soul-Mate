from app.normalize import parse_line


def test_parse_hex_user_id():
    items = parse_line("61b46d790000000010008153")
    assert len(items) == 1
    assert items[0].type == "user_id"
    assert items[0].user_id == "61b46d790000000010008153"


def test_parse_profile_link_extracts_uid():
    url = "https://www.xiaohongshu.com/user/profile/61b46d790000000010008153?xsec_token=abc&xhsshare=CopyLink"
    items = parse_line(url)
    assert items[0].type == "user_id"
    assert items[0].user_id == "61b46d790000000010008153"
    assert items[0].share_text == url


def test_parse_short_link_as_share_text():
    items = parse_line("http://xhslink.com/a/AbCdEf")
    assert len(items) == 1
    assert items[0].type == "share_text"
    assert items[0].share_text == "http://xhslink.com/a/AbCdEf"


def test_parse_red_id_numeric():
    items = parse_line("757954382")
    assert items[0].type == "red_id"
    assert items[0].value == "757954382"


def test_parse_red_id_with_label():
    items = parse_line("小红书号：757954382")
    assert items[0].type == "red_id"
    assert items[0].value == "757954382"


def test_parse_multiple_urls_in_one_line():
    line = "https://www.xiaohongshu.com/user/profile/61b46d790000000010008153 和 http://xhslink.com/a/xyz"
    items = parse_line(line)
    assert len(items) == 2


def test_parse_unknown_text():
    items = parse_line("大家好，这是我的客户")
    assert items[0].type == "unknown"