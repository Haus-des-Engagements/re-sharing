import base64
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from reportlab.pdfgen import canvas


def png_bytes(size=(40, 20)) -> bytes:
    output = BytesIO()
    Image.new("RGBA", size, (0, 0, 0, 255)).save(output, format="PNG")
    return output.getvalue()


def data_url(content: bytes, mime="image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def signature_data(name="Ada Example") -> dict:
    """Form data of a typed name and a drawn signature."""
    return {"signature_name": name, "signature_image": data_url(png_bytes())}


def pdf_bytes(pages=1) -> bytes:
    """A PDF that can be read, with ``Source page <n>`` on each page."""
    output = BytesIO()
    pdf = canvas.Canvas(output)
    for number in range(pages):
        pdf.drawString(72, 720, f"Source page {number + 1}")
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def readable_pdf_file(name="signed.pdf", pages=1):
    return SimpleUploadedFile(name, pdf_bytes(pages), content_type="application/pdf")
