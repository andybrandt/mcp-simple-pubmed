"""
Client for interacting with PubMed/Entrez API.
"""
import os
import time
import logging
import http.client
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
from Bio import Entrez

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pubmed-client")

class PubMedClient:
    """Client for interacting with PubMed/Entrez API."""

    def __init__(self, email: str, tool: str, api_key: Optional[str] = None):
        """Initialize PubMed client with required credentials.

        Args:
            email: Valid email address for API access
            tool: Unique identifier for the tool
            api_key: Optional API key for higher rate limits
        """
        self.email = email
        self.tool = tool
        self.api_key = api_key
        
        # Configure Entrez
        Entrez.email = email
        Entrez.tool = tool
        if api_key:
            Entrez.api_key = api_key

    async def search_articles(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for articles matching the query.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of article metadata dictionaries
        """
        try:
            logger.info(f"Searching PubMed with query: {query}")
            results = []
            
            # Step 1: Search for article IDs
            handle = Entrez.esearch(db="pubmed", term=query, retmax=str(max_results))
            if not handle:
                logger.error("Got None handle from esearch")
                return []
                
            if isinstance(handle, http.client.HTTPResponse):
                logger.info("Got valid HTTP response from esearch")
                xml_content = handle.read()
                handle.close()
                
                # Parse XML to get IDs
                root = ET.fromstring(xml_content)
                id_list = root.findall('.//Id')
                
                if not id_list:
                    logger.info("No results found")
                    return []
                    
                pmids = [id_elem.text for id_elem in id_list]
                logger.info(f"Found {len(pmids)} articles")
                
                # Step 2: Get details for each article
                for pmid in pmids:
                    article = await self.get_article_details(pmid)
                    if article:
                        results.append(article)
            
            return results

        except Exception as e:
            logger.exception(f"Error in search_articles: {str(e)}")
            raise

    async def get_article_details(self, pmid: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific article by PMID.

        Args:
            pmid: PubMed ID of the article

        Returns:
            Dictionary with article metadata or None if not found
        """
        try:
            logger.info(f"Fetching details for PMID {pmid}")
            detail_handle = Entrez.efetch(db="pubmed", id=pmid, rettype="xml")
            
            if detail_handle and isinstance(detail_handle, http.client.HTTPResponse):
                article_xml = detail_handle.read()
                detail_handle.close()
                
                # Parse article details
                article_root = ET.fromstring(article_xml)
                
                # Get basic article data
                article = {
                    "pmid": pmid,
                    "title": self._get_xml_text(article_root, './/ArticleTitle') or "No title",
                    "abstract": self._get_full_abstract(article_root) or "No abstract available",
                    "journal": self._get_xml_text(article_root, './/Journal/Title') or "",
                    "authors": [],
                    "keywords": [],
                    "mesh_terms": []
                }
                
                # Get authors
                author_list = article_root.findall('.//Author')
                for author in author_list:
                    last_name = self._get_xml_text(author, 'LastName') or ""
                    fore_name = self._get_xml_text(author, 'ForeName') or ""
                    if last_name or fore_name:
                        article["authors"].append(f"{last_name} {fore_name}".strip())
                
                # Get publication date
                pub_date = article_root.find('.//PubDate')
                if pub_date is not None:
                    year = self._get_xml_text(pub_date, 'Year')
                    month = self._get_xml_text(pub_date, 'Month')
                    day = self._get_xml_text(pub_date, 'Day')
                    article["publication_date"] = {
                        "year": year,
                        "month": month,
                        "day": day
                    }
                    
                # Get DOI and PMCID if available
                # Important: Only get ArticleIds from the main ArticleIdList, not from references
                pubmed_data = article_root.find('.//PubmedData')
                if pubmed_data is not None:
                    # Use direct child path to avoid getting IDs from ReferenceList
                    article_id_list_elem = pubmed_data.find('ArticleIdList')
                    if article_id_list_elem is not None:
                        for article_id in article_id_list_elem:
                            id_type = article_id.get('IdType')
                            if id_type == 'doi':
                                article["doi"] = article_id.text
                            elif id_type == 'pmc':
                                article["pmcid"] = article_id.text

                # Get Keywords
                keyword_list = article_root.findall('.//Keyword')
                for keyword in keyword_list:
                    if keyword.text:
                        # Clean up keyword text (remove trailing periods, etc.)
                        clean_keyword = keyword.text.strip().rstrip('.')
                        if clean_keyword:
                            article["keywords"].append(clean_keyword)

                # Get MeSH terms
                mesh_heading_list = article_root.findall('.//MeshHeading')
                for mesh_heading in mesh_heading_list:
                    descriptor = mesh_heading.find('DescriptorName')
                    if descriptor is not None and descriptor.text:
                        mesh_term = {
                            "descriptor": descriptor.text,
                            "ui": descriptor.get('UI', ''),
                            "qualifiers": []
                        }

                        # Get qualifiers if present
                        qualifiers = mesh_heading.findall('QualifierName')
                        for qualifier in qualifiers:
                            if qualifier.text:
                                mesh_term["qualifiers"].append({
                                    "name": qualifier.text,
                                    "ui": qualifier.get('UI', '')
                                })

                        article["mesh_terms"].append(mesh_term)

                return article
                
            return None

        except Exception as e:
            logger.exception(f"Error getting article details for PMID {pmid}: {str(e)}")
            return None
            
    def _get_xml_text(self, elem: Optional[ET.Element], xpath: str) -> Optional[str]:
        """Helper method to safely get text from XML element."""
        if elem is None:
            return None
        found = elem.find(xpath)
        return found.text if found is not None else None

    def _get_full_abstract(self, article_root: Optional[ET.Element]) -> Optional[str]:
        """Get complete abstract text, handling structured abstracts with multiple sections."""
        if article_root is None:
            return None

        abstract_texts = article_root.findall('.//Abstract/AbstractText')

        if not abstract_texts:
            return None

        # If there's only one AbstractText element, return it directly
        if len(abstract_texts) == 1:
            return abstract_texts[0].text

        # For structured abstracts with multiple sections
        abstract_parts = []
        for text_elem in abstract_texts:
            label = text_elem.get('Label')
            text = text_elem.text or ""

            if label:
                # Format as "LABEL: text"
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)

        # Join all parts with double newline for readability
        return "\n\n".join(abstract_parts)