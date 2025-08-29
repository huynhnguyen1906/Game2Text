import time
import os
import re
import eel
import glob
import base64
import codecs
import threading
from pathlib import Path
from datetime import datetime
from config import r_config, LOG_CONFIG
from util import create_directory_if_not_exists, base64_to_image_path
from gamescript import add_matching_script_to_logs
from tools import bundle_dir

TEXT_LOG_PATH = Path(bundle_dir, 'logs', 'text')
IMAGE_LOG_PATH = Path(bundle_dir, 'logs', 'images')

game_script_matcher = None

def get_time_string():
    return time.strftime('%Y%m%d-%H%M%S')

def parse_time_string(time_string):
    return datetime.strptime(time_string, '%Y%m%d-%H%M%S')

def get_hours_string(datetime_object):
    return datetime.strftime(datetime_object, '%I:%M%p')

def log_text(start_time, request_time, text, translated_text=None):
    parsed_text = text.replace('\n', '')
    if (len(parsed_text) < 1):
        return
    filename = '{}/{}.txt'.format(TEXT_LOG_PATH, start_time)
    create_directory_if_not_exists(filename)
    
    # Nếu có bản dịch, thêm vào sau văn bản gốc với dấu phân cách đặc biệt
    log_content = parsed_text
    if translated_text:
        # Sử dụng ký tự phân cách |||TRANSLATION||| để phân biệt giữa văn bản gốc và bản dịch
        log_content = f"{parsed_text}|||TRANSLATION|||{translated_text}"
    
    with open(filename, 'a', encoding='utf-8', newline='') as f:
        if(os.path.getsize(filename) > 0):
            f.write('{}{}, {}'.format('\n', request_time, log_content))
        else:
            f.write('{}, {}'.format(request_time, log_content))
        f.close()
        
def log_media(session_start_time, request_time):
    is_log_images = r_config(LOG_CONFIG, 'logimages').lower() == 'true'
    if is_log_images:
        image_extension = r_config(LOG_CONFIG, 'logimagetype')
        file_name = request_time + '.' + image_extension
        full_image_path = str(Path(IMAGE_LOG_PATH, session_start_time, file_name))
        thread = threading.Thread(target = log_video_image,  args=[full_image_path])
        thread.start()
    else:
        insert_newest_log_without_image()

def log_video_image(image_path):
    create_directory_if_not_exists(image_path)
    base64_image = eel.getVideoImage()()
    # Manually add image data to log data because image is yet to be saved to file
    insert_newest_log_with_image(base64_image, os.path.splitext(image_path)[1])
    # Save image
    base64_to_image_path(base64_image, image_path)


def get_image_type(log_id, folder_name):
    path = Path(IMAGE_LOG_PATH, folder_name)
    if not path.is_dir():
        return None
    file_name = next((f for f in os.listdir(path) if re.match('{}.(?:jpg|jpeg|png|tiff|webp)$'.format(log_id), f)), None)
    if not file_name:
        return None
    return Path(file_name).suffix.split('.')[1]

def get_base64_image_with_log(log_id, folder_name):
    imagePath = str(Path(IMAGE_LOG_PATH, folder_name, log_id + '.png')) 
    path = Path(IMAGE_LOG_PATH, folder_name)
    if not path.is_dir():
        return None
    file_name = next((f for f in os.listdir(path) if re.match('{}.(?:jpg|jpeg|png|tiff|webp)$'.format(log_id), f)), None)
    if not file_name:
        return None
    with open('{}/{}'.format(path, file_name), 'rb') as image_file:
        base64_bytes  = base64.b64encode(image_file.read())
    base64_image_string = base64_bytes.decode('utf-8')
    return base64_image_string

@eel.expose
def show_logs():
    last_session_max_log_size = int(r_config(LOG_CONFIG, 'lastsessionmaxlogsize'))
    saved_logs = get_logs(limit=last_session_max_log_size)
    if len(saved_logs) > 0:
        # Workaround to fix the problem first image data is not transferred to log window
        image_data_list = eel.getCachedScreenshots()() 
        if image_data_list:
            for log in saved_logs:
                if log['id'] in image_data_list.keys():
                    # Remove cache if file is saved
                    if log['image']:
                        eel.removeCachedScreenshot(log['id'])()
                    # Get image from cache
                    else:
                        image_data = image_data_list[log['id']]
                        log['image'] =  image_data['base64ImageString']
                        log['image_type'] = image_data['imageType']
        return saved_logs


def text_to_log(text, file_path):
    # Validate the log format - first check if text is long enough and has proper format
    text = text.strip()
    if not text or len(text) < 17:  # Must have at least timestamp (15) + ", " (2)
        return None  # Return None for invalid entries instead of creating error logs
    
    try:
        # Try to extract timestamp (should be the first 15 characters)
        log_id = text[:15]
        
        # Validate timestamp format with regex
        if not re.match(r'^\d{8}-\d{6}$', log_id):
            return None  # Return None for invalid timestamp format
            
        date = parse_time_string(log_id)
        
        # Check if there's a comma and space after timestamp
        if len(text) < 17 or text[15:17] != ', ':
            return None  # Return None if format is incorrect
            
        # Extract content (should start after timestamp + comma + space = 17 chars)
        content = text[17:] if len(text) > 17 else ""
            
        # Only get image if we have a valid timestamp
        image = get_base64_image_with_log(log_id=log_id, folder_name=Path(file_path).stem)
        image_type = get_image_type(log_id=log_id, folder_name=Path(file_path).stem)
        
        # Check if text contains translation
        translated_text = None
        
        # If translation delimiter is found
        if "|||TRANSLATION|||" in content:
            parts = content.split("|||TRANSLATION|||", 1)
            original_text = parts[0].strip()
            translated_text = parts[1].strip()
        else:
            original_text = content.strip()
            
    except ValueError:
        # If parsing fails, return None instead of creating error entries
        return None
            
        # Only get image if we have a valid timestamp
        image = get_base64_image_with_log(log_id=log_id, folder_name=Path(file_path).stem)
        image_type = get_image_type(log_id=log_id, folder_name=Path(file_path).stem)
        
        # Check if text contains translation
        translated_text = None
        
        # If translation delimiter is found
        if "|||TRANSLATION|||" in content:
            parts = content.split("|||TRANSLATION|||", 1)
            original_text = parts[0]
            translated_text = parts[1]
        else:
            original_text = content
    except ValueError:
        # If the line doesn't start with a valid timestamp, create a fallback entry
        log_id = get_time_string()  # Use current time as fallback
        date = parse_time_string(log_id)
        original_text = f"Error parsing log: {text[:50]}..." if len(text) > 50 else f"Error parsing log: {text}"
        translated_text = None
        image = None
        image_type = None
    
    log = {
        'id': log_id,
        'file': Path(file_path).name,
        'folder': Path(file_path).stem,
        'image': image,
        'image_type': image_type,
        'audio': '', # TODO: get audio file path
        'hours': get_hours_string(date),
        'text': original_text,
        'translated_text': translated_text
    }
    return log

def add_gamescript_to_logs(logs):
    gamescript = r_config(LOG_CONFIG, 'gamescriptfile',)
    if (gamescript):
        if (Path(gamescript).is_file()):
            logs = add_matching_script_to_logs(gamescript, logs)
            for log in logs:
                if ('matches' in log):
                    eel.updateLogDataById(log['id'], {'matches': log['matches'], 'autoMatch': True, 'isMatched': False})()    
    return
    
def get_logs(limit=0):
    output = []
    if not os.path.exists(TEXT_LOG_PATH):
        return []
    list_of_files = glob.glob(str(TEXT_LOG_PATH) + '/*.txt')
    if len(list_of_files) < 1:
        return []
    latest_file = max(list_of_files, key=os.path.getctime)
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()  # Remove whitespace and newlines
                
                # Skip empty lines
                if not line:
                    continue
                    
                # Skip lines that are too short to contain a valid log entry
                if len(line) < 17:  # timestamp (15) + comma + space + at least some content
                    print(f"Skipping short line: {line}")
                    continue
                
                # Check if line starts with a valid timestamp
                if not re.match(r'^\d{8}-\d{6},', line):
                    print(f"Skipping line without valid timestamp: {line[:30]}...")
                    continue
                
                try:
                    log = text_to_log(line, latest_file)
                    # Only add logs that are not None and have actual text content
                    if log is not None and log.get('text', '').strip():
                        output.append(log)
                except Exception as e:
                    print(f"Error parsing log line: {str(e)}")
                    # Continue processing other lines
                    continue
            f.close()
        if limit > 0 and len(output) > limit:
            output = output[-limit:]
        # Start another thread to match logs to game script
        is_matching = eel.isMatchingScript()()
        if is_matching:
            thread = threading.Thread(target = add_gamescript_to_logs,  args=[output])
            thread.start()
    except Exception as e:
        print(f"Error reading log file: {str(e)}")
        # Return any logs we were able to parse
    return output

def get_latest_log():
    log = {}
    if not os.path.exists(TEXT_LOG_PATH):
        return {}
    list_of_files = glob.glob(str(TEXT_LOG_PATH) + '/*.txt')
    if len(list_of_files) < 1:
        return {}
    latest_file = max(list_of_files, key=os.path.getctime)
    if not latest_file:
        return {}
    
    try:
        # Read the file safely and find the last valid line
        last_valid_line = ""
        with open(latest_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()  # Remove whitespace and newlines
                
                # Skip empty lines
                if not line:
                    continue
                    
                # Skip lines that are too short to contain a valid log entry
                if len(line) < 17:  # timestamp (15) + comma + space + at least some content
                    continue
                
                # Check if line starts with a valid timestamp and has content
                if re.match(r'^\d{8}-\d{6},', line) and len(line) > 17:
                    # Check if there's actual content after the timestamp
                    content_part = line[17:].strip()
                    if content_part:  # Only consider lines with actual content
                        last_valid_line = line
            f.close()
        
        # If we couldn't find any valid line
        if not last_valid_line:
            # Create a dummy log with the current time
            log_id = get_time_string()
            date = parse_time_string(log_id)
            log = {
                'id': log_id,
                'file': Path(latest_file).name,
                'folder': Path(latest_file).stem,
                'image': None,
                'image_type': None, 
                'audio': '',
                'hours': get_hours_string(date),
                'text': 'No valid log entries found',
                'translated_text': None
            }
            return log

        # Try to parse the last valid line
        try:
            log = text_to_log(last_valid_line, latest_file)
            if log is None:  # If text_to_log returns None, create a fallback
                log_id = get_time_string()
                date = parse_time_string(log_id)
                log = {
                    'id': log_id,
                    'file': Path(latest_file).name,
                    'folder': Path(latest_file).stem,
                    'image': None, 
                    'image_type': None,
                    'audio': '',
                    'hours': get_hours_string(date),
                    'text': 'Unable to parse latest log entry',
                    'translated_text': None
                }
        except Exception as e:
            print(f"Error parsing latest log: {str(e)}")
            # Create a fallback log
            log_id = get_time_string()
            date = parse_time_string(log_id)
            log = {
                'id': log_id,
                'file': Path(latest_file).name,
                'folder': Path(latest_file).stem,
                'image': None, 
                'image_type': None,
                'audio': '',
                'hours': get_hours_string(date),
                'text': f"Error in last log: {last_valid_line[:30]}...",
                'translated_text': None
            }
    except Exception as e:
        print(f"Error reading log file: {str(e)}")
        # Create a fallback log with current time
        log_id = get_time_string()
        date = parse_time_string(log_id)
        log = {
            'id': log_id,
            'file': Path(latest_file).name,
            'folder': Path(latest_file).stem,
            'image': None,
            'image_type': None,
            'audio': '',
            'hours': get_hours_string(date),
            'text': f"Error accessing log file",
            'translated_text': None
        }
        return log
        
    # Start another thread to match log to game script
    try:
        is_matching = eel.isMatchingScript()()
        if is_matching:
            thread = threading.Thread(target=add_gamescript_to_logs, args=[[log],])
            thread.start()
    except Exception as e:
        print(f"Error starting game script matching: {str(e)}")
        
    return log

@eel.expose
def delete_log(log_id, folder_name):
    filename = '{}/{}.txt'.format(TEXT_LOG_PATH, folder_name)
    if (Path(filename).is_file()):
        temp_filename = '{}/temp.txt'.format(TEXT_LOG_PATH)
        # lines = []
        with open(filename, "r", encoding='utf-8') as file:
            lines = file.readlines()
        with open(temp_filename, "w", encoding='utf-8') as new_file:
            newLines = [line.rstrip('\r\n') for line in lines if line[:15] != log_id]
            for line in newLines:
                if line != newLines[0]:
                    new_file.write('\n')
                new_file.write(line)

        # Remove original file and rename the temporary as the original one
        os.remove(filename)
        os.rename(temp_filename, filename)
        return
    return 

@eel.expose
def update_log_text(log_id, folder_name, text, translated_text=None):
    parsed_text = text.replace('\n', '')
    if (len(parsed_text) < 1):
        return
    
    # Nếu có bản dịch, thêm vào sau văn bản gốc với dấu phân cách đặc biệt
    log_content = parsed_text
    if translated_text:
        # Sử dụng ký tự phân cách |||TRANSLATION||| để phân biệt giữa văn bản gốc và bản dịch
        log_content = f"{parsed_text}|||TRANSLATION|||{translated_text}"
    
    filename = '{}/{}.txt'.format(TEXT_LOG_PATH, folder_name)
    if (Path(filename).is_file()):
        temp_filename = '{}/temp.txt'.format(TEXT_LOG_PATH)
        with codecs.open(filename, 'r', encoding='utf-8') as fi, \
            codecs.open(temp_filename, 'w', encoding='utf-8') as fo:

            for line in fi:
                line_id = line[:15]
                if (line_id == log_id):
                    fo.write('{}, {}'.format(log_id, log_content))
                else:
                    fo.write(line)

        # Remove original file and rename the temporary as the original one
        os.remove(filename)
        os.rename(temp_filename, filename)
        return
    return
        
def insert_newest_log_with_image(base64_image_string, image_type):
    log = get_latest_log()
    log['image'] = base64_image_string
    log['image_type'] = image_type
    eel.addLogs([log])()

def insert_newest_log_without_image():
    eel.addLogs([get_latest_log()])()

# Middleman for selected main window to launch add card in log window
@eel.expose
def highlight_text_in_logs(text):
    eel.showCardWithSelectedText(text)()

@eel.expose
def update_log_with_translation(log_id, text, translated_text):
    """
    Updates a log entry with both original text and its translation
    
    Args:
        log_id (str): The ID of the log
        text (str): The original text
        translated_text (str): The translated text
    """
    try:
        # Validate log_id format to prevent file corruption
        if not log_id or len(log_id) != 15:
            print(f"Invalid log ID format: {log_id}")
            return
        
        try:
            # Verify log_id is a valid timestamp
            parse_time_string(log_id)
        except ValueError:
            print(f"Invalid timestamp format in log ID: {log_id}")
            return
            
        # Extract folder name from log ID (session start time)
        folder_name = None
        list_of_files = glob.glob(str(TEXT_LOG_PATH) + '/*.txt')
        if len(list_of_files) > 0:
            latest_file = max(list_of_files, key=os.path.getctime)
            folder_name = Path(latest_file).stem
        
        if folder_name:
            update_log_text(log_id, folder_name, text, translated_text)
            # Also update the UI to show the translation
            eel.updateLogDataById(log_id, {'text': text, 'translated_text': translated_text})()
    except Exception as e:
        print(f"Error updating log with translation: {str(e)}")
    return

@eel.expose
def repair_log_files():
    """
    Repairs corrupted log files by ensuring each line starts with a proper timestamp.
    Should be called when the application starts.
    """
    if not os.path.exists(TEXT_LOG_PATH):
        return False
        
    list_of_files = glob.glob(str(TEXT_LOG_PATH) + '/*.txt')
    if len(list_of_files) < 1:
        return False
        
    files_fixed = 0
    
    for log_file in list_of_files:
        file_corrupted = False
        valid_lines = []
        current_valid_line = None
        
        # Read the file and identify valid/corrupted lines
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    # Check if line starts with a valid timestamp format
                    if len(line) >= 15 and re.match(r'^\d{8}-\d{6}', line[:15]):
                        # This is a new valid line
                        if current_valid_line:
                            valid_lines.append(current_valid_line)
                        current_valid_line = line.rstrip('\r\n')
                    else:
                        # This line doesn't start with a timestamp
                        file_corrupted = True
                        if current_valid_line:
                            # Append to the previous valid line
                            current_valid_line += " " + line.rstrip('\r\n')
                        else:
                            # Skip lines that don't start with a timestamp and don't have a valid line preceding them
                            print(f"Skipping invalid log line: {line[:30]}...")
                
                # Add the last valid line if it exists
                if current_valid_line:
                    valid_lines.append(current_valid_line)
        except Exception as e:
            print(f"Error reading log file {log_file}: {str(e)}")
            continue
            
        # If the file was corrupted, rewrite it with the fixed content
        if file_corrupted:
            try:
                backup_file = log_file + ".bak"
                # Create a backup of the original file
                os.rename(log_file, backup_file)
                
                # Write the corrected content
                with open(log_file, 'w', encoding='utf-8') as f:
                    for i, valid_line in enumerate(valid_lines):
                        if i > 0:
                            f.write('\n')
                        f.write(valid_line)
                
                files_fixed += 1
                print(f"Fixed corrupted log file: {log_file}")
            except Exception as e:
                print(f"Error fixing log file {log_file}: {str(e)}")
                # Try to restore the backup if something went wrong
                if os.path.exists(backup_file):
                    try:
                        if os.path.exists(log_file):
                            os.remove(log_file)
                        os.rename(backup_file, log_file)
                    except:
                        pass
    
    return files_fixed