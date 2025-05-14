#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os

libdir = 'lib'
if os.path.exists(libdir):
    sys.path.append(libdir)

import threading
import logging
import time
import random
from PIL import Image, ImageFilter
from flask import Flask, jsonify
from waveshare_epd import epd7in3f

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
EXPECTED_RATIO = SCREEN_WIDTH/SCREEN_HEIGHT
WALLPAPER_DIR = '/mnt/Data/装机/壁纸/树莓派'

app = Flask(__name__)

# 全局状态
DEFAULT_INTERVAL = 3600
timer_lock = threading.Lock()
epd_lock = threading.Lock()
current_timer = None
next_interval = DEFAULT_INTERVAL
eink_instance = None

wallpaper_paths = []
create_times = []
ctime_path_dict = {}



def update_wallpaper_paths(check_ctime=False):
    walk = os.walk(WALLPAPER_DIR)
    if check_ctime:
        create_times.clear()
        ctime_path_dict.clear()
    wallpaper_paths.clear()
    for f in walk:
        for file in f[2]:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_path = os.path.join(f[0], file)
                if check_ctime:
                    ctime = os.path.getctime(file_path)
                    create_times.append(ctime)
                    ctime_path_dict[ctime] = file_path
                wallpaper_paths.append(file_path)
    if not wallpaper_paths:
        logging.error("No wallpaper found in the specified directory.")


def process_image(image):
    w, h = image.size
    current_ratio = w / h

    if current_ratio > EXPECTED_RATIO:
        # 太宽，从中间裁切为所需比例
        new_width = int(h * EXPECTED_RATIO)
        left = (w - new_width) // 2
        right = left + new_width
        image = image.crop((left, 0, right, h))
        image = image.resize((SCREEN_WIDTH, SCREEN_HEIGHT), Image.LANCZOS)

    elif current_ratio < EXPECTED_RATIO:
        # 太高，从中间裁切一个 ratio 的画布，做模糊背景
        new_height = int(w / EXPECTED_RATIO)
        top = (h - new_height) // 2
        bottom = top + new_height
        crop_for_blur = image.crop((0, top, w, bottom))
        blurred = crop_for_blur.filter(ImageFilter.GaussianBlur(radius=20))
        blurred = blurred.resize((SCREEN_WIDTH, SCREEN_HEIGHT), Image.LANCZOS)

        # 原图缩放到目标高度
        new_width = int(SCREEN_HEIGHT * current_ratio)
        resized_foreground = image.resize((new_width, SCREEN_HEIGHT), Image.LANCZOS)

        # 将前景贴在中间
        final_image = blurred.copy()
        paste_x = (SCREEN_WIDTH - new_width) // 2
        final_image.paste(resized_foreground, (paste_x, 0))
        image = final_image

    elif current_ratio == EXPECTED_RATIO and w != SCREEN_WIDTH:
        image = image.resize((SCREEN_WIDTH, SCREEN_HEIGHT), Image.LANCZOS)

    return image


class EInkDisplay:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)
        self.epd = epd7in3f.EPD()
        self.last_update_time = 0

    def epd_display(self, path):
        if time.time() - self.last_update_time < 600:
            logging.info("Too fast, skip")
            return 1, self.last_update_time + 600 - time.time()
        logging.info(f'Display {path}')
        try:
            image = Image.open(path)
        except Exception as e:
            wallpaper_paths.remove(path)
            logging.error(f"Failed to open image {path}: {e}")
            return 2, f"Failed to open image {path}: {e}"
        image = process_image(image)
        image = image.transpose(Image.ROTATE_180)
        try:
            # Init
            logging.info("Init and Clear")
            self.epd.init()
            self.epd.Clear()
            # Display
            self.epd.display(self.epd.getbuffer(image))
        except IOError as e:
            logging.info(e)
            return 2, f"IOError: {e}"
        except KeyboardInterrupt:
            logging.info("Ctrl + C:")
            epd7in3f.epdconfig.module_exit(cleanup=True)
            exit()
        logging.info("Goto Sleep...")
        self.last_update_time = time.time()
        self.epd.sleep()
        return 0, 0


# 你要定时执行的函数
def scheduled_task(path=None):
    logging.info('开始执行')
    with epd_lock:
        if not wallpaper_paths:
            update_wallpaper_paths()
        if not wallpaper_paths:
            logging.error("No wallpaper found in the specified directory.")
            return
        # 如果没传入 path，就随机挑选一张
        if path is None:
            while True:
                current_img_path = random.choice(wallpaper_paths)
                if os.path.exists(current_img_path):
                    break
                else:
                    update_wallpaper_paths()
        else:
            current_img_path = path
        status, value = eink_instance.epd_display(current_img_path)
    if status == 0:
        # 正常等待1小时或2小时刷新
        if path is None:
            # 没有传入 path，即随机刷新，所以等待1小时（参数留空）
            schedule_next()
        else:
            # 指定文件已刷新，等待2小时
            logging.info(f"Next update in 2 hours.")
            schedule_next(delay=7200)
    if status == 1:
        # 提早下一次刷新
        if path is None:
            # 随机刷新
            logging.info(f"Next update in {value} seconds.")
            schedule_next(delay=value)
        else:
            # 指定文件刷新
            logging.info(f"。。。。。。")
            schedule_next(delay=600, path=path)


def schedule_next(delay=None, path=None):
    global current_timer, next_interval
    logging.info('schedule_next')
    with timer_lock:
        if current_timer:
            current_timer.cancel()
        if delay is None:
            next_interval = DEFAULT_INTERVAL
        else:
            next_interval = delay
        current_timer = threading.Timer(next_interval, scheduled_task, args=(path,))
        current_timer.start()
        print(f"[{time.ctime()}] 任务将在 {next_interval} 秒后执行")


@app.route('/api/switch_now', methods=['GET'])
def switch_now():
    logging.info('/api/switch_now')
    threading.Thread(target=scheduled_task).start()
    with timer_lock:
        next_interval = DEFAULT_INTERVAL
    return jsonify({"status": "triggered", "next_interval": next_interval})


# 显示最新
@app.route('/api/display_new', methods=['GET'])
def display_new():
    logging.info('/api/display_new')
    update_wallpaper_paths(check_ctime=True)
    if not create_times:
        logging.error("No new wallpapers found for display_new.")
        return jsonify({"status": "no_wallpapers"})
    latest_ctime = max(create_times)
    path = ctime_path_dict[latest_ctime]
    threading.Thread(target=scheduled_task, args=(path,)).start()
    return jsonify({"status": "delay_updated", "next_interval": delay})


@app.route('/api/get_status', methods=['GET'])
def get_status():
    logging.info('/api/get_status')
    with timer_lock:
        remaining_min = int(next_interval / 60)
        return jsonify({
            "remaining_minutes": remaining_min,
            "timer_active": current_timer.is_alive() if current_timer else False
        })

def main():
    global eink_instance
    eink_instance = EInkDisplay()
    update_wallpaper_paths()
    schedule_next(0)
    app.run(host='0.0.0.0', port=36547)
    epd7in3f.epdconfig.module_exit(cleanup=True)

if __name__ == "__main__":
    main()
