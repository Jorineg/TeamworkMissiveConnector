"""Parser to convert Craft's XML-Markdown mix to clean Markdown."""
import re
from typing import List, Dict, Optional
from src.logging_conf import logger


def parse_craft_markdown(raw: str) -> str:
    """
    Convert Craft's XML-Markdown mix to clean Markdown.
    Falls back to original content on parse errors.
    """
    if not raw:
        return raw
    try:
        return _parse_content(raw)
    except Exception as e:
        logger.warning(f"Craft markdown parse failed, using raw: {e}")
        return raw


def _parse_content(content: str) -> str:
    """Main parsing logic."""
    # Remove outer page wrapper and extract content
    content = _unwrap_page(content)
    
    # Process collections first (most complex)
    content = _process_collections(content)
    
    # Process nested pages (cards, subpages)
    content = _process_nested_pages(content)
    
    # Process simple inline tags
    content = _process_simple_tags(content)
    
    # Clean up whitespace
    content = _clean_whitespace(content)
    
    return content.strip()


def _unwrap_page(content: str) -> str:
    """Extract content from <page> wrapper."""
    # Match <page id="...">...<pageTitle>...</pageTitle><content>...</content></page>
    match = re.search(
        r'<page[^>]*>\s*<pageTitle>([^<]*)</pageTitle>\s*<content>(.*?)</content>\s*</page>',
        content, re.DOTALL
    )
    if match:
        title = match.group(1).strip()
        inner = match.group(2)
        return f"# {title}\n\n{inner}"
    
    # Simpler case: just <page><content>...</content></page>
    match = re.search(r'<content>(.*?)</content>', content, re.DOTALL)
    if match:
        return match.group(1)
    
    return content


def _process_collections(content: str) -> str:
    """Convert <collection> blocks to Markdown tables."""
    pattern = re.compile(
        r'<collection>\s*'
        r'<title>([^<]*)</title>\s*'
        r'<properties>([^<]*)</properties>\s*'
        r'<content>(.*?)</content>\s*'
        r'</collection>',
        re.DOTALL
    )
    
    def replace_collection(match):
        title = match.group(1).strip()
        props_raw = match.group(2).strip()
        items_content = match.group(3)
        
        # Parse property names
        props = [p.strip() for p in props_raw.split(',') if p.strip()]
        
        # Parse collection items
        items = _parse_collection_items(items_content, props)
        
        # Build markdown table
        return _build_collection_table(title, props, items)
    
    return pattern.sub(replace_collection, content)


def _parse_collection_items(content: str, props: List[str]) -> List[Dict]:
    """Parse <collectionItem> elements."""
    items = []
    pattern = re.compile(
        r'<collectionItem>\s*(.*?)\s*</collectionItem>',
        re.DOTALL
    )
    
    for match in pattern.finditer(content):
        item_content = match.group(1)
        item = {'_title': '', '_content': '', '_props': {}}
        
        # Extract title
        title_match = re.search(r'<title>([^<]*)</title>', item_content)
        if title_match:
            item['_title'] = title_match.group(1).strip()
        
        # Extract properties
        prop_pattern = re.compile(r'<property name="([^"]+)">([^<]*)</property>')
        for prop_match in prop_pattern.finditer(item_content):
            prop_name = prop_match.group(1)
            prop_value = prop_match.group(2).strip()
            item['_props'][prop_name] = prop_value
        
        # Extract nested content
        content_match = re.search(r'<content>(.*?)</content>', item_content, re.DOTALL)
        if content_match:
            nested = content_match.group(1).strip()
            # Recursively process nested content
            item['_content'] = _process_simple_tags(nested)
        
        # Skip empty items
        if item['_title'] or any(item['_props'].values()):
            items.append(item)
    
    return items


def _build_collection_table(title: str, props: List[str], items: List[Dict]) -> str:
    """Build Markdown table from collection data."""
    if not items:
        return f"## {title}\n\n*Empty collection*\n"
    
    lines = [f"## {title}\n"]
    
    # Header row
    header = "| Title | " + " | ".join(props) + " |"
    separator = "|" + "---|" * (len(props) + 1)
    lines.append(header)
    lines.append(separator)
    
    # Data rows + nested content
    nested_contents = []
    for item in items:
        row_cells = [_escape_table_cell(item['_title'])]
        for prop in props:
            val = item['_props'].get(prop, '')
            row_cells.append(_escape_table_cell(val))
        lines.append("| " + " | ".join(row_cells) + " |")
        
        # Collect nested content for after the table
        if item['_content']:
            nested_contents.append((item['_title'], item['_content']))
    
    lines.append("")
    
    # Add nested content as subsections
    for item_title, item_content in nested_contents:
        if item_title:
            lines.append(f"### {item_title}\n")
        lines.append(item_content.strip())
        lines.append("")
    
    return "\n".join(lines)


def _escape_table_cell(text: str) -> str:
    """Escape pipe characters in table cells."""
    if not text:
        return ""
    return text.replace("|", "\\|").replace("\n", " ")


def _process_nested_pages(content: str) -> str:
    """Convert nested <page> elements to Markdown sections."""
    # Match nested pages with various styles
    pattern = re.compile(
        r'<page[^>]*>\s*'
        r'<pageTitle>([^<]*)</pageTitle>\s*'
        r'<content>(.*?)</content>\s*'
        r'</page>',
        re.DOTALL
    )
    
    def replace_page(match):
        title = match.group(1).strip()
        inner = match.group(2).strip()
        # Recursively process inner content
        inner = _process_nested_pages(inner)
        inner = _process_simple_tags(inner)
        return f"### {title}\n\n{inner}\n"
    
    return pattern.sub(replace_page, content)


def _process_simple_tags(content: str) -> str:
    """Convert simple XML tags to Markdown equivalents."""
    # <callout>text</callout> -> > text
    content = re.sub(
        r'<callout>([^<]*(?:<[^/][^>]*>[^<]*</[^>]+>[^<]*)*)</callout>',
        lambda m: "> " + m.group(1).strip().replace("\n", "\n> "),
        content
    )
    
    # <highlight color="...">text</highlight> -> **text**
    content = re.sub(
        r'<highlight[^>]*>([^<]*)</highlight>',
        r'**\1**',
        content
    )
    
    # Remove remaining unknown tags but keep content
    content = re.sub(r'<pageTitle>([^<]*)</pageTitle>', r'# \1', content)
    content = re.sub(r'<content>|</content>', '', content)
    content = re.sub(r'<page[^>]*>|</page>', '', content)
    
    return content


def _clean_whitespace(content: str) -> str:
    """Clean up excessive whitespace."""
    # Replace multiple blank lines with double newline
    content = re.sub(r'\n{3,}', '\n\n', content)
    # Remove trailing whitespace on lines
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
    # Ensure proper spacing around headers
    content = re.sub(r'\n(#{1,6} )', r'\n\n\1', content)
    return content

