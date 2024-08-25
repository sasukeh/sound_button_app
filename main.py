import os
import sys
import socket
import base64
from flask import Flask, request, render_template, redirect, url_for, send_from_directory

# Webサーバー設定
app = Flask(__name__)
UPLOAD_FOLDER = 'static/sounds'  # アップロード先のディレクトリ
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'mp4', 'm4a'}  # 許可するファイル形式

# ボタン番号とGPIOピンのマッピング
BUTTON_PIN_SOUND_MAP = {
    1: (3, "sound1.wav"),    # ピン3 (GPIO 2)
    2: (5, "sound2.wav"),    # ピン5 (GPIO 3)
    3: (7, "sound3.wav"),    # ピン7 (GPIO 4)
    4: (8, "sound4.wav"),    # ピン8 (GPIO 14)
    5: (10, "sound5.wav"),   # ピン10 (GPIO 15)
    6: (11, "sound6.wav"),   # ピン11 (GPIO 17)
    7: (12, "sound7.wav"),   # ピン12 (GPIO 18)
    8: (13, "sound8.wav"),   # ピン13 (GPIO 27)
    9: (15, "sound9.wav"),   # ピン15 (GPIO 22)
    10: (16, "sound10.wav"), # ピン16 (GPIO 23)
    11: (18, "sound11.wav"), # ピン18 (GPIO 24)
    12: (19, "sound12.wav"), # ピン19 (GPIO 10)
    13: (21, "sound13.wav"), # ピン21 (GPIO 9)
    14: (22, "sound14.wav"), # ピン22 (GPIO 25)
    15: (23, "sound15.wav"), # ピン23 (GPIO 11)
    16: (24, "sound16.wav")  # ピン24 (GPIO 8)
}

# GPIOの初期化
is_raspberry_pi = False

try:
    import RPi.GPIO as GPIO
    import pygame
    import time
    is_raspberry_pi = True
except (ImportError, RuntimeError):
    print("GPIOライブラリが見つからないため、GPIO機能を無効化しています。")

if is_raspberry_pi:
    GPIO.setmode(GPIO.BOARD)  # 物理ピン番号を使用
    for button_pin, (physical_pin, _) in BUTTON_PIN_SOUND_MAP.items():
        GPIO.setup(physical_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    pygame.mixer.init()

    def play_sound(sound_file):
        pygame.mixer.music.load(sound_file)
        pygame.mixer.music.play()

# アプリ起動時に必要なディレクトリを作成する
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_assigned_buttons():
    """Assignされているボタンのリストを返す"""
    assigned_buttons = []
    for button, (_, sound_file) in BUTTON_PIN_SOUND_MAP.items():
        file_path = os.path.join(UPLOAD_FOLDER, sound_file)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            assigned_buttons.append(button)
    return assigned_buttons

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if ('file' not in request.files and 'file_data' not in request.form) or 'button' not in request.form:
            return redirect(request.url)
        
        button_number = int(request.form['button'])
        
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            if file and allowed_file(file.filename):
                _, sound_file = BUTTON_PIN_SOUND_MAP[button_number]
                file_path = os.path.join(UPLOAD_FOLDER, sound_file)
                file.save(file_path)
        elif 'file_data' in request.form and request.form['file_data'] != '':
            file_data = request.form['file_data']
            _, sound_file = BUTTON_PIN_SOUND_MAP[button_number]
            file_path = os.path.join(UPLOAD_FOLDER, sound_file)

            # Base64デコード前にデータURIが正しい形式かどうかを確認
            if "," in file_data:
                try:
                    file_bytes = base64.b64decode(file_data.split(",")[1])
                    with open(file_path, 'wb') as f:
                        f.write(file_bytes)
                except (IndexError, ValueError) as e:
                    print(f"Error decoding file data: {e}")
                    return redirect(request.url)
            else:
                print("Error: file data is not in the expected format.")
                return redirect(request.url)
        else:
            return redirect(request.url)

        return redirect(url_for('upload_file'))

    files = os.listdir(UPLOAD_FOLDER)
    assigned_buttons = get_assigned_buttons()  # Assignされているボタンのリスト
    return render_template('index.html', files=files, buttons=range(1, 17), assigned_buttons=assigned_buttons)

@app.route('/play_sound/<filename>')
def play_sound(filename):
    """指定された音声ファイルを再生するためのルート"""
    return send_from_directory(UPLOAD_FOLDER, filename)

if is_raspberry_pi:
    def button_listener():
        try:
            while True:
                for button_number, (physical_pin, sound_file) in BUTTON_PIN_SOUND_MAP.items():
                    if GPIO.input(physical_pin) == GPIO.HIGH:
                        sound_path = os.path.join(UPLOAD_FOLDER, sound_file)
                        if os.path.exists(sound_path):
                            play_sound(sound_path)
                        time.sleep(0.5)
                time.sleep(0.1)
        except KeyboardInterrupt:
            GPIO.cleanup()

def find_available_port(start_port=5000, max_port=5100):
    """指定された範囲内で利用可能なポートを見つける"""
    port = start_port
    while port <= max_port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('localhost', port)) != 0:
                return port
        port += 1
    raise RuntimeError("利用可能なポートが見つかりませんでした。")

if __name__ == '__main__':
    if is_raspberry_pi:
        from threading import Thread
        button_thread = Thread(target=button_listener)
        button_thread.start()

    # 利用可能なポートを探してWebサーバーを起動
    available_port = find_available_port()
    # SSLコンテキストを追加してHTTPSで起動
    app.run(host='0.0.0.0', port=available_port, ssl_context=('cert.pem', 'key.pem'))