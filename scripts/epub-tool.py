#!/usr/bin/env python3
"""
epub-tool: Inspect TOC structure and extract chapters/files from EPUBs into valid smaller EPUBs.
"""

import argparse
import os
import posixpath
import re
import subprocess
import sys
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


def get_flattened_toc(toc_items, depth=0):
    """
    Recursively unpacks the TOC tree into a flat list with depth metadata.
    Returns: [{'title': ..., 'href': ..., 'file_name': ..., 'fragment': ..., 'depth': ...}]
    """
    flat = []
    for item in toc_items:
        if isinstance(item, epub.Link):
            href = item.href or ""
            file_name = href.split('#')[0]
            fragment = href.split('#')[1] if '#' in href else None
            flat.append({
                'title': item.title.strip() if item.title else file_name,
                'href': href,
                'file_name': file_name,
                'fragment': fragment,
                'depth': depth
            })
        elif isinstance(item, (list, tuple)):
            if len(item) == 2 and isinstance(item[0], epub.Section):
                sec = item[0]
                href = sec.href or ""
                flat.append({
                    'title': sec.title.strip() if sec.title else "Section",
                    'href': href,
                    'file_name': href.split('#')[0],
                    'fragment': href.split('#')[1] if '#' in href else None,
                    'depth': depth
                })
                flat.extend(get_flattened_toc(item[1], depth=depth + 1))
            else:
                flat.extend(get_flattened_toc(item, depth=depth))
        elif isinstance(item, epub.Section):
            href = item.href or ""
            flat.append({
                'title': item.title.strip() if item.title else "Section",
                'href': href,
                'file_name': href.split('#')[0],
                'fragment': href.split('#')[1] if '#' in href else None,
                'depth': depth
            })
    return flat


def parse_range(range_str, max_val):
    """Parses range strings like '12-18', '2,4,6', or '3' into a 0-indexed list of integers."""
    selected_indices = set()
    for part in range_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-', 1)
            s_idx, e_idx = int(start) - 1, int(end) - 1
            if s_idx < 0 or e_idx >= max_val or s_idx > e_idx:
                raise ValueError(f"Range '{part}' is out of bounds (1-{max_val}).")
            selected_indices.update(range(s_idx, e_idx + 1))
        else:
            idx = int(part) - 1
            if idx < 0 or idx >= max_val:
                raise ValueError(f"Index '{part}' is out of bounds (1-{max_val}).")
            selected_indices.add(idx)
    return sorted(list(selected_indices))


def resolve_asset_path(base_doc_path, relative_path):
    """Normalizes relative asset paths against the document directory."""
    doc_dir = posixpath.dirname(base_doc_path)
    clean_path = relative_path.split('#')[0].split('?')[0]
    return posixpath.normpath(posixpath.join(doc_dir, clean_path))


def find_referenced_assets_in_html(doc_name, html_content):
    """Finds images, SVG objects, stylesheets, fonts, and media relative to the document."""
    soup = BeautifulSoup(html_content, 'html.parser')
    assets = set()

    for tag in soup.find_all(['img', 'image', 'link', 'source', 'video', 'audio', 'object', 'use']):
        src = tag.get('src') or tag.get('href') or tag.get('xlink:href') or tag.get('data')
        if src and not src.startswith(('http://', 'https://', 'data:', '#', 'mailto:')):
            resolved = resolve_asset_path(doc_name, src)
            assets.add(resolved)
            assets.add(posixpath.basename(resolved))

    return assets


def find_referenced_assets_in_css(css_name, css_content):
    """Finds url(...) references within CSS files (e.g. background images, web fonts)."""
    assets = set()
    if isinstance(css_content, bytes):
        css_content = css_content.decode('utf-8', errors='ignore')

    matches = re.findall(r'url\s*\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)', css_content, re.IGNORECASE)
    for src in matches:
        if src and not src.startswith(('http://', 'https://', 'data:', '#')):
            resolved = resolve_asset_path(css_name, src)
            assets.add(resolved)
            assets.add(posixpath.basename(resolved))
    return assets


def extract_pages(input_path, chapter_range_str, output_path, run_validation=False):
    book = epub.read_epub(input_path)
    toc_entries = get_flattened_toc(book.toc)

    if not toc_entries:
        print("Error: No Table of Contents entries found in the EPUB.", file=sys.stderr)
        sys.exit(1)

    selected_indices = parse_range(chapter_range_str, len(toc_entries))
    selected_toc = [toc_entries[i] for i in selected_indices]
    
    # Map selected entries to their actual XHTML files
    selected_file_names = {entry['file_name'] for entry in selected_toc if entry['file_name']}

    if not selected_file_names:
        print("Error: Selected TOC entries do not reference valid documents.", file=sys.stderr)
        sys.exit(1)

    # Initialize new EPUB
    new_book = epub.EpubBook()
    orig_id = book.get_metadata('DC', 'identifier')
    new_book.set_identifier(orig_id[0][0] + "-subset" if orig_id else "epub-extract-id")

    orig_title = book.get_metadata('DC', 'title')
    title = f"{orig_title[0][0]} (Excerpt)" if orig_title else "Extracted Chapters"
    new_book.set_title(title)

    orig_lang = book.get_metadata('DC', 'language')
    new_book.set_language(orig_lang[0][0] if orig_lang else 'en')

    # Step 1: Scan selected HTML documents for asset dependencies
    assets_to_keep = set()
    for item in book.get_items():
        if item.get_name() in selected_file_names:
            assets_to_keep.update(find_referenced_assets_in_html(item.get_name(), item.get_content()))

    # Step 2: Scan any referenced CSS files for secondary assets (fonts, images)
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_STYLE:
            item_name = item.get_name()
            if item_name in assets_to_keep or posixpath.basename(item_name) in assets_to_keep:
                assets_to_keep.update(find_referenced_assets_in_css(item_name, item.get_content()))

    # Step 3: Add documents, assets, and reconstruct the spine/TOC
    new_spine = ['nav']
    new_toc = []
    added_names = set()

    for entry in selected_toc:
        new_toc.append(epub.Link(entry['href'], entry['title'], entry['file_name']))

    asset_types = [
        ebooklib.ITEM_IMAGE,
        ebooklib.ITEM_STYLE,
        ebooklib.ITEM_FONT,
        ebooklib.ITEM_AUDIO,
        ebooklib.ITEM_VIDEO,
        ebooklib.ITEM_VECTOR,
        ebooklib.ITEM_SCRIPT
    ]

    for item in book.get_items():
        name = item.get_name()
        base_name = posixpath.basename(name)

        if name in selected_file_names:
            new_book.add_item(item)
            new_spine.append(item)
            added_names.add(name)
        elif (item.get_type() in asset_types) and (name in assets_to_keep or base_name in assets_to_keep):
            if name not in added_names:
                new_book.add_item(item)
                added_names.add(name)

    new_book.toc = new_toc
    new_book.add_item(epub.EpubNcx())
    new_book.add_item(epub.EpubNav())
    new_book.spine = new_spine

    epub.write_epub(output_path, new_book, {})
    print(f"Extracted {len(selected_file_names)} file(s) across {len(selected_indices)} TOC entry selection(s) -> {output_path}")

    if run_validation:
        print("\nRunning EPUBCheck validation...")
        try:
            res = subprocess.run(['epubcheck', output_path], capture_output=True, text=True)
            print(res.stdout)
            if res.returncode != 0:
                print(res.stderr, file=sys.stderr)
        except FileNotFoundError:
            print("epubcheck executable not found in PATH.")


def main():
    parser = argparse.ArgumentParser(description="epub-tool: Inspect TOC structure and extract EPUB chapters.")
    parser.add_argument("input_epub", help="Path to source EPUB file")
    parser.add_argument("--list", action="store_true", help="List all chapters and subsections in the TOC")
    parser.add_argument("--pages", "-c", help="Serial numbers to extract from --list (e.g., '12-18')")
    parser.add_argument("-o", "--output", default="extracted.epub", help="Output file path")
    parser.add_argument("--check", action="store_true", help="Run EPUBCheck validation on output")

    args = parser.parse_args()

    if not os.path.exists(args.input_epub):
        print(f"Error: File not found: {args.input_epub}", file=sys.stderr)
        sys.exit(1)

    book = epub.read_epub(args.input_epub)

    if args.list:
        flat_toc = get_flattened_toc(book.toc)
        print(f"TOC for '{args.input_epub}':")
        for i, entry in enumerate(flat_toc, start=1):
            indent = "  " * entry['depth']
            print(f"{i:3d}. {indent}{entry['title']} ({entry['href']})")
        return

    if not args.pages:
        print("Error: Specify --pages (e.g., --pages 12-18) or run with --list.", file=sys.stderr)
        sys.exit(1)

    extract_pages(args.input_epub, args.pages, args.output, run_validation=args.check)


if __name__ == "__main__":
    main()

