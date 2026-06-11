import os
import asyncio
import discord
from discord.ext import tasks, commands
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ==================== НАСТРОЙКИ ====================
TOKEN = os.environ.get("DISCORD_TOKEN")  # Берем токен из скрытых настроек Render
CHANNEL_ID = 1488538529314246738         # ID твоего канала в Discord
GUILD_ID = "c7fgh-V2QTSYBJqKPpNtkg"      # ID твоей гильдии (x E C L I P S E x)
SERVER_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo" # Европа
# ===================================================

intents = discord.Intents.default()
intents.message_content = True  # Включаем чтение сообщений для корректной работы бота
bot = commands.Bot(command_prefix="!", intents=intents)
processed_events = set()

# Этот мини-веб-сервер нужен ТОЛЬКО для того, чтобы Render думал, что это сайт, и держал его онлайн бесплатно
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_web_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()

@bot.event
async def on_ready():
    print(f"[{bot.user.name}] Бот успешно запущен на Render и готов к работе!")
    check_killboard.start()

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
            color = discord.Color.green() if is_kill else discord.Color.red()
            title = f"⚔️ Килл! [{killer.get('Name')}] уничтожил цель!" if is_kill else f"💀 Смерть! Погиб [{victim.get('Name')}]"
            
            embed = discord.Embed(title=title, color=color, url=f"https://albiononline.com/killboard/kill/{event_id}")
            
            killer_ip = int(killer.get("AverageItemPower", 0))
            killer_alliance = f"[{killer.get('AllianceName')}] " if killer.get('AllianceName') else ""
            embed.add_field(name="👤 Убийца", value=f"**{killer.get('Name')}**\n{killer_alliance}{killer.get('GuildName') or 'Без гильдии'}\n🛑 IP: {killer_ip}", inline=True)
            
            victim_ip = int(victim.get("AverageItemPower", 0))
            victim_alliance = f"[{victim.get('AllianceName')}] " if victim.get('AllianceName') else ""
            embed.add_field(name="🎯 Жертва", value=f"**{victim.get('Name')}**\n{victim_alliance}{victim.get('GuildName') or 'Без гильдии'}\n🛑 IP: {victim_ip}", inline=True)
            
            fame = event.get("TotalVictimKillFame", 0)
            embed.add_field(name="✨ Получено PvP Славы", value=f"{fame:,}", inline=False)
            
            weapon = killer.get("Equipment", {}).get("MainHand", {}).get("Type")
            if weapon: 
                embed.set_thumbnail(url=f"https://render.albiononline.com/v1/item/{weapon}.png")
            
            await channel.send(embed=embed)
            await asyncio.sleep(1)

# Запуск веб-сервера в отдельном потоке для обхода ограничений Render
threading.Thread(target=run_web_server, daemon=True).start()

# Запуск самого Дискорд бота
bot.run(TOKEN)
