# YouTube Discord Notification Bot

This Discord bot notifies your server members when new YouTube videos are uploaded to specified channels.

## Setup Instructions

1. Create a Discord Bot:
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to the "Bot" section and create a bot
   - Copy the bot token

2. Get YouTube API Key:
   - Go to https://console.cloud.google.com
   - Create a new project
   - Enable the YouTube Data API v3
   - Create credentials (API key)
   - Copy the API key

3. Create a `.env` file with your tokens:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   YOUTUBE_API_KEY=your_youtube_api_key
   ```

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Run the bot:
   ```
   python bot.py
   ```

## Usage

- Use `!addchannel <channel_url>` to add a YouTube channel to monitor
- Use `!removechannel <channel_url>` to stop monitoring a channel
- Use `!listchannels` to see all monitored channels
