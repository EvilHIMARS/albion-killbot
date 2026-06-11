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

# --- ПАПКИ И ШРИФТЫ ---
ASSETS_DIR = "assets"
FONT_BOLD = f"{ASSETS_DIR}/Roboto-Bold.ttf"
FONT_REGULAR = f"{ASSETS_DIR}/Roboto-Regular.ttf"

def setup_assets():
    if not os.path.exists(ASSETS_DIR): os.makedirs(ASSETS_DIR)
    fonts = {
        FONT_BOLD: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf",
        FONT_REGULAR: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
    }
    for path, url in fonts.items():
        if not os.path.exists(path):
            try:
                res = requests.get(url, timeout=10)
                with open(path, "wb") as f: f.write(res.content)
            except: pass

def get_font(font_type="regular", size=14):
    try: return ImageFont.truetype(FONT_BOLD if font_type == "bold" else FONT_REGULAR, size)
    except: return ImageFont.load_default()

# --- УТИЛИТЫ ---
async def get_guild_logo(session, guild_id):
    url = f"https://render.albiononline.com/v1/guild/{guild_id}.png"
    try:
        async with session.get(url, timeout=3) as resp:
            if resp.status == 200:
                data = await resp.read()
                return Image.open(BytesIO(data)).convert("RGBA").resize((120, 120))
    except: return None

# --- ГЕНЕРАЦИЯ КАРТОЧЕК ---
async def draw_equipment_grid(session, draw, base_img, equipment, start_x, start_y):
    slot_bg = (26, 28, 35, 255)
    slot_outline = (55, 60, 75, 255)
    slots = ["Bag","Head","Cape","MainHand","Armor","OffHand","Potion","Shoes","Food","Mount"]
    layout = {"Bag":(0,0),"Head":(1,0),"Cape":(2,0),"MainHand":(0,1),"Armor":(1,1),"OffHand":(2,1),"Potion":(0,2),"Shoes":(1,2),"Food":(2,2),"Mount":(1,3)}
    
    for slot, (gx, gy) in layout.items():
        x, y = start_x + gx * 110, start_y + gy * 110
        draw.rounded_rectangle([x, y, x + 100, y + 100], radius=5, fill=slot_bg, outline=slot_outline, width=1)

    for slot, item_data in equipment.items():
        if slot not in layout: continue
        gx, gy = layout[slot]
        x, y = start_x + gx * 110, start_y + gy * 110
        url = f"https://render.albiononline.com/v1/item/{item_data.get('Type')}.png?size=100"
        try:
            async with session.get(url, timeout=3) as resp:
                if resp.status == 200:
                    img = Image.open(BytesIO(await resp.read())).convert("RGBA")
                    base_img.paste(img, (x, y), img)
        except: pass

async def generate_guild_card(data):
    img = Image.new("RGBA", (600, 300), color=(17, 18, 23, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([10, 10, 590, 290], radius=15, fill=(26, 28, 35, 255))
    
    async with aiohttp.ClientSession() as session:
        logo = await get_guild_logo(session, data.get('Id'))
        if logo: img.paste(logo, (30, 90), logo)
    
    draw.text((170, 40), data.get('Name', 'Guild'), fill=(255, 255, 255), font=get_font("bold", 30))
    draw.text((170, 80), f"Alliance: {data.get('AllianceName') or 'None'}", fill=(160, 165, 181), font=get_font("regular", 18))
    draw.text((170, 130), f"Members: {data.get('MemberCount', 0)}", fill=(234, 179, 8), font=get_font("bold", 20))
    draw.text((170, 160), f"Kill Fame: {data.get('killFame', 0):,}", fill=(16, 185, 129), font=get_font("bold", 20))
    
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf

async def generate_pro_killboard_sheet(killer, victim, fame, timestamp, inventory):
    img = Image.new("RGBA", (1200, 900), color=(17, 18, 23, 255))
    draw = ImageDraw.Draw(img)
    
    async with aiohttp.ClientSession() as session:
        k_logo = await get_guild_logo(session, killer.get("GuildId"))
        v_logo = await get_guild_logo(session, victim.get("GuildId"))
        
        draw.rounded_rectangle([40, 40, 560, 160], radius=10, fill=(26, 28, 35, 255))
        draw.rounded_rectangle([640, 40, 1160, 160], radius=10, fill=(26, 28, 35, 255))
        
        draw.text((120, 55), killer['Name'], fill=(255, 255, 255), font=get_font("bold", 32))
        draw.text((720, 55), victim['Name'], fill=(255, 255, 255), font=get_font("bold", 32))
        
        if k_logo: img.paste(k_logo, (50, 50), k_logo)
        if v_logo: img.paste(v_logo, (650, 50), v_logo)

        draw.rounded_rectangle([480, 200, 720, 350], radius=10, fill=(26, 28, 35, 255))
        draw.rounded_rectangle([520, 220, 680, 260], radius=5, fill=(239, 68, 68, 255))
        draw.text((565, 228), "KILLED", fill=(255, 255, 255), font=get_font("bold", 22))
        draw.text((510, 280), f"Fame: {fame:,}", fill=(16, 185, 129), font=get_font("regular", 20))
        
        await draw_equipment_grid(session, draw, img, killer["Equipment"], 40, 220)
        await draw_equipment_grid(session, draw, img, victim["Equipment"], 840, 220)

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf

# --- КОМАНДЫ ---
@bot.command(name="гильдия")
async def guild_info_card(ctx):
    url = f"{SERVER_URL}/guilds/{GUILD_ID}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            buf = await generate_guild_card(res.json())
            await ctx.send(file=discord.File(buf, "guild_info.png"))
        else:
            await ctx.send("❌ Не удалось получить данные гильдии.")
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

@bot.command(name="тест_килл")
async def test_kill(ctx):
    fake_items = {"MainHand": {"Type": "T8_MAIN_FIRESTAFF@3"}}
    k = {"Name": "Killer", "GuildId": GUILD_ID, "Equipment": fake_items}
    v = {"Name": "Victim", "GuildId": None, "Equipment": fake_items}
    buf = await generate_pro_killboard_sheet(k, v, 100000, "2026-06-11", [])
    await ctx.send(file=discord.File(buf, "kill.png"))

bot.run(TOKEN)
