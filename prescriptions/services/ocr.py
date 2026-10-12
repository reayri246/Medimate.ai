import io
import shutil
import warnings

from PIL import Image, ImageOps
import pytesseract
from pypdf import PdfReader


def extract_text_from_uploaded_file(uploaded_file, language='en'):
    name = (uploaded_file.name or '').lower()

    if name.endswith('.txt'):
        data = uploaded_file.read()
        return data.decode('utf-8', errors='ignore').strip()

    if name.endswith('.pdf'):
        try:
            uploaded_file.seek(0)
            reader = PdfReader(io.BytesIO(uploaded_file.read()))
            pages = [page.extract_text() or '' for page in reader.pages]
            text = '\n\n'.join(pages).strip()
            return text if text else 'No readable text was found in the PDF file.'
        except Exception:
            return 'The PDF could not be parsed automatically. Please review it manually.'

    if name.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        if shutil.which('tesseract') is None:
            return 'OCR is not available on this system because Tesseract is not installed.'
        try:
            uploaded_file.seek(0)
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(uploaded_file) as source_image:
                    image = ImageOps.exif_transpose(source_image)
                    image.load()
            image = ImageOps.autocontrast(image.convert('L'))
            ocr_language = 'eng'
            language_notice = ''
            if language == 'te':
                available_languages = pytesseract.get_languages(config='')
                if 'tel' in available_languages:
                    ocr_language = 'eng+tel'
                else:
                    language_notice = (
                        '[Telugu OCR language data is not installed; text was processed using English OCR only.]\n'
                    )
            text = pytesseract.image_to_string(image, lang=ocr_language).strip()
            text = language_notice + text
            return text if text else 'No text was detected in the uploaded image.'
        except Exception:
            return 'The uploaded image could not be OCR-processed automatically.'

    return 'The file type is not supported for automatic OCR extraction.'
