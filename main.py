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

# Путь, куда скачаем шрифт для поддержки кириллицы и нормальных размеров
FONT_FILE = "Arial-Bold.ttf"

def load_system_font(size):
    """Надёжно скачивает и загружает шрифт, который не превратится в квадраты"""
    if not os.path.exists(FONT_FILE):
        try:
            # Прямая ссылка на проверенный шрифт TrueType с поддержкой RU/EN
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Medium.ttf"
            res = requests.get(url, timeout=10)
            with open(FONT_FILE, "wb") as f:
                f.write(res.content)
            print("[Шрифт] Успешно загружен и готов к работе!")
        except Exception as e:
            print(f"[Шрифт] Ошибка скачивания: {e}")
            return ImageFont.load_default()
            
    try:
        return ImageFont.truetype(FONT_FILE, size)
    except:
        return ImageFont.load_default()

# Координаты куклы персонажа (3х4 ячейки с шагом 105px)
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
    # Прогревочный запуск скачивания шрифта
    load_system_font(14)
    print(f"[{bot.user.name}] Бот запущен. Дизайн полностью скопирован с Albion Tools!")
    if not check_killboard.is_running():
        check_killboard.start()

def parse_item_tier(item_type):
    """Вытаскивает из технического названия (напр. T8_ARMOR_PLATE_SET1@3) Тир и Чары"""
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

# --- РИСОВАНИЕ СЕТКИ ПРЕДМЕТОВ ---
async def draw_equipment_grid(session, base_img, equipment, start_x, start_y, font_meta):
    draw = ImageDraw.Draw(base_img)
    for slot, (gx, gy) in SLOT_MAPPING.items():
        x = start_x + gx * 105
        y = start_y + gy * 105
        # Оригинальная текстура пустых слотов: серо-коричневый цвет с темной обводкой
        draw.rectangle([x, y, x + 95, y + 95], fill=(132, 120, 108), outline=(85, 75, 65), width=2)

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
                    
                    # Рисуем тир (например, VIII.3) в левом верхнем углу ячейки
                    tier_text = parse_item_tier(item_type)
                    if tier_text:
                        draw.text((x + 6, y + 6), tier_text, fill=(255, 200, 50), font=font_meta)
        except:
            pass

# --- ОСНОВНОЙ РЕНДЕР КАРТОЧКИ ---
async def generate_exact_albion_tools_sheet(killer_data, victim_data, fame, date_str, inventory_list):
    # Размер холста увеличен в высоту (1000x950), чтобы влез инвентарь снизу
    img = Image.new("RGBA", (1000, 950), color=(219, 197, 172, 255))
    draw = ImageDraw.Draw(img)
    
    # Подгружаем шрифты разных размеров
    font_bold = load_system_font(20)
    font_sub = load_system_font(16)
    font_center = load_system_font(18)
    font_meta = load_system_font(13)

    # 1. СТРОКИ ИГРОКОВ (ВЕРХ)
    # Убийца
    draw.text((30, 40), f"{killer_data['Name'].upper()} - {killer_data['IP']:,}", fill=(40, 30, 20), font=font_bold)
    draw.text((30, 70), f"[{killer_data['Alliance']}] {killer_data['Guild']}", fill=(80, 70, 60), font=font_sub)
    
    # Жертва
    draw.text((660, 40), f"{victim_data['Name'].upper()} - {victim_data['IP']:,}", fill=(40, 30, 20), font=font_bold)
    draw.text((660, 70), f"[{victim_data['Alliance']}] {victim_data['Guild']}", fill=(80, 70, 60), font=font_sub)
    
    # Водяной знак по центру
    draw.text((410, 25), "albiononlinetools.com", fill=(100, 90, 80), font=font_sub)

    # 2. ЦЕНТРАЛЬНЫЙ БЛОК (СЛАВА, СЕРЕБРО, КНОПКА КИЛЛ)
    # Иконка славы (Красная лента/круг)
    draw.ellipse([480, 140, 520, 180], fill=(160, 50, 40))
    draw.text((465, 195), f"{fame:,}", fill=(40, 30, 20), font=font_center)
    
    # Иконка серебра (Серый мешок/круг)
    draw.ellipse([480, 340, 520, 380], fill=(100, 105, 110))
    draw.text((465, 395), "382,552", fill=(40, 30, 20), font=font_center)
    
    # Скрещенные мечи и кнопка KILLED
    draw.ellipse([450, 470, 550, 530], fill=(210, 185, 150), outline=(80, 70, 60), width=2)
    draw.line([(475, 485), (525, 515)], fill=(50, 40, 30), width=4)
    draw.line([(525, 485), (475, 515)], fill=(50, 40, 30), width=4)
    
    # Плашка КИЛЛЕД
    draw.rectangle([(455, 545), (545, 575)], fill=(200, 180, 150), outline=(80, 70, 60))
    draw.text((472, 550), "KILLED", fill=(40, 30, 20), font=font_meta)
    
    # Дата внизу центрального блока
    draw.text((395, 660), date_str, fill=(80, 70, 60), font=font_sub)

    # 3. ОТРИСОВКА КУКОЛ ЭКИПИРОВКИ
    async with aiohttp.ClientSession() as session:
        await draw_equipment_grid(session, img, killer_data["Equipment"], 30, 120, font_meta)
        await draw_equipment_grid(session, img, victim_data["Equipment"], 660, 120, font_meta)

        # 4. НИЖНЯЯ ЧАСТЬ: ИНВЕНТАРЬ (СТРОГО КАК НА СКРИНШОТЕ ОРИГИНАЛА)
        draw.text((30, 720), "Group Size: 1", fill=(60, 55, 50), font=font_sub)
        draw.text((30, 750), "Participants: 0", fill=(60, 55, 50), font=font_sub)
        
        # Отрисовка ячеек инвентаря (9 штук в ряд, как на картинке)
        inv_start_x = 30
        inv_start_y = 800
        
        for i in range(9):
            x = inv_start_x + i * 105
            draw.rectangle([x, inv_start_y, x + 95, inv_start_y + 95], fill=(195, 175, 150), outline=(140, 125, 110), width=2)
            
            # Если у жертвы есть реальные вещи в инвентаре — вставляем их
            if i < len(inventory_list) and inventory_list[i]:
                item_type = inventory_list[i].get("Type")
                count = inventory_list[i].get("Count", 1)
                
                url = f"https://render.albiononline.com/v1/item/{item_type}.png?size=95"
                try:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            inv_img = Image.open(BytesIO(img_data)).convert("RGBA")
                            img.paste(inv_img, (x, inv_start_y), inv_img)
                            
                            if count > 1:
                                draw.text((x + 70, inv_start_y + 70), str(count), fill=(255, 255, 255), font=font_meta)
                except:
                    pass

    # Финализация
    final_buffer = BytesIO()
    img = img.convert("RGB")
    img.save(final_buffer, format="PNG")
    final_buffer.seek(0)
    return final_buffer

# --- КОМАНДЫ ДЛЯ ЧАТА ДИСКОРДА ---

@bot.command(name="гильдия")
async def guild_info_command(ctx):
    """Выводит подробную информацию о гильдии, за которой следит бот"""
    await ctx.send("🔍 Запрашиваю актуальные данные о гильдии с серверов Albion Online...")
    url = f"https://gameinfo-ams.albiononline.com/api/gameinfo/guilds/{GUILD_ID}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            await ctx.send(f"❌ Не удалось связаться с API игры (Код: {response.status_code}).")
            return
            
        data = response.json()
        g_name = data.get("Name", "x E C L I P S E x")
        g_founder = data.get("FounderName", "Bogdan")
        g_alliance = data.get("AllianceName") or "Нет альянса"
        g_alliance_tag = f"[{data.get('AllianceTag')}]" if data.get('AllianceTag') else ""
        g_members = data.get("MemberCount", 0)
        g_fame = data.get("killFame", 0)
        
        info_message = (
            f"🛡️ **МОНИТОРИНГ ГИЛЬДИИ АКТИВЕН** 🛡️\n"
            f"----------------------------------------\n"
            f" Название: **{g_name}**\n"
            f" Альянс: **{g_alliance_tag} {g_alliance}**\n"
            f" Guild Master / Основатель: **{g_founder}**\n"
            f" Количество бойцов: **{g_members} чел.**\n"
            f" Всего PvP Славы (Kill Fame): **{g_fame:,}**\n"
            f"----------------------------------------\n"
            f"🤖 *Бот автоматически сканирует киллборд на предмет убийств и смертей этого состава.*"
        )
        await ctx.send(info_message)
    except Exception as e:
        await ctx.send(f"❌ Ошибка при разборе данных гильдии: {str(e)}")

@bot.command(name="канал")
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    await ctx.send("📍 Канал привязан! Дизайн Albion Tools активирован.")

@bot.command(name="тест_килл")
@commands.has_permissions(administrator=True)
async def test_kill_command(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Напиши сначала `!канал`")
        return

    await ctx.send("⏳ Создаю точную копию оригинального шаблона со шрифтами...")

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
    
    fake_inventory = [
        {"Type": "T4_BOOK", "Count": 2},
    ]

    killer = {"Name": "DEDVARAG", "Guild": "x E C L I P S E x", "Alliance": "VITER", "IP": 1229, "Equipment": fake_items}
    victim = {"Name": "Odwaznik", "Guild": "Без гильдии", "Alliance": "-", "IP": 1197, "Equipment": fake_items}

    img_buffer = await generate_exact_albion_tools_sheet(killer, victim, 25938, "2026-06-11 03:26:12", fake_inventory)
    file = discord.File(fp=img_buffer, filename="kill_exact.png")
    await channel.send(file=file)

# --- ФОНОВОЙ МОНИТОРИНГ ЖИВЫХ СОБЫТИЙ ---

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
            inventory = [item for item in victim.get("Inventory", []) if item]

            img_buffer = await generate_exact_albion_tools_sheet(k_data, v_data, event.get("TotalVictimKillFame", 0), date_raw, inventory)
            file = discord.File(fp=img_buffer, filename=f"kill_{event_id}.png")
            try:
                await channel.send(file=file)
            except:
                pass
            await asyncio.sleep(1)

threading.Thread(target=run_web_server, daemon=True).start()
bot.run(TOKEN)
