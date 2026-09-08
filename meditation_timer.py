import time
import subprocess
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import st7789
import pygame

# --- Initialize Audio Engine ---
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)

gong_sound = None
try:
    gong_sound = pygame.mixer.Sound("/home/pi/gong.wav")
except Exception as e:
    print("Warning: gong.wav load error:", e)

# Pre-load MP3 into Pygame music engine
has_music_file = False
try:
    pygame.mixer.music.load("/home/pi/music.mp3")
    has_music_file = True
except Exception as e:
    print("Warning: music.mp3 load error:", e)

# --- Initialize Display ---
disp = st7789.ST7789(
    port=0,
    cs=1,
    dc=9,
    backlight=13,
    rotation=90,
    spi_speed_hz=40 * 1000 * 1000
)
disp.begin()

WIDTH = disp.width
HEIGHT = disp.height

# --- Pirate Audio GPIO Button Setup ---
BUTTON_A = 5   # Top Left: Short = +1 Min | Long = Play/Stop Music
BUTTON_B = 6   # Bottom Left: -1 Min
BUTTON_X = 16  # Top Right: Start / Pause
BUTTON_Y = 24  # Bottom Right: Short = Reset | Long = Shutdown

BUTTONS = [BUTTON_A, BUTTON_B, BUTTON_X, BUTTON_Y]

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTONS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# --- State Variables ---
timer_minutes = 10
remaining_seconds = timer_minutes * 60
is_running = False
is_playing_music = False

def show_shutdown_screen():
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font_msg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except:
        font_msg = ImageFont.load_default()
    draw.text((WIDTH // 2, HEIGHT // 2), "Shutting\nDown...", font=font_msg, fill=(255, 100, 100), anchor="mm", align="center")
    disp.display(img)
    time.sleep(1.5)

    img_black = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
    disp.display(img_black)
    
    GPIO.setup(13, GPIO.OUT)
    GPIO.output(13, GPIO.LOW)

def draw_ui():
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(14, 17, 26))
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except:
        font_large = font_small = ImageFont.load_default()

    mins, secs = divmod(remaining_seconds, 60)
    time_str = f"{mins:02d}:{secs:02d}"

    # Centered Countdown
    draw.text((WIDTH // 2, HEIGHT // 2), time_str, font=font_large, fill=(255, 255, 255), anchor="mm")

    # Corner button labels
    btn_a_txt = "♫ Stop" if is_playing_music else "+1m/♫"
    draw.text((10, 16), btn_a_txt, font=font_small, fill=(100, 200, 255))
    draw.text((10, HEIGHT - 16), "-1m", font=font_small, fill=(100, 200, 255), anchor="ld")

    status_txt = "Pause" if is_running else "Start"
    status_color = (255, 100, 100) if is_running else (100, 255, 100)
    draw.text((WIDTH - 10, 16), status_txt, font=font_small, fill=status_color, anchor="ra")
    draw.text((WIDTH - 10, HEIGHT - 16), "Reset/OFF", font=font_small, fill=(255, 200, 100), anchor="rd")

    disp.display(img)

def toggle_music():
    global is_playing_music
    if not has_music_file:
        return

    if is_playing_music:
        pygame.mixer.music.stop()
        is_playing_music = False
    else:
        pygame.mixer.music.play(loops=-1)
        is_playing_music = True

# Initial screen draw
draw_ui()
last_tick = time.time()

try:
    while True:
        now = time.time()

        # Button A (Short = +1 Min | Long = Toggle Music)
        if not GPIO.input(BUTTON_A):
            press_start = time.time()
            is_long_press = False

            while not GPIO.input(BUTTON_A):
                if time.time() - press_start >= 1.2:
                    is_long_press = True
                    break
                time.sleep(0.05)

            if is_long_press:
                toggle_music()
                draw_ui()
                # Wait for user to release the button
                while not GPIO.input(BUTTON_A):
                    time.sleep(0.05)
            elif not is_running:
                timer_minutes = min(90, timer_minutes + 1)
                remaining_seconds = timer_minutes * 60
                draw_ui()
                time.sleep(0.18)

        # Button B (-1 Min)
        if not GPIO.input(BUTTON_B) and not is_running:
            timer_minutes = max(1, timer_minutes - 1)
            remaining_seconds = timer_minutes * 60
            draw_ui()
            time.sleep(0.18)

        # Button X (Start / Pause)
        if not GPIO.input(BUTTON_X):
            is_running = not is_running
            draw_ui()
            time.sleep(0.3)

        # Button Y (Short = Reset | Long 3s = Shutdown)
        if not GPIO.input(BUTTON_Y):
            press_start = time.time()
            is_long_press = False

            while not GPIO.input(BUTTON_Y):
                if time.time() - press_start >= 3.0:
                    is_long_press = True
                    break
                time.sleep(0.05)

            if is_long_press:
                if is_playing_music:
                    pygame.mixer.music.stop()
                show_shutdown_screen()
                time.sleep(1)
                subprocess.run(["sudo", "shutdown", "-h", "now"])
            else:
                is_running = False
                remaining_seconds = timer_minutes * 60
                draw_ui()
                time.sleep(0.2)

        # Countdown tick logic
        if is_running and (now - last_tick >= 1.0):
            last_tick = now
            if remaining_seconds > 0:
                remaining_seconds -= 1
                draw_ui()
            else:
                is_running = False
                if gong_sound:
                    gong_sound.play()
                draw_ui()

        time.sleep(0.05)

except KeyboardInterrupt:
    if is_playing_music:
        pygame.mixer.music.stop()
    GPIO.cleanup()
