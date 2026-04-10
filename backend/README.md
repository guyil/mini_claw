# feishu_sheet_parser

## Purpose
Parse a Feishu wiki node that points to a sheet, extract visible tabular text/mapping, and normalize it into `category -> bsr_url` pairs.

## Intended workflow
1. Resolve Feishu wiki node metadata.
2. If object is `sheet`, fetch page HTML via authenticated browser session or exported share page.
3. Extract rows using DOM/table heuristics.
4. Normalize headers such as `category`, `品类`, `bsr`, `url`, `链接`.
5. Output JSON mapping for downstream Amazon BSR research.

## Current local prototype files
- parser.py: parser helpers for HTML/text table extraction
- sample_usage.md: usage notes

## Constraints
Current Bot toolset lacks a direct Feishu Sheet cell-read API. This skill therefore provides a local parsing layer, but full automation still requires one of:
- browser access to an authenticated Feishu sheet page
- exported CSV/XLSX
- a future Feishu sheet API connector
