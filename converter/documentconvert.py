# converter/documentconvert.py
import io
from PyPDF2 import PdfReader, PdfWriter
import docx
from docx.shared import Inches

def convert_document(contents, from_format, to_format, remove_metadata=False):
    """
    Convert document from one format to another.
    Currently supports limited conversions between PDF, DOCX, and TXT.
    """
    input_stream = io.BytesIO(contents)
    output_stream = io.BytesIO()
    
    print(f"Converting from {from_format} to {to_format}")
    
    # PDF to TXT
    if from_format == 'pdf' and to_format == 'txt':
        pdf = PdfReader(input_stream)
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
        output_stream.write(text.encode('utf-8'))
    
    # TXT to PDF
    elif from_format == 'txt' and to_format == 'pdf':
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        text = input_stream.read().decode('utf-8')
        c = canvas.Canvas(output_stream, pagesize=letter)
        
        # Simple handling of multiline text
        y = 750  # starting y position
        for line in text.split('\n'):
            c.drawString(72, y, line)
            y -= 15
            if y < 50:  # new page if we run out of space
                c.showPage()
                y = 750
        
        c.save()
    
    # DOCX to TXT
    elif from_format == 'docx' and to_format == 'txt':
        doc = docx.Document(input_stream)
        text = ""
        for para in doc.paragraphs:
            text += para.text + '\n'
        output_stream.write(text.encode('utf-8'))
    
    # TXT to DOCX
    elif from_format == 'txt' and to_format == 'docx':
        doc = docx.Document()
        text = input_stream.read().decode('utf-8')
        for line in text.split('\n'):
            doc.add_paragraph(line)
        doc.save(output_stream)
    
    # PDF to DOCX (simple approach - text extraction)
    elif from_format == 'pdf' and to_format == 'docx':
        pdf = PdfReader(input_stream)
        doc = docx.Document()
        
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                doc.add_paragraph(text)
            doc.add_page_break()
        
        doc.save(output_stream)
    
    # DOCX to PDF (simple approach)
    elif from_format == 'docx' and to_format == 'pdf':
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        doc = docx.Document(input_stream)
        c = canvas.Canvas(output_stream, pagesize=letter)
        
        y = 750  # starting y position
        for para in doc.paragraphs:
            if para.text:
                c.drawString(72, y, para.text)
                y -= 15
                if y < 50:
                    c.showPage()
                    y = 750
        
        c.save()
    
    else:
        raise ValueError(f"Conversion from {from_format} to {to_format} not supported yet.")
    
    return output_stream.getvalue()