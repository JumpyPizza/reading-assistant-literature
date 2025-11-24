import fitz  # PyMuPDF is imported as 'fitz'

def extract_first_n_pages(input_pdf_path, output_pdf_path, num_pages=10):
    """
    Extracts the first 'num_pages' from an input PDF and saves them 
    to a new output PDF.
    """
    try:
        # 1. Open the source PDF document
        source_doc = fitz.open(input_pdf_path)
        
        # Determine the actual number of pages to extract. 
        # It should be the minimum of 'num_pages' and the total number of pages in the document.
        pages_to_extract = min(num_pages, len(source_doc))
        
        # 2. Create a new blank PDF document
        output_doc = fitz.open()
        
        # 3. Copy the pages from the source to the new document
        # We use a page range from 0 (first page) up to, but not including, pages_to_extract.
        output_doc.insert_pdf(
            source_doc, 
            from_page=0, 
            to_page=pages_to_extract - 1
        )
        
        # 4. Save the new document
        output_doc.save(output_pdf_path)
        
        # 5. Close the documents
        source_doc.close()
        output_doc.close()
        
        print(f"✅ Successfully extracted the first {pages_to_extract} pages.")
        print(f"   Saved to: {output_pdf_path}")
        
    except FileNotFoundError:
        print(f"❌ Error: Input file not found at '{input_pdf_path}'")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

# --- Example Usage ---
# IMPORTANT: Replace 'input.pdf' with the actual name of your PDF file
INPUT_FILE = "input.pdf"
OUTPUT_FILE = "test1.pdf"
PAGES_TO_EXTRACT = 10

extract_first_n_pages(INPUT_FILE, OUTPUT_FILE, PAGES_TO_EXTRACT)