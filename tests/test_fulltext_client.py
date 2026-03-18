"""
Unit tests for FullTextClient.

Tests use mocked Entrez API responses to avoid hitting the real NCBI API.
"""
import pytest
from unittest.mock import patch, MagicMock
import io

from mcp_simple_pubmed.fulltext_client import FullTextClient, PmidMismatchError


@pytest.fixture
def client():
    """Create a FullTextClient instance for testing."""
    return FullTextClient(
        email="test@example.com",
        tool="test-tool"
    )


# ── elink XML fixtures ────────────────────────────────────────────────

ELINK_XML_PMC_DIRECT = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eLinkResult PUBLIC "-//NLM//DTD elink 20101123//EN"
 "https://eutils.ncbi.nlm.nih.gov/eutils/dtd/20101123/elink.dtd">
<eLinkResult>
  <LinkSet>
    <DbFrom>pubmed</DbFrom>
    <IdList><Id>12345678</Id></IdList>
    <LinkSetDb>
      <DbTo>pmc</DbTo>
      <LinkName>pubmed_pmc</LinkName>
      <Link><Id>9999999</Id></Link>
    </LinkSetDb>
  </LinkSet>
</eLinkResult>"""

ELINK_XML_REFS_ONLY = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eLinkResult PUBLIC "-//NLM//DTD elink 20101123//EN"
 "https://eutils.ncbi.nlm.nih.gov/eutils/dtd/20101123/elink.dtd">
<eLinkResult>
  <LinkSet>
    <DbFrom>pubmed</DbFrom>
    <IdList><Id>36738762</Id></IdList>
    <LinkSetDb>
      <DbTo>pmc</DbTo>
      <LinkName>pubmed_pmc_refs</LinkName>
      <Link><Id>12952356</Id></Link>
      <Link><Id>12942054</Id></Link>
    </LinkSetDb>
  </LinkSet>
</eLinkResult>"""

ELINK_XML_NO_LINKS = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eLinkResult PUBLIC "-//NLM//DTD elink 20101123//EN"
 "https://eutils.ncbi.nlm.nih.gov/eutils/dtd/20101123/elink.dtd">
<eLinkResult>
  <LinkSet>
    <DbFrom>pubmed</DbFrom>
    <IdList><Id>99999999</Id></IdList>
  </LinkSet>
</eLinkResult>"""

ELINK_XML_BOTH_TYPES = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eLinkResult PUBLIC "-//NLM//DTD elink 20101123//EN"
 "https://eutils.ncbi.nlm.nih.gov/eutils/dtd/20101123/elink.dtd">
<eLinkResult>
  <LinkSet>
    <DbFrom>pubmed</DbFrom>
    <IdList><Id>24677277</Id></IdList>
    <LinkSetDb>
      <DbTo>pmc</DbTo>
      <LinkName>pubmed_pmc</LinkName>
      <Link><Id>7777777</Id></Link>
    </LinkSetDb>
    <LinkSetDb>
      <DbTo>pmc</DbTo>
      <LinkName>pubmed_pmc_refs</LinkName>
      <Link><Id>8888888</Id></Link>
      <Link><Id>9999999</Id></Link>
    </LinkSetDb>
  </LinkSet>
</eLinkResult>"""


# ── check_full_text_availability tests ────────────────────────────────

class TestCheckFullTextAvailability:
    """Tests for check_full_text_availability method."""

    async def test_paper_in_pmc_returns_true_and_pmc_id(self, client):
        """When elink returns pubmed_pmc link, should return (True, pmc_id)."""
        mock_handle = MagicMock()
        mock_handle.read.return_value = ELINK_XML_PMC_DIRECT
        mock_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_handle):
            available, pmc_id = await client.check_full_text_availability("12345678")

        assert available is True
        assert pmc_id == "9999999"

    async def test_only_citing_refs_returns_false(self, client):
        """When elink returns only pubmed_pmc_refs, should return (False, None).

        This is the regression test for issue #11: before the fix, the code
        would grab the first LinkSetDb regardless of LinkName, returning a
        citing paper's PMC ID instead of reporting unavailability.
        """
        mock_handle = MagicMock()
        mock_handle.read.return_value = ELINK_XML_REFS_ONLY
        mock_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_handle):
            available, pmc_id = await client.check_full_text_availability("36738762")

        assert available is False
        assert pmc_id is None

    async def test_no_links_returns_false(self, client):
        """When elink returns no LinkSetDb elements, should return (False, None)."""
        mock_handle = MagicMock()
        mock_handle.read.return_value = ELINK_XML_NO_LINKS
        mock_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_handle):
            available, pmc_id = await client.check_full_text_availability("99999999")

        assert available is False
        assert pmc_id is None

    async def test_both_link_types_picks_pubmed_pmc(self, client):
        """When elink returns both pubmed_pmc and pubmed_pmc_refs,
        should pick pubmed_pmc and return its PMC ID."""
        mock_handle = MagicMock()
        mock_handle.read.return_value = ELINK_XML_BOTH_TYPES
        mock_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_handle):
            available, pmc_id = await client.check_full_text_availability("24677277")

        assert available is True
        assert pmc_id == "7777777"


# ── PMC full-text XML fixtures ────────────────────────────────────────

PMC_XML_MATCHING_PMID = b"""<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset>
  <article>
    <front>
      <article-meta>
        <article-id pub-id-type="pmid">12345678</article-id>
        <article-id pub-id-type="pmc">9999999</article-id>
        <title-group><article-title>Test Article</article-title></title-group>
      </article-meta>
    </front>
    <body><p>Full text content here.</p></body>
  </article>
</pmc-articleset>"""

PMC_XML_MISMATCHED_PMID = b"""<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset>
  <article>
    <front>
      <article-meta>
        <article-id pub-id-type="pmid">99999999</article-id>
        <article-id pub-id-type="pmc">12952356</article-id>
        <title-group><article-title>Wrong Article</article-title></title-group>
      </article-meta>
    </front>
    <body><p>This is a completely different paper.</p></body>
  </article>
</pmc-articleset>"""

PMC_XML_NO_PMID = b"""<?xml version="1.0" encoding="UTF-8"?>
<pmc-articleset>
  <article>
    <front>
      <article-meta>
        <article-id pub-id-type="pmc">9999999</article-id>
        <title-group><article-title>Article Without PMID</article-title></title-group>
      </article-meta>
    </front>
    <body><p>Content without PMID in metadata.</p></body>
  </article>
</pmc-articleset>"""


# ── get_full_text tests ───────────────────────────────────────────────

class TestGetFullText:
    """Tests for get_full_text method."""

    async def test_successful_fetch_with_matching_pmid(self, client):
        """When PMC XML contains matching PMID, should return content."""
        mock_elink_handle = MagicMock()
        mock_elink_handle.read.return_value = ELINK_XML_PMC_DIRECT
        mock_elink_handle.__bool__ = lambda self: True

        mock_efetch_handle = MagicMock()
        mock_efetch_handle.read.return_value = PMC_XML_MATCHING_PMID
        mock_efetch_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_elink_handle), \
             patch("mcp_simple_pubmed.fulltext_client.Entrez.efetch",
                    return_value=mock_efetch_handle):
            result = await client.get_full_text("12345678")

        assert result is not None
        assert "Full text content here" in result

    async def test_pmid_mismatch_raises_error(self, client):
        """When PMC XML contains different PMID, should raise PmidMismatchError."""
        mock_elink_handle = MagicMock()
        mock_elink_handle.read.return_value = ELINK_XML_PMC_DIRECT
        mock_elink_handle.__bool__ = lambda self: True

        mock_efetch_handle = MagicMock()
        mock_efetch_handle.read.return_value = PMC_XML_MISMATCHED_PMID
        mock_efetch_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_elink_handle), \
             patch("mcp_simple_pubmed.fulltext_client.Entrez.efetch",
                    return_value=mock_efetch_handle):
            with pytest.raises(PmidMismatchError) as exc_info:
                await client.get_full_text("12345678")

        assert exc_info.value.requested_pmid == "12345678"
        assert exc_info.value.found_pmid == "99999999"

    async def test_not_available_returns_none(self, client):
        """When article is not in PMC, should return None."""
        mock_handle = MagicMock()
        mock_handle.read.return_value = ELINK_XML_NO_LINKS
        mock_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_handle):
            result = await client.get_full_text("99999999")

        assert result is None

    async def test_no_pmid_in_xml_allows_content_through(self, client):
        """When PMC XML has no PMID element, should return content (permissive).

        The XPath fix is the primary guard; the PMID verification is a safety
        net that only acts when it can positively detect a mismatch.
        """
        mock_elink_handle = MagicMock()
        mock_elink_handle.read.return_value = ELINK_XML_PMC_DIRECT
        mock_elink_handle.__bool__ = lambda self: True

        mock_efetch_handle = MagicMock()
        mock_efetch_handle.read.return_value = PMC_XML_NO_PMID
        mock_efetch_handle.__bool__ = lambda self: True

        with patch("mcp_simple_pubmed.fulltext_client.Entrez.elink",
                    return_value=mock_elink_handle), \
             patch("mcp_simple_pubmed.fulltext_client.Entrez.efetch",
                    return_value=mock_efetch_handle):
            result = await client.get_full_text("12345678")

        assert result is not None
        assert "Content without PMID" in result
