#!/usr/bin/env python3
import os
import socket
import time
from PIL import Image, ImageDraw, ImageFont
# NOTE: waveshare_epd is setup on via ~/.bashrc echo 'export PYTHONPATH=/data/git/e-Paper/RaspberryPi_JetsonNano/python/lib:$PYTHONPATH' >> ~/.bashrc

from waveshare_epd import epd2in13_V4
import psutil

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No net"

def get_temp():
    # read CPU temp in Celsius
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            t = int(f.read()) / 1000
        return f"{t:.1f}°C"
    except:
        return "N/A"

def main():
    epd = epd2in13_V4.EPD()
    epd.init()
    epd.Clear(0xFF)

    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)

    while True:
        ip = get_ip()
        temp = get_temp()
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        image = Image.new("1", (epd.height, epd.width), 255)
        draw = ImageDraw.Draw(image)
        draw.text((5, 5), f"Zero3W", font=font_large, fill=0)
        draw.text((5, 35), f"IP: {ip}", font=font_small, fill=0)
        draw.text((5, 55), f"CPU: {temp}", font=font_small, fill=0)
        draw.text((5, 75), now, font=font_small, fill=0)

        epd.display(epd.getbuffer(image))
        time.sleep(60)  # refresh once per minute

if __name__ == "__main__":
    main()


