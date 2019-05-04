# encoding=utf-8
import os
import time
import re
import math

from PIL import Image, ImageFont, ImageDraw
import numpy as np
import cv2


def normalize_filename(filename):
    return re.sub(r"[\\\/\.\#\%\$\!\@\(\)\[\]\s]+", "_", filename)


def datetime_now():
    return time.strftime('%Y-%m-%d_%H-%M-%S', time.gmtime())


def time_tostring(t):
    return time.strftime('%H:%M:%S', time.gmtime(t))


def fetch_font(font_file, font_size=64):
    font = ImageFont.truetype(font_file, font_size)
    font_name = '_'.join(font.getname())

    font_dict = dict()
    font_dict['font'] = font
    font_dict['font_name'] = normalize_filename(font_name)
    font_dict['font_size'] = font_size

    return font_dict


def fetch_fonts(font_folder, font_size=64):

    font_dicts = []
    font_files = os.listdir(font_folder)
    for font_file in font_files:
        font_path = f"{font_folder}/{font_file}"
        font_dict = fetch_font(font_path, font_size=font_size)
        font_dicts.append(font_dict)

    return font_dicts


def draw_text(text, font_dict, image_size=64):

    font = font_dict['font']
    font_size = font_dict['font_size']
    font_name = font_dict['font_name']

    canvas_size = int(image_size * 2)
    canvas = Image.new('L', (canvas_size, canvas_size), color=0)
    ctx = ImageDraw.Draw(canvas)

    # find the offset to draw the image
    text_offset = (canvas_size - font_size) / 2

    # draw the text
    ctx.text(
        (text_offset, text_offset),
        text,
        fill=255,
        font=font
    )

    np_img = np.array(canvas)
    non_zeros_indies = np_img.nonzero()

    # If the font does not support this character,
    # it will draw either none or a square
    # The try ... except block below is to deal with blank image
    try:
        max_x = non_zeros_indies[1][np.argmax(non_zeros_indies[1])]
        min_x = non_zeros_indies[1][np.argmin(non_zeros_indies[1])]

        max_y = non_zeros_indies[0][np.argmax(non_zeros_indies[0])]
        min_y = non_zeros_indies[0][np.argmin(non_zeros_indies[0])]
    except:
        # blank image encounter
        return None

    actual_width = max_x - min_x
    actual_height = max_y - min_y

    x_padding = (image_size - actual_width) / 2
    y_padding = (image_size - actual_height) / 2

    offset_x = min_x - x_padding
    offset_y = min_y - y_padding

    # centered-kanji image
    final_img = canvas.crop((
        offset_x, offset_y, offset_x + image_size,
        offset_y + image_size
    ))

    return final_img
