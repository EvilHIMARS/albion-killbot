"""
Discord commands cog
"""
import discord
from discord.ext import commands
from typing import Optional
from api_client import AlbionAPIClient
from image_renderer import renderer
from logger import logger
from config import config
import json
import os


class CommandsCog(commands.Cog):
    """Discord commands"""
    
    # File for storing channel settings
    SETTINGS_FILE = "settings.json"
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = self._load_settings()
    
    def _load_settings(self) -> dict:
        """Load settings from file"""
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load settings: {e}")
        return {"channel_id": config.DISCORD_CHANNEL_ID}
    
    def _save_settings(self):
        """Save settings to file"""
        try:
            with open(self.SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f)
            logger.info(f"Settings saved: {self.settings}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    @commands.command(name="канал")
    async def set_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Set the channel for kill reports
        
        Usage:
        !канал #channel_name  - Set specific channel
        !канал current         - Set current channel
        !канал show           - Show current channel
        """
        if channel is None:
            # Check if user mentioned a channel or used "current"
            if ctx.message.content.strip().endswith("current"):
                channel = ctx.channel
            elif ctx.message.content.strip().endswith("show"):
                current_id = self.settings.get("channel_id")
                current_channel = self.bot.get_channel(current_id)
                if current_channel:
                    embed = discord.Embed(
                        title="📍 Kill Reports Channel",
                        description=f"Current channel: {current_channel.mention}",
                        color=discord.Color.blue()
                    )
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Channel not found! Use `!канал current` to set this channel.")
                return
            else:
                await ctx.send("❌ Usage: `!канал #channel_name` or `!канал current` or `!канал show`")
                return
        
        # Save channel
        self.settings["channel_id"] = channel.id
        self._save_settings()
        
        embed = discord.Embed(
            title="✅ Channel Updated",
            description=f"Kill reports will be sent to {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logger.info(f"Channel set to {channel.name} ({channel.id})")
    
    @commands.command(name="гильдия")
    async def guild_info(self, ctx, guild_id: Optional[str] = None):
        """Fetch and display guild information"""
        await ctx.defer()
        
        try:
            async with AlbionAPIClient() as api:
                guild_data = await api.get_guild(guild_id or config.GUILD_ID)
                
                if not guild_data:
                    await ctx.send("❌ Guild not found")
                    return
                
                image_buffer = await renderer.render_guild_card(guild_data)
                file = discord.File(image_buffer, "guild_info.png")
                embed = discord.Embed(
                    title=f"🏰 Guild: {guild_data.get('Name')}",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed, file=file)
                
        except Exception as e:
            logger.error(f"Error in guild_info: {e}")
            await ctx.send(f"❌ Error: {str(e)}")
    
    @commands.command(name="тест_килл")
    async def test_kill(self, ctx):
        """Generate a test kill report"""
        await ctx.defer()
        
        try:
            killer = {
                "Name": "ProPlayer",
                "GuildId": "c7fgh-V2QTSYBJqKPpNtkg",
                "GuildName": "Alpha Legion",
                "Equipment": {
                    "MainHand": {"Type": "T8_MAIN_FIRESTAFF@3"},
                    "Head": {"Type": "T8_HEAD_CLOTH_SET1@3"},
                    "Armor": {"Type": "T8_ARMOR_CLOTH_SET1@3"}
                }
            }
            
            victim = {
                "Name": "NoobPlayer",
                "GuildId": None,
                "GuildName": "Solo",
                "Equipment": {
                    "MainHand": {"Type": "T4_MAIN_SWORD@1"},
                    "Head": {"Type": "T4_HEAD_PLATE_SET1@1"}
                }
            }
            
            image_buffer = await renderer.render_kill_report(
                killer=killer,
                victim=victim,
                fame=100000,
                timestamp="2026-06-11 18:30:00"
            )
            file = discord.File(image_buffer, "test_kill.png")
            embed = discord.Embed(
                title="⚔️ Kill Report - Test",
                description=f"{killer['Name']} killed {victim['Name']}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, file=file)
            
        except Exception as e:
            logger.error(f"Error in test_kill: {e}")
            await ctx.send(f"❌ Error: {str(e)}")
    
    @commands.command(name="статус")
    async def status(self, ctx):
        """Show bot status"""
        current_id = self.settings.get("channel_id")
        current_channel = self.bot.get_channel(current_id)
        
        embed = discord.Embed(
            title="🤖 Albion Killbot Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value="✅ Online", inline=False)
        embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.0f}ms", inline=False)
        embed.add_field(
            name="Kill Reports Channel",
            value=current_channel.mention if current_channel else "Not set",
            inline=False
        )
        embed.add_field(name="Guild", value=config.GUILD_ID, inline=False)
        embed.add_field(name="Live Tracking", value="🟢 Enabled" if config.ENABLE_LIVE_TRACKING else "🔴 Disabled", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="помощь")
    async def help_command(self, ctx):
        """Show all commands"""
        embed = discord.Embed(
            title="📚 Albion Killbot Commands",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="!канал",
            value="Set channel for kill reports\n`!канал #channel_name` or `!канал current` or `!канал show`",
            inline=False
        )
        embed.add_field(
            name="!гильдия [guild_id]",
            value="Show guild information",
            inline=False
        )
        embed.add_field(
            name="!тест_килл",
            value="Generate a test kill report",
            inline=False
        )
        embed.add_field(
            name="!статус",
            value="Show bot status and settings",
            inline=False
        )
        embed.add_field(
            name="!помощь",
            value="Show this help message",
            inline=False
        )
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Setup cog"""
    await bot.add_cog(CommandsCog(bot))
