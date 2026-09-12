from pathlib import Path
import unittest


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "matching-metrics-v0.1.md"


class MatchingMetricsDocumentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC_PATH.read_text(encoding="utf-8")

    def test_document_exists_and_has_title(self):
        self.assertTrue(DOC_PATH.is_file())
        self.assertIn("# 用户特征与匹配指标 v0.1", self.text)

    def test_required_sections_are_present(self):
        sections = [
            "## 4. Claim：最小可追溯特征",
            "## 5. 用户特征 v0.1",
            "## 6. 双人匹配特征",
            "## 7. 匹配分定义",
            "## 8. 结果标签",
            "## 9. 指标体系",
            "## 10. 事件与数据契约",
            "## 12. 合规红线",
            "## 13. v0.1 验收标准",
        ]
        for section in sections:
            with self.subTest(section=section):
                self.assertIn(section, self.text)

    def test_required_contract_terms_are_present(self):
        terms = [
            "claim_id",
            "evidence_ids",
            "policy_version",
            "P(关系结果良好 | A、B、当前状态、互动过程、推荐策略)",
            "good_outcome_14d",
            "敏感个人信息",
            "成长同向性",
            "时间边界",
            "空间与自主",
            "y_growth_alignment_30d",
            "y_boundary_respect_30d",
            "边界侵犯投诉率",
        ]
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, self.text)


if __name__ == "__main__":
    unittest.main()