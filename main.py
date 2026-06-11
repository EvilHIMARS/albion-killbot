import os
import asyncio
import discord
from discord.ext import tasks, commands
import requests
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ==================== НАСТРОЙКИ ====================
TOKEN = os.environ.get("DISCORD_TOKEN")  # Токен из настроек Render
CHANNEL_ID = 1488538529314246738         # ID канала по умолчанию
GUILD_ID = "c7fgh-V2QTSYBJqKPpNtkg"      # ID твоей гильдии (x E C L I P S E x)
SERVER_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo" # Европа
# ===================================================

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)
processed_events = set()
FONT_PATH = "/tmp/Roboto-Bold.ttf"

# Координаты слотов для сетки 3х4 (шаг 145px под Full-HD)
SLOT_MAPPING = {
    "Bag": (0, 0),       "Head": (1, 0),      "Cape": (2, 0),
    "MainHand": (0, 1),  "Armor": (1, 1),     "OffHand": (2, 1),
    "Potion": (0, 2),    "Shoes": (1, 2),     "Food": (2, 2),
    "Mount": (1, 3)
}

def download_font():
    if not os.path.exists(FONT_PATH):
        try:
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
            response = requests.get(url, timeout=10)
            with open(FONT_PATH, "wb") as f:
                f.write(response.content)
            print("[Система] Красивый русский шрифт Roboto загружен!")
        except Exception as e:
            print(f"[Ошибка] Не удалось скачать шрифт: {e}")

def parse_item_meta(item_type):
    """Разбирает имя шмотки (напр. T8_MAIN_AXE_KEEPER@3) на Тир и Энчант"""
    if not item_type:
        return ""
    tier = ""
    for i in range(4, 9):
        if item_type.startswith(f"T{i}"):
            tier = f"T{i}"
            break
    enchant = ""
    if "@" in item_type:
        enchant = f".{item_type.split('@')[-1]}"
    return f"{tier}{enchant}"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive")
        
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_web_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()

@bot.event
async def on_ready():
    download_font()
    print(f"[{bot.user.name}] Бот на Render готов генерировать Full-HD карточки шмота!")
    if not check_killboard.is_running():
        check_killboard.start()

# --- ФУНКЦИЯ ОТРИСОВКИ СЕТКИ ПРЕДМЕТОВ ---
async def draw_equipment_grid(draw_ctx, base_img, equipment_dict, start_x, start_y, font):
    for slot, (grid_x, grid_y) in SLOT_MAPPING.items():
        x = start_x + grid_x * 150
        y = start_y + grid_y * 150
        # Рисуем пустые ячейки под инвентарь
        draw_ctx.rectangle([x, y, x + 130, y + 130], fill=(35, 20, 60), outline=(142, 68, 173), width=2)

    async with aiohttp.ClientSession() as session:
        for slot, item_data in equipment_dict.items():
            if not item_data or slot not in SLOT_MAPPING:
                continue
            item_type = item_data.get("Type")
            if not item_type:
                continue
                
            grid_x, grid_y = SLOT_MAPPING[slot]
            x = start_x + grid_x * 150
            y = start_y + grid_y * 150
            
            url = f"https://render.albiononline.com/v1/item/{item_type}.png?size=130"
            try:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        item_img = Image.open(BytesIO(img_data)).convert("RGBA")
                        base_img.paste(item_img, (x, y), item_img)
                        
                        # Пишем тир шмотки (например 8.3) поверх картинки
                        meta_text = parse_item_meta(item_type)
                        if meta_text:
                            draw_ctx.text((x + 10, y + 10), meta_text, fill=(241, 196, 15), font=font)
            except:
                pass

# --- ГЕНЕРАЦИЯ HD КАРТИНКИ (1920x1080) ---
async def generate_hd_battle_sheet(killer_data, victim_data, fame, is_kill):
    # Создаем холст 1920x1080 с темно-фиолетовым фоном #2D0A4E
    img = Image.new("RGB", (1920, 1080), color=(45, 10, 78))
    draw = ImageDraw.Draw(img)
    
    # Внешняя неоновая рамка
    border_color = (46, 204, 113) if is_kill else (231, 76, 60)
    draw.rectangle([(20, 20), (1900, 1060)], outline=border_color, width=5)
    
    try:
        font_title = ImageFont.truetype(FONT_PATH, 64)
        font_header = ImageFont.truetype(FONT_PATH, 40)
        font_sub = ImageFont.truetype(FONT_PATH, 26)
        font_item = ImageFont.truetype(FONT_PATH, 18)
    except:
        font_title = font_header = font_sub = font_item = None

    # ЛЕВАЯ СТОРОНА: УБИЙЦА
    draw.text((100, 80), "УБИЙЦА ⚔️", fill=(46, 204, 113), font=font_header)
    draw.text((100, 150), killer_data['Name'], fill=(255, 255, 255), font=font_title)
    draw.text((100, 240), f"Гильдия: [{killer_data['Alliance']}] {killer_data['Guild']}", fill=(200, 200, 200), font=font_sub)
    draw.text((100, 280), f"Мощность IP: {killer_data['IP']}", fill=(241, 196, 15), font=font_sub)

    # ПРАВАЯ СТОРОНА: ЖЕРТВА
    draw.text((1100, 80), "💀 ЖЕРТВА", fill=(231, 76, 60), font=font_header)
    draw.text((1100, 150), victim_data['Name'], fill=(255, 255, 255), font=font_title)
    draw.text((1100, 240), f"Гильдия: [{victim_data['Alliance']}] {victim_data['Guild']}", fill=(200, 200, 200), font=font_sub)
    draw.text((1100, 280), f"Мощность IP: {victim_data['IP']}", fill=(241, 196, 15), font=font_sub)

    # ЦЕНТР: ПЛАШКА "KILL"
    draw.rectangle([(840, 140), (1080, 250)], fill=(192, 57, 43), outline=(255, 255, 255), width=3)
    draw.text((900, 160), "KILL", fill=(255, 255, 255), font=font_header)

    # Сетка шмота убийцы (слева внизу)
    draw.text((100, 390), "ЭКИПИРОВКА УБИЙЦЫ:", fill=(46, 204, 113), font=font_header)
    await draw_equipment_grid(draw, img, killer_data["Equipment"], 100, 460, font_item)

    # Сетка шмота жертвы (справа внизу)
    draw.text((1100, 390), "ЭКИПИРОВКА ЖЕРТВЫ:", fill=(231, 76, 60), font=font_header)
    await draw_equipment_grid(draw, img, victim_data["Equipment"], 1100, 460, font_item)

    # НИЖНИЙ БАР: СТАТИСТИКА
    draw.line([(100, 1000), (1820, 1000)], fill=(254, 201, 47), width=3)
    draw.text((100, 1015), f"✨ ПОЛУЧЕНО PVP СЛАВЫ: {fame:,}", fill=(46, 204, 113), font=font_sub)
    
    final_buffer = BytesIO()
    img.save(final_buffer, format="PNG")
    final_buffer.seek(0)
    return final_buffer

# --- КОМАНДЫ ДЛЯ ДИСКОРДА ---

@bot.command(name="тест")
async def test_command(ctx):
    await ctx.send("✅ Бот онлайн и готов генерировать Full-HD карточки в стиле Albion Tools!")

@bot.command(name="канал")
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    await ctx.send(f"📍 Логи киллборда будут отправляться в этот канал: {ctx.channel.mention}!")

@bot.command(name="тест_килл")
@commands.has_permissions(administrator=True)
async def test_kill_command(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Пропиши сначала `!канал` в нужном чате.")
        return

    await ctx.send("🎨 Рисую тяжелую Full-HD карточку экипировки... Подожди пару секунд.")

    # Тестовые данные предметов (Т8.3 топоры, плащи, броня)
    fake_items = {
        "Head": {"Type": "T8_HEAD_PLATE_SET1@3"},
        "Armor": {"Type": "T8_ARMOR_PLATE_SET1@3"},
        "Shoes": {"Type": "T8_SHOES_PLATE_SET1@3"},
        "MainHand": {"Type": "T8_MAIN_AXE_KEEPER@3"},
        "Cape": {"Type": "T8_CAPE@3"},
        "Mount": {"Type": "T5_MOUNT_ARMORED_HORSE"},
        "Potion": {"Type": "T8_POTION_HEAL"},
        "Food": {"Type": "T8_FOOD_STEW"}
    }

    killer = {"Name": "DEDVARAG", "Guild": "x E C L I P S E x", "Alliance": "VITER", "IP": 1629, "Equipment": fake_items}
    victim = {"Name": "Odwaznik", "Guild": "Enemy Guild", "Alliance": "BAD", "IP": 1197, "Equipment": fake_items}

    img_buffer = await generate_hd_battle_sheet(killer, victim, 382552, is_kill=True)
    file = discord.File(fp=img_buffer, filename="kill_hd_sheet.png")
    await channel.send(file=file)

# --- АВТОМАТИЧЕСКИЙ МОНИТОРИНГ ЖИВЫХ КИЛЛОВ ---

@tasks.loop(seconds=30)
async def check_killboard():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: 
        return
    try:
        response = requests.get(f"{SERVER_URL}/events?limit=30&offset=0", timeout=10)
        if response.status_code != 200: 
            return
        events = response.json()
    except: 
        return

    for event in reversed(events):
        event_id = event.get("EventId")
        if not event_id or event_id in processed_events: 
            continue
        processed_events.add(event_id)
        if len(processed_events) > 300: 
            processed_events.pop()

        killer = event.get("Killer", {})
        victim = event.get("Victim", {})
        is_kill = killer.get("GuildId") == GUILD_ID
        is_death = victim.get("GuildId") == GUILD_ID

        if is_kill or is_death:
            k_data = {
                "Name": killer.get("Name", "Неизвестно"),
                "Guild": killer.get("GuildName") or "Без гильдии",
                "Alliance": killer.get("AllianceName") or "-",
                "IP": int(killer.get("AverageItemPower", 0)),
                "Equipment": killer.get("Equipment", {})
            }
            v_data = {
                "Name": victim.get("Name", "Неизвестно"),
                "Guild": victim.get("GuildName") or "Без гильдии",
                "Alliance": victim.get("AllianceName") or "-",
                "IP": int(victim.get("AverageItemPower", 0)),
                "Equipment": victim.get("Equipment", {})
            }

            img_buffer = await generate_hd_battle_sheet(k_data, v_data, event.get("TotalVictimKillFame", 0), is_kill)
            file = discord.File(fp=img_buffer, filename=f"battle_{event_id}.png")
            try:
                await channel.send(file=file)
            except:
                pass
            await asyncio.sleep(1)

threading.Thread(target=run_web_server, daemon=True).start()
bot.run(TOKEN)
