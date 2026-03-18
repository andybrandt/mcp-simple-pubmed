"""
Client for retrieving full text content of PubMed articles.
Separate from main PubMed client to maintain code separation and stability.
"""
import logging
import time
import http.client
from typing import Optional, Tuple
from Bio import Entrez
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pubmed-fulltext")


class PmidMismatchError(Exception):
    """Raised when the PMC article's PMID does not match the requested PMID.

    This indicates that elink returned a PMC article that is not the same
    as the requested PubMed article — typically a citing paper rather than
    the article itself.

    Attributes:
        requested_pmid: The PMID that was originally requested.
        found_pmid: The PMID found in the fetched PMC XML.
    """

    def __init__(self, requested_pmid: str, found_pmid: str):
        self.requested_pmid = requested_pmid
        self.found_pmid = found_pmid
        super().__init__(
            f"PMC article PMID {found_pmid} does not match "
            f"requested PMID {requested_pmid}"
        )


class FullTextClient:
    """Client for retrieving full text content from PubMed Central."""

    def __init__(self, email: str, tool: str, api_key: Optional[str] = None):
        """Initialize full text client with required credentials.

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

    async def check_full_text_availability(self, pmid: str) -> Tuple[bool, Optional[str]]:
        """Check if full text is available in PMC and get PMC ID if it exists.
        
        Args:
            pmid: PubMed ID of the article
            
        Returns:
            Tuple of (availability boolean, PMC ID if available)
        """
        try:
            logger.info(f"Checking PMC availability for PMID {pmid}")
            handle = Entrez.elink(dbfrom="pubmed", db="pmc", id=pmid)
            
            if not handle:
                logger.info(f"No PMC link found for PMID {pmid}")
                return False, None
                
            xml_content = handle.read()
            handle.close()
            
            # Parse XML to get PMC ID
            root = ET.fromstring(xml_content)
            # Filter for direct PMC link only — not pubmed_pmc_refs (citing papers)
            linksetdb = root.find(".//LinkSetDb[LinkName='pubmed_pmc']")
            if linksetdb is None:
                logger.info(f"No PMC ID found for PMID {pmid}")
                return False, None
                
            id_elem = linksetdb.find(".//Id")
            if id_elem is None:
                logger.info(f"No PMC ID element found for PMID {pmid}")
                return False, None
                
            pmc_id = id_elem.text
            logger.info(f"Found PMC ID {pmc_id} for PMID {pmid}")
            return True, pmc_id
            
        except Exception as e:
            logger.exception(f"Error checking PMC availability for PMID {pmid}: {str(e)}")
            return False, None

    async def get_full_text(self, pmid: str) -> Optional[str]:
        """Get full text of the article if available through PMC.
        
        Handles truncated responses by making additional requests.
        
        Args:
            pmid: PubMed ID of the article
            
        Returns:
            Full text content if available, None otherwise
        """
        try:
            # First check availability and get PMC ID
            available, pmc_id = await self.check_full_text_availability(pmid)
            if not available or pmc_id is None:
                logger.info(f"Full text not available in PMC for PMID {pmid}")
                return None

            logger.info(f"Fetching full text for PMC ID {pmc_id}")
            content = ""
            retstart = 0
            
            while True:
                full_text_handle = Entrez.efetch(
                    db="pmc", 
                    id=pmc_id, 
                    rettype="xml",
                    retstart=retstart
                )
                
                if not full_text_handle:
                    break
                    
                chunk = full_text_handle.read()
                full_text_handle.close()
                
                if isinstance(chunk, bytes):
                    chunk = chunk.decode('utf-8')
                
                content += chunk
                
                # Check if there might be more content
                if "[truncated]" not in chunk and "Result too long" not in chunk:
                    break
                    
                # Increment retstart for next chunk
                retstart += len(chunk)
                
                # Add small delay to respect API rate limits
                time.sleep(0.5)
                
            # Verify the fetched article matches the requested PMID
            root = ET.fromstring(content)
            article_pmid_elem = root.find(
                ".//article-meta/article-id[@pub-id-type='pmid']"
            )
            if article_pmid_elem is not None and article_pmid_elem.text != pmid:
                raise PmidMismatchError(
                    requested_pmid=pmid,
                    found_pmid=article_pmid_elem.text
                )

            return content

        except PmidMismatchError:
            raise  # Must propagate to server layer
        except Exception as e:
            logger.exception(f"Error getting full text for PMID {pmid}: {str(e)}")
            return None