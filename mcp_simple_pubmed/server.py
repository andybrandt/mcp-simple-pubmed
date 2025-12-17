"""
MCP server implementation for PubMed integration using FastMCP SDK.
"""
import os
import json
import logging
from typing import Optional, Dict, Any, Tuple, List

from fastmcp import FastMCP
from mcp.types import TextContent
from mcp_simple_pubmed.pubmed_client import PubMedClient
from mcp_simple_pubmed.fulltext_client import FullTextClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pubmed-server")

# Initialize FastMCP app
app = FastMCP("pubmed-server")

def configure_clients() -> Tuple[PubMedClient, FullTextClient]:
    """Configure PubMed and full text clients with environment settings."""
    email = os.environ.get("PUBMED_EMAIL")
    if not email:
        raise ValueError("PUBMED_EMAIL environment variable is required")
        
    tool = os.environ.get("PUBMED_TOOL", "mcp-simple-pubmed")
    api_key = os.environ.get("PUBMED_API_KEY")

    pubmed_client = PubMedClient(email=email, tool=tool, api_key=api_key)
    fulltext_client = FullTextClient(email=email, tool=tool, api_key=api_key)
    
    return pubmed_client, fulltext_client

# Initialize the clients
pubmed_client, fulltext_client = configure_clients()

@app.tool(
    annotations={
        "title": "Search articles about medical and life sciences research available on PubMed.",
        "readOnlyHint": True,
        "openWorldHint": True  # Calls external PubMed API
    }
)
async def search_pubmed(query: str, max_results: int = 10) -> str:
    """Search PubMed for medical and life sciences research articles.

    You can use these search features:
    - Simple keyword search: "covid vaccine"
    - Field-specific search:
      - Title search: [Title]
      - Author search: [Author]
      - MeSH terms: [MeSH Terms]
      - Journal: [Journal]
    - Date ranges: Add year or date range like "2020:2024[Date - Publication]"
    - Combine terms with AND, OR, NOT
    - Use quotation marks for exact phrases

    Examples:
    - "covid vaccine" - basic search
    - "breast cancer"[Title] AND "2023"[Date - Publication]
    - "Smith J"[Author] AND "diabetes"
    - "RNA"[MeSH Terms] AND "therapy"

    The search will return:
    - Paper titles
    - Authors
    - Publication details
    - Abstract preview (when available)
    - Links to full text (when available)
    - DOI when available
    - Keywords and MeSH terms

    Note: Use quotes around multi-word terms for best results.
    """
    try:
        # Validate and constrain max_results
        max_results = min(max(1, max_results), 50)
        
        logger.info(f"Processing search with query: {query}, max_results: {max_results}")

        # Perform the search
        results = await pubmed_client.search_articles(
            query=query,
            max_results=max_results
        )
        
        # Create resource URIs for articles
        articles_with_resources = []
        for article in results:
            pmid = article["pmid"]
            # Add original URIs
            article["abstract_uri"] = f"pubmed://{pmid}/abstract"
            article["full_text_uri"] = f"pubmed://{pmid}/full_text"
            
            # Add DOI URL if DOI exists
            if "doi" in article:
                article["doi_url"] = f"https://doi.org/{article['doi']}"
                
            # Add PubMed URLs
            article["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            # Add PMC URL only if PMCID is available
            if "pmcid" in article:
                article["pmc_url"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article['pmcid']}/"
            
            articles_with_resources.append(article)

        # Format the response
        formatted_results = json.dumps(articles_with_resources, indent=2)
        logger.info(f"Search completed successfully, found {len(results)} results")

        return formatted_results
        
    except Exception as e:
        logger.exception(f"Error in search_pubmed")
        raise ValueError(f"Error processing search request: {str(e)}")

@app.tool(
    annotations={
        "title": "Get a paper's full text",
        "readOnlyHint": True,
        "openWorldHint": True  # Calls external PubMed API
    }
)
async def get_paper_fulltext(pmid: str) -> str:
    """Get full text of a PubMed article using its ID.

    This tool attempts to retrieve the complete text of the paper if available through PubMed Central.
    If the paper is not available in PMC, it will return a message explaining why and provide information
    about where the text might be available (e.g., through DOI).

    Example usage:
    get_paper_fulltext(pmid="39661433")

    Returns:
    - If successful: The complete text of the paper
    - If not available: A clear message explaining why (e.g., "not in PMC", "requires journal access")
    """
    try:
        logger.info(f"Attempting to get full text for PMID: {pmid}")

        # First check PMC availability
        available, pmc_id = await fulltext_client.check_full_text_availability(pmid)
        
        if available:
            full_text = await fulltext_client.get_full_text(pmid)
            if full_text:
                logger.info(f"Successfully retrieved full text from PMC for PMID {pmid}")
                return full_text

        # Get article details to provide alternative locations
        article = await pubmed_client.get_article_details(pmid)
        
        message = "Full text is not available in PubMed Central.\n\n"
        message += "The article may be available at these locations:\n"
        message += f"- PubMed page: https://pubmed.ncbi.nlm.nih.gov/{pmid}/\n"
        
        if article and "doi" in article:
            message += f"- Publisher's site (via DOI): https://doi.org/{article['doi']}\n"
            
        logger.info(f"Full text not available in PMC for PMID {pmid}, provided alternative locations")
        return message
        
    except Exception as e:
        logger.exception(f"Error in get_paper_fulltext")
        raise ValueError(f"Error retrieving full text: {str(e)}")


@app.resource("pubmed://{pmid}/{resource_type}")
async def read_pubmed_resource(pmid: str, resource_type: str) -> str:
    """
    Reads different types of content for a given PubMed ID (PMID).
    This can be the article's abstract or its full text.

    You can find PMIDs by searching for articles using the search_pubmed tool.

    Example usage:
    read_pubmed_resource(pmid="39661433", resource_type="abstract")
    read_pubmed_resource(pmid="39661433", resource_type="full_text")
    """
    logger.info(f"Reading resource for pmid={pmid}, type={resource_type}")
    try:
        if resource_type == "abstract":
            article = await pubmed_client.get_article_details(pmid)
            return json.dumps(article, indent=2)

        elif resource_type == "full_text":
            available, pmc_id = await fulltext_client.check_full_text_availability(pmid)
            if available:
                full_text = await fulltext_client.get_full_text(pmid)
                if full_text:
                    return full_text
            
            # If not available, provide the same helpful message as the tool
            article = await pubmed_client.get_article_details(pmid)
            message = "Full text is not available in PubMed Central.\n\n"
            message += "The article may be available at these locations:\n"
            message += f"- PubMed page: https://pubmed.ncbi.nlm.nih.gov/{pmid}/\n"
            if article and "doi" in article:
                message += f"- Publisher's site (via DOI): https://doi.org/{article['doi']}\n"
            return message

        else:
            raise ValueError(f"Invalid resource type requested: {resource_type}")

    except Exception as e:
        logger.exception(f"Error reading resource pmid={pmid}, type={resource_type}")
        raise ValueError(f"Error reading resource: {str(e)}")


# =============================================================================
# Prompts - Templates to help users construct effective PubMed searches
# =============================================================================

@app.prompt()
def systematic_review_search(topic: str, years: str = "5") -> List[TextContent]:
    """Generate a systematic review search strategy for a medical topic."""
    return [
        TextContent(
            type="text",
            text=f"""Help me create a comprehensive PubMed search strategy for a systematic review on: "{topic}"

Please build a search query that includes:
1. MeSH terms (Medical Subject Headings) for the main concept
2. Free-text synonyms and related terms
3. Boolean operators (AND, OR) to combine terms
4. Date filter for the last {years} years using [PDAT]

Use PubMed field tags like:
- [MeSH Terms] for controlled vocabulary
- [Title/Abstract] for free text
- [PDAT] for publication date

Example format: (term1[MeSH Terms] OR term2[Title/Abstract]) AND ("2020"[PDAT] : "2025"[PDAT])

After constructing the query, use the search_pubmed tool to execute it."""
        )
    ]


@app.prompt()
def pico_search(
    population: str,
    intervention: str,
    comparison: str = "",
    outcome: str = ""
) -> List[TextContent]:
    """Build a PICO-based search query for clinical questions."""
    pico_parts = [f"Population: {population}", f"Intervention: {intervention}"]
    if comparison:
        pico_parts.append(f"Comparison: {comparison}")
    if outcome:
        pico_parts.append(f"Outcome: {outcome}")

    pico_list = "\n".join("- " + p for p in pico_parts)

    return [
        TextContent(
            type="text",
            text=f"""Help me search PubMed for this clinical question using the PICO framework:

{pico_list}

Please:
1. Identify MeSH terms and synonyms for each PICO element
2. Combine terms within each element using OR
3. Combine PICO elements using AND
4. Consider adding study type filters (e.g., Clinical Trial, Meta-Analysis)

Build the query and use search_pubmed to find relevant articles."""
        )
    ]


@app.prompt()
def author_search(author_name: str, affiliation: str = "") -> List[TextContent]:
    """Find all publications by a specific author."""
    affiliation_note = f" affiliated with {affiliation}" if affiliation else ""

    return [
        TextContent(
            type="text",
            text=f"""Help me find all PubMed publications by author: {author_name}{affiliation_note}

Please:
1. Format the author name correctly for PubMed (LastName FirstInitial, e.g., "Smith J")
2. Use the [Author] field tag
3. If affiliation is provided, combine with [Affiliation] field
4. Consider name variations (full name vs initials)

Build the query and use search_pubmed to retrieve the publications."""
        )
    ]


def main():
    """Run the MCP server."""
    app.run()

if __name__ == "__main__":
    main() 