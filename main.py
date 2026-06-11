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
from datetime import datetime

# ==================== НАСТРОЙКИ ====================
TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = 1488538529314246738         
GUILD_ID = "c7fgh-V2QTSYBJqKPpNtkg"      
SERVER_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo" 
# ===================================================

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)
processed_events = set()

# --- СТРУКТУРА ПАПОК И ШРИФТОВ ---
ASSETS_DIR = "assets"
FONT_BOLD = f"{ASSETS_DIR}/Roboto-Bold.ttf"
FONT_REGULAR = f"{ASSETS_DIR}/Roboto-Regular.ttf"

def setup_assets():
    """Создает папку assets и скачивает идеальные шрифты, если их нет"""
    if not os.path.exists(ASSETS_DIR):
        os.makedirs(ASSETS_DIR)
        
    fonts_to_download = {
        FONT_BOLD: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf",
        FONT_REGULAR: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
    }
    
    for path, url in fonts_to_download.items():
        if not os.path.exists(path):
            try:
                print(f"[Система] Скачиваю шрифт {path}...")
                res = requests.get(url, timeout=10)
                with open(path, "wb") as f:
                    f.write(res.content)
            except Exception as e:
                print(f"[Ошибка] Не удалось скачать {path}: {e}")

def get_font(font_type="regular", size=14):
    path = FONT_BOLD if font_type == "bold" else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")
    def log_message(self, format, *args):
        return

def run_web_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()

@bot.event
async def on_ready():
    setup_assets() # Подготавливаем файлы при старте
    print(f"[{bot.user.name}] Запущен! Использую идеальный темный английский шаблон.")
    if not check_killboard.is_running():
        check_killboard.start()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def parse_item_tier(item_type):
    if not item_type: return ""
    tier = ""
    for i in range(4, 9):
        if item_type.startswith(f"T{i}"):
            tier = f"T{i}"
            break
    enchant = ""
    if "@" in item_type:
        enchant = f".{item_type.split('@')[-1]}"
    return f"{tier}{enchant}"

SLOT_MAPPING = {
    "Bag": (0, 0),       "Head": (1, 0),      "Cape": (2, 0),
    "MainHand": (0, 1),  "Armor": (1, 1),     "OffHand": (2, 1),
    "Potion": (0, 2),    "Shoes": (1, 2),     "Food": (2, 2),
    "Mount": (1, 3)
}

async def draw_equipment_grid(session, draw, base_img, equipment, start_x, start_y):
    font_tier = get_font("bold", 14)
    # Цвета в стиле killboard-1.com
    slot_bg = (26, 28, 35, 255)       # Тёмный фон слота
    slot_outline = (55, 60, 75, 255)  # Серо-синяя обводка

    for slot, (gx, gy) in SLOT_MAPPING.items():
        x = start_x + gx * 110
        y = start_y + gy * 110
        draw.rectangle([x, y, x + 100, y + 100], fill=slot_bg, outline=slot_outline, width=1)

    for slot, item_data in equipment.items():
        if not item_data or slot not in SLOT_MAPPING: continue
        item_type = item_data.get("Type")
        if not item_type: continue
            
        gx, gy = SLOT_MAPPING[slot]
        x = start_x + gx * 110
        y = start_y + gy * 110
        
        url = f"https://render.albiononline.com/v1/item/{item_type}.png?size=100"
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    item_img = Image.open(BytesIO(img_data)).convert("RGBA")
                    base_img.paste(item_img, (x, y), item_img)
                    
                    tier_text = parse_item_tier(item_type)
                    if tier_text:
                        # Тень для текста, чтобы читалось идеально
                        draw.text((x + 7, y + 7), tier_text, fill=(0, 0, 0), font=font_tier)
                        draw.text((x + 5, y + 5), tier_text, fill=(234, 179, 8), font=font_tier) # Золотой
        except:
            pass

# --- ГЛАВНЫЙ ГЕНЕРАТОР КАРТОЧКИ ---
async def generate_pro_killboard_sheet(killer, victim, fame, timestamp, inventory):
    # Темный современный фон
    bg_color = (17, 18, 23, 255)
    panel_color = (26, 28, 35, 255)
    
    img = Image.new("RGBA", (1200, 900), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Шрифты
    f_name = get_font("bold", 32)
    f_guild = get_font("regular", 20)
    f_stats = get_font("bold", 22)
    f_title = get_font("bold", 40)
    f_sub = get_font("regular", 16)

    # 1. ПЛАШКИ ИГРОКОВ (Верхняя часть)
    draw.rectangle([40, 40, 560, 160], fill=panel_color, radius=10)
    draw.rectangle([640, 40, 1160, 160], fill=panel_color, radius=10)

    # Killer Info
    draw.text((60, 55), killer['Name'], fill=(255, 255, 255), font=f_name)
    k_guild_text = f"[{killer['Alliance']}] {killer['Guild']}" if killer['Alliance'] != "-" else killer['Guild']
    draw.text((60, 95), k_guild_text, fill=(160, 165, 181), font=f_guild)
    draw.text((60, 125), f"Item Power: {killer['IP']}", fill=(234, 179, 8), font=f_sub)

    # Victim Info
    draw.text((660, 55), victim['Name'], fill=(255, 255, 255), font=f_name)
    v_guild_text = f"[{victim['Alliance']}] {victim['Guild']}" if victim['Alliance'] != "-" else victim['Guild']
    draw.text((660, 95), v_guild_text, fill=(160, 165, 181), font=f_guild)
    draw.text((660, 125), f"Item Power: {victim['IP']}", fill=(234, 179, 8), font=f_sub)

    # 2. ЦЕНТРАЛЬНАЯ ИНФОРМАЦИЯ (Kill, Fame, Date)
    draw.text((565, 55), "VS", fill=(239, 68, 68), font=f_title)
    
    draw.rectangle([480, 200, 720, 350], fill=panel_color, radius=10)
    
    # Имитация плашки KILL
    draw.rectangle([520, 220, 680, 260], fill=(239, 68, 68, 255), radius=5)
    draw.text((565, 228), "KILLED", fill=(255, 255, 255), font=f_stats)
    
    # Fame & Time
    draw.text((510, 280), f"Kill Fame: {fame:,}", fill=(16, 185, 129), font=f_guild)
    # Форматируем дату в стиль '11 Jun 2026, 21:05'
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        date_str = dt.strftime("%d %b %Y, %H:%M")
    except:
        date_str = timestamp
    draw.text((510, 315), date_str, fill=(160, 165, 181), font=f_sub)

    # 3. ЭКИПИРОВКА (Куклы)
    async with aiohttp.ClientSession() as session:
        # Убийца
        draw.text((40, 190), "KILLER EQUIPMENT", fill=(160, 165, 181), font=f_sub)
        await draw_equipment_grid(session, draw, img, killer["Equipment"], 40, 220)
        
        # Жертва
        draw.text((640, 190), "VICTIM EQUIPMENT", fill=(160, 165, 181), font=f_sub)
        await draw_equipment_grid(session, draw, img, victim["Equipment"], 840, 220) # Смещено вправо

        # 4. ИНВЕНТАРЬ (Inventory)
        draw.text((40, 680), "VICTIM INVENTORY", fill=(160, 165, 181), font=f_sub)
        
        inv_start_x = 40
        inv_start_y = 710
        
        for i in range(10): # 10 ячеек в ряд
            x = inv_start_x + i * 110
            draw.rectangle([x, inv_start_y, x + 100, inv_start_y + 100], fill=panel_color, outline=(55, 60, 75, 255), width=1)
            
            if i < len(inventory) and inventory[i]:
                item_type = inventory[i].get("Type")
                count = inventory[i].get("Count", 1)
                
                url = f"https://render.albiononline.com/v1/item/{item_type}.png?size=100"
                try:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            inv_img = Image.open(BytesIO(img_data)).convert("RGBA")
                            img.paste(inv_img, (x, inv_start_y), inv_img)
                            
                            if count > 1:
                                draw.text((x + 70, inv_start_y + 75), str(count), fill=(255, 255, 255), font=get_font("bold", 16))
                except:
                    pass

    # Финализация
    final_buffer = BytesIO()
    img = img.convert("RGB")
    img.save(final_buffer, format="PNG", quality=95)
    final_buffer.seek(0)
    return final_buffer

# --- КОМАНДЫ ДИСКОРДА ---
@bot.command(name="гильдия")
async def guild_info_command(ctx):
    await ctx.send("🔍 Fetching guild data...")
    url = f"https://gameinfo-ams.albiononline.com/api/gameinfo/guilds/{GUILD_ID}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return
        data = response.json()
        
        info = (
            f"🛡️ **GUILD MONITORING ACTIVE** 🛡️\n"
            f"**Name:** {data.get('Name')}\n"
            f"**Alliance:** [{data.get('AllianceTag')}] {data.get('AllianceName')}\n"
            f"**Members:** {data.get('MemberCount')}\n"
            f"**Total Kill Fame:** {data.get('killFame'):,}"
        )
        await ctx.send(info)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="канал")
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    await ctx.send("📍 Channel set! Pro English Killboard design activated.")

@bot.command(name="тест_килл")
@commands.has_permissions(administrator=True)
async def test_kill_command(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Use `!канал` first.")
        return

    await ctx.send("⏳ Generating Pro English Killboard template...")

    # Фейковые вещи для теста
    fake_items = {
        "Head": {"Type": "T8_HEAD_CLOTH_SET1@3"},
        "Armor": {"Type": "T8_ARMOR_CLOTH_SET1@3"},
        "Shoes": {"Type": "T8_SHOES_CLOTH_SET1@3"},
        "MainHand": {"Type": "T8_MAIN_FIRESTAFF@3"},
        "Cape": {"Type": "T8_CAPE@3"},
        "Mount": {"Type": "T5_MOUNT_ARMORED_HORSE"},
        "Potion": {"Type": "T8_POTION_HEAL"},
        "Food": {"Type": "T8_FOOD_STEW"}
    }
    
    fake_inventory = [
        {"Type": "T4_RUNE", "Count": 99},
        {"Type": "T5_SOUL", "Count": 45},
    ]

    # Используем нейтральные ники для демонстрации дизайна
    killer = {"Name": "ShadowStriker", "Guild": "x E C L I P S E x", "Alliance": "VITER", "IP": 1450, "Equipment": fake_items}
    victim = {"Name": "FallenHero", "Guild": "Random Guild", "Alliance": "-", "IP": 1390, "Equipment": fake_items}

    img_buffer = await generate_pro_killboard_sheet(killer, victim, 145230, "2026-06-11 21:05:00", fake_inventory)
    file = discord.File(fp=img_buffer, filename="pro_killboard.png")
    await channel.send(file=file)

# --- ФОНОВЫЙ МОНИТОРИНГ ---
@tasks.loop(seconds=30)
async def check_killboard():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return
    try:
        response = requests.get(f"{SERVER_URL}/events?limit=30&offset=0", timeout=10)
        if response.status_code != 200: return
        events = response.json()
    except: return

    for event in reversed(events):
        event_id = event.get("EventId")
        if not event_id or event_id in processed_events: continue
        processed_events.add(event_id)
        if len(processed_events) > 300: processed_events.pop()

        killer = event.get("Killer", {})
        victim = event.get("Victim", {})
        is_kill = killer.get("GuildId") == GUILD_ID
        is_death = victim.get("GuildId") == GUILD_ID

        if is_kill or is_death:
            k_data = {
                "Name": killer.get("Name", "Unknown"),
                "Guild": killer.get("GuildName") or "-",
                "Alliance": killer.get("AllianceName") or "-",
                "IP": int(killer.get("AverageItemPower", 0)),
                "Equipment": killer.get("Equipment", {})
            }
            v_data = {
                "Name": victim.get("Name", "Unknown"),
                "Guild": victim.get("GuildName") or "-",
                "Alliance": victim.get("AllianceName") or "-",
                "IP": int(victim.get("AverageItemPower", 0)),
                "Equipment": victim.get("Equipment", {})
            }
            
            date_raw = event.get("TimeStamp", "2026-06-11T00:00:00").replace("T", " ").split(".")[0]
            inventory = [item for item in victim.get("Inventory", []) if item]

            img_buffer = await generate_pro_killboard_sheet(k_data, v_data, event.get("TotalVictimKillFame", 0), date_raw, inventory)
            file = discord.File(fp=img_buffer, filename=f"kill_{event_id}.png")
            try:
                await channel.send(file=file)
            except: pass
            await asyncio.sleep(1)

threading.Thread(target=run_web_server, daemon=True).start()
bot.run(TOKEN)
