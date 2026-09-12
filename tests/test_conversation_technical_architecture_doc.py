import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "conversation-technical-architecture-v0.1.md"


class ConversationTechnicalArchitectureDocumentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC_PATH.read_text(encoding="utf-8")

    def test_document_exists_and_has_title(self):
        self.assertTrue(DOC_PATH.is_file())
        self.assertIn("# 同频匹配后交流技术方案 v0.1", self.text)

    def test_required_sections_are_present(self):
        sections = [
            "## 3. 核心技术决策",
            "## 4. 总体架构",
            "## 5. 代码模块边界",
            "## 6. 数据架构",
            "## 7. 领域流程与事务",
            "## 9. API 契约",
            "## 10. 实时通信与 Outbox",
            "## 11. 前端实现",
            "## 12. 安全、隐私与合规",
            "## 14. 测试策略",
            "## 15. 部署与环境",
            "## 16. 实施计划",
            "## 17. v0.1 技术验收标准",
        ]
        for section in sections:
            with self.subTest(section=section):
                self.assertIn(section, self.text)

    def test_required_stack_terms_are_present(self):
        terms = [
            "Next.js 15",
            "React 19",
            "FastAPI",
            "Pydantic v2",
            "SQLAlchemy 2",
            "PostgreSQL 16",
            "Redis Pub/Sub",
            "Celery + Celery Beat",
            "WebSocket",
            "Outbox",
            "OpenTelemetry",
            "pytest + Vitest + Playwright",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_required_data_and_transaction_contracts_are_present(self):
        terms = [
            "connection_requests",
            "conversation_members",
            "conversation_cues",
            "outbox_events",
            "pair_key",
            "PostgreSQL 是连接、会话和消息状态的唯一业务真相",
            "消息正文和审计事件分离",
            "条件更新",
            "同一数据库事务",
            "(conversation_id, client_message_id)",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_realtime_and_failure_boundaries_are_present(self):
        terms = [
            "Redis 或 WebSocket 不可用时",
            "断线用户通过 REST 游标补拉",
            "Outbox payload 不包含消息正文",
            "业务正确性不依赖内存 Hub",
            "不通过长期查询参数传递令牌",
            "客户端重复发送同一 `client_message_id` 时返回原消息",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_target_api_routes_are_present(self):
        routes = [
            "POST /api/v1/connection-requests",
            "POST /api/v1/connection-requests/{id}/accept",
            "GET  /api/v1/conversations",
            "POST /api/v1/conversations/{id}/messages",
            "POST /api/v1/conversations/{id}/close",
            "POST   /api/v1/blocks",
            "POST   /api/v1/safety/reports",
            "WS /api/v1/ws/conversations/{conversation_id}",
        ]
        for route in routes:
            with self.subTest(route=route):
                self.assertIn(route, self.text)

    def test_v0_1_explicitly_avoids_overengineering(self):
        terms = [
            "不拆分聊天、通知和安全微服务",
            "不引入 Kafka、Kubernetes、Elasticsearch",
            "不在 v0.1 引入端到端加密",
            "不得因为“以后可能使用”提前引入上述组件",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_readme_links_conversation_technical_architecture(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/conversation-technical-architecture-v0.1.md", readme)


if __name__ == "__main__":
    unittest.main()
