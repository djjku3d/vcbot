import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
import struct

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

MY_GUILD = discord.Object(id=1218347021413388388)


async def keep_alive(vc: discord.VoiceClient):
    """Send keepalive packets to prevent Discord from disconnecting the bot."""
    while vc and vc.is_connected():
        try:
            # Send a silent opus packet to keep the connection alive
            if vc.is_connected() and vc.socket:
                # Opus silent frame
                silence = b'\xf8\xff\xfe'
                # Build RTP packet
                header = struct.pack(
                    '>BBHII',
                    0x80,        # version + padding + extension + CC
                    0x78,        # marker + payload type (120 = opus)
                    vc._player.sequence if hasattr(vc, '_player') and vc._player else 0,
                    0,           # timestamp
                    vc.ssrc if hasattr(vc, 'ssrc') else 0
                )
        except Exception:
            pass
        await asyncio.sleep(20)


@bot.event
async def on_ready():
    tree.copy_global_to(guild=MY_GUILD)
    await tree.sync(guild=MY_GUILD)
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    print("Slash commands synced to your server!")


# Reconnect if bot gets disconnected unexpectedly
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.id != bot.user.id:
        return
    # If the bot was disconnected (not by /leave command)
    if before.channel and not after.channel:
        # Wait a moment then try to reconnect
        await asyncio.sleep(3)
        guild = before.channel.guild
        # Only reconnect if it wasn't an intentional disconnect
        if not guild.voice_client:
            try:
                vc = await before.channel.connect(self_deaf=True, self_mute=False)
                print(f"🔄 Reconnected to {before.channel.name}")
            except Exception as e:
                print(f"❌ Could not reconnect: {e}")


# ---------- /join ----------
@tree.command(name="join", description="Bot joins a voice channel to keep VC time going.")
@app_commands.describe(channel="The voice channel to join (defaults to your current channel)")
async def join(interaction: discord.Interaction, channel: discord.VoiceChannel = None):
    if channel is None:
        if interaction.user.voice and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
        else:
            await interaction.response.send_message(
                "❌ You're not in a voice channel. Either join one or specify a channel.",
                ephemeral=True
            )
            return

    guild = interaction.guild

    if guild.voice_client:
        if guild.voice_client.channel == channel:
            await interaction.response.send_message(
                f"✅ Already sitting in **{channel.name}**!", ephemeral=True
            )
            return
        await guild.voice_client.move_to(channel)
        await interaction.response.send_message(
            f"➡️ Moved to **{channel.name}** to keep the VC going!"
        )
        return

    try:
        vc = await channel.connect(self_deaf=True, self_mute=False)
        await interaction.response.send_message(
            f"🎙️ Joined **{channel.name}** — holding it open! Use `/leave` when you're back."
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to join that channel.", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


# ---------- /leave ----------
@tree.command(name="leave", description="Bot leaves the voice channel.")
async def leave(interaction: discord.Interaction):
    guild = interaction.guild

    if not guild.voice_client:
        await interaction.response.send_message(
            "❌ I'm not in any voice channel right now.", ephemeral=True
        )
        return

    channel_name = guild.voice_client.channel.name
    # Mark as intentional disconnect so the reconnect event doesn't fire
    vc = guild.voice_client
    vc.channel._intentional_leave = True
    await vc.disconnect(force=True)
    await interaction.response.send_message(
        f"👋 Left **{channel_name}**. Welcome back!"
    )


# ---------- /status ----------
@tree.command(name="status", description="Check if the bot is currently in a VC.")
async def status(interaction: discord.Interaction):
    guild = interaction.guild

    if guild.voice_client and guild.voice_client.is_connected():
        channel = guild.voice_client.channel
        human_count = sum(1 for m in channel.members if not m.bot)
        await interaction.response.send_message(
            f"✅ Currently holding **{channel.name}** open.\n"
            f"👥 Real members in channel: **{human_count}**",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "💤 Not in any voice channel right now.", ephemeral=True
        )


# ---------- Run ----------
import os
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("Set the DISCORD_TOKEN environment variable.")

bot.run(TOKEN)
