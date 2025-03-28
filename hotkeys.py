import keyboard
import eel
from config import r_config, HOTKEYS_CONFIG

def refresh_ocr_hotkey():
    try:
        # Sử dụng JavaScript Promise để đợi kết quả
        eel.refreshOCR()(lambda x: None)
    except Exception as e:
        print(f"Failed to trigger OCR refresh: {e}")

def register_global_hotkeys():
    try:
        # Lấy phím tắt từ config và format lại
        refresh_ocr_key = r_config(HOTKEYS_CONFIG, "refresh_ocr")
        refresh_ocr_key = refresh_ocr_key.replace('<', '').replace('>', '')
        
        # Đăng ký global hotkey
        keyboard.add_hotkey(refresh_ocr_key.lower(), refresh_ocr_hotkey, suppress=True)
        print(f"Registered global hotkey: {refresh_ocr_key}")
    except Exception as e:
        print(f"Failed to register hotkey: {e}")

def setup_hotkeys():
    register_global_hotkeys()

# Xuất hotkey map cho việc reference
hotkey_map = {
    r_config(HOTKEYS_CONFIG, "refresh_ocr"): refresh_ocr_hotkey
}