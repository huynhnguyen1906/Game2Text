import pytesseract
import re
from pathlib import Path
from logger import log_text, log_media
from config import r_config, OCR_CONFIG
from util import base64_to_image, base64_to_image_path
from tools import path_to_tesseract, get_tessdata_dir, bundle_dir
from ocr_space import ocr_space_file, OCRSPACE_API_URL_USA, OCRSPACE_API_URL_EU

HORIZONTAL_TEXT_DETECTION = 6
VERTICAL_TEXT_DETECTON = 5
MIN_ENGLISH_WORD_CONFIDENCE = 35
CJK_REGEX = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]+')
CONTROL_REGEX = re.compile(r'[\x00-\x1f\x7f-\x9f]+')
SPACE_REGEX = re.compile(r'\s+')
ASCII_LETTER_REGEX = re.compile(r'[A-Za-z]')

def get_temp_image_path():
    return str(Path(bundle_dir,"logs", "images", "temp.png"))

def detect_and_log(engine, cropped_image,  text_orientation, session_start_time, request_time):
    result = image_to_text(engine, cropped_image, text_orientation)
    if result is not None:
        # Auto-translate the OCR result
        translated_text = None
        try:
            # Only translate if the result is not empty
            if result and len(result.strip()) > 0:
                from translate import multi_translate
                translated_text = multi_translate(result)
        except Exception as e:
            print(f"Translation error in OCR: {str(e)}")
            
        # Log both the original text and the translation
        log_text(session_start_time, request_time, result, translated_text)
        log_media(session_start_time, request_time)
        return {'id': request_time, 'result': result }
    else:
        return {'error': 'OCR Failed'}

def image_to_text(engine, base64img, text_orientation):
    if engine == "OCR Space USA" or engine == "OCR Space EU":
        api_url = OCRSPACE_API_URL_USA if engine == "OCR Space USA" else OCRSPACE_API_URL_EU
        image_path = base64_to_image_path(base64img, get_temp_image_path())
        language = r_config(OCR_CONFIG, "ocr_space_language")
        return clean_ocr_text(ocr_space_file(filename=image_path, language=language, url=api_url), language)
    else: 
        # default to tesseract
        image = base64_to_image(base64img, get_temp_image_path())
        return tesseract_ocr(image, text_orientation)

def is_english_language(language):
    return language.lower().split('+')[0] == 'eng'

def clean_ocr_text(text, language):
    if not text:
        return text
    text = text.replace('\f', ' ')
    text = text.replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")
    text = text.replace('…', '...')

    if is_english_language(language):
        text = CJK_REGEX.sub(' ', text)
        text = ''.join(char if 32 <= ord(char) <= 126 else ' ' for char in text)
    else:
        text = CONTROL_REGEX.sub(' ', text)

    text = SPACE_REGEX.sub(' ', text).strip()
    return text.strip(' |\\/`~_-')

def should_keep_low_confidence_english_token(text):
    letters = ASCII_LETTER_REGEX.findall(text)
    if len(letters) < 4:
        return False
    return len(letters) / max(len(text), 1) >= 0.6

def tesseract_data_to_text(image, language, custom_config):
    data = pytesseract.image_to_data(
        image,
        config=custom_config,
        lang=language,
        output_type=pytesseract.Output.DICT
    )
    lines = []
    current_line = []
    current_line_id = None

    for i, raw_text in enumerate(data.get('text', [])):
        text = clean_ocr_text(raw_text, language)
        if not text:
            continue

        try:
            confidence = float(data['conf'][i])
        except (ValueError, TypeError):
            confidence = -1

        if confidence < MIN_ENGLISH_WORD_CONFIDENCE and not should_keep_low_confidence_english_token(text):
            continue

        line_id = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        if current_line_id is not None and line_id != current_line_id and current_line:
            lines.append(' '.join(current_line))
            current_line = []

        current_line_id = line_id
        current_line.append(text)

    if current_line:
        lines.append(' '.join(current_line))

    return ' '.join(lines)

def tesseract_ocr(image, text_orientation):
    language = r_config(OCR_CONFIG, "tesseract_language")
    psm = HORIZONTAL_TEXT_DETECTION
    # Add English Tessdata for legacy Tesseract (English is included in v4 Japanese trained data)
    is_legacy_tesseract = r_config(OCR_CONFIG, "oem") == '0'
    if is_legacy_tesseract:
        language += '+eng'
    # Manual Vertical Text Orientation
    if (text_orientation == 'vertical'):
        psm = VERTICAL_TEXT_DETECTON
        language += "_vert"
    custom_config = r'{} --oem {} --psm {} -c preserve_interword_spaces=1 {}'.format(get_tessdata_dir(), r_config(OCR_CONFIG, "oem"), psm, r_config(OCR_CONFIG, "extra_options").strip('"'))
    if is_english_language(language):
        result = tesseract_data_to_text(image, language, custom_config)
        if result:
            return result
    result = pytesseract.image_to_string(image, config=custom_config, lang=language)
    return clean_ocr_text(result, language)

tesseract_cmd = path_to_tesseract()
if tesseract_cmd is not None:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
