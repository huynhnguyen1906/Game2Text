import sys
import io

# Redirect stdout/stderr ngay từ đầu
if not sys.stdout:
    sys.stdout = io.StringIO()
if not sys.stderr:
    sys.stderr = io.StringIO()

# Rồi mới import eel (và các thứ liên quan)
import eel
import threading, os, platform, time, concurrent.futures
...

thread_pool_ref = concurrent.futures.ThreadPoolExecutor # Necessary for distribution to import ThreadPoolExecutor before app code
from pathlib import Path
from ocr import detect_and_log
from translate import multi_translate
from hotkeys import hotkey_map
from util import RepeatedTimer, create_directory_if_not_exists, get_default_browser_name, get_PID_list, format_output
from textractor import Textractor
from tools import path_to_textractor, open_folder_textractor_path
from pynput import keyboard
from clipboard import clipboard_to_output, text_to_clipboard
from logger import get_time_string, log_text, log_media, update_log_text, repair_log_files
from ankiconnect import invoke, get_anki_models, update_anki_models, create_anki_note, fetch_anki_fields
from imageprofile import export_image_profile, load_image_profiles, open_image_profile
from gamescript import load_game_scripts, open_game_script
from dictionary import load_all_dictionaries, look_up, get_local_dictionaries, load_dictionary, get_jpod_audio_url
from config import r_config, r_config_all, r_config_section, w_config, APP_CONFIG, LOG_CONFIG, TEXTHOOKER_CONFIG

session_start_time = get_time_string()
textractor = None
TRANSLATION_QUEUE_LIMIT = 5
translation_executor = concurrent.futures.ThreadPoolExecutor(max_workers=TRANSLATION_QUEUE_LIMIT)
translation_queue_slots = threading.BoundedSemaphore(TRANSLATION_QUEUE_LIMIT)

# run_eel()

# Set web files folder and optionally specify which file types to check for eel.expose()
#   *Default allowed_extensions are: ['.js', '.html', '.txt', '.htm', '.xhtml']

def close(page, sockets):
    if not sockets:
      os._exit(0)

@eel.expose     
def recognize_image(engine, image, orientation):
    response = detect_and_log(engine, image, orientation, session_start_time, get_time_string())
    if response and response.get('result'):
        queue_log_translation(response['id'], response['result'])
    return response

@eel.expose
def log_output(text):
    log_id = get_time_string()
    log_text(session_start_time, log_id, text)
    log_media(session_start_time, log_id)
    queue_log_translation(log_id, text)
    return log_id

def queue_log_translation(log_id, text):
    if not text or len(text.strip()) == 0:
        return

    if not translation_queue_slots.acquire(blocking=False):
        queue_full_message = "Bạn đã chạm giới hạn queue dịch. Hãy đợi các câu trước dịch xong rồi dịch tiếp."
        eel.updateLogDataById(log_id, {
            'translation_pending': False,
            'translation_status': 'queue_full',
            'translation_error': queue_full_message
        })()
        return

    eel.updateLogDataById(log_id, {
        'translation_pending': True,
        'translation_status': 'pending',
        'translation_error': None
    })()
    translation_executor.submit(translate_log_in_background, log_id, text)

def translate_log_in_background(log_id, text):
    try:
        translated_text = multi_translate(text)
        update_log_text(log_id, session_start_time, text, translated_text)
        eel.updateLogDataById(log_id, {
            'text': text,
            'translated_text': translated_text,
            'translation_pending': False,
            'translation_status': 'done',
            'translation_error': None
        })()
    except Exception as e:
        error_message = f"Translation Error: {str(e)}"
        eel.updateLogDataById(log_id, {
            'translation_pending': False,
            'translation_status': 'error',
            'translation_error': error_message
        })()
    finally:
        translation_queue_slots.release()

@eel.expose
def export_image_filter_profile(profile):
    return export_image_profile(profile)

@eel.expose
def load_image_filter_profiles():
    return load_image_profiles()

@eel.expose
def open_image_filter_profile():
    return open_image_profile()

@eel.expose
def load_game_text_scripts():
    return load_game_scripts()

@eel.expose
def open_game_text_script():
    return open_game_script()

@eel.expose
def update_main_window_text(text):
    is_log_text = False
    # Đảm bảo cập nhật text từ logs luôn có hiệu lực
    # bằng cách reset previousText nếu cần
    eel.resetPreviousText()()
    eel.updateOutput(text, is_log_text)()

@eel.expose
def update_log_window_text(log_id, text):
    update_log_text(log_id, session_start_time, text)
    eel.updateLogDataById(log_id, {'text': text})()

@eel.expose        
def translate(text):
    return multi_translate(text)

@eel.expose
def monitor_clipboard():
    if clipboard_timer.is_running:
        clipboard_timer.stop()
    else:
        clipboard_timer.start()

@eel.expose
def copy_text_to_clipboard(text):
    text_to_clipboard(text)

@eel.expose
def read_config(section, key):
    return r_config(section, key)

@eel.expose
def read_config_all():
    return r_config_all()

@eel.expose
def update_config(section, d):
    return w_config(section, d)

@eel.expose
def invoke_anki(action, params={}):
    return invoke(action, params)

@eel.expose
def get_anki_card_models():
    return get_anki_models()

@eel.expose
def fetch_anki_fields_by_modals(model_names):
    fetch_anki_fields_thread = threading.Thread(target=fetch_anki_fields, args=((model_names,)))
    fetch_anki_fields_thread.start()

@eel.expose
def update_anki_card_models(ankiModels):
    return update_anki_models(ankiModels)

@eel.expose
def create_note(note_data):
    return create_anki_note(note_data)

@eel.expose
def set_dictionary(dictionary):
    load_dictionary(dictionary)

@eel.expose
def get_jpod_url(kanji, kana):
    return get_jpod_audio_url(kanji=kanji, kana=kana)

@eel.expose
def get_dictionaries():
    return get_local_dictionaries()

@eel.expose
def look_up_dictionary(word):
    return look_up(word)

@eel.expose
def get_path_to_textractor():
    return path_to_textractor()

@eel.expose
def open_folder_for_textractor():
    return open_folder_textractor_path()

@eel.expose
def get_PIDs():
    return get_PID_list()

@eel.expose
def attach_process(pids):
    textractor_thread = threading.Thread(target=start_textractor, args=[pids,])
    textractor_thread.start()

@eel.expose
def detach_process(pids):
    try:
        global textractor
        for pid in pids:
            textractor.detach(pid)
    except Exception as e:
        print('error', str(e))
        return 'Error: failed to detach processes' + str(e)

def start_textractor(pids):
    try:
        global textractor
        textractor = Textractor(executable_path=path_to_textractor(), callback=monitor_textractor)
        time.sleep(1)
        textractor.attach_multiple(pids)
        textractor.read()
    except Exception as e:
        print('error', str(e))
        return 'Error: failed to attach processes' + str(e)

@eel.expose
def hook_code(code, pids):
    try:
        global textractor
        for pid in pids:
            textractor.hook(code, pid)
    except Exception as e:
        print(e)
        return 'Error: failed to hook code'

def monitor_textractor(output_objects):
    texthooker_config = r_config_section(TEXTHOOKER_CONFIG)
    output_objects = format_output(
        output_objects=output_objects, 
        remove_repeat_mode=texthooker_config['remove_repeat_mode'].lower(),
        is_remove_duplicates= texthooker_config['remove_duplicates'] == 'true',
        is_remove_spaces=texthooker_config['remove_spaces'] == 'true')
    eel.textractorPipe(output_objects)

@eel.expose
def open_new_window(html_file, height=900, width=600):
    eel.start(html_file, 
    close_callback=close, 
    mode=get_default_browser_name() if r_config(APP_CONFIG, "browser") == 'default' else r_config(APP_CONFIG, "browser"), 
    host=r_config(APP_CONFIG, "host"),
    size=(width, height), 
    port = int(r_config(APP_CONFIG, "port")))
    return

def run_eel():
    # Initialize Eel
    eel.init('web', allowed_extensions=['.js', '.html', '.map'])
    
    # Repair any corrupted log files before starting the application
    try:
        num_fixed = repair_log_files()
        if num_fixed > 0:
            print(f"Fixed {num_fixed} corrupted log files at startup")
    except Exception as e:
        print(f"Error repairing log files: {str(e)}")
    
    # Configure browser settings
    browser_mode = get_default_browser_name() if r_config(APP_CONFIG, "browser") == 'default' else r_config(APP_CONFIG, "browser")
    paths_config = r_config_section('PATHS')
    if 'browser' in paths_config:
        eel.browsers.set_path(browser_mode, paths_config['browser'])
    
    # Start the application
    eel.start('index.html',
    close_callback=close, 
    mode=browser_mode, 
    host=r_config(APP_CONFIG, "host"), 
    port=int(r_config(APP_CONFIG, "port"))
    )

if __name__ == '__main__':
    main_thread = threading.Thread(target=run_eel, args=())
    main_thread.start()

    # Thread to load dictionaries
    dictionary_thread = threading.Thread(target=load_all_dictionaries, args=()) 
    dictionary_thread.start()

    # Thread to export clipboard text continuously
    clipboard_timer = RepeatedTimer(1, clipboard_to_output)
    clipboard_timer.stop()

    # Thread to reset main window state every 30 minutes
    reset_window_timer = RepeatedTimer(1800, lambda: eel.resetPreviousText()())  # 1800 giây = 30 phút

    # Setup global hotkeys
    from hotkeys import setup_hotkeys
    setup_hotkeys()

    # Keep main thread running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        os._exit(0)
