import os
import mimetypes
import io
from pathlib import Path
from django.conf import settings
from celery import shared_task
from PIL import Image
import fitz  # PyMuPDF
import numpy as np
from openai import OpenAI


@shared_task
def postprocess_file(file_id):
    """
    Process uploaded file:
    - Generate thumbnail for PDFs
    - Extract text from PDFs/text files
    - Generate OpenAI embedding for the text
    """
    from .models import File, Embedding

    try:
        file_obj = File.objects.get(id=file_id)

        # Get the file path and mime type
        file_path = file_obj.file.path
        mime_type = mimetypes.guess_type(file_path)[0]
        file_obj.mime_type = mime_type

        # Variable to store extracted text
        extracted_text = ""

        # Handle PDF files (thumbnail + text extraction)
        if mime_type == "application/pdf":
            try:
                # Open PDF with PyMuPDF
                pdf_document = fitz.open(file_path)

                if pdf_document.page_count > 0:
                    # Get first page
                    first_page = pdf_document[0]

                    # Extract text (up to 8000 chars)
                    extracted_text = ""
                    for page in pdf_document:
                        extracted_text += page.get_text()
                        if len(extracted_text) >= 8000:
                            break
                    extracted_text = extracted_text[:8000]

                    # Create thumbnail (render to PNG)
                    pix = first_page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_data = pix.tobytes("png")

                    # Resize image to 360px width
                    img = Image.open(io.BytesIO(img_data))
                    width, height = img.size
                    new_width = 360
                    new_height = int(height * (new_width / width))
                    img = img.resize((new_width, new_height), Image.LANCZOS)

                    # Save thumbnail
                    thumb_name = f"{Path(file_obj.name).stem}_thumb.png"
                    thumb_path = os.path.join("thumbs", thumb_name)
                    thumb_io = io.BytesIO()
                    img.save(thumb_io, format="PNG")

                    from django.core.files.base import ContentFile

                    file_obj.thumb.save(
                        thumb_path, ContentFile(thumb_io.getvalue()), save=False
                    )

                pdf_document.close()
            except Exception as e:
                print(f"Error processing PDF: {e}")

        # Handle text files
        elif mime_type and (
            mime_type.startswith("text/") or mime_type == "application/json"
        ):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    extracted_text = f.read(8000)
            except Exception as e:
                print(f"Error extracting text: {e}")

        # Generate embedding if we have text
        if extracted_text:
            try:
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                response = client.embeddings.create(
                    input=extracted_text, model=settings.EMBED_MODEL
                )
                vector = response.data[0].embedding

                # Save embedding
                Embedding.objects.create(
                    file=file_obj, vector=vector, extracted_text=extracted_text
                )
            except Exception as e:
                print(f"Error generating embedding: {e}")

        # Mark as processed
        file_obj.processed = True
        file_obj.save()

        return {"status": "success", "file_id": file_id}

    except Exception as e:
        print(f"Error in postprocess_file task: {e}")
        return {"status": "error", "message": str(e)}
