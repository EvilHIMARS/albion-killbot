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

# Функция для скачивания нормального шрифта с поддержкой русского языка
def download_font():
    if not os.path.exists(FONT_PATH):
        try:
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
            response = requests.get(url, timeout=10)
            with open(FONT_PATH, "wb") as f:
                f.write(response.content)
            print("[Шрифты] Красивый шрифт успешно загружен!")
        except Exception as e:
            print(f"[Ошибка шрифта] Не удалось скачать шрифт: {e}")

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
    print(f"[{bot.user.name}] Бот успешно запущен и готов рисовать вертикальные карточки!")
    if not check_killboard.is_running():
        check_killboard.start()

# --- ВЕРТИКАЛЬНОЕ РИСОВАНИЕ КАРТОЧКИ ---
async def generate_kill_image(killer_name, killer_guild, killer_ip, victim_name, victim_guild, victim_ip, fame, weapon_type, is_kill):
    # Создаем вертикальный темный шаблон (ширина 400, высота 450)
    bg_color = (22, 28, 24) if is_kill else (34, 22, 22)
    img = Image.new("RGB", (400, 450), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Рамка карточки
    border_color = (46, 204, 113) if is_kill else (231, 76, 60)
    draw.rectangle([(0, 0), (399, 449)], outline=border_color, width=5)
    
    # Подключаем скачанный шрифт разных размеров
    try:
        font_main = ImageFont.truetype(FONT_PATH, 16)
        font_sub = ImageFont.truetype(FONT_PATH, 14)
        font_fame = ImageFont.truetype(FONT_PATH, 18)
    except:
        font_main = font_sub = font_fame = None # Если что-то пойдет не так, откатится на дефолт

    # 1. Скачиваем и рисуем иконку оружия в самом верху по центру
    if weapon_type:
        url = f"https://render.albiononline.com/v1/item/{weapon_type}.png?size=120"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        item_data = await resp.read()
                        item_img = Image.open(BytesIO(item_data)).convert("RGBA")
                        img.paste(item_img, (140, 20), item_img)
        except:
            pass

    # 2. Блок УБИЙЦЫ (Текст по центру)
    draw.text((20, 160), "⚔️ УБИЙЦА", fill=(46, 204, 113), font=font_main)
    draw.text((20, 185), f"Ник: {killer_name}", fill=(255, 255, 255), font=font_sub)
    draw.text((20, 205), f"Гильдия: {killer_guild}", fill=(180, 180, 180), font=font_sub)
    draw.text((20, 225), f"IP: {killer_ip}", fill=(241, 196, 15), font=font_sub)

    # Разделительная линия
    draw.line([(20, 260), (380, 260)], fill=(60, 60, 60), width=1)

    # 3. Блок ЖЕРТВЫ
    draw.text((20, 280), "💀 ЖЕРТВА", fill=(231, 76, 60), font=font_main)
    draw.text((20, 305), f"Ник: {victim_name}", fill=(255, 255, 255), font=font_sub)
    draw.text((20, 325), f"Гильдия: {victim_guild}", fill=(180, 180, 180), font=font_sub)
    draw.text((20, 345), f"IP: {victim_ip}", fill=(241, 196, 15), font=font_sub)

    # Разделительная линия
    draw.line([(20, 380), (380, 380)], fill=(60, 60, 60), width=1)

    # 4. Блок СЛАВЫ (В самом низу)
    draw.text((20, 400), f"🔥 PvP Слава: {fame:,}", fill=(254, 201, 47), font=font_fame)
            
    final_buffer = BytesIO()
    img.save(final_buffer, format="PNG")
    final_buffer.seek(0)
    return final_buffer

# --- КОМАНДЫ ДЛЯ ЧАТА ---

@bot.command(name="тест")
async def test_command(ctx):
    await ctx.send(f"✅ Бот онлайн и готов генерировать вертикальные карточки!")

@bot.command(name="канал")
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global CHANNEL_ID
    CHANNEL_ID = ctx.channel.id
    await ctx.send(f"📍 Канал для картинок киллборда изменен на {ctx.channel.mention}!")

@bot.command(name="тест_килл")
@commands.has_permissions(administrator=True)
async def test_kill_command(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Сначала укажи канал командой `!канал`")
        return

    await ctx.send("🎨 Рисую новую вертикальную карточку...")
    
    img_buffer = await generate_kill_image(
        killer_name="GvG_Monster", killer_guild="Toxic Players", killer_ip=1620,
        victim_name=ctx.author.name, victim_guild="x E C L I P S E x", victim_ip=1430,
        fame=350000, weapon_type="T8_MAIN_AXE_KEEPER@3", is_kill=False
    )
    
    file = discord.File(fp=img_buffer, filename="kill_event.png")
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
            weapon = killer.get("Equipment", {}).get("MainHand", {}).get("Type")
            
            img_buffer = await generate_kill_image(
                killer_name=killer.get("Name", "Неизвестно"),
                killer_guild=killer.get("GuildName") or "Без гильдии",
                killer_ip=int(killer.get("AverageItemPower", 0)),
                victim_name=victim.get("Name", "Неизвестно"),
                victim_guild=victim.get("GuildName") or "Без гильдии",
                victim_ip=int(victim.get("AverageItemPower", 0)),
                fame=event.get("TotalVictimKillFame", 0),
                weapon_type=weapon,
                is_kill=is_kill
            )
            
            file = discord.File(fp=img_buffer, filename=f"kill_{event_id}.png")
            try:
                await channel.send(file=file)
            except:
                pass
            await asyncio.sleep(1)

threading.Thread(target=run_web_server, daemon=True).start()
bot.run(TOKEN)
