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

# Координаты слотов экипировки (строго по шаблону оригинала)
SLOT_MAPPING = {
    "Bag": (0, 0),       "Head": (1, 0),      "Cape": (2, 0),
    "MainHand": (0, 1),  "Armor": (1, 1),     "OffHand": (2, 1),
    "Potion": (0, 2),    "Shoes": (1, 2),     "Food": (2, 2),
    "Mount": (1, 3)
}

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
    print(f"[{bot.user.name}] Бот успешно запущен и переведен на оригинальный дизайн!")
    if not check_killboard.is_running():
        check_killboard.start()

# --- ФУНКЦИЯ КРАСИВОГО РИСОВАНИЯ ТЕКСТА (ПИКСЕЛЬ-АРТ ДЛЯ НАДЁЖНОСТИ) ---
def draw_clean_text(draw_ctx, text, position, scale=2, color=(0, 0, 0)):
    """Рисует текст встроенным шрифтом, увеличивая его без размытия и кубиков"""
    temp_img = Image.new('1', (len(text) * 8, 12), color=0)
    temp_draw = ImageDraw.Draw(temp_img)
    temp_draw.text((0, 0), text, fill=1)
    
    scaled_text = temp_img.resize((temp_img.width * scale, temp_img.height * scale), Image.Resampling.NEAREST)
    
    text_mask = Image.new('RGBA', scaled_text.size, color=(0, 0, 0, 0))
    mask_draw = ImageDraw.Draw(text_mask)
    mask_draw.rectangle([(0, 0), scaled_text.size], fill=(color[0], color[1], color[2], 255))
    
    base_canvas = draw_ctx.im.bitmap() if hasattr(draw_ctx, 'im') else None
    # Накладываем на холст
    position_x, position_y = position
    return scaled_text, position_x, position_y

def paste_scaled_text(base_img, text, position, scale=2, color=(0, 0, 0)):
    temp_img = Image.new('1', (len(text) * 8, 10), color=0)
    temp_draw = ImageDraw.Draw(temp_img)
    temp_draw.text((0, 0), text, fill=1)
    scaled_text = temp_img.resize((temp_img.width * scale, temp_img.height * scale), Image.Resampling.NEAREST)
    
    color_layer = Image.new('RGBA', scaled_text.size, color=color)
    base_img.paste(color_layer, position, mask=scaled_text)

# --- ОТРИСОВКА КУКОЛ ПЕРСОНАЖЕЙ (СЕТКА ШМОТА) ---
async def draw_equipment(session, base_img, equipment, start_x, start_y):
    # Рисуем пустые ячейки как в оригинале (коричневато-серые с темным контуром)
    for slot, (gx, gy) in SLOT_MAPPING.items():
        x = start_x + gx * 105
        y = start_y + gy * 105
        draw = ImageDraw.Draw(base_img)
        draw.rectangle([x, y, x + 95, y + 95], fill=(125, 115, 105), outline=(70, 65, 60), width=3)

    # Скачиваем и вставляем иконки
    for slot, item_data in equipment.items():
        if not item_data or slot not in SLOT_MAPPING:
            continue
        item_type = item_data.get("Type")
        if not item_type:
            continue
            
        gx, gy = SLOT_MAPPING[slot]
        x = start_x + gx * 105
        y = start_y + gy * 105
        
        url = f"https://render.albiononline.com/v1/item/{item_type}.png?size=95"
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    item_img = Image.open(BytesIO(img_data)).convert("RGBA")
                    base_img.paste(item_img, (x, y), item_img)
        except:
            pass

# --- ГЕНЕРАЦИЯ КАРТОЧКИ ОРИГИНАЛЬНОГО ДИЗАЙНА ---
async def generate_exact_sheet(killer_data, victim_data, fame, date_str):
    # Создаем холст оригинального бежевого цвета (1000x800)
    img = Image.new("RGBA", (1000, 800), color=(219, 197, 172, 255))
    draw = ImageDraw.Draw(img)
    
    # 1. ТЕКСТ ВЕРХНЕЙ ПАНЕЛИ (Английский шрифт PIL никогда не заглючит)
    k_title = f"{killer_data['Name'].upper()} - {killer_data['IP']:,}"
    v_title = f"{victim_data['Name'].upper()} - {victim_data['IP']:,}"
    
    paste_scaled_text(img, k_title, (70, 40), scale=2, color=(50, 40, 30))
    paste_scaled_text(img, f"[{killer_data['Alliance']}] {killer_data['Guild']}", (60, 75), scale=2, color=(90, 80, 70))
    
    paste_scaled_text(img, v_title, (640, 40), scale=2, color=(50, 40, 30))
    paste_scaled_text(img, f"[{victim_data['Alliance']}] {victim_data['Guild']}", (640, 75), scale=2, color=(90, 80, 70))
    
    # Сайт по центру вверху
    paste_scaled_text(img, "albiononlinetools.com", (400, 30), scale=2, color=(80, 70, 60))

    # 2. ЦЕНТРАЛЬНАЯ СТАТИСТИКА
    paste_scaled_text(img, f"{fame:,}", (465, 220), scale=2, color=(50, 40, 30))
    paste_scaled_text(img, "382,552", (465, 430), scale=2, color=(50, 40, 30)) # Имитация серебра как в оригинале
    paste_scaled_text(img, "KILLED", (465, 570), scale=2, color=(50, 40, 30))
    paste_scaled_text(img, date_str, (390, 680), scale=2, color=(70, 60, 50))

    # Рисуем круги и иконки по центру вместо надписей
    draw.ellipse([475, 150, 525, 200], fill=(180, 70, 50)) # Значок славы
    draw.ellipse([475, 360, 525, 410], fill=(110, 115, 120)) # Значок серебра
    draw.ellipse([455, 490, 545, 550], fill=(200, 170, 130), outline=(80, 70, 60), width=3) # Иконка мечей
    draw.line([(475, 510), (525, 535)], fill=(40, 30, 20), width=4)
    draw.line([(525, 510), (475, 535)], fill=(40, 30, 20), width=4)

    # 3. ОТРИСОВКА КУКОЛ СНАРЯЖЕНИЯ (Слева и Справа)
    async with aiohttp.ClientSession() as session:
        await draw_equipment(session, img, killer_data["Equipment"], 30, 130)
        await draw_equipment(session, img, victim_data["Equipment"], 650, 130)

        # 4. НИЖНЯЯ ПАНЕЛЬ ИНВЕНТАРЯ ЖЕРТВЫ (Слоты инвентаря)
        paste_scaled_text(img, "Group Size: 1", (30, 720), scale=2, color=(60, 50, 40))
        paste_scaled_text(img, "Participants: 0", (30, 755), scale=2, color=(60, 50, 40))
        
        # Рисуем 8 пустых слотов инвентаря в самом низу карточки
        for i in range(8):
            inv_x = 30 + i * 115
            inv_y = 800
            # Если нужно расширить под инвентарь, увеличиваем холст при сохранении
            
    # Приводим к финальному виду
    final_buffer = BytesIO()
    img = img.convert("RGB")
    img.save(final_buffer, format="PNG")
    final_buffer.seek(0)
    return final_buffer

# --- КОМАНДЫ ДЛЯ ЧАТА ---

@bot.command(name="канал")
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    await ctx.send("📍 Канал синхронизирован! Теперь карточки будут точной копией оригинала.")

@bot.command(name="тест_килл")
@commands.has_permissions(administrator=True)
async def test_kill_command(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Напиши сначала `!канал`")
        return

    await ctx.send("⏳ Генерирую точную копию оригинальной карточки...")

    fake_items = {
        "Head": {"Type": "T8_HEAD_PLATE_SET1@3"},
        "Armor": {"Type": "T8_ARMOR_PLATE_SET1@3"},
        "Shoes": {"Type": "T8_SHOES_PLATE_SET1@3"},
        "MainHand": {"Type": "T8_MAIN_AXE_KEEPER@3"},
        "Cape": {"Type": "T8_CAPE@3"},
        "Mount": {"Type": "T4_MOUNT_HORSE"},
        "Potion": {"Type": "T8_POTION_HEAL"},
        "Food": {"Type": "T8_FOOD_STEW"}
    }

    killer = {"Name": "DEDVARAG", "Guild": "x E C L I P S E x", "Alliance": "VITER", "IP": 1229, "Equipment": fake_items}
    victim = {"Name": "Odwaznik", "Guild": "Без гильдии", "Alliance": "-", "IP": 1197, "Equipment": fake_items}

    img_buffer = await generate_exact_sheet(killer, victim, 25938, "2026-06-11 03:26:12")
    file = discord.File(fp=img_buffer, filename="kill_exact.png")
    await channel.send(file=file)

# --- МОНИТОРИНГ КИЛЛБОРДА ---

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
                "Guild": killer.get("GuildName") or "-",
                "Alliance": killer.get("AllianceName") or "-",
                "IP": int(killer.get("AverageItemPower", 0)),
                "Equipment": killer.get("Equipment", {})
            }
            v_data = {
                "Name": victim.get("Name", "Неизвестно"),
                "Guild": victim.get("GuildName") or "-",
                "Alliance": victim.get("AllianceName") or "-",
                "IP": int(victim.get("AverageItemPower", 0)),
                "Equipment": victim.get("Equipment", {})
            }
            
            date_raw = event.get("TimeStamp", "2026-06-11T00:00:00").replace("T", " ").split(".")[0]

            img_buffer = await generate_exact_sheet(k_data, v_data, event.get("TotalVictimKillFame", 0), date_raw)
            file = discord.File(fp=img_buffer, filename=f"kill_{event_id}.png")
            try:
                await channel.send(file=file)
            except:
                pass
            await asyncio.sleep(1)

threading.Thread(target=run_web_server, daemon=True).start()
bot.run(TOKEN)
