import asyncio
import os
from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport
import json

async def main():
    """A simple test client to connect to the PubMed server and test its tools."""
    # Set the required environment variable for the server process
    server_env = {"PUBMED_EMAIL": "test@example.com"}
    
    # Configure the stdio transport with the server script and environment
    transport = StdioTransport(
        command="python",
        args=["mcp_simple_pubmed/server.py"],
        env=server_env
    )
    
    # Create a client that uses our configured transport
    client = Client(transport)
    
    print("Starting client...")
    async with client:
        try:
            # --- Test 1: List Tools ---
            print("\n--- Running Test 1: List Tools ---")
            tools = await client.list_tools()
            print("--- Available Tools ---")
            for tool in tools:
                print(f"- {tool.name}: {tool.annotations.title if tool.annotations else 'No title'}")
                print(f"  {tool.description}\n")

            # --- Test 2: Search for articles ---
            print("\n\n--- Running Test 2: Search for articles ---")
            print("Calling 'search_pubmed' tool with query: 'tuberculosis treatment'...")
            search_result = await client.call_tool(
                "search_pubmed", 
                {"query": "tuberculosis treatment", "max_results": 5}
            )
            
            print("\n--- Search Result ---")
            parsed_search_result = json.loads(search_result.data)
            print(json.dumps(parsed_search_result, indent=2))
            
            # --- Test 3: Fetch full text of the first article from search ---
            if parsed_search_result:
                print("\n\n--- Running Test 3: Fetch full text of the first article from search ---")
                first_article_pmid = parsed_search_result[0].get("pmid")
                if first_article_pmid:
                    print(f"Calling 'get_paper_fulltext' for PMID: {first_article_pmid}...")
                    fulltext_result_1 = await client.call_tool(
                        "get_paper_fulltext",
                        {"pmid": first_article_pmid}
                    )
                    print("\n--- Full Text Result 1 ---")
                    # Print only a snippet as this can be long
                    print(fulltext_result_1.data[:500] + "...")
                else:
                    print("Could not find PMID in the first search result.")
            else:
                print("Search returned no results, skipping full text fetch.")

            # --- Test 4: Fetch full text for a specific, known article ---
            print("\n\n--- Running Test 4: Fetch full text for a specific, known article ---")
            specific_pmid = "24677277"
            print(f"Calling 'get_paper_fulltext' for PMID: {specific_pmid}...")
            fulltext_result_2 = await client.call_tool(
                "get_paper_fulltext",
                {"pmid": specific_pmid}
            )
            print("\n--- Full Text Result 2 ---")
            # Print only a snippet if it's very long
            result_text = fulltext_result_2.data
            if len(result_text) > 1000:
                print(result_text[:1000] + "\n\n... (truncated for brevity)")
            else:
                print(result_text)

            # --- Test 5: Read abstract resource from the first search result ---
            if parsed_search_result:
                print("\n\n--- Running Test 5: Read abstract resource ---")
                first_article = parsed_search_result[0]
                abstract_uri = first_article.get("abstract_uri")
                
                if abstract_uri:
                    print(f"Reading resource at URI: {abstract_uri}...")
                    abstract_result = await client.read_resource(abstract_uri)
                    
                    print("\n--- Abstract Resource Result ---")
                    # The result from a resource read is a list of contents. We'll parse the first.
                    parsed_abstract = json.loads(abstract_result[0].text)
                    print(json.dumps(parsed_abstract, indent=2))
                else:
                    print("Could not find abstract_uri in the first search result.")
            else:
                print("Search returned no results, skipping resource read.")

            # --- Test 6: Read full_text resource for a specific, known article ---
            print("\n\n--- Running Test 6: Read full_text resource ---")
            specific_pmid_for_resource = "24677277"
            full_text_uri = f"pubmed://{specific_pmid_for_resource}/full_text"
            print(f"Reading resource at URI: {full_text_uri}...")
            full_text_resource_result = await client.read_resource(full_text_uri)
            
            print("\n--- Full Text Resource Result ---")
            # The result from a resource read is a list of contents. We'll print the first.
            result_text = full_text_resource_result[0].text
            if len(result_text) > 1000:
                print(result_text[:1000] + "\n\n... (truncated for brevity)")
            else:
                print(result_text)

            # --- Test 7: List Prompts ---
            print("\n\n--- Running Test 7: List Prompts ---")
            prompts = await client.list_prompts()
            print("--- Available Prompts ---")
            for prompt in prompts:
                print(f"- {prompt.name}: {prompt.description}")
                if prompt.arguments:
                    for arg in prompt.arguments:
                        required_marker = " (required)" if arg.required else ""
                        print(f"    - {arg.name}{required_marker}: {arg.description}")

            # --- Test 8: Get a Prompt (systematic_review_search) ---
            print("\n\n--- Running Test 8: Get Prompt (systematic_review_search) ---")
            prompt_result = await client.get_prompt(
                "systematic_review_search",
                arguments={"topic": "diabetes prevention", "years": "3"}
            )
            print("--- Prompt Result ---")
            for message in prompt_result.messages:
                # Handle different content types
                content = message.content
                if hasattr(content, 'text'):
                    print(f"Content: {content.text[:300]}...")
                else:
                    print(f"Content: {str(content)[:300]}...")

            # --- Test 9: Get a Prompt (pico_search) ---
            print("\n\n--- Running Test 9: Get Prompt (pico_search) ---")
            pico_result = await client.get_prompt(
                "pico_search",
                arguments={
                    "population": "adults with type 2 diabetes",
                    "intervention": "metformin",
                    "comparison": "placebo",
                    "outcome": "HbA1c reduction"
                }
            )
            print("--- PICO Prompt Result ---")
            for message in pico_result.messages:
                content = message.content
                if hasattr(content, 'text'):
                    print(f"Content: {content.text[:300]}...")
                else:
                    print(f"Content: {str(content)[:300]}...")

            # --- Test 10: Get a Prompt (author_search) ---
            print("\n\n--- Running Test 10: Get Prompt (author_search) ---")
            author_result = await client.get_prompt(
                "author_search",
                arguments={"author_name": "Fauci Anthony", "affiliation": "NIH"}
            )
            print("--- Author Search Prompt Result ---")
            for message in author_result.messages:
                content = message.content
                if hasattr(content, 'text'):
                    print(f"Content: {content.text[:300]}...")
                else:
                    print(f"Content: {str(content)[:300]}...")

        except Exception as e:
            print(f"An error occurred: {e}")
            
if __name__ == "__main__":
    asyncio.run(main()) 