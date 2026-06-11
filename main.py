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

# Слоты экипировки и их координаты на локальной сетке 3х4 (шаг 70px)
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
            print("[Шрифты] Шрифт загружен успешно!")
        except Exception as e:
            print(f"[Ошибка шрифта] Загрузка не удалась: {e}")

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
    print(f"[{bot.user.name}] Бот успешно запущен и готов генерировать боевые карточки шмота!")
    if not check_killboard.is_running():
        check_killboard.start()

# --- ФУНКЦИЯ СКАЧИВАНИЯ И ОТРИСОВКИ СЕТКИ ПРЕДМЕТОВ ---
async def draw_equipment_grid(draw_ctx, base_img, equipment_dict, start_x, start_y):
    # Рисуем пустые заглушки под шмот (квадраты со скруглением или просто рамки)
    for slot, (grid_x, grid_y) in SLOT_MAPPING.items():
        x = start_x + grid_x * 75
        y = start_y + grid_y * 75
        draw_ctx.rectangle([x, y, x + 65, y + 65], fill=(35, 35, 35), outline=(50, 50, 50), width=1)

    # Скачиваем и накладываем реальные иконки шмота
    async with aiohttp.ClientSession() as session:
        for slot, item_data in equipment_dict.items():
            if not item_data or slot not in SLOT_MAPPING:
                continue
            item_type = item_data.get("Type")
            if not item_type:
                continue
                
            grid_x, grid_y = SLOT_MAPPING[slot]
            x = start_x + grid_x * 75
            y = start_y + grid_y * 75
            
            url = f"https://render.albiononline.com/v1/item/{item_type}.png?size=65"
            try:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        item_img = Image.open(BytesIO(img_data)).convert("RGBA")
                        base_img.paste(item_img, (x, y), item_img)
            except:
                pass

# --- ГЕНЕРАЦИЯ ПОЛНОРАЗМЕРНОЙ КАРТИНКИ (СТИЛЬ ALBION TOOLS) ---
async def generate_battle_sheet(killer_data, victim_data, fame, is_kill):
    # Большое горизонтальное полотно (ширина 780, высота 380)
    bg_color = (24, 28, 25) if is_kill else (34, 24, 24)
    img = Image.new("RGB", (780, 380), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Цветная рамка исхода боя
    border_color = (46, 204, 113) if is_kill else (231, 76, 60)
    draw.rectangle([(0, 0), (779, 379)], outline=border_color, width=4)
    
    try:
        font_name = ImageFont.truetype(FONT_PATH, 16)
        font_guild = ImageFont.truetype(FONT_PATH, 14)
        font_center = ImageFont.truetype(FONT_PATH, 15)
    except:
        font_name = font_guild = font_center = None

    # ТЕКСТ СЛЕВА: УБИЙЦА
    draw.text((30, 20), f"⚔️ {killer_data['Name']}", fill=(46, 204, 113), font=font_name)
    draw.text((30, 42), f"[{killer_data['Alliance']}] {killer_data['Guild']}", fill=(200, 200, 200), font=font_guild)
    draw.text((30, 62), f"IP: {killer_data['IP']}", fill=(241, 196, 15), font=font_guild)
    
    # ТЕКСТ СПРАВА: ЖЕРТВА
    draw.text((530, 20), f"💀 {victim_data['Name']}", fill=(231, 76, 60), font=font_name)
    draw.text((530, 42), f"[{victim_data['Alliance']}] {victim_data['Guild']}", fill=(200, 200, 200), font=font_guild)
    draw.text((530, 62), f"IP: {victim_data['IP']}", fill=(241, 196, 15), font=font_guild)

    # ЦЕНТРАЛЬНЫЙ БЛОК (Слава и статус)
    draw.text((320, 150), "🔥 PvP СЛАВА", fill=(254, 201, 47), font=font_center)
    draw.text((330, 175), f"{fame:,}", fill=(255, 255, 255), font=font_name)
    
    status_text = "ИГРОК УБИТ" if is_kill else "ЧЛЕН ГИЛЬДИИ ПОГИБ"
    status_color = (46, 204, 113) if is_kill else (231, 76, 60)
    draw.text((310, 220), status_text, fill=status_color, font=font_center)

    # Отрисовка двух сеток инвентаря (Убийца x=30, Жертва x=530, y=90)
    await draw_equipment_grid(draw, img, killer_data["Equipment"], 30, 90)
    await draw_equipment_grid(draw, img, victim_data["Equipment"], 530, 90)
    
    final_buffer = BytesIO()
    img.save(final_buffer, format="PNG")
    final_buffer.seek(0)
    return final_buffer

# --- КОМАНДЫ ДЛЯ ЧАТА ---

@bot.command(name="тест")
async def test_command(ctx):
    await ctx.send("✅ Бот готов выводить фулл-сеты экипировки по образцу Albion Tools!")

@bot.command(name="канал")
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    await ctx.send(f"📍 Канал для логов боя изменен на {ctx.channel.mention}!")

@bot.command(name="тест_килл")
@commands.has_permissions(administrator=True)
async def test_kill_command(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Используй команду `!канал` в целевом чате.")
        return

    await ctx.send("🎨 Генерирую полноценный боевой лист со шмотом...")

    # Фейковый набор предметов для теста (Т8 топоры, броня, маунты)
    fake_equipment = {
        "Head": {"Type": "T8_HEAD_PLATE_SET1"},
        "Armor": {"Type": "T8_ARMOR_PLATE_SET1"},
        "Shoes": {"Type": "T8_SHOES_PLATE_SET1"},
        "MainHand": {"Type": "T8_MAIN_AXE_KEEPER@3"},
        "Cape": {"Type": "T8_CAPE"},
        "Mount": {"Type": "T4_MOUNT_HORSE"},
        "Potion": {"Type": "T8_POTION_HEAL"},
        "Food": {"Type": "T8_FOOD_STEW"}
    }

    killer = {"Name": "DEDVARAG", "Guild": "x E C L I P S E x", "Alliance": "VITER", "IP": 1629, "Equipment": fake_equipment}
    victim = {"Name": "Odwaznik", "Guild": "Без гильдии", "Alliance": "-", "IP": 1197, "Equipment": fake_equipment}

    img_buffer = await generate_battle_sheet(killer, victim, 25938, is_kill=True)
    file = discord.File(fp=img_buffer, filename="kill_sheet.png")
    await channel.send(file=file)

# --- ФОНОВЫЙ МОНИТОРИНГ ---

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

            img_buffer = await generate_battle_sheet(k_data, v_data, event.get("TotalVictimKillFame", 0), is_kill)
            file = discord.File(fp=img_buffer, filename=f"battle_{event_id}.png")
            try:
                await channel.send(file=file)
            except:
                pass
            await asyncio.sleep(1)

threading.Thread(target=run_web_server, daemon=True).start()
bot.run(TOKEN)
