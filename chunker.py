"""
ProteusP Smart Chunker
옵시디언 문서를 헤더 기반 + 의미 단위로 청킹하고 메타데이터 보존
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from proteusp.config import ProteusPConfig, get_config
from proteusp.parser import ObsidianDocument


@dataclass
class DocumentChunk:
    """A single chunk extracted from an Obsidian document with metadata."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""
    source_file: str = ""
    source_header: str = ""
    chunk_index: int = 0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "metadata": self.metadata,
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "chunk_index": self.chunk_index,
        }


def split_by_headers(
    text: str,
    headers: List[dict],
    min_chunk_chars: int = 50,
    max_chunk_chars: int = 2000,
) -> List[Tuple[str, str]]:
    """
    Split text by markdown headers while preserving header context.
    Returns list of (header_chain, content) tuples.
    """
    if not headers:
        # No headers - return whole text as single chunk if substantial
        stripped = text.strip()
        if len(stripped) >= min_chunk_chars:
            return [("", stripped)]
        return []

    chunks: List[Tuple[str, str]] = []
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # Find all header positions
    header_matches = list(header_pattern.finditer(text))
    header_chain: List[Tuple[int, str]] = []  # [(level, text), ...]

    for i, match in enumerate(header_matches):
        level = len(match.group(1))
        header_text = match.group(2).strip()

        # Pop headers that are deeper or equal to current level
        while header_chain and header_chain[-1][0] >= level:
            header_chain.pop()

        header_chain.append((level, header_text))

        # Determine content start/end
        content_start = match.end()
        if i + 1 < len(header_matches):
            content_end = header_matches[i + 1].start()
        else:
            content_end = len(text)

        content = text[content_start:content_end].strip()
        if len(content) < min_chunk_chars and i + 1 < len(header_matches):
            # Too short - merge with next section
            continue

        header_chain_str = " > ".join(h[1] for h in header_chain)
        chunks.append((header_chain_str, content))

    return chunks


def chunk_document(
    doc: ObsidianDocument,
    config: Optional[ProteusPConfig] = None,
) -> List[DocumentChunk]:
    """
    Split a single ObsidianDocument into chunks with rich metadata.
    """
    cfg = config or get_config()
    chunks: List[DocumentChunk] = []

    # Try header-based splitting first
    header_sections = split_by_headers(
        doc.content, doc.headers,
        max_chunk_chars=cfg.chunk_size * 2,
    )

    if header_sections:
        for idx, (header_chain, content) in enumerate(header_sections):
            if not content.strip():
                continue
            # Further split long sections
            sub_chunks = _split_long_text(
                content, cfg.chunk_size, cfg.chunk_overlap
            )
            for sub_idx, sub_text in enumerate(sub_chunks):
                if not sub_text.strip():
                    continue
                chunk = _build_chunk(
                    doc=doc,
                    text=sub_text,
                    header_chain=header_chain,
                    chunk_index=len(chunks),
                )
                chunks.append(chunk)
    else:
        # No headers - split by size
        sub_chunks = _split_long_text(
            doc.content, cfg.chunk_size, cfg.chunk_overlap
        )
        for idx, text in enumerate(sub_chunks):
            if not text.strip():
                continue
            chunk = _build_chunk(
                doc=doc, text=text, header_chain="", chunk_index=idx
            )
            chunks.append(chunk)

    # If document is very short, create a single chunk
    if not chunks and doc.content.strip():
        chunk = _build_chunk(doc=doc, text=doc.content.strip(), chunk_index=0)
        chunks.append(chunk)

    return chunks


def _split_long_text(
    text: str,
    chunk_size: int,
    overlap: int,
) -> List[str]:
    """Split long text into overlapping chunks at paragraph or sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    paragraphs = re.split(r"\n\s*\n", text)
    current_chunk = ""
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        para_len = len(para)

        if not para:
            continue

        if current_len + para_len + 2 <= chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
                current_len += para_len + 2
            else:
                current_chunk = para
                current_len = para_len
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # Start new chunk with overlap from previous
            if chunks and overlap > 0:
                # Take last `overlap` chars from previous chunk
                prev = chunks[-1]
                overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                current_chunk = overlap_text + "\n\n" + para
                current_len = len(current_chunk)
            else:
                current_chunk = para
                current_len = para_len

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [text]


def _build_chunk(
    doc: ObsidianDocument,
    text: str,
    chunk_index: int = 0,
    header_chain: str = "",
) -> DocumentChunk:
    """Build a DocumentChunk with comprehensive metadata from the source doc."""
    # Generate a stable chunk ID
    safe_name = doc.file_name.replace(" ", "_")[:40]
    chunk_id = f"{safe_name}#chunk{chunk_index:04d}"

    metadata = {
        "source": doc.file_path,
        "file_name": doc.file_name,
        "chunk_index": chunk_index,
        "header_chain": header_chain,
        "char_count": len(text),
        "tags": ",".join(doc.all_tags),
        "all_tags": doc.all_tags,
        "wiki_links": ",".join(doc.wiki_links[:10]),  # limit to 10
    }

    # Add frontmatter fields as metadata
    for key in ("created", "created_at", "date", "modified", "updated"):
        if key in doc.frontmatter:
            metadata[f"fm_{key}"] = str(doc.frontmatter[key])

    # Preserve selected frontmatter keys
    for fm_key in ("author", "category", "project", "status", "type"):
        if fm_key in doc.frontmatter:
            metadata[fm_key] = str(doc.frontmatter[fm_key])

    return DocumentChunk(
        text=text,
        metadata=metadata,
        chunk_id=chunk_id,
        source_file=doc.file_path,
        source_header=header_chain,
        chunk_index=chunk_index,
    )


def chunk_vault(
    documents: List[ObsidianDocument],
    config: Optional[ProteusPConfig] = None,
) -> List[DocumentChunk]:
    """
    Chunk an entire Obsidian vault into a flat list of DocumentChunks.
    """
    cfg = config or get_config()
    all_chunks: List[DocumentChunk] = []

    for doc in documents:
        chunks = chunk_document(doc, cfg)
        all_chunks.extend(chunks)

    print(f"Chunked into {len(all_chunks)} total chunks from {len(documents)} documents")
    return all_chunks
