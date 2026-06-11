"""
Professional image rendering for kill reports and guild cards
"""
import os
from io import BytesIO
from typing import Dict, Any
from PIL import Image, ImageDraw, ImageFont
from config import config
from cache_manager import cache
from logger import logger
import requests


class FontManager:
    """Manages fonts for rendering"""
    
    def __init__(self):
        self.fonts = {}
        self._setup_fonts()
    
    def _setup_fonts(self):
        """Download and setup fonts"""
        os.makedirs(config.ASSETS_DIR, exist_ok=True)
        
        font_urls = {
            "bold": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf",
            "regular": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf",
        }
        
        for font_type, url in font_urls.items():
            path = os.path.join(config.ASSETS_DIR, f"Roboto-{font_type.capitalize()}.ttf")
            if not os.path.exists(path):
                try:
                    resp = requests.get(url, timeout=10)
                    with open(path, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"Downloaded font: {font_type}")
                except Exception as e:
                    logger.warning(f"Failed to download font {font_type}: {e}")
    
    def get_font(self, style: str = "regular", size: int = 14) -> ImageFont.FreeTypeFont:
        """Get font instance"""
        key = f"{style}_{size}"
        
        if key in self.fonts:
            return self.fonts[key]
        
        font_name = "Roboto-Bold.ttf" if style == "bold" else "Roboto-Regular.ttf"
        font_path = os.path.join(config.ASSETS_DIR, font_name)
        
        try:
            font = ImageFont.truetype(font_path, size)
            self.fonts[key] = font
            return font
        except Exception as e:
            logger.warning(f"Failed to load font {font_name}: {e}, using default")
            return ImageFont.load_default()


class KillReportRenderer:
    """Renders professional kill reports like killboard-1.com"""
    
    # Color palette (dark theme)
    DARK_BG = (17, 18, 23, 255)
    CARD_BG = (26, 28, 35, 255)
    SLOT_BG = (35, 38, 45, 255)
    SLOT_OUTLINE = (55, 60, 75, 255)
    TEXT_PRIMARY = (255, 255, 255)
    TEXT_SECONDARY = (160, 165, 181)
    TEXT_GOLD = (234, 179, 8)
    ACCENT_RED = (239, 68, 68)
    ACCENT_GREEN = (16, 185, 129)
    
    EQUIPMENT_SLOTS = {
        "Bag": (0, 0),
        "Head": (1, 0),
        "Cape": (2, 0),
        "MainHand": (0, 1),
        "Armor": (1, 1),
        "OffHand": (2, 1),
        "Potion": (0, 2),
        "Shoes": (1, 2),
        "Food": (2, 2),
        "Mount": (1, 3),
    }
    
    def __init__(self):
        self.font_manager = FontManager()
    
    async def render_kill_report(self, killer: Dict[str, Any], victim: Dict[str, Any], fame: int, timestamp: str) -> BytesIO:
        """Render professional kill report"""
        img = Image.new("RGBA", (1600, 950), self.DARK_BG)
        draw = ImageDraw.Draw(img)
        
        try:
            # === TOP SECTION ===
            # Killer header
            draw.rectangle([40, 40, 700, 140], fill=self.CARD_BG, outline=self.ACCENT_GREEN, width=2)
            killer_font = self.font_manager.get_font("bold", 24)
            draw.text((60, 60), killer.get("Name", "Killer"), fill=self.TEXT_PRIMARY, font=killer_font)
            guild_font = self.font_manager.get_font("regular", 14)
            draw.text((60, 90), f"Guild: {killer.get('GuildName', 'No Guild')}", fill=self.TEXT_SECONDARY, font=guild_font)
            
            # Victim header
            draw.rectangle([900, 40, 1560, 140], fill=self.CARD_BG, outline=self.ACCENT_RED, width=2)
            victim_font = self.font_manager.get_font("bold", 24)
            draw.text((920, 60), victim.get("Name", "Victim"), fill=self.TEXT_PRIMARY, font=victim_font)
            draw.text((920, 90), f"Guild: {victim.get('GuildName', 'No Guild')}", fill=self.TEXT_SECONDARY, font=guild_font)
            
            # === CENTER SECTION (VS) ===
            vs_font = self.font_manager.get_font("bold", 60)
            draw.text((800, 80), "VS", fill=self.TEXT_SECONDARY, font=vs_font, anchor="mm")
            
            # === KILLED BADGE ===
            draw.rectangle([600, 180, 1000, 260], fill=(0, 0, 0, 0), outline=self.ACCENT_RED, width=3)
            killed_font = self.font_manager.get_font("bold", 24)
            draw.text((800, 200), "⚔️ KILLED ⚔️", fill=self.ACCENT_RED, font=killed_font, anchor="mm")
            fame_font = self.font_manager.get_font("bold", 20)
            draw.text((800, 235), f"💰 Fame: {fame:,}", fill=self.ACCENT_GREEN, font=fame_font, anchor="mm")
            
            # === EQUIPMENT GRIDS ===
            # Killer equipment
            await self._draw_equipment_grid(draw, img, killer.get("Equipment", {}), 40, 300)
            
            # Victim equipment
            await self._draw_equipment_grid(draw, img, victim.get("Equipment", {}), 900, 300)
            
            # === BOTTOM INFO ===
            info_font = self.font_manager.get_font("regular", 14)
            draw.text((800, 910), f"📅 {timestamp}", fill=self.TEXT_SECONDARY, font=info_font, anchor="mm")
            
            return self._save_to_buffer(img)
            
        except Exception as e:
            logger.error(f"Failed to render kill report: {e}")
            raise
    
    async def _draw_equipment_grid(self, draw: ImageDraw.ImageDraw, img: Image.Image, equipment: Dict[str, Any], start_x: int, start_y: int):
        """Draw equipment grid"""
        slot_size = 90
        slot_spacing = 110
        
        # Draw slot backgrounds
        for slot_name, (gx, gy) in self.EQUIPMENT_SLOTS.items():
            x = start_x + gx * slot_spacing
            y = start_y + gy * slot_spacing
            
            # Slot background
            draw.rounded_rectangle([x, y, x + slot_size, y + slot_size], radius=8, fill=self.SLOT_BG, outline=self.SLOT_OUTLINE, width=2)
        
        # Draw items
        for slot_name, item_data in equipment.items():
            if slot_name not in self.EQUIPMENT_SLOTS:
                continue
            
            gx, gy = self.EQUIPMENT_SLOTS[slot_name]
            x = start_x + gx * slot_spacing
            y = start_y + gy * slot_spacing
            
            item_type = item_data.get("Type", "")
            if not item_type:
                continue
            
            item_url = f"https://render.albiononline.com/v1/item/{item_type}.png?size=90"
            item_data_bytes = await cache.get_image(item_url)
            
            if item_data_bytes:
                try:
                    item_img = Image.open(BytesIO(item_data_bytes)).convert("RGBA")
                    img.paste(item_img, (x, y), item_img)
                    
                    # Add frame around item
                    draw.rounded_rectangle([x, y, x + slot_size, y + slot_size], radius=8, outline=self.TEXT_GOLD, width=2)
                except Exception as e:
                    logger.warning(f"Failed to load item image {item_type}: {e}")
    
    async def render_guild_card(self, guild: Dict[str, Any]) -> BytesIO:
        """Render guild information card"""
        img = Image.new("RGBA", (900, 450), self.DARK_BG)
        draw = ImageDraw.Draw(img)
        
        try:
            # Background card
            draw.rounded_rectangle([30, 30, 870, 420], radius=20, fill=self.CARD_BG, outline=self.ACCENT_GREEN, width=3)
            
            # Logo
            if guild.get("Id"):
                try:
                    logo_data = await cache.get_image(f"https://render.albiononline.com/v1/guild/{guild['Id']}.png")
                    if logo_data:
                        logo = Image.open(BytesIO(logo_data)).convert("RGBA").resize((120, 120))
                        img.paste(logo, (50, 50), logo)
                except Exception as e:
                    logger.warning(f"Failed to load guild logo: {e}")
            
            # Guild name
            name_font = self.font_manager.get_font("bold", 36)
            draw.text((200, 70), guild.get("Name", "Guild"), fill=self.TEXT_PRIMARY, font=name_font)
            
            # Guild info
            info_font = self.font_manager.get_font("regular", 18)
            alliance_font = self.font_manager.get_font("regular", 16)
            
            draw.text((200, 120), f"Alliance: {guild.get('AllianceName', 'None')}", fill=self.TEXT_SECONDARY, font=alliance_font)
            draw.text((200, 160), f"Members: {guild.get('MemberCount', 0)}", fill=self.TEXT_GOLD, font=info_font)
            draw.text((200, 200), f"Kill Fame: {guild.get('killFame', 0):,}", fill=self.ACCENT_GREEN, font=info_font)
            draw.text((200, 240), f"Death Fame: {guild.get('deathFame', 0):,}", fill=self.ACCENT_RED, font=info_font)
            draw.text((200, 280), f"Founded: {guild.get('Founded', 'Unknown')}", fill=self.TEXT_SECONDARY, font=alliance_font)
            
            return self._save_to_buffer(img)
            
        except Exception as e:
            logger.error(f"Failed to render guild card: {e}")
            raise
    
    def _save_to_buffer(self, img: Image.Image) -> BytesIO:
        """Save image to BytesIO buffer"""
        buf = BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        buf.seek(0)
        return buf


renderer = KillReportRenderer()
