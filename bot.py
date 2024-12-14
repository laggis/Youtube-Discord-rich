import os
import json
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Configure bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# YouTube API setup
youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))

# Store channels and their last video IDs
CHANNELS_FILE = 'channels.json'
INITIAL_CHECK_DONE = {}

def load_channels():
    try:
        with open(CHANNELS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_channels(channels):
    with open(CHANNELS_FILE, 'w') as f:
        json.dump(channels, f)

channels = load_channels()

async def get_channel_id(url):
    try:
        if 'channel/' in url:
            channel_id = url.split('channel/')[-1].split('/')[0]
        elif 'user/' in url:
            username = url.split('user/')[-1].split('/')[0]
            response = youtube.channels().list(
                part='id',
                forUsername=username
            ).execute()
            if response['items']:
                channel_id = response['items'][0]['id']
            else:
                return None
        else:
            return None
        return channel_id
    except HttpError:
        return None

async def get_latest_video(channel_id):
    try:
        response = youtube.search().list(
            part='id,snippet',
            channelId=channel_id,
            order='date',
            maxResults=1,
            type='video'
        ).execute()

        if not response['items']:
            return None

        video = response['items'][0]
        video_id = video['id']['videoId']
        
        # Get additional video details
        video_response = youtube.videos().list(
            part='statistics,contentDetails',
            id=video_id
        ).execute()
        
        video_details = video_response['items'][0]
        
        return {
            'id': video_id,
            'title': video['snippet']['title'],
            'description': video['snippet']['description'],
            'thumbnail': video['snippet']['thumbnails']['high']['url'],
            'channel_title': video['snippet']['channelTitle'],
            'published_at': video['snippet']['publishedAt'],
            'url': f"https://www.youtube.com/watch?v={video_id}",
            'duration': video_details['contentDetails']['duration'],
            'views': video_details['statistics'].get('viewCount', '0'),
            'likes': video_details['statistics'].get('likeCount', '0')
        }
    except HttpError:
        return None

@tasks.loop(minutes=5)
async def check_new_videos():
    notification_channel = bot.get_channel(int(os.getenv('NOTIFICATION_CHANNEL_ID')))
    if not notification_channel:
        return

    for channel_url, data in channels.items():
        try:
            latest_video = await get_latest_video(data['channel_id'])
            if not latest_video:
                continue

            # Skip notification on first check for each channel
            if channel_url not in INITIAL_CHECK_DONE:
                INITIAL_CHECK_DONE[channel_url] = True
                channels[channel_url]['last_video_id'] = latest_video['id']
                save_channels(channels)
                continue

            if latest_video['id'] != data['last_video_id']:
                channels[channel_url]['last_video_id'] = latest_video['id']
                save_channels(channels)
                
                # Convert duration from ISO 8601 format
                duration_str = latest_video['duration'].replace('PT', '')
                hours = '0'
                minutes = '0'
                seconds = '0'
                
                if 'H' in duration_str:
                    hours, duration_str = duration_str.split('H')
                if 'M' in duration_str:
                    minutes, duration_str = duration_str.split('M')
                if 'S' in duration_str:
                    seconds = duration_str.replace('S', '')
                
                duration = f"{hours}:{minutes.zfill(2)}:{seconds.zfill(2)}" if hours != '0' else f"{minutes}:{seconds.zfill(2)}"
                
                # Format view count with commas
                views = "{:,}".format(int(latest_video['views']))
                likes = "{:,}".format(int(latest_video['likes']))
                
                # Create timestamp from published_at
                published_time = datetime.strptime(latest_video['published_at'], '%Y-%m-%dT%H:%M:%SZ')
                timestamp = int(published_time.timestamp())
                
                embed = discord.Embed(
                    title=latest_video['title'],
                    url=latest_video['url'],
                    description=latest_video['description'][:200] + '...' if len(latest_video['description']) > 200 and 'discord.com/oauth2/authorize' not in latest_video['description'] else '',
                    color=discord.Color.red()
                )
                
                embed.set_author(
                    name=latest_video['channel_title'],
                    icon_url="https://www.youtube.com/s/desktop/e4d15d2c/img/favicon_144x144.png",
                    url=f"https://www.youtube.com/channel/{data['channel_id']}"
                )
                
                embed.set_thumbnail(url=latest_video['thumbnail'])
                
                embed.add_field(
                    name="📊 Stats",
                    value=f"👀 Views: {views}\n👍 Likes: {likes}\n⏱️ Duration: {duration}",
                    inline=True
                )
                
                embed.add_field(
                    name="🔗 Quick Links",
                    value=f"[▶️ Watch Now]({latest_video['url']})\n[📺 Channel](https://www.youtube.com/channel/{data['channel_id']})",
                    inline=True
                )
                
                embed.set_footer(text="YouTube", icon_url="https://www.youtube.com/s/desktop/e4d15d2c/img/favicon_144x144.png")
                embed.timestamp = published_time
                
                await notification_channel.send(
                    content="🔔 **New Video Alert!**",
                    embed=embed
                )
        except Exception as e:
            print(f"Error checking channel {channel_url}: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    check_new_videos.start()

@bot.command(name='addchannel')
async def add_channel(ctx, channel_url: str):
    channel_id = await get_channel_id(channel_url)
    if not channel_id:
        await ctx.send("Invalid YouTube channel URL.")
        return

    latest_video = await get_latest_video(channel_id)
    if not latest_video:
        await ctx.send("Couldn't fetch channel information.")
        return

    channels[channel_url] = {
        'channel_id': channel_id,
        'last_video_id': latest_video['id']
    }
    save_channels(channels)
    await ctx.send(f"Added channel: {channel_url}")

@bot.command(name='removechannel')
async def remove_channel(ctx, channel_url: str):
    if channel_url in channels:
        del channels[channel_url]
        save_channels(channels)
        await ctx.send(f"Removed channel: {channel_url}")
    else:
        await ctx.send("Channel not found in monitoring list.")

@bot.command(name='listchannels')
async def list_channels(ctx):
    if not channels:
        await ctx.send("No channels are being monitored.")
        return

    channel_list = "\n".join(channels.keys())
    await ctx.send(f"Monitored channels:\n{channel_list}")

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
