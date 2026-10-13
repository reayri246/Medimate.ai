import io
import logging
import os
import shutil
import warnings
from pathlib import Path

from PIL import Image, ImageOps
import pymupdf
import pytesseract
from pytesseract import Output
from pytesseract.pytesseract import TesseractError, TesseractNotFoundError
from pypdf import PdfReader
from pypdf.errors import PdfReadError


logger = logging.getLogger(__name__)
MAX_PDF_OCR_PAGES = 20
PDF_RENDER_DPI = 180
MAX_RENDERED_PAGE_EDGE = 3200
TESSERACT_TIMEOUT_SECONDS = 15
MIN_EMBEDDED_TEXT_LENGTH = 20
OCR_CONFIG = '--oem 3 --psm 6'


def _tesseract_available():
    executable = shutil.which('tesseract')
    if not executable:
        configured_executable = os.getenv('TESSERACT_CMD')
        if configured_executable and Path(configured_executable).is_file():
            executable = configured_executable
    if not executable:
        program_files = os.getenv('ProgramFiles', r'C:\Program Files')
        common_location = Path(program_files) / 'Tesseract-OCR' / 'tesseract.exe'
        if common_location.is_file():
            executable = str(common_location)
    if executable:
        pytesseract.pytesseract.tesseract_cmd = executable
        return True
    return False


def _ocr_language(language):
    if language != 'te':
        return 'eng', ''
    try:
        available_languages = pytesseract.get_languages(config='')
    except (TesseractError, TesseractNotFoundError, OSError):
        logger.warning('Could not read installed Tesseract language packs.')
        available_languages = []
    if 'tel' in available_languages:
        return 'eng+tel', ''
    return 'eng', '[Telugu OCR language data is not installed; text was processed using English OCR only.]\n'


def _normalize_image(image):
    image = ImageOps.exif_transpose(image)
    image.load()
    return ImageOps.autocontrast(image.convert('L'))


def _ocr_image(image, language):
    prepared = _normalize_image(image)
    binary = prepared.point(lambda pixel: 255 if pixel > 170 else 0)
    best_text = ''
    best_score = -1.0

    for candidate in (prepared, binary):
        try:
            result = pytesseract.image_to_data(
                candidate,
                lang=language,
                config=OCR_CONFIG,
                output_type=Output.DICT,
                timeout=TESSERACT_TIMEOUT_SECONDS,
            )
        except (TesseractError, TesseractNotFoundError, RuntimeError, OSError) as exc:
            logger.warning('Tesseract failed to process an image: %s', type(exc).__name__)
            continue

        lines = {}
        scores = []
        for index, (word, confidence) in enumerate(zip(result.get('text', []), result.get('conf', []))):
            word = word.strip()
            try:
                score = float(confidence)
            except (TypeError, ValueError):
                continue
            if word and score >= 0:
                line_key = tuple(
                    result.get(key, [0] * len(result.get('text', [])))[index]
                    for key in ('block_num', 'par_num', 'line_num')
                )
                lines.setdefault(line_key, []).append(word)
                scores.append(score)
        text = '\n'.join(' '.join(words) for words in lines.values())
        average_score = sum(scores) / len(scores) if scores else 0
        if text and average_score > best_score:
            best_text = text
            best_score = average_score

    return best_text


def _image_from_bytes(data):
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        image = Image.open(io.BytesIO(data))
        try:
            image.load()
            return image.copy()
        finally:
            image.close()


def _extract_pdf(uploaded_file, language):
    uploaded_file.seek(0)
    data = uploaded_file.read()
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        pdf = pymupdf.open(stream=data, filetype='pdf')
    except (OSError, ValueError, RuntimeError, PdfReadError, pymupdf.FileDataError) as exc:
        logger.warning('Could not open uploaded PDF: %s', type(exc).__name__)
        return 'The PDF could not be opened. Check the original file and try another copy.'

    total_pages = len(reader.pages)
    if total_pages == 0:
        pdf.close()
        return 'The PDF does not contain any readable pages.'

    has_tesseract = _tesseract_available()
    ocr_language, language_notice = _ocr_language(language) if has_tesseract else ('eng', '')
    output = []
    pages_to_process = min(total_pages, MAX_PDF_OCR_PAGES)
    for page_index in range(pages_to_process):
        try:
            page_text = (reader.pages[page_index].extract_text() or '').strip()
        except (OSError, ValueError, KeyError, PdfReadError) as exc:
            logger.warning('Could not extract embedded text from PDF page %s: %s', page_index + 1, type(exc).__name__)
            page_text = ''

        if len(''.join(page_text.split())) >= MIN_EMBEDDED_TEXT_LENGTH:
            output.append(f'[PDF page {page_index + 1} - embedded text]\n{page_text}')
            continue
        if not has_tesseract:
            if page_text:
                output.append(f'[PDF page {page_index + 1} - partial embedded text]\n{page_text}')
            else:
                output.append(f'[PDF page {page_index + 1} - no readable text; OCR is unavailable]')
            continue

        try:
            page = pdf.load_page(page_index)
            scale = min(
                PDF_RENDER_DPI / 72,
                MAX_RENDERED_PAGE_EDGE / max(page.rect.width, page.rect.height),
            )
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            image = _image_from_bytes(pixmap.tobytes('png'))
            recognized = _ocr_image(image, ocr_language).strip()
        except (RuntimeError, ValueError, OSError, Image.DecompressionBombError) as exc:
            logger.warning('Could not render PDF page %s for OCR: %s', page_index + 1, type(exc).__name__)
            recognized = ''
        if recognized:
            if page_text:
                output.append(f'[PDF page {page_index + 1} - partial embedded text]\n{page_text}')
            output.append(f'[PDF page {page_index + 1} - OCR; verify against original]\n{recognized}')
        elif page_text:
            output.append(f'[PDF page {page_index + 1} - partial embedded text]\n{page_text}')
        else:
            output.append(f'[PDF page {page_index + 1} - no text detected; verify page manually]')

    pdf.close()
    if total_pages > pages_to_process:
        output.append(
            f'[OCR page limit reached: {total_pages - pages_to_process} additional PDF page(s) were not processed.]'
        )
    if language_notice:
        output.insert(0, language_notice.strip())
    return '\n\n'.join(output)


def extract_text_from_uploaded_file(uploaded_file, language='en'):
    """Extract text from local files; OCR output is always provisional."""
    name = (uploaded_file.name or '').lower()

    if name.endswith('.txt'):
        try:
            uploaded_file.seek(0)
            data = uploaded_file.read()
        except OSError as exc:
            logger.warning('Could not read uploaded text document: %s', type(exc).__name__)
            return 'The uploaded text file could not be read.'
        return data.decode('utf-8', errors='replace').strip() or 'No readable text was found in the uploaded text file.'

    if name.endswith('.pdf'):
        return _extract_pdf(uploaded_file, language)

    if name.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        if not _tesseract_available():
            return 'OCR is unavailable on this server because Tesseract is not installed.'
        try:
            uploaded_file.seek(0)
            image = _image_from_bytes(uploaded_file.read())
            ocr_language, language_notice = _ocr_language(language)
            text = _ocr_image(image, ocr_language).strip()
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            logger.warning('Uploaded image could not be prepared for OCR: %s', type(exc).__name__)
            return 'The uploaded image could not be prepared for OCR. Try a clear, upright image.'

        if not text:
            return language_notice + 'No text was detected. The image may be unclear, handwritten, or unsupported.'
        return language_notice + '[OCR text; verify against the original]\n' + text

    return 'The file type is not supported for automatic OCR extraction.'
