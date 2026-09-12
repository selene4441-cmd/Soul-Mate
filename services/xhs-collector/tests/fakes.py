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

    def close(self):
        pass