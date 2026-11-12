# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.17] - 2026-11-12

### Fixed
- **Truncated titles, abstracts and keywords** ([#17](https://github.com/andybrandt/mcp-simple-pubmed/pull/17), thanks to @dajiaohuang) - PubMed XML contains inline markup such as `<i>`, `<b>`, `<sup>` and `<sub>` (for example italicised species names). Text was read with ElementTree's `element.text`, which stops at the first inline element, so `"Study of <i>E. coli</i> growth"` became `"Study of "`. An abstract starting with an inline element was reported as missing, and so was a keyword. In a sample of 40 recent records, 31 titles and 49 of 75 abstract sections were affected. All free-text fields (title, journal, abstract, keywords, MeSH terms) now use `itertext()` to collect the full text.

### Added
- Unit tests for inline-markup handling (`tests/test_mixed_content.py`), including an end-to-end `get_article_details` test with a mocked efetch response

### Changed
- README: replaced broken Smithery badge ([#16](https://github.com/andybrandt/mcp-simple-pubmed/pull/16))

## [0.1.16] - 2026-03-19

### Fixed
- Redundant second elink call on every full-text request: the server now passes the already-known PMC ID to `get_full_text` ([#12](https://github.com/andybrandt/mcp-simple-pubmed/issues/12))
- Restored compatibility with Python 3.10 and later (`requires-python = ">=3.10"`, Dockerfile base image `python:3.10-slim`)

## [0.1.15] - 2026-03-18

### Fixed
- **get_full_text returning wrong paper** ([#11](https://github.com/andybrandt/mcp-simple-pubmed/issues/11)) - When a requested article was not in PMC, elink returned citing papers (`pubmed_pmc_refs`) instead of the article itself (`pubmed_pmc`). The code grabbed the first result regardless of link type, silently returning a completely different paper's full text. Fixed with XPath filter and PMID verification safety net.

### Added
- `PmidMismatchError` exception for explicit handling when fetched PMC article doesn't match the requested PMID
- Informative error messages to AI clients when full text retrieval fails due to PMID mismatch
- Unit test suite (`tests/test_fulltext_client.py`) with 8 tests covering `check_full_text_availability` and `get_full_text`
- Regression test in `test_client.py` for issue #11 (PMID 36738762)
- Build script (`build.sh`) for pip package and Docker image builds
- pytest and pytest-asyncio as dev dependencies

### Changed
- Dockerfile Python version from 3.10 to 3.13 to match `requires-python` in pyproject.toml
- License format in pyproject.toml from classifier to SPDX expression (`license = "MIT"`)

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

