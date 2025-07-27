import os
import json
from extractor import extract_outline

def main():
    input_dir = '/app/input'
    output_dir = '/app/output'

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Process each PDF file in the input directory
    for filename in os.listdir(input_dir):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(input_dir, filename)
            outline = extract_outline(pdf_path)

            # Prepare output JSON file path
            json_filename = f"{os.path.splitext(filename)[0]}.json"
            json_path = os.path.join(output_dir, json_filename)

            # Write the outline to a JSON file
            with open(json_path, 'w') as json_file:
                json.dump(outline, json_file)

if __name__ == "__main__":
    main()