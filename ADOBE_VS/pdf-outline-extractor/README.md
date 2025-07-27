# PDF Outline Extractor

## Overview
The PDF Outline Extractor is a Python-based application designed to extract structured outlines from PDF documents. It identifies the title and headings (H1, H2, H3) within the PDF and outputs this information in a clean, hierarchical JSON format. This tool is particularly useful for enabling smarter document experiences, such as semantic search and insight generation.

## Approach
The application processes PDF files by reading their content and identifying the structure based on heading levels. It utilizes various utility functions to handle PDF reading, formatting the output, and managing errors. The main extraction logic is encapsulated in the `extract_outline` function, which returns the extracted data in the specified JSON format.

## Libraries Used
- **PyPDF2**: For reading and extracting text from PDF files.
- **json**: For formatting the output as JSON.
- **typing**: For type safety and clarity in data structures.

## Directory Structure
- `src/main.py`: Entry point for the application, handling input/output directories and processing PDF files.
- `src/extractor.py`: Contains the logic for extracting the title and headings from the PDF.
- `src/utils.py`: Utility functions for reading PDFs, formatting output, and error handling.
- `src/types/outline.py`: Defines data structures for the outline extraction.
- `Dockerfile`: Instructions for building the Docker image.
- `requirements.txt`: Lists the necessary Python dependencies.
- `sample/sample.pdf`: Sample input PDF for testing.
- `sample/sample.json`: Sample output JSON demonstrating the expected format.

## Building the Docker Image
To build the Docker image, run the following command in the root directory of the project:

```
docker build --platform linux/amd64 -t mysolutionname:somerandomidentifier .
```

## Running the Solution
After building the image, you can run the solution using the following command:

```
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none mysolutionname:somerandomidentifier
```

This command will process all PDF files in the `/app/input` directory and generate corresponding JSON files in the `/app/output` directory.

## Testing
Ensure to test the application with both simple and complex PDF documents to validate the accuracy of heading detection and overall performance.

## Notes
- The application is designed to work offline and does not require internet access.
- It adheres to the constraints of execution time and model size, ensuring efficient processing of PDF files.