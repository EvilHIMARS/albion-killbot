# Albion Killbot 🗡️

Professional Discord bot for tracking kills in Albion Online with beautiful live killboards.

## Features

✨ **Core Features:**
- 🔴 Real-time kill tracking and notifications
- 🎨 Professional kill report rendering with equipment display
- 🏰 Guild information cards
- 📊 Kill statistics and leaderboards (coming soon)
- ⚡ Slash commands support
- 🔄 Automatic retry logic with exponential backoff
- 💾 Image caching for performance

## Architecture

```
albion-killbot/
├── main.py                 # Bot entry point
├── config.py              # Configuration management
├── logger.py              # Logging setup
├── api_client.py          # Albion API client
├── cache_manager.py       # Image cache management
├── image_renderer.py      # Kill report rendering
├── cogs/
│   ├── commands.py        # Slash commands
│   └── tracking.py        # Kill polling & tracking
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── Dockerfile            # Docker config
└── README.md             # This file
```

## Installation

### Prerequisites
- Python 3.11+
- Discord Bot Token
- Albion Guild ID

### Local Setup

1. **Clone repository:**
```bash
git clone https://github.com/EvilHIMARS/albion-killbot.git
cd albion-killbot
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\\Scripts\\activate  # Windows
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your values
```

5. **Run bot:**
```bash
python main.py
```

### Docker Deployment

1. **Build image:**
```bash
docker build -t albion-killbot .
```

2. **Run container:**
```bash
docker run -d \
  --name killbot \
  -e DISCORD_TOKEN=your_token \
  -e DISCORD_CHANNEL_ID=your_channel_id \
  -e GUILD_ID=your_guild_id \
  albion-killbot
```

## Configuration

### Environment Variables

```env
# Required
DISCORD_TOKEN=your_bot_token
DISCORD_CHANNEL_ID=channel_id
GUILD_ID=albion_guild_id

# Optional
COMMAND_PREFIX=!              # Command prefix (default: !)
ENABLE_LIVE_TRACKING=True    # Enable kill tracking
ENABLE_STATS=True            # Enable statistics
POLL_INTERVAL=15             # Polling interval in seconds
LOG_LEVEL=INFO               # Logging level
```

## Commands

### Slash Commands

- `/guild_info [guild_id]` - Get guild information
- `/test_kill` - Generate a test kill report
- `/status` - Show bot status

## API Integration

The bot integrates with:

- **Albion Online Game Info API**: `https://gameinfo-ams.albiononline.com/api/gameinfo`
- **Item/Guild Render API**: `https://render.albiononline.com/v1`

## Performance

- **Caching**: All images are cached for 24 hours
- **Rate Limiting**: Automatic retry with exponential backoff
- **Polling**: Efficient kill tracking with configurable intervals
- **Memory**: Optimized image rendering with BytesIO

## Error Handling

- Comprehensive logging to `logs/killbot.log`
- Automatic retry logic for API failures
- Graceful degradation on missing assets
- User-friendly error messages in Discord

## Development

### Adding New Features

1. Create new cog in `cogs/` directory
2. Inherit from `commands.Cog`
3. Implement required methods
4. Add to bot's setup_hook loading

### Testing

```bash
# Run test command in Discord
/test_kill
```

## Troubleshooting

### Bot not responding
- Check Discord token in .env
- Verify bot has permissions in channel
- Check logs: `tail -f logs/killbot.log`

### No kills showing
- Verify GUILD_ID is correct
- Check channel ID
- Enable ENABLE_LIVE_TRACKING in .env
- Verify guild has kill data in API

### Image rendering issues
- Ensure fonts are downloaded: `python -c "from image_renderer import renderer"`
- Check PIL/Pillow installation
- Verify cache directory exists

## Contributing

Contributions welcome! Please:

1. Fork repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## License

MIT License - see LICENSE file

## Support

For issues and questions:
- 📝 Open an issue on GitHub
- 💬 Discord: [Your Discord Server]
- 📧 Email: contact@example.com

---

**Made with ❤️ for Albion Online community**
