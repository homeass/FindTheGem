"""
ProteusP Obsidian Markdown Parser
옵시디언 노트의 프론트매터, 태그, 위키링크, 헤더 구조 파싱
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class ObsidianDocument:
    """Parsed Obsidian markdown document with full metadata."""
    file_path: str
    file_name: str
    content: str                          # Raw content (without frontmatter)
    frontmatter: dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)       # #tag from body
    frontmatter_tags: List[str] = field(default_factory=list)  # tags from YAML
    wiki_links: List[str] = field(default_factory=list)  # [[Link]] targets
    headers: List[dict] = field(default_factory=list)    # {level, text}
    char_count: int = 0
    line_count: int = 0
    created_time: Optional[str] = None
    modified_time: Optional[str] = None

    @property
    def all_tags(self) -> List[str]:
        """Merge body tags and frontmatter tags, deduplicated."""
        seen = set()
        result = []
        for t in self.frontmatter_tags + self.tags:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result


# Regex patterns for Obsidian-specific syntax
PATTERN_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
PATTERN_TAG = re.compile(r"(?<!\w)#([\w가-힣/_-]+)")
PATTERN_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
PATTERN_HEADER = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
PATTERN_INTERNAL_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Extract YAML frontmatter and return (frontmatter_dict, remaining_text).
    Returns ({}, text) if no valid frontmatter.
    """
    match = PATTERN_FRONTMATTER.match(text)
    if not match:
        return {}, text

    yaml_text = match.group(1).strip()
    remaining = text[match.end():]
    try:
        fm = yaml.safe_load(yaml_text) or {}
        if not isinstance(fm, dict):
            return {}, text
        return fm, remaining
    except yaml.YAMLError:
        return {}, remaining


def extract_tags(text: str, seen_tags: Optional[set] = None) -> List[str]:
    """
    Extract all unique #tags from text content.
    Skips tags inside code blocks and markdown links.
    """
    if seen_tags is None:
        seen_tags = set()

    # Remove code blocks before tag extraction
    no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]*`", "", no_code)

    tags = []
    for match in PATTERN_TAG.finditer(no_code):
        tag = match.group(1).strip()
        if tag and tag not in seen_tags:
            seen_tags.add(tag)
            # Normalize: #tag/tag2 -> tag/tag2
            tag = tag.lstrip("#")
            if tag:
                tags.append(tag)
    return tags


def extract_wiki_links(text: str) -> List[str]:
    """Extract all [[WikiLink]] targets from text."""
    return [match.group(1).strip() for match in PATTERN_WIKILINK.finditer(text)]


def extract_headers(text: str) -> List[dict]:
    """Extract headers with their levels."""
    headers = []
    for match in PATTERN_HEADER.finditer(text):
        level = len(match.group(1))
        header_text = match.group(2).strip()
        headers.append({"level": level, "text": header_text})
    return headers


def get_frontmatter_tags(frontmatter: dict) -> List[str]:
    """Extract tags from frontmatter (supports 'tags' key as string or list)."""
    tags = []
    for key in ("tags", "tag", "categories"):
        val = frontmatter.get(key, [])
        if isinstance(val, str):
            tags.extend([t.strip() for t in val.split(",") if t.strip()])
        elif isinstance(val, list):
            tags.extend([str(t).strip() for t in val if t])
    return tags


def parse_obsidian_file(file_path: str) -> Optional[ObsidianDocument]:
    """
    Parse a single Obsidian markdown file into a structured document.
    Returns None if the file is not a valid markdown file.
    """
    path = Path(file_path)

    if not path.exists() or path.suffix.lower() not in (".md", ".markdown"):
        return None

    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except (IOError, PermissionError) as e:
        print(f"Warning: Cannot read {file_path}: {e}")
        return None

    # Step 1: Extract frontmatter
    frontmatter, body_text = parse_frontmatter(raw_text)

    # Step 2: Extract structured data from body
    tags = extract_tags(body_text)
    frontmatter_tags = get_frontmatter_tags(frontmatter)
    wiki_links = extract_wiki_links(body_text)
    headers = extract_headers(body_text)

    # Step 3: Build document
    doc = ObsidianDocument(
        file_path=str(path.resolve()),
        file_name=path.stem,
        content=body_text.strip(),
        frontmatter=frontmatter,
        tags=tags,
        frontmatter_tags=frontmatter_tags,
        wiki_links=wiki_links,
        headers=headers,
        char_count=len(body_text),
        line_count=body_text.count("\n") + 1,
    )

    # Optional: extract time metadata from frontmatter
    for key in ("created", "created_at", "date"):
        if key in frontmatter:
            doc.created_time = str(frontmatter[key])
            break
    for key in ("modified", "updated", "last_modified"):
        if key in frontmatter:
            doc.modified_time = str(frontmatter[key])
            break

    return doc


def resolve_wiki_links(
    documents: List[ObsidianDocument],
) -> dict[str, List[str]]:
    """
    Build a mapping of wiki link targets to document paths.
    Returns {normalized_link_name: [file_path1, file_path2, ...]}
    """
    name_to_paths: dict[str, List[str]] = {}
    for doc in documents:
        name = doc.file_name.lower()
        if name not in name_to_paths:
            name_to_paths[name] = []
        name_to_paths[name].append(doc.file_path)

    # Resolve each document's wiki links
    link_map: dict[str, List[str]] = {}
    for doc in documents:
        related = []
        for link in doc.wiki_links:
            link_lower = link.lower()
            if link_lower in name_to_paths:
                related.extend(name_to_paths[link_lower])
        if related:
            link_map[doc.file_path] = list(set(related))

    return link_map


def parse_vault(vault_path: str, recursive: bool = True) -> List[ObsidianDocument]:
    """
    Parse all markdown files in an Obsidian vault directory.
    Returns a list of ObsidianDocument objects.
    """
    path = Path(vault_path)
    if not path.exists():
        print(f"Warning: Vault path does not exist: {vault_path}")
        return []

    pattern = "**/*.md" if recursive else "*.md"
    documents = []

    for md_file in sorted(path.glob(pattern)):
        # Skip hidden files and directories
        if any(part.startswith(".") for part in md_file.parts):
            continue
        doc = parse_obsidian_file(str(md_file))
        if doc:
            documents.append(doc)

    print(f"Parsed {len(documents)} markdown files from {vault_path}")
    return documents
