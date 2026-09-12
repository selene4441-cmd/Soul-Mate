import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "conversation-product-design-v0.1.md"


class ConversationProductDesignDocumentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC_PATH.read_text(encoding="utf-8")

    def test_document_exists_and_has_title(self):
        self.assertTrue(DOC_PATH.is_file())
        self.assertIn("# 同频匹配后交流产品方案 v0.1", self.text)

    def test_required_sections_are_present(self):
        sections = [
            "## 3. 产品定位与原则",
            "## 5. 核心对象与状态机",
            "## 6. 核心用户流程",
            "## 7. 功能需求",
            "## 8. 页面与交互",
            "## 9. 数据模型",
            "## 10. API 契约",
            "## 11. 事件与指标",
            "## 12. 安全与隐私",
            "## 13. 实施顺序",
            "## 14. v0.1 验收标准",
        ]
        for section in sections:
            with self.subTest(section=section):
                self.assertIn(section, self.text)

    def test_required_product_contract_terms_are_present(self):
        terms = [
            "先同意，后交流",
            "先议题，后聊天",
            "系统不冒充用户",
            "ConnectionRequest",
            "ConversationCue",
            "conversation_members",
            "双向接受",
            "交流提示",
            "不展示精确“已读时间”",
            "消息正文默认不得用于广告、画像、匹配训练",
            "种子自动连接进入测试夹具",
            "拒绝后的重复请求率必须为 0",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_target_api_contract_is_present(self):
        endpoints = [
            "POST   /api/v1/connection-requests",
            "POST   /api/v1/connection-requests/{id}/accept",
            "POST   /api/v1/connection-requests/{id}/decline",
            "GET    /api/v1/conversations",
            "POST   /api/v1/conversations/{id}/messages",
            "POST   /api/v1/conversations/{id}/close",
            "POST   /api/v1/blocks",
            "POST   /api/v1/safety/reports",
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, self.text)

    def test_document_distinguishes_design_from_current_delivery(self):
        self.assertIn("不代表当前代码已经全部实现", self.text)
        self.assertIn("现有仓库中的邀请、Match、Conversation、Message 和 WebSocket 是原型能力", self.text)

    def test_readme_links_conversation_product_design(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/conversation-product-design-v0.1.md", readme)


if __name__ == "__main__":
    unittest.main()
