"""
Unit tests for extracting text from PubMed XML with inline markup.

PubMed titles, abstracts and keywords may contain inline elements such as
<i>, <b>, <sup> and <sub> (for example italicised species names). Using
ElementTree's `element.text` returns only the text before the first child
element, which silently truncated titles and abstracts (PR #17).

Tests use mocked Entrez API responses to avoid hitting the real NCBI API.
"""
import http.client
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from mcp_simple_pubmed.pubmed_client import PubMedClient


@pytest.fixture
def client() -> PubMedClient:
    """Create a PubMedClient instance for testing."""
    return PubMedClient(email="test@example.com", tool="test-tool")


# ── efetch XML fixture ────────────────────────────────────────────────

# Shaped like a real efetch response; inline markup is placed where PubMed
# actually puts it (title, abstract sections, author keywords).
PUBMED_XML_MIXED_CONTENT = b"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE" Owner="NLM">
      <PMID Version="1">12345678</PMID>
      <Article PubModel="Print">
        <Journal>
          <JournalIssue CitedMedium="Internet">
            <PubDate><Year>2024</Year><Month>Dec</Month></PubDate>
          </JournalIssue>
          <Title>Journal of <i>Synthetic</i> Biology</Title>
        </Journal>
        <ArticleTitle>Targeting MCR-1 of <i>Escherichia coli</i> with natural products.</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND"><i>E. coli</i> resistance is rising.</AbstractText>
          <AbstractText Label="RESULTS">Binding energy was 10<sup>-3</sup> lower.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Smith</LastName><ForeName>Anna</ForeName></Author>
        </AuthorList>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D004926">Escherichia coli</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
      <KeywordList Owner="NOTNLM">
        <Keyword MajorTopicYN="N"><i>mcr-1</i> gene.</Keyword>
        <Keyword MajorTopicYN="N">colistin</Keyword>
      </KeywordList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">12345678</ArticleId>
        <ArticleId IdType="doi">10.1000/example</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""


def make_efetch_handle(xml_bytes: bytes) -> MagicMock:
    """Create a mock efetch handle that passes the HTTPResponse type check.

    Args:
        xml_bytes: XML content the handle's read() method returns

    Returns:
        Mock object behaving like an http.client.HTTPResponse
    """
    handle = MagicMock(spec=http.client.HTTPResponse)
    handle.read.return_value = xml_bytes
    return handle


# ── helper method tests ───────────────────────────────────────────────

class TestXmlTextHelpers:
    """Tests for the low-level text extraction helpers."""

    def test_title_includes_inline_text_and_tail(
            self, client: PubMedClient) -> None:
        """Text inside and after an inline element should be kept."""
        root = ET.fromstring(
            "<Article><ArticleTitle>Alpha <i>beta</i> gamma"
            "</ArticleTitle></Article>")
        assert client._get_xml_text(root, "ArticleTitle") == "Alpha beta gamma"

    def test_missing_element_is_none(self, client: PubMedClient) -> None:
        """A missing element should give None, not an empty string."""
        root = ET.fromstring("<Article/>")
        assert client._get_xml_text(root, "ArticleTitle") is None

    def test_empty_element_is_none(self, client: PubMedClient) -> None:
        """An element with no text should give None, as before PR #17."""
        root = ET.fromstring("<Article><ArticleTitle/></Article>")
        assert client._get_xml_text(root, "ArticleTitle") is None

    def test_element_text_joins_all_nested_text(self) -> None:
        """The helper should join text from all nesting levels in order."""
        elem = ET.fromstring("<t>a<i>b<b>c</b>d</i>e</t>")
        assert PubMedClient._element_text(elem) == "abcde"


# ── abstract tests ────────────────────────────────────────────────────

class TestFullAbstract:
    """Tests for _get_full_abstract with inline markup."""

    def test_single_abstract_can_start_with_inline_element(
            self, client: PubMedClient) -> None:
        """An abstract starting with an inline element must not become None."""
        root = ET.fromstring(
            "<Article><Abstract><AbstractText><b>Alpha</b> beta"
            "</AbstractText></Abstract></Article>")
        assert client._get_full_abstract(root) == "Alpha beta"

    def test_structured_abstract_preserves_labels_and_inline_text(
            self, client: PubMedClient) -> None:
        """Section labels and inline text should both be kept."""
        root = ET.fromstring(
            '<Article><Abstract>'
            '<AbstractText Label="ONE">Alpha <i>beta</i>.</AbstractText>'
            '<AbstractText>Gamma</AbstractText>'
            '</Abstract></Article>')
        assert client._get_full_abstract(root) == "ONE: Alpha beta.\n\nGamma"


# ── end-to-end article parsing test ───────────────────────────────────

class TestGetArticleDetails:
    """Tests for get_article_details on a record with inline markup."""

    async def test_all_text_fields_keep_inline_content(
            self, client: PubMedClient) -> None:
        """Title, journal, abstract and keywords should all be complete."""
        handle = make_efetch_handle(PUBMED_XML_MIXED_CONTENT)

        with patch("mcp_simple_pubmed.pubmed_client.Entrez.efetch",
                   return_value=handle):
            article = await client.get_article_details("12345678")

        assert article is not None
        assert article["title"] == (
            "Targeting MCR-1 of Escherichia coli with natural products.")
        assert article["journal"] == "Journal of Synthetic Biology"
        assert article["abstract"] == (
            "BACKGROUND: E. coli resistance is rising.\n\n"
            "RESULTS: Binding energy was 10-3 lower.")
        # Trailing period is stripped by the existing keyword clean-up
        assert article["keywords"] == ["mcr-1 gene", "colistin"]
        assert article["mesh_terms"][0]["descriptor"] == "Escherichia coli"
        assert article["authors"] == ["Smith Anna"]
        assert article["doi"] == "10.1000/example"
