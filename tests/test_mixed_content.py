import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


class MixedContentTests(unittest.TestCase):
    def setUp(self):
        bio = types.ModuleType("Bio")
        bio.Entrez = types.SimpleNamespace()
        path = Path(__file__).resolve().parents[1] / "mcp_simple_pubmed" / "pubmed_client.py"
        spec = importlib.util.spec_from_file_location("pubmed_mixed_content_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"Bio": bio}):
            spec.loader.exec_module(module)
        self.client = module.PubMedClient("synthetic@example.invalid", "offline-test")

    def test_title_includes_inline_text_and_tail(self):
        root = ET.fromstring("<Article><ArticleTitle>Alpha <i>beta</i> gamma</ArticleTitle></Article>")
        self.assertEqual(self.client._get_xml_text(root, "ArticleTitle"), "Alpha beta gamma")

    def test_single_abstract_can_start_with_inline_element(self):
        root = ET.fromstring("<Article><Abstract><AbstractText><b>Alpha</b> beta</AbstractText></Abstract></Article>")
        self.assertEqual(self.client._get_full_abstract(root), "Alpha beta")

    def test_structured_abstract_preserves_labels_and_inline_text(self):
        root = ET.fromstring('<Article><Abstract><AbstractText Label="ONE">Alpha <i>beta</i>.</AbstractText><AbstractText>Gamma</AbstractText></Abstract></Article>')
        self.assertEqual(self.client._get_full_abstract(root), "ONE: Alpha beta.\n\nGamma")

    def test_missing_text_is_none(self):
        self.assertIsNone(self.client._get_xml_text(ET.fromstring("<Article/>"), "ArticleTitle"))


if __name__ == "__main__":
    unittest.main()
