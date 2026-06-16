#!/usr/bin/env python3

import argparse, os 
from pypdf import PdfReader, PdfWriter

def extract_chapter(input_pdf, output_pdf, start_page, end_page):
  try:
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    total_pages = len(reader.pages)
    
    # Validations
    if start_page < 1 or end_page > total_pages:
      print(f"Error: Page range must be between 1 and {total_pages}.")
      return
    if start_page > end_page:
      print("Error: Start page cannot be greater than end page.")
      return

    # Extract pages (converting 1-indexed to 0-indexed)
    for page_num in range(start_page - 1, end_page):
      writer.add_page(reader.pages[page_num])

    output_dir = os.path.dirname(output_pdf)
    if output_dir:
      os.makedirs(output_dir, exist_ok=True)

    with open(output_pdf, "wb") as output_file:
      writer.write(output_file)
        
    print(f"🎉 Success! Pages {start_page}-{end_page} saved to '{output_pdf}'")
      
  except FileNotFoundError:
    print(f"Error: The file '{input_pdf}' could not be found. Check the path.")
  except Exception as e:
    print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
  # Setting up command line arguments
  parser = argparse.ArgumentParser(description="Extract a chapter from a scanned PDF book.")

  parser.add_argument("input", help="Path to the original huge PDF file")
  parser.add_argument("output", help="Name/Path for the extracted chapter PDF")
  parser.add_argument("start", type=int, help="Starting page number (inclusive)")
  parser.add_argument("end", type=int, help="Ending page number (inclusive)")

  args = parser.parse_args()
    
  # Run the extraction
  extract_chapter(args.input, args.output, args.start, args.end)
