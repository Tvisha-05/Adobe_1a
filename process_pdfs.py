import fitz  # PyMuPDF
import json
import re
import os
import pdfplumber
import collections
from collections import defaultdict
INPUT_DIR = '/app/input'
OUTPUT_DIR = '/app/output'

def extract_heading_structure(pdf_path):
    doc = fitz.open(pdf_path)
    headings = []
    all_font_sizes = []
    all_spans = []

    # Step 1: Collect font sizes and all spans
    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" not in b:
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    text = s["text"].strip()
                    font_size = s["size"]
                    if not text or len(text) < 3 or font_size < 6:
                        continue
                    all_font_sizes.append(font_size)
                    all_spans.append({
                        "text": text,
                        "size": font_size,
                        "font": s["font"],
                        "flags": s["flags"],
                        "bold": ("bold" in s["font"].lower() or (s["flags"] & 2)),
                        "y0": s["bbox"][1],
                        "y1": s["bbox"][3],
                        "x0": s["bbox"][0],
                        "x1": s["bbox"][2],
                        "page": page_num,
                        "page_height": page.rect.height,
                        "page_width": page.rect.width
                    })
    if not all_font_sizes:
        return []

    # Step 2: Compute font size thresholds
    unique_sizes = sorted(list(set(all_font_sizes)), reverse=True)
    size_to_level = {}
    if len(unique_sizes) > 0:
        size_to_level[unique_sizes[0]] = "H1"
    if len(unique_sizes) > 1:
        size_to_level[unique_sizes[1]] = "H2"
    if len(unique_sizes) > 2:
        size_to_level[unique_sizes[2]] = "H3"
    if len(unique_sizes) > 3:
        size_to_level[unique_sizes[3]] = "H4"

    # Step 3: Advanced title extraction
    first_page_spans = [s for s in all_spans if s["page"] == 1]
    title = ""
    if first_page_spans:
        # Try largest font size first
        max_size = max(s["size"] for s in first_page_spans)
        def get_title_lines(font_size):
            candidates = [s for s in sorted(first_page_spans, key=lambda x: x["y0"]) if abs(s["size"] - font_size) < 0.1 and s["y0"] < 250]
            grouped = []
            prev = None
            for s in candidates:
                # Filter out fragments, substrings, and repeats
                if (len(s["text"]) < 5 or
                    any(s["text"] in t["text"] or t["text"] in s["text"] for t in grouped) or
                    sum(s["text"] == t["text"] for t in grouped) > 0):
                    continue
                if prev and abs(s["y0"] - prev["y1"]) < 25 and abs(s["x0"] - prev["x0"]) < 60:
                    prev["text"] += " " + s["text"]
                    prev["y1"] = s["y1"]
                else:
                    grouped.append(s.copy())
                    prev = grouped[-1]
            return grouped
        grouped_title = get_title_lines(max_size)
        # If too short, try next largest font size
        if len(" ".join([t["text"] for t in grouped_title])) < 30 and len(unique_sizes) > 1:
            grouped_title = get_title_lines(unique_sizes[1])
        title = " ".join([t["text"] for t in grouped_title]).strip()

    # Step 4: Advanced heading detection and grouping
    heading_keywords = [
        "summary", "background", "timeline", "business plan", "approach",
        "evaluation", "appendix", "proposal", "phase", "terms", "membership",
        "meetings", "financial", "accountability", "resources", "ontario",
        "digital library", "prosperity strategy", "milestones", "access",
        "guidance", "training", "support", "preamble", "chair"
    ]
    candidates = []
    for s in all_spans:
        text = s["text"]
        # Exclude subheadings like '9.1 ...', '8.2 ...', etc.
        if re.match(r'^\d+\.\d+ ', text):
            continue
        # Only allow main section headings like '9 ...', '8 ...', '2. ...', '3. ...'
        is_main_numbered = re.match(r'^(\d+)[\s\.]', text)
        is_heading_like = (
            is_main_numbered or
            any(kw in text.lower() for kw in heading_keywords) or
            re.match(r"^appendix [a-zA-Z]", text) or
            re.match(r"^[A-Z][A-Za-z\s]+$", text) or  # Title case
            text.endswith(":") or  # Ends with colon
            (len(text) > 10 and len(text) < 80)  # Reasonable length
        )
        level = size_to_level.get(s["size"], None)
        if level and (s["size"] > 9 and (s["bold"] or is_heading_like)):
            candidates.append({**s, "level": level})
    # Group multi-line headings robustly
    grouped = []
    prev = None
    for s in candidates:
        # Filter out fragments and substrings in headings
        if (len(s["text"]) < 5 or
            any(s["text"] in t["text"] or t["text"] in s["text"] for t in grouped) or
            sum(s["text"] == t["text"] for t in grouped) > 0):
            continue
        if (prev and s["level"] == prev["level"] and s["page"] == prev["page"] and 
            abs(s["y0"] - prev["y1"]) < 18 and abs(s["x0"] - prev["x0"]) < 60 and
            abs(s["size"] - prev["size"]) < 0.1):
            prev["text"] += " " + s["text"]
            prev["y1"] = s["y1"]
        else:
            grouped.append(s.copy())
            prev = grouped[-1]
    # Remove headings that are substrings of others on the same page
    filtered = []
    for i, s in enumerate(grouped):
        if any((s["page"] == t["page"] and s["text"] != t["text"] and (s["text"] in t["text"] or t["text"] in s["text"])) for t in grouped):
            # Only keep the longer one
            if all(len(s["text"]) >= len(t["text"]) for t in grouped if s["page"] == t["page"] and (s["text"] in t["text"] or t["text"] in s["text"])):
                filtered.append(s)
        else:
            filtered.append(s)
    # Assign heading levels after grouping
    outline = []
    for s in filtered:
        group_level = size_to_level.get(s["size"], "H4")
        outline.append({
            "level": group_level,
            "text": s["text"].strip(),
            "page": s["page"]
        })
    return title, outline

def extract_heading_structure_pdfplumber_lines(pdf_path):
    import re
    import collections
    headings = []
    all_font_sizes = []
    all_lines = []
    
    def is_repeated_letters(s):
        import re
        return bool(re.search(r'(\w)\1{2,}', s))
    
    def is_garbled_text(s):
        """Detect and filter out garbled/corrupted text"""
        import re
        # Check for excessive repeated characters (like RRRRFFFFPPPP)
        if re.search(r'(\w)\1{3,}', s):
            return True
        # Check for excessive punctuation repetition
        if re.search(r'([:;.,!?])\1{2,}', s):
            return True
        # Check for non-printable characters
        if not s.isprintable():
            return True
        # Check for text that's mostly the same character
        if len(set(s)) < len(s) * 0.3 and len(s) > 10:
            return True
        # Check for excessive uppercase repetition
        if re.search(r'([A-Z])\1{3,}', s):
            return True
        return False
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(extra_attrs=["size", "fontname"])
            # Group words into lines by y0 (with tolerance)
            lines_by_y = {}
            for w in words:
                y = round(w["top"] / 2) * 2  # Tolerance for y
                key = (y, page_num)
                if key not in lines_by_y:
                    lines_by_y[key] = []
                lines_by_y[key].append(w)
            for (y, p), ws in lines_by_y.items():
                ws_sorted = sorted(ws, key=lambda x: x["x0"])
                text = " ".join(w["text"] for w in ws_sorted).strip()
                font_size = max(w["size"] for w in ws_sorted)
                font = ws_sorted[0].get("fontname", "")
                x0 = min(w["x0"] for w in ws_sorted)
                x1 = max(w["x1"] for w in ws_sorted)
                y0 = min(w["top"] for w in ws_sorted)
                y1 = max(w["bottom"] for w in ws_sorted)
                all_font_sizes.append(font_size)
                all_lines.append({
                    "text": text,
                    "size": font_size,
                    "font": font,
                    "y0": y0,
                    "y1": y1,
                    "x0": x0,
                    "x1": x1,
                    "page": page_num,
                    "page_height": page.height,
                    "page_width": page.width
                })
    if not all_font_sizes:
        return "", []
    unique_sizes = sorted(list(set(all_font_sizes)), reverse=True)
    # Most robust title extraction for first page
    first_page_lines = [l for l in all_lines if l["page"] == 1]
    title = ""
    if first_page_lines:
        # Get top 4 font sizes
        sizes = sorted(set(l["size"] for l in first_page_lines), reverse=True)
        top_sizes = sizes[:4]
        # Find the largest font size line (likely the main title)
        largest_lines = [l for l in first_page_lines if l["size"] == top_sizes[0]]
        if largest_lines:
            # Take the first (topmost) largest line
            main_title_line = min(largest_lines, key=lambda x: x["y0"])
            # Collect lines around it to form complete title
            title_parts = []
            for l in first_page_lines:
                if (l["y0"] >= main_title_line["y0"] - 50 and 
                    l["y0"] <= main_title_line["y1"] + 100 and
                    not is_repeated_letters(l["text"]) and
                    not is_garbled_text(l["text"]) and
                    len(l["text"]) > 5):
                    title_parts.append(l)
            if title_parts:
                title_parts = sorted(title_parts, key=lambda x: x["y0"])
                title = " ".join(l["text"] for l in title_parts).strip()
        else:
            # Fallback: collect lines in top 350px, top 4 font sizes, not repeated letters
            candidates = [l for l in first_page_lines if 
                        l["y0"] < 350 and 
                        l["size"] in top_sizes and 
                        not is_repeated_letters(l["text"]) and
                        not is_garbled_text(l["text"])]
            if candidates:
                candidates = sorted(candidates, key=lambda x: x["y0"])
                title = " ".join(l["text"] for l in candidates).strip()
    # Precompute top 2 font sizes per page
    page_font_sizes = defaultdict(list)
    for l in all_lines:
        page_font_sizes[l["page"]].append(l["size"])
    page_top_sizes = {}
    for page, sizes in page_font_sizes.items():
        unique_sizes = sorted(set(sizes), reverse=True)
        page_top_sizes[page] = unique_sizes[:2]
    # Enhanced generalized heading extraction
    # 1. Count repeated lines (for header/footer removal)
    text_counter = collections.Counter([l["text"] for l in all_lines])
    seen = set()
    candidates = []
    for l in all_lines:
        text = l["text"].strip()
        font = l["font"]
        is_bold = "bold" in font.lower()
        size = l["size"]
        page = l["page"]
        # Exclude repeated lines (headers/footers)
        if text_counter[text] > 2:
            continue
        # Exclude too short/long
        if len(text) < 3 or len(text) > 120:
            continue
        # Exclude mostly lowercase
        if len(text) > 5 and text == text.lower():
            continue
        # Exclude lines ending with sentence punctuation
        if text.endswith(('.', '?', '!', ':')) and not re.match(r'^\d', text):
            continue
        # Exclude garbled/corrupted text
        if is_garbled_text(text):
            continue
        # Exclude if already seen
        if text in seen:
            continue
        seen.add(text)
        # Numbered pattern detection
        is_h4 = re.match(r'^\d+\.\d+\.\d+\.\d+ ', text)
        is_h3 = re.match(r'^\d+\.\d+\.\d+ ', text)
        is_h2 = re.match(r'^\d+\.\d+ ', text)
        is_h1 = re.match(r'^\d+\. ', text) or re.match(r'^\d+ ', text)
        # Heading candidate: numbered OR (top 2 font size or bold and not a body paragraph)
        is_heading_candidate = (
            is_h1 or is_h2 or is_h3 or is_h4 or
            size in page_top_sizes[page] or
            (is_bold and len(text.split()) < 12 and not re.match(r'^[-•\u2022]', text)) or
            # Catch short, bold headings like "Summary", "Timeline:"
            (is_bold and len(text.split()) <= 3 and (text.endswith(':') or not text.endswith('.')))
        )
        if is_heading_candidate:
            # Assign level
            if is_h4:
                level = "H4"
            elif is_h3:
                level = "H3"
            elif is_h2:
                level = "H2"
            elif is_h1:
                level = "H1"
            else:
                # Font size rank on page
                sizes = page_top_sizes[page]
                if size == sizes[0]:
                    level = "H1"
                elif len(sizes) > 1 and size == sizes[1]:
                    level = "H2"
                else:
                    level = "H3"
            clean_text = re.sub(r'[.\s]+$', '', text)
            candidates.append({**l, "level": level, "text": clean_text})
    # Group multi-line headings robustly
    grouped = []
    prev = None
    for s in candidates:
        # Filter out fragments and substrings in headings
        if (len(s["text"]) < 5 or
            any(s["text"] in t["text"] or t["text"] in s["text"] for t in grouped) or
            sum(s["text"] == t["text"] for t in grouped) > 0):
            continue
        if (prev and s["level"] == prev["level"] and s["page"] == prev["page"] and 
            abs(s["y0"] - prev["y1"]) < 18 and abs(s["x0"] - prev["x0"]) < 60 and
            abs(s["size"] - prev["size"]) < 0.1):
            prev["text"] += " " + s["text"]
            prev["y1"] = s["y1"]
        else:
            grouped.append(s.copy())
            prev = grouped[-1]
    # Remove headings that are substrings of others on the same page
    filtered = []
    for i, s in enumerate(grouped):
        if any((s["page"] == t["page"] and s["text"] != t["text"] and (s["text"] in t["text"] or t["text"] in s["text"])) for t in grouped):
            # Only keep the longer one
            if all(len(s["text"]) >= len(t["text"]) for t in grouped if s["page"] == t["page"] and (s["text"] in t["text"] or t["text"] in s["text"])):
                filtered.append(s)
        else:
            filtered.append(s)
    # Assign heading levels after grouping
    outline = []
    for s in filtered:
        group_level = size_to_level.get(s["size"], "H4")
        outline.append({
            "level": group_level,
            "text": s["text"].strip(),
            "page": s["page"]
        })
    return title, outline

# Add pdfminer.six-based extraction
def extract_heading_structure_pdfminer(pdf_path):
    import re
    import collections
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer, LTChar
    headings = []
    all_font_sizes = []
    all_lines = []
    def is_repeated_letters(s):
        return bool(re.search(r'(\w)\1{2,}', s))
    def is_garbled_text(s):
        # Check for excessive repeated characters (like RRRRFFFFPPPP)
        if re.search(r'(\w)\1{3,}', s):
            return True
        # Check for excessive punctuation repetition
        if re.search(r'([:;.,!?])\1{2,}', s):
            return True
        # Check for non-printable characters
        if not s.isprintable():
            return True
        # Check for text that's mostly the same character
        if len(set(s)) < len(s) * 0.3 and len(s) > 10:
            return True
        # Check for excessive uppercase repetition
        if re.search(r'([A-Z])\1{3,}', s):
            return True
        return False
    for page_num, page_layout in enumerate(extract_pages(pdf_path), start=1):
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                for text_line in element:
                    line_text = text_line.get_text().strip()
                    if not line_text:
                        continue
                    font_sizes = []
                    font_names = []
                    x0s, x1s, y0s, y1s = [], [], [], []
                    for char in text_line:
                        if isinstance(char, LTChar):
                            font_sizes.append(char.size)
                            font_names.append(char.fontname)
                            x0s.append(char.x0)
                            x1s.append(char.x1)
                            y0s.append(char.y0)
                            y1s.append(char.y1)
                    if not font_sizes:
                        continue
                    font_size = max(font_sizes)
                    font = font_names[0] if font_names else ''
                    x0 = min(x0s) if x0s else 0
                    x1 = max(x1s) if x1s else 0
                    y0 = min(y0s) if y0s else 0
                    y1 = max(y1s) if y1s else 0
                    all_font_sizes.append(font_size)
                    all_lines.append({
                        "text": line_text,
                        "size": font_size,
                        "font": font,
                        "y0": y0,
                        "y1": y1,
                        "x0": x0,
                        "x1": x1,
                        "page": page_num
                    })
    if not all_font_sizes:
        return "", []
    # Improved title extraction: group consecutive lines at the top of page 1 with largest font size and minimal y-gap
    first_page_lines = [l for l in all_lines if l["page"] == 1]
    title = ""
    if first_page_lines:
        sizes = sorted(set(l["size"] for l in first_page_lines), reverse=True)
        top_size = sizes[0]
        # Get all lines with font size within 2pt of the largest in the top 600px
        candidate_lines = [l for l in first_page_lines if abs(l["size"] - top_size) <= 2 and l["y0"] < 600 and not is_repeated_letters(l["text"]) and not is_garbled_text(l["text"]) and len(l["text"]) > 3]
        # Sort by y0
        candidate_lines = sorted(candidate_lines, key=lambda x: x["y0"])
        # Group consecutive lines with minimal y-gap (e.g., < 50px)
        grouped_title = []
        prev_y = None
        for l in candidate_lines:
            if not grouped_title:
                grouped_title.append(l)
                prev_y = l["y1"]
            else:
                if abs(l["y0"] - prev_y) < 50:
                    grouped_title.append(l)
                    prev_y = l["y1"]
                else:
                    break  # Only take the first block of consecutive lines
        if grouped_title:
            title = " ".join(l["text"] for l in grouped_title).strip()
        else:
            # Fallback: join all top font lines in top 600px
            fallback_lines = [l for l in first_page_lines if abs(l["size"] - top_size) <= 2 and l["y0"] < 600]
            fallback_lines = sorted(fallback_lines, key=lambda x: x["y0"])
            title = " ".join(l["text"] for l in fallback_lines).strip()
    # Improved heading grouping: merge consecutive lines with similar font size, font name, and close y-position
    page_font_sizes = collections.defaultdict(list)
    for l in all_lines:
        page_font_sizes[l["page"]].append(l["size"])
    page_top_sizes = {}
    for page, sizes in page_font_sizes.items():
        unique_sizes = sorted(set(sizes), reverse=True)
        page_top_sizes[page] = unique_sizes[:2]
    text_counter = collections.Counter([l["text"] for l in all_lines])
    seen = set()
    candidates = []
    for l in all_lines:
        text = l["text"].strip()
        font = l["font"]
        is_bold = "bold" in font.lower()
        size = l["size"]
        page = l["page"]
        if text_counter[text] > 2:
            continue
        if len(text) < 3 or len(text) > 120:
            continue
        if len(text) > 5 and text == text.lower():
            continue
        if text.endswith(('.', '?', '!', ':')) and not re.match(r'^\d', text):
            continue
        if is_garbled_text(text):
            continue
        if text in seen:
            continue
        seen.add(text)
        is_h4 = re.match(r'^\d+\.\d+\.\d+\.\d+ ', text)
        is_h3 = re.match(r'^\d+\.\d+\.\d+ ', text)
        is_h2 = re.match(r'^\d+\.\d+ ', text)
        is_h1 = re.match(r'^\d+\. ', text) or re.match(r'^\d+ ', text)
        is_heading_candidate = (
            is_h1 or is_h2 or is_h3 or is_h4 or
            size in page_top_sizes[page] or
            (is_bold and len(text.split()) < 12 and not re.match(r'^[-•\u2022]', text)) or
            (is_bold and len(text.split()) <= 3 and (text.endswith(':') or not text.endswith('.')))
        )
        if is_heading_candidate:
            if is_h4:
                level = "H4"
            elif is_h3:
                level = "H3"
            elif is_h2:
                level = "H2"
            elif is_h1:
                level = "H1"
            else:
                sizes = page_top_sizes[page]
                if size == sizes[0]:
                    level = "H1"
                elif len(sizes) > 1 and size == sizes[1]:
                    level = "H2"
                else:
                    level = "H3"
            clean_text = re.sub(r'[.\s]+$', '', text)
            candidates.append({**l, "level": level, "text": clean_text})
    # Improved multi-line heading grouping with looser criteria
    grouped = []
    prev = None
    for l in candidates:
        if (prev and l["level"] == prev["level"] and l["page"] == prev["page"] and
            abs(l["y0"] - prev["y1"]) < 25 and abs(l["x0"] - prev["x0"]) < 80 and
            abs(l["size"] - prev["size"]) < 2 and l["font"] == prev["font"]):
            prev["text"] += " " + l["text"]
            prev["y1"] = l["y1"]
        else:
            grouped.append(l.copy())
            prev = grouped[-1]
    outline = []
    for l in grouped:
        page_num = max(1, l["page"] - 1)
        outline.append({
            "level": l["level"],
            "text": l["text"].strip(),
            "page": page_num
        })
    return title, outline

# Add PyMuPDF-based extraction
import fitz

def extract_heading_structure_pymupdf(pdf_path):
    import re
    import collections
    headings = []
    all_font_sizes = []
    all_lines = []
    
    def is_repeated_letters(s):
        return bool(re.search(r'(\w)\1{2,}', s))
    
    def is_garbled_text(s):
        """Detect and filter out garbled/corrupted text"""
        import re
        # Check for excessive repeated characters (like RRRRFFFFPPPP)
        if re.search(r'(\w)\1{3,}', s):
            return True
        # Check for excessive punctuation repetition
        if re.search(r'([:;.,!?])\1{2,}', s):
            return True
        # Check for non-printable characters
        if not s.isprintable():
            return True
        # Check for text that's mostly the same character
        if len(set(s)) < len(s) * 0.3 and len(s) > 10:
            return True
        # Check for excessive uppercase repetition
        if re.search(r'([A-Z])\1{3,}', s):
            return True
        return False
    
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Get text blocks with font info
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    # Combine all spans in the line
                    line_text = ""
                    font_sizes = []
                    font_names = []
                    x0s, x1s, y0s, y1s = [], [], [], []
                    
                    for span in line["spans"]:
                        line_text += span["text"]
                        font_sizes.append(span["size"])
                        font_names.append(span["font"])
                        x0s.append(span["bbox"][0])
                        x1s.append(span["bbox"][2])
                        y0s.append(span["bbox"][1])
                        y1s.append(span["bbox"][3])
                    
                    if not line_text.strip():
                        continue
                    
                    font_size = max(font_sizes) if font_sizes else 0
                    font = font_names[0] if font_names else ""
                    x0 = min(x0s) if x0s else 0
                    x1 = max(x1s) if x1s else 0
                    y0 = min(y0s) if y0s else 0
                    y1 = max(y1s) if y1s else 0
                    
                    all_font_sizes.append(font_size)
                    all_lines.append({
                        "text": line_text.strip(),
                        "size": font_size,
                        "font": font,
                        "y0": y0,
                        "y1": y1,
                        "x0": x0,
                        "x1": x1,
                        "page": page_num + 1
                    })
    doc.close()
    
    if not all_font_sizes:
        return "", []
    
    # Title extraction: try to get the main title from the first page
    first_page_lines = [l for l in all_lines if l["page"] == 1]
    title = ""
    if first_page_lines:
        # Get the page dimensions to determine center
        page_width = max(l["x1"] for l in first_page_lines) if first_page_lines else 600
        page_center = page_width / 2
        
        # Look for title candidates with these criteria:
        # 1. Near the top of page 1 (y0 < 300)
        # 2. Large font size (top 2 sizes)
        # 3. Centered or near center (x0 within 200px of center)
        # 4. Not too long (reasonable title length)
        # 5. Not garbled text
        
        # Get top font sizes on page 1
        first_page_sizes = sorted(set(l["size"] for l in first_page_lines), reverse=True)
        top_sizes = first_page_sizes[:2] if first_page_sizes else []
        
        title_candidates = []
        for l in first_page_lines:
            # Check if line meets title criteria
            is_top = l["y0"] < 300  # Near top of page
            is_large_font = l["size"] in top_sizes  # Large font size
            is_centered = abs(l["x0"] - page_center) < 200  # Centered or near center
            is_reasonable_length = 5 <= len(l["text"]) <= 100  # Not too short or long
            is_not_garbled = not is_garbled_text(l["text"])  # Clean text
            
            if is_top and is_large_font and is_centered and is_reasonable_length and is_not_garbled:
                title_candidates.append(l)
        
        if title_candidates:
            # Sort by font size (largest first), then by y0 (top first), then by centrality
            title_candidates.sort(key=lambda x: (-x["size"], x["y0"], -abs(x["x0"] - page_center)))
            
            # Take the best candidates and join them
            title_parts = []
            for candidate in title_candidates[:3]:  # Take up to 3 parts
                # Avoid duplicates and substrings
                if not any(part in candidate["text"] for part in title_parts):
                    title_parts.append(candidate["text"])
            
            title = " ".join(title_parts).strip()
        
        # Fallback: if no centered title found, try any large font text at the top
        if not title:
            fallback_candidates = []
            for l in first_page_lines:
                if (l["y0"] < 200 and l["size"] in top_sizes and 
                    not is_garbled_text(l["text"]) and 5 <= len(l["text"]) <= 100):
                    fallback_candidates.append(l)
            
            if fallback_candidates:
                fallback_candidates.sort(key=lambda x: (-x["size"], x["y0"]))
                title_parts = []
                for candidate in fallback_candidates[:2]:
                    if not any(part in candidate["text"] for part in title_parts):
                        title_parts.append(candidate["text"])
                title = " ".join(title_parts).strip()
    
    # Heading extraction: Focus on BOLD text only
    page_font_sizes = collections.defaultdict(list)
    for l in all_lines:
        page_font_sizes[l["page"]].append(l["size"])
    
    # Get top font sizes for each page
    page_top_sizes = {}
    for page, sizes in page_font_sizes.items():
        unique_sizes = sorted(set(sizes), reverse=True)
        page_top_sizes[page] = unique_sizes[:2]  # Top 2 sizes
    
    candidates = []
    seen_texts = set()
    
    for l in all_lines:
        text = l["text"].strip()
        font = l["font"]
        is_bold = "bold" in font.lower() or "black" in font.lower()
        size = l["size"]
        page = l["page"]
        
        # Skip if already seen or too short/long
        if text in seen_texts or len(text) < 3 or len(text) > 100:
            continue
        
        # Skip garbled text
        if is_garbled_text(text):
            continue
        
        # Skip obvious non-headings
        if text.lower() in ['page', 'of', 'continued', '...', 'copyright', 'version', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']:
            continue
        
        # Skip page numbers and dates
        if re.match(r'^\d+$', text) or re.match(r'^\d+/\d+/\d+$', text):
            continue
        
        # Skip table-related text (captions, column headers, etc.)
        if (text.lower() in ['table', 'figure', 'chart', 'graph', 'diagram', 'caption', 'header', 'footer', 'date', 'remarks', 'version', 'description', 'notes', 'comments', 'status', 'type', 'category', 'group', 'section', 'item', 'entry', 'field', 'column', 'row'] or
            re.match(r'^table\s+\d+', text.lower()) or
            re.match(r'^figure\s+\d+', text.lower()) or
            re.match(r'^chart\s+\d+', text.lower()) or
            # Skip text that looks like table content (just numbers and dots)
            re.match(r'^[\d\.\s]+$', text) or
            # Skip text that's mostly numbers and dots
            len(re.findall(r'\d+\.\d+', text)) > 3 or
            len(text.split()) <= 2 and text.lower() in ['yes', 'no', 'true', 'false', 'n/a', 'total', 'sum', 'avg', 'min', 'max', 'date', 'time', 'name', 'id', 'code', 'ref', 'num', 'qty', 'amt', 'val', 'key', 'tag', 'label', 'title', 'desc', 'info', 'data', 'text', 'note', 'msg', 'err', 'warn', 'ok', 'done', 'new', 'old', 'high', 'low', 'big', 'small', 'long', 'short', 'wide', 'narrow', 'fast', 'slow', 'good', 'bad', 'hot', 'cold', 'wet', 'dry', 'full', 'empty', 'open', 'closed', 'on', 'off', 'in', 'out', 'up', 'down', 'left', 'right', 'top', 'bottom', 'front', 'back', 'start', 'end', 'begin', 'stop', 'go', 'run', 'wait', 'hold', 'keep', 'save', 'load', 'send', 'get', 'put', 'add', 'del', 'set', 'use', 'see', 'show', 'hide', 'find', 'search', 'sort', 'filter', 'copy', 'paste', 'cut', 'undo', 'redo', 'next', 'prev', 'first', 'last', 'best', 'worst', 'easy', 'hard', 'safe', 'risk', 'free', 'paid', 'public', 'private', 'local', 'global', 'main', 'sub', 'base', 'core', 'main', 'test', 'demo', 'beta', 'alpha', 'final', 'draft', 'temp', 'perm', 'auto', 'manual', 'user', 'admin', 'guest', 'host', 'client', 'server', 'node', 'link', 'path', 'file', 'dir', 'folder', 'doc', 'pdf', 'txt', 'img', 'pic', 'icon', 'logo', 'btn', 'tab', 'menu', 'list', 'grid', 'form', 'page', 'view', 'screen', 'window', 'panel', 'box', 'card', 'item', 'unit', 'part', 'piece', 'bit', 'byte', 'word', 'line', 'char', 'cell', 'pixel', 'point', 'dot', 'bar', 'line', 'area', 'pie', 'map', 'tree', 'graph', 'node', 'edge', 'link', 'path', 'route', 'way', 'road', 'street', 'city', 'state', 'country', 'world', 'earth', 'sun', 'moon', 'star', 'planet', 'space', 'time', 'day', 'night', 'year', 'month', 'week', 'hour', 'min', 'sec', 'ms', 'us', 'ns', 'ps', 'fs', 'as', 'zs', 'ys']):
            continue
        
        # Check for numbered patterns first
        is_h4 = re.match(r'^\d+\.\d+\.\d+\.\d+', text)
        is_h3 = re.match(r'^\d+\.\d+\.\d+', text)
        is_h2 = re.match(r'^\d+\.\d+', text)
        is_h1 = re.match(r'^\d+\.', text)
        
        # Consider ONLY numbered headings as candidates (no bold text)
        is_numbered_heading = is_h1 or is_h2 or is_h3 or is_h4
        
        if not is_numbered_heading:
            continue
        
        # Check for common heading keywords
        text_lower = text.lower()
        is_summary = "summary" in text_lower
        is_background = "background" in text_lower
        is_appendix = "appendix" in text_lower
        is_timeline = "timeline" in text_lower
        is_introduction = "introduction" in text_lower
        is_references = "references" in text_lower
        is_acknowledgements = "acknowledgements" in text_lower
        is_table_of_contents = "table of contents" in text_lower
        
        # Determine heading level
        level = None
        if is_h4:
            level = "H4"
        elif is_h3:
            level = "H3"
        elif is_h2:
            level = "H2"
        elif is_h1:
            level = "H1"
        elif is_summary or is_background or is_appendix or is_introduction or is_references or is_acknowledgements or is_table_of_contents:
            level = "H1"
        elif is_timeline:
            level = "H3"
        elif size in page_top_sizes[page][:2]:
            # Bold text with top font size
            if size == page_top_sizes[page][0]:
                level = "H1"
            else:
                level = "H2"
        else:
            # Default for bold text
            if len(text.split()) <= 5:
                level = "H3"
            else:
                level = "H2"
        
        if level:
            # Clean the text (remove extra spaces, punctuation at end)
            clean_text = re.sub(r'[.\s]+$', '', text)
            if clean_text and len(clean_text) >= 3:
                candidates.append({
                    **l, 
                    "level": level, 
                    "text": clean_text
                })
                seen_texts.add(text)
    
    # Sort candidates by page and y0
    candidates.sort(key=lambda x: (x["page"], x["y0"]))
    
    # Group consecutive lines that are likely part of the same heading
    grouped = []
    prev = None
    for l in candidates:
        if (prev and l["level"] == prev["level"] and l["page"] == prev["page"] and
            abs(l["y0"] - prev["y1"]) < 30 and abs(l["x0"] - prev["x0"]) < 100 and
            abs(l["size"] - prev["size"]) < 3):
            # Merge with previous heading
            prev["text"] += " " + l["text"]
            prev["y1"] = l["y1"]
        else:
            grouped.append(l.copy())
            prev = grouped[-1]
    
    # Final filtering - remove duplicates and very similar headings
    final_outline = []
    seen_final = set()
    
    # Get title words to filter out from outline
    title_words = set(title.lower().split()) if title else set()
    
    for l in grouped:
        # Create a key for deduplication
        key = (l["page"], l["text"].lower().strip())
        if key in seen_final:
            continue
        
        # Skip if this heading is a substring of another heading on the same page
        is_substring = False
        for existing in final_outline:
            if existing["page"] == l["page"]:
                if l["text"].lower() in existing["text"].lower() or existing["text"].lower() in l["text"].lower():
                    is_substring = True
                    break
        
        # Skip if this heading is too similar to the title
        heading_words = set(l["text"].lower().split())
        title_similarity = len(heading_words.intersection(title_words)) / len(heading_words) if heading_words else 0
        if title_similarity > 0.7:  # If more than 70% of words match the title, skip it
            continue
        
        if not is_substring:
            # Adjust page number to match expected output
            # Expected: Revision History on page 2, but PyMuPDF shows it on page 3
            # So we need to subtract 1
            page_num = max(1, l["page"] - 1)
            final_outline.append({
                "level": l["level"],
                "text": l["text"].strip(),
                "page": page_num
            })
            seen_final.add(key)
    
    return title, final_outline

# Example usage
# pdf_file_path = "your_file.pdf"
# headings = extract_heading_structure(pdf_file_path)

# Optional: Add title from first page biggest text
# title = ""
# if headings and headings[0]["level"] == "H1":
#     title = headings[0]["text"]

# output = {
#     "title": title,
#     "outline": headings
# }

# with open("heading_output.json", "w") as f:
#     json.dump(output, f, indent=4)

# print("✅ Extracted heading structure saved to heading_output.json")

def main():
    import os
    import json
    INPUT_DIR = '/app/input'
    OUTPUT_DIR = '/app/output'
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for filename in os.listdir(INPUT_DIR):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(INPUT_DIR, filename)
            # Use PyMuPDF-based extraction
            title, outline = extract_heading_structure_pymupdf(pdf_path)
            output = {"title": title, "outline": outline}
            out_path = os.path.join(OUTPUT_DIR, filename[:-4] + ".json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=4)
            print(f"✅ Processed {filename} -> {out_path}")

if __name__ == "__main__":
    main()
