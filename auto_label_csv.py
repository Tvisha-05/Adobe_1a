import csv
import re

def auto_label(row):
    text = row['text'].strip()
    size = float(row['size'])
    bold = int(row['bold'])
    section_number_pattern = int(row['section_number_pattern'])
    keyword = int(row['keyword'])

    # Title: largest font, bold, first rows (adjust as needed)
    if size >= 24 and bold:
        return 1
    # H1: main headings, bold or keyword, or section pattern
    if size >= 15 and (bold or keyword or section_number_pattern):
        return 2
    # H2: subsection, section pattern, not as large
    if size >= 14 and section_number_pattern:
        return 3
    # H3: smaller, section pattern
    if size >= 13 and section_number_pattern:
        return 4
    # Not a heading
    return 0

with open('labeled_spans.csv', newline='') as infile, open('labeled_spans_auto.csv', 'w', newline='') as outfile:
    reader = csv.DictReader(infile)
    fieldnames = reader.fieldnames
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    for row in reader:
        row['label'] = auto_label(row)
        writer.writerow(row)

print("Auto-labeled CSV saved as labeled_spans_auto.csv")