"""
MCP server providing access to PubMed articles through Entrez API.
"""
import asyncio
import os
from . import server

def main():
    """Main entry point for the package."""
    asyncio.run(server.main())

__version__ = "0.1.16"