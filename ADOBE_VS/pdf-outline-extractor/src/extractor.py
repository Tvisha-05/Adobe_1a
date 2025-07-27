def extract_outline(pdf_path):
    import PyPDF2
    import json
    from collections import defaultdict

    outline = {
        "title": "",
        "outline": []
    }

    # Open the PDF file
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        num_pages = len(reader.pages)

        # Extract title and headings
        for page_number in range(num_pages):
            page = reader.pages[page_number]
            text = page.extract_text()

            if page_number == 0:
                # Assume the title is the first line of the first page
                outline["title"] = text.splitlines()[0] if text else "Untitled"

            # Process each line to find headings
            for line in text.splitlines():
                if line.startswith("# "):  # H1
                    outline["outline"].append({"level": "H1", "text": line[2:], "page": page_number + 1})
                elif line.startswith("## "):  # H2
                    outline["outline"].append({"level": "H2", "text": line[3:], "page": page_number + 1})
                elif line.startswith("### "):  # H3
                    outline["outline"].append({"level": "H3", "text": line[4:], "page": page_number + 1})

    return outline

def save_outline_to_json(outline, output_path):
    with open(output_path, "w") as json_file:
        json.dump(outline, json_file, indent=4)