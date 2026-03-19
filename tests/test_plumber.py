import pdfplumber

with pdfplumber.open("DocCerts - Documentation.pdf") as pdf:
    text = pdf.pages[1].extract_text()  # page 2 (table of contents)
    print(text[:500])