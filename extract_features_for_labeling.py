import fitz
import csv
import re

def extract_features(span, font_stats):
    text = span["text"]
    font_size = span["size"]
    rel_size = font_size / font_stats["mean"] if font_stats["mean"] else font_size
    is_title_case = int(text.istitle())
    is_all_caps = int(text.isupper())
    is_bold = int(span["bold"])
    is_italic = int("italic" in span["font"].lower())
    is_centered = int(abs((span["x0"] + span["x1"]) / 2 - span["page_width"] / 2) < 50)
    return [
        text,
        font_size,
        rel_size,
        is_bold,
        is_italic,
        is_all_caps,
        is_title_case,
        is_centered,
        len(text),
        int(bool(re.match(r'^\d+(\.\d+)* ', text))),
        span["y0"],
        span["x0"],
        int(text.lower() in {"table of contents", "acknowledgements", "introduction", "references"}),
        hash(span["font"]) % 10000,
        ""  # label to be filled manually
    ]

def extract_spans(pdf_path):
    doc = fitz.open(pdf_path)
    spans = []
    font_sizes = []
    for page_num, page in enumerate(doc, 1):
        page_height = page.rect.height
        page_width = page.rect.width
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text:
                            continue
                        is_bold = "bold" in span["font"].lower() or (span["flags"] & 2)
                        font_sizes.append(span["size"])
                        spans.append({
                            "text": text,
                            "size": span["size"],
                            "bold": is_bold,
                            "font": span["font"],
                            "y0": span["bbox"][1],
                            "y1": span["bbox"][3],
                            "x0": span["bbox"][0],
                            "x1": span["bbox"][2],
                            "page": page_num,
                            "page_height": page_height,
                            "page_width": page_width
                        })
    font_stats = {"mean": sum(font_sizes)/len(font_sizes) if font_sizes else 0}
    return spans, font_stats

def main():
    pdf_path = "sample_dataset/pdfs/file03.pdf"  # Change to your PDF path
    spans, font_stats = extract_spans(pdf_path)
    with open("labeled_spans.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "text","size","rel_size","bold","italic","is_caps","is_title_case","is_centered","length","section_number_pattern","y0","x0","keyword","font_hash","label"
        ])
        for span in spans:
            writer.writerow(extract_features(span, font_stats))

if __name__ == "__main__":
    main() 