# PDF Outline Extractor (Adobe India Hackathon 2025 - Challenge 1a)

## Overview
This solution extracts a structured outline (Title, H1, H2, H3 headings) from PDF documents and outputs them as JSON files, conforming to the required schema. It is containerized for CPU-only, offline execution and meets all challenge constraints.

## Approach
- Uses [PyMuPDF](https://github.com/pymupdf/PyMuPDF) for fast, robust PDF parsing.
- Extracts text spans with font size, style, and position.
- Clusters font sizes to determine heading levels (Title, H1, H2, H3).
- Outputs a JSON file per PDF, matching the provided schema.

## Usage
### Build Docker Image
```
docker build --platform linux/amd64 -t pdf-processor .
```

### Run Container
```
docker run --rm -v $(pwd)/sample_dataset/pdfs:/app/input:ro -v $(pwd)/sample_dataset/outputs:/app/output --network none pdf-processor
```

- Place input PDFs in `sample_dataset/pdfs/`.
- Output JSONs will appear in `sample_dataset/outputs/`.

## Output Format
Each output JSON matches the schema in `sample_dataset/schema/output_schema.json`:
```
{
  "title": "Document Title",
  "outline": [
    { "level": "H1", "text": "Section Heading", "page": 1 },
    { "level": "H2", "text": "Subsection", "page": 2 },
    ...
  ]
}
```

## Libraries Used
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF)
- Python 3.10

## Notes
- No internet access required at runtime.
- Model-free, fully open source.
- Efficient for large PDFs (≤50 pages in ≤10 seconds).

## Contact
For questions, contact the author. 