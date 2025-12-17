# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.14] - 2025-12-17

### Added
- **MCP Prompts feature** - Server-side prompt templates to help users construct effective PubMed searches:
  - `systematic_review_search` - Generates comprehensive search strategies for systematic reviews with MeSH terms, free-text synonyms, Boolean operators, and date filters
  - `pico_search` - Builds clinical question searches using the PICO framework (Population, Intervention, Comparison, Outcome)
  - `author_search` - Finds all publications by a specific author with proper PubMed name formatting
- New test cases for prompt listing and retrieval in test_client.py

### Changed
- Updated FastMCP dependency from 2.10.0 to 2.14.1 for improved stability and pydantic compatibility
- Updated README.md with comprehensive feature documentation

## [0.1.13] - 2025-07-15

### Added
- Full text retrieval from PubMed Central
- Resource templates for direct article access (`pubmed://{pmid}/abstract`, `pubmed://{pmid}/full_text`)
- Advanced search support with date ranges via [PDAT] field

### Changed
- Migrated to FastMCP 2.0 SDK with decorator-based tool registration
- Improved tool annotations with `readOnlyHint` and `openWorldHint`

## [0.1.12] and earlier

Initial releases with basic PubMed search and abstract retrieval functionality.

