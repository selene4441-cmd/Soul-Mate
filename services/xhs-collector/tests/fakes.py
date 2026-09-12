from app.tikhub import TikhubError


class FakeTikhubClient:
    def __init__(self, fail_values=None):
        self.calls = []
        self.fail_values = set(fail_values or [])

    def fetch_user(self, parsed):
        self.calls.append(parsed)
        if parsed.value in self.fail_values:
            raise TikhubError("账号不存在")
        return {
            "user_id": parsed.user_id or "61b46d790000000010008153",
            "red_id": "757954382",
            "nickname": "测试用户",
            "avatar": "https://example.com/avatar.jpg",
            "description": "简介",
            "gender": "女",
            "ip_location": "上海",
            "followers_count": 1200,
            "following_count": 300,
            "notes_count": 88,
            "interaction_count": 45600,
            "raw_json": '{"code": 200}',
        }

    def fetch_posted_notes(self, user_id, max_notes=100):
        return {
            "notes": [
                {
                    "note_id": "note-1",
                    "title": "标题",
                    "desc": "列表简介",
                    "note_type": "normal",
                    "likes": 11,
                    "comments_count": 1,
                    "collected_count": 0,
                    "share_count": 0,
                    "ip_location": "Chongqing",
                    "published_at": 1781914596,
                    "images": ["https://example.com/note.jpg"],
                    "tags": ["tag1"],
                    "note_url": "https://www.xiaohongshu.com/discovery/item/note-1",
                }
            ]
        }

    def fetch_note_detail(self, note_id, note_type=""):
        return {
            "note_id": note_id,
            "title": "标题",
            "desc": "完整正文内容",
            "note_type": note_type or "normal",
            "likes": 11,
            "comments_count": 1,
            "collected_count": 0,
            "share_count": 0,
            "ip_location": "Chongqing",
            "published_at": 1781914596,
            "images": ["https://example.com/note.jpg"],
            "tags": ["tag1", "tag2"],
            "note_url": "https://www.xiaohongshu.com/discovery/item/" + note_id,
        }

    def close(self):
        pass