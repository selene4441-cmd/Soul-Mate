from app.tikhub import _find_error, _find_note_node, _parse_note, extract_user_fields


def sample_payload():
    return {
        "code": 200,
        "message": "success",
        "data": {
            "data": {
                "user_id": "61b46d790000000010008153",
                "red_id": "757954382",
                "nickname": "测试博主",
                "avatar": "https://example.com/avatar.jpg",
                "desc": "简介",
                "gender": "女",
                "ip_location": "上海",
                "fans": 1200,
                "follows": 300,
                "notes": 88,
                "interaction_count": 45600,
            }
        },
    }


def test_extract_user_fields_from_nested_payload():
    fields = extract_user_fields(sample_payload())
    assert fields["user_id"] == "61b46d790000000010008153"
    assert fields["red_id"] == "757954382"
    assert fields["nickname"] == "测试博主"
    assert fields["followers_count"] == 1200
    assert fields["following_count"] == 300
    assert fields["notes_count"] == 88
    assert fields["interaction_count"] == 45600


def test_find_error_detects_non_success_code():
    is_error, message = _find_error({"code": 404, "message": "not found"})
    assert is_error is True
    assert "not found" in message

def app_v2_payload():
    return {
        "code": 200,
        "data": {
            "data": {
                "userid": "69c87994000000003202f457",
                "red_id": "95840884011",
                "nickname": "KY",
                "desc": "是我吗？",
                "gender": 2,
                "ip_location": "Beijing",
                "fans": 13,
                "follows": 8,
                "images": "https://example.com/avatar.jpg",
                "note_num_stat": {"liked": 13, "posted": 1, "collected": 0},
                "interactions": [
                    {"type": "follows", "count": 8},
                    {"type": "fans", "count": 13},
                    {"type": "interaction", "count": 13},
                ],
            }
        },
    }


def test_extract_notes_and_interaction_from_app_v2_shape():
    fields = extract_user_fields(app_v2_payload())
    assert fields["nickname"] == "KY"
    assert fields["red_id"] == "95840884011"
    assert fields["followers_count"] == 13
    assert fields["following_count"] == 8
    assert fields["notes_count"] == 1
    assert fields["interaction_count"] == 13

def test_parse_note_from_list_shape():
    node = {
        "id": "6a35dbe4000000001702e64d",
        "title": "回忆？",
        "desc": "或许，也没什么好留恋的了吧？",
        "type": "normal",
        "likes": 11,
        "comments_count": 1,
        "collected_count": 0,
        "share_count": 0,
        "ip_location": "Chongqing",
        "create_time": 1781914596,
        "images_list": [{"url": "https://example.com/a.jpg"}],
        "hash_tag": [{"name": "这一刻的想法"}],
    }
    parsed = _parse_note(node)
    assert parsed["note_id"] == "6a35dbe4000000001702e64d"
    assert parsed["title"] == "回忆？"
    assert parsed["likes"] == 11
    assert parsed["images"] == ["https://example.com/a.jpg"]
    assert parsed["tags"] == ["这一刻的想法"]


def test_find_note_node_from_detail_shape():
    payload = {
        "data": {
            "data": [
                {"note_list": [{"id": "n1", "title": "标题", "desc": "正文"}]}
            ]
        }
    }
    node = _find_note_node(payload)
    assert node["id"] == "n1"
    assert node["desc"] == "正文"