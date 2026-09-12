import unittest
from pathlib import Path

DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "web-technical-architecture-v0.1.md"


class WebTechnicalArchitectureDocumentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC_PATH.read_text(encoding="utf-8")

    def test_document_exists_and_has_title(self):
        self.assertTrue(DOC_PATH.is_file())
        self.assertIn("# 同频 Web 产品技术方案 v0.1", self.text)

    def test_required_sections_are_present(self):
        sections = [
            "## 2. 范围与总体决策",
            "## 4. 总体架构",
            "## 5. 技术栈",
            "## 7. 后端领域模块",
            "## 8. 数据架构",
            "## 10. 匹配与解释流程",
            "## 11. 安全与合规",
            "## 13. 测试策略",
            "## 14. 部署与环境",
            "## 16. v0.1 验收标准",
        ]
        for section in sections:
            with self.subTest(section=section):
                self.assertIn(section, self.text)

    def test_required_stack_terms_are_present(self):
        terms = [
            "Next.js",
            "TypeScript",
            "FastAPI",
            "PostgreSQL",
            "pgvector",
            "Redis",
            "Celery",
            "WebSocket",
            "OpenAPI",
            "OSS / COS",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_privacy_and_explainability_contracts_are_present(self):
        terms = [
            "consent_scope",
            "model_version",
            "policy_version",
            "模块化单体",
            "原始内容与排序隔离",
            "安全可以否决推荐",
            "浏览器不接收内部排序分数",
            "共同点、差异点和未知信息",
            "匹配百分比",
            "固定人格标签",
            "第三方聊天",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)

    def test_electron_is_explicitly_out_of_scope(self):
        self.assertIn("不使用 Electron", self.text)


if __name__ == "__main__":
    unittest.main()
