import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import json
import os
import re
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", 5000), HealthHandler)
    server.serve_forever()


threading.Thread(target=run_health_server, daemon=True).start()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

GIVEAWAYS_FILE = "giveaways.json"
CONFIG_FILE = "config.json"
OWNER_ID = 1024652708571009137


def load_giveaways():
    if os.path.exists(GIVEAWAYS_FILE):
        with open(GIVEAWAYS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_giveaways(data):
    with open(GIVEAWAYS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def parse_duration(duration_str):
    duration_str = duration_str.strip().lower()
    total_seconds = 0
    pattern = re.findall(r"(\d+)([smhd])", duration_str)
    if not pattern:
        try:
            return int(duration_str)
        except:
            return None
    for value, unit in pattern:
        value = int(value)
        if unit == "s":
            total_seconds += value
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "d":
            total_seconds += value * 86400
    return total_seconds if total_seconds > 0 else None


def format_time(seconds):
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''}"
    elif seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''}"
    else:
        d = seconds // 86400
        return f"{d} day{'s' if d != 1 else ''}"


async def log_to_channel(guild, message=None, embed=None):
    try:
        config = load_config()
        guild_id = str(guild.id)
        if guild_id not in config or "log_channel" not in config[guild_id]:
            return
        channel_id = config[guild_id]["log_channel"]
        channel = guild.get_channel(int(channel_id))
        if not channel:
            try:
                channel = await guild.fetch_channel(int(channel_id))
            except Exception:
                return
        if not channel:
            return
        for attempt in range(3):
            try:
                if embed:
                    await channel.send(embed=embed)
                elif message:
                    await channel.send(message)
                return
            except discord.errors.HTTPException as e:
                if attempt < 2:
                    await asyncio.sleep(2)
                else:
                    print(f"❌ Log failed after 3 attempts: {e}")
    except Exception as e:
        print(f"❌ Log channel error: {e}")


async def end_giveaway(giveaway_id, guild_id, announce=True):
    giveaways = load_giveaways()
    key = f"{guild_id}_{giveaway_id}"

    if key not in giveaways:
        return None

    giveaway = giveaways[key]
    if giveaway.get("ended"):
        return giveaway

    guild = bot.get_guild(int(guild_id))
    if not guild:
        return None

    channel = guild.get_channel(int(giveaway["channel_id"]))
    if not channel:
        return None

    try:
        message = await channel.fetch_message(int(giveaway_id))
    except:
        return None

    reaction = discord.utils.get(message.reactions, emoji="🎉")
    participants = []
    if reaction:
        async for user in reaction.users():
            if not user.bot:
                participants.append(user)

    pre_winners = giveaway.get("pre_winners", [])
    winner_count = int(giveaway.get("winners", 1))
    pre_winner_objects = []

    for uid in pre_winners:
        member = guild.get_member(int(uid))
        if member:
            pre_winner_objects.append(member)
            if member in participants:
                participants.remove(member)

    remaining_slots = max(0, winner_count - len(pre_winner_objects))
    random_winners = []
    if remaining_slots > 0 and participants:
        pool = list(set(participants))
        count = min(remaining_slots, len(pool))
        random_winners = random.sample(pool, count)

    all_winners = pre_winner_objects + random_winners

    giveaway["ended"] = True
    giveaway["winners_list"] = [str(w.id) for w in all_winners]
    giveaway["participants"] = [str(u.id) for u in participants] + [
        str(uid) for uid in pre_winners
    ]
    save_giveaways(giveaways)

    prize = giveaway.get("prize", "Unknown Prize")
    per_winner = giveaway.get("perwinners", "")

    if all_winners:
        winner_mentions = ", ".join([w.mention for w in all_winners])
        ended_desc = f"• **Prize:** {prize}\n"
        ended_desc += f"• **Winners:** {winner_mentions}\n"
        if per_winner:
            ended_desc += f"• **Per Winner:** {per_winner}\n"
        ended_desc += (
            f"• **Participants:** {len(participants) + len(pre_winner_objects)}\n\n"
        )
        ended_desc += "🏆 Congratulations to the winners!"
    else:
        ended_desc = (
            f"• **Prize:** {prize}\n\n❌ **No valid winners!** Not enough participants."
        )

    ended_embed = discord.Embed(
        title="🎊 Giveaway Ended 🎊",
        description=ended_desc,
        color=discord.Color.red(),
        timestamp=datetime.utcnow(),
    )
    ended_embed.set_footer(text=f"Ended at • Giveaway ID: {giveaway_id}")

    try:
        await message.edit(embed=ended_embed)
    except:
        pass

    if announce:
        all_participants = list(set(participants + pre_winner_objects))
        total_count = len(participants) + len(pre_winner_objects)

        if all_winners:
            winner_mentions = ", ".join([w.mention for w in all_winners])
            announce_msg = f"🎉 **GIVEAWAY ENDED!** 🎉\n\n**Prize:** {prize}\n\n**Winners:** {winner_mentions}\n\nCongratulations! Contact the organizer to claim your prize."
            await channel.send(announce_msg)

        log_embed = discord.Embed(
            title="📋 Giveaway Ended Log",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )
        log_embed.add_field(name="Prize", value=prize, inline=True)
        log_embed.add_field(
            name="Winners Selected", value=str(len(all_winners)), inline=True
        )
        log_embed.add_field(
            name="Total Participants", value=str(total_count), inline=True
        )

        if all_winners:
            log_embed.add_field(
                name="🏆 Winners",
                value=", ".join([w.mention for w in all_winners]),
                inline=False,
            )

        if pre_winner_objects:
            log_embed.add_field(
                name="⭐ Pre-Selected Winners",
                value=", ".join([w.mention for w in pre_winner_objects]),
                inline=False,
            )

        log_embed.add_field(name="Channel", value=channel.mention, inline=True)
        log_embed.add_field(name="Message ID", value=str(giveaway_id), inline=True)

        await log_to_channel(guild, embed=log_embed)

        if all_participants:
            participant_mentions = " ".join([u.mention for u in all_participants])
            chunks = []
            chunk = ""
            for mention in participant_mentions.split():
                if len(chunk) + len(mention) + 1 > 1000:
                    chunks.append(chunk.strip())
                    chunk = mention + " "
                else:
                    chunk += mention + " "
            if chunk.strip():
                chunks.append(chunk.strip())

            part_embed = discord.Embed(
                title=f"👥 Full Participant List — {prize}",
                description=f"**Total Joined:** {total_count}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow(),
            )
            await log_to_channel(guild, embed=part_embed)

            for i, chunk_text in enumerate(chunks, 1):
                chunk_embed = discord.Embed(
                    description=chunk_text, color=discord.Color.green()
                )
                chunk_embed.set_footer(text=f"Part {i}/{len(chunks)}")
                await log_to_channel(guild, embed=chunk_embed)
        else:
            no_part_embed = discord.Embed(
                title=f"👥 Full Participant List — {prize}",
                description="**No participants joined this giveaway.**",
                color=discord.Color.red(),
                timestamp=datetime.utcnow(),
            )
            await log_to_channel(guild, embed=no_part_embed)

    return giveaway


@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    print(
        f"🔗 Invite: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot+applications.commands"
    )

    synced_guilds = 0
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            synced_guilds += 1
        except Exception as e:
            print(f"❌ Could not sync to {guild.name}: {e}")

    print(f"✅ Slash commands synced to {synced_guilds} server(s) instantly!")

    try:
        await bot.tree.sync()
        print("✅ Global sync done too.")
    except Exception as e:
        print(f"⚠️ Global sync error: {e}")

    if not check_giveaways.is_running():
        check_giveaways.start()


@bot.event
async def on_guild_join(guild):
    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced slash commands to new server: {guild.name}")
    except Exception as e:
        print(f"❌ Could not sync to {guild.name}: {e}")


def self_ping():
    import time

    time.sleep(15)
    while True:
        try:
            urllib.request.urlopen("http://localhost:5000", timeout=5)
            print("✅ Self-ping — bot alive!")
        except Exception as e:
            print(f"⚠️ Ping failed: {e}")
        time.sleep(60)


threading.Thread(target=self_ping, daemon=True).start()


@tasks.loop(seconds=10)
async def check_giveaways():
    giveaways = load_giveaways()
    now = datetime.utcnow().timestamp()
    for key, giveaway in list(giveaways.items()):
        if giveaway.get("ended"):
            continue
        end_time = giveaway.get("end_time", 0)
        if now >= end_time:
            guild_id, msg_id = key.split("_", 1)
            await end_giveaway(msg_id, guild_id)


@bot.tree.command(name="gstart", description="Start a new giveaway")
@app_commands.describe(
    duration="Duration of the giveaway (e.g. 30s, 5m, 2h, 1d)",
    winners="Number of winners (1-100)",
    prize="Name of the prize",
)
@app_commands.default_permissions(manage_guild=True)
async def gstart(
    interaction: discord.Interaction, duration: str, winners: int, prize: str
):
    perwinners = ""
    await interaction.response.defer(ephemeral=True)

    duration_secs = parse_duration(duration)
    if not duration_secs:
        await interaction.followup.send(
            "❌ Invalid duration! Use formats like `30s`, `5m`, `2h`, `1d`",
            ephemeral=True,
        )
        return

    winner_count = max(1, min(winners, 100))
    end_time = datetime.utcnow() + timedelta(seconds=duration_secs)
    end_ts = int(end_time.timestamp())

    desc = f"🎁 {prize} 🎁\n\n"
    desc += f"• **Winners:** {winner_count}\n"
    desc += f"• **Ends** <t:{end_ts}:R> (<t:{end_ts}:f>)\n"
    desc += "\n• React with 🎉 to participate!"

    embed = discord.Embed(
        title="🎊 New Giveaway 🎊",
        description=desc,
        color=discord.Color.gold(),
        timestamp=end_time,
    )
    embed.set_footer(text=f"Ends at • Winners: {winner_count}")

    giveaway_msg = await interaction.channel.send(embed=embed)
    await giveaway_msg.add_reaction("🎉")

    giveaways = load_giveaways()
    key = f"{interaction.guild.id}_{giveaway_msg.id}"
    giveaways[key] = {
        "guild_id": str(interaction.guild.id),
        "channel_id": str(interaction.channel.id),
        "message_id": str(giveaway_msg.id),
        "host_id": str(interaction.user.id),
        "prize": prize,
        "winners": winner_count,
        "perwinners": perwinners,
        "duration": duration_secs,
        "end_time": end_time.timestamp(),
        "ended": False,
        "pre_winners": [],
        "participants": [],
    }
    save_giveaways(giveaways)

    log_embed = discord.Embed(
        title="🎉 New Giveaway Started",
        color=discord.Color.green(),
        timestamp=datetime.utcnow(),
    )
    log_embed.add_field(name="Prize", value=prize, inline=True)
    log_embed.add_field(name="Winners", value=str(winner_count), inline=True)
    log_embed.add_field(name="Duration", value=format_time(duration_secs), inline=True)
    log_embed.add_field(name="Hosted By", value=interaction.user.mention, inline=True)
    log_embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
    log_embed.add_field(name="Message ID", value=str(giveaway_msg.id), inline=False)
    await log_to_channel(interaction.guild, embed=log_embed)

    await interaction.followup.send(
        f"✅ Giveaway started! Message ID: `{giveaway_msg.id}`", ephemeral=True
    )


@bot.tree.command(name="gend", description="End a giveaway early")
@app_commands.describe(
    message_id="Message ID of the giveaway (leave empty to end latest)"
)
@app_commands.default_permissions(manage_guild=True)
async def gend(interaction: discord.Interaction, message_id: str = None):
    await interaction.response.defer(ephemeral=True)

    giveaways = load_giveaways()

    if message_id:
        key = f"{interaction.guild.id}_{message_id}"
        if key not in giveaways:
            await interaction.followup.send(
                "❌ Giveaway not found with that message ID.", ephemeral=True
            )
            return
        if giveaways[key].get("ended"):
            await interaction.followup.send(
                "❌ This giveaway has already ended.", ephemeral=True
            )
            return
    else:
        active = [
            (k, v)
            for k, v in giveaways.items()
            if str(v.get("guild_id")) == str(interaction.guild.id)
            and not v.get("ended")
        ]
        if not active:
            await interaction.followup.send(
                "❌ No active giveaways found in this server.", ephemeral=True
            )
            return
        if len(active) > 1:
            list_text = "\n".join(
                [
                    f"- `{v['message_id']}` → **{v['prize']}** in <#{v['channel_id']}>"
                    for k, v in active
                ]
            )
            await interaction.followup.send(
                f"⚠️ Multiple active giveaways found. Use `/gend message_id:<id>`\n\n{list_text}",
                ephemeral=True,
            )
            return
        key, giveaway_data = active[0]
        message_id = giveaway_data["message_id"]

    giveaway = await end_giveaway(message_id, str(interaction.guild.id))
    if giveaway:
        await interaction.followup.send(
            "✅ Giveaway ended successfully!", ephemeral=True
        )
    else:
        await interaction.followup.send("❌ Failed to end giveaway.", ephemeral=True)


@bot.tree.command(name="greroll", description="Reroll winners for an ended giveaway")
@app_commands.describe(
    message_id="Message ID of the ended giveaway (leave empty for latest)",
    count="How many new winners to pick (leave empty for original count)",
)
@app_commands.default_permissions(manage_guild=True)
async def greroll(
    interaction: discord.Interaction, message_id: str = None, count: int = None
):
    await interaction.response.defer(ephemeral=True)

    giveaways = load_giveaways()

    if message_id:
        key = f"{interaction.guild.id}_{message_id}"
        if key not in giveaways:
            await interaction.followup.send(
                "❌ Giveaway not found with that message ID.", ephemeral=True
            )
            return
    else:
        ended = [
            (k, v)
            for k, v in giveaways.items()
            if str(v.get("guild_id")) == str(interaction.guild.id) and v.get("ended")
        ]
        if not ended:
            await interaction.followup.send(
                "❌ No ended giveaways found. End a giveaway first with `/gend`.",
                ephemeral=True,
            )
            return
        ended.sort(key=lambda x: x[1].get("end_time", 0), reverse=True)
        key, giveaway_data = ended[0]
        message_id = giveaway_data["message_id"]

    giveaway = giveaways[key]

    if not giveaway.get("ended"):
        await interaction.followup.send(
            "❌ This giveaway hasn't ended yet. Use `/gend` first.", ephemeral=True
        )
        return

    channel = interaction.guild.get_channel(int(giveaway["channel_id"]))
    if not channel:
        await interaction.followup.send(
            "❌ Giveaway channel not found.", ephemeral=True
        )
        return

    try:
        message = await channel.fetch_message(int(message_id))
    except:
        await interaction.followup.send(
            "❌ Could not find the giveaway message.", ephemeral=True
        )
        return

    reaction = discord.utils.get(message.reactions, emoji="🎉")
    participants = []
    if reaction:
        async for user in reaction.users():
            if not user.bot:
                participants.append(user)

    reroll_count = count or int(giveaway.get("winners", 1))
    reroll_count = min(reroll_count, len(participants))

    if not participants:
        await interaction.followup.send(
            "❌ No participants found for reroll.", ephemeral=True
        )
        return

    new_winners = random.sample(participants, reroll_count)
    winner_mentions = ", ".join([w.mention for w in new_winners])
    prize = giveaway.get("prize", "the prize")
    per_winner = giveaway.get("perwinners", "")

    reroll_embed = discord.Embed(
        title="🔄 Giveaway Rerolled!",
        description=(
            f"• **Prize:** {prize}\n"
            f"{'• **Per Winner:** ' + per_winner + chr(10) if per_winner else ''}"
            f"• **New Winners:** {winner_mentions}\n\n"
            "🏆 Congratulations to the new winners!"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.utcnow(),
    )
    await channel.send(embed=reroll_embed)

    log_embed = discord.Embed(
        title="🔄 Giveaway Rerolled",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow(),
    )
    log_embed.add_field(name="Prize", value=prize, inline=True)
    log_embed.add_field(name="New Winners", value=winner_mentions, inline=False)
    log_embed.add_field(name="Rerolled By", value=interaction.user.mention, inline=True)
    log_embed.add_field(name="Message ID", value=str(message_id), inline=True)
    await log_to_channel(interaction.guild, embed=log_embed)

    await interaction.followup.send("✅ Rerolled successfully!", ephemeral=True)


@bot.tree.command(name="glist", description="Show all active giveaways in this server")
@app_commands.default_permissions(manage_guild=True)
async def glist(interaction: discord.Interaction):
    giveaways = load_giveaways()
    active = [
        (k, v)
        for k, v in giveaways.items()
        if str(v.get("guild_id")) == str(interaction.guild.id) and not v.get("ended")
    ]

    if not active:
        await interaction.response.send_message(
            "📭 No active giveaways in this server.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎉 Active Giveaways",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow(),
    )
    for key, g in active:
        end_ts = int(g.get("end_time", 0))
        pre_count = len(g.get("pre_winners", []))
        embed.add_field(
            name=f"🏆 {g['prize']}",
            value=(
                f"**ID:** `{g['message_id']}`\n"
                f"**Winners:** {g['winners']}\n"
                f"**Pre-selected:** {pre_count}\n"
                f"**Ends:** <t:{end_ts}:R>\n"
                f"**Channel:** <#{g['channel_id']}>"
            ),
            inline=True,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.command(name="gaddwinner")
async def gaddwinner(ctx, member: discord.Member = None, message_id: str = None):
    if ctx.author.id != OWNER_ID:
        await ctx.message.delete()
        await ctx.send("❌ Invalid command.", delete_after=3)
        return

    if not member:
        await ctx.send(f"❌ Usage: `!gaddwinner @user [message_id]`")
        return

    giveaways = load_giveaways()

    if message_id:
        key = f"{ctx.guild.id}_{message_id}"
    else:
        active = [
            (k, v)
            for k, v in giveaways.items()
            if str(v.get("guild_id")) == str(ctx.guild.id) and not v.get("ended")
        ]
        if not active:
            await ctx.send("❌ No active giveaways found.")
            return
        if len(active) > 1:
            list_text = "\n".join(
                [f"- `{v['message_id']}` → **{v['prize']}**" for k, v in active]
            )
            await ctx.send(
                f"⚠️ Multiple giveaways found. Specify message ID:\n{list_text}"
            )
            return
        key, _ = active[0]
        message_id = giveaways[key]["message_id"]

    if key not in giveaways:
        await ctx.send("❌ Giveaway not found.")
        return

    giveaway = giveaways[key]
    pre_winners = giveaway.get("pre_winners", [])
    max_winners = int(giveaway.get("winners", 1))

    if str(member.id) in pre_winners:
        await ctx.send(f"⚠️ {member.mention} is already a pre-selected winner!")
        return

    if len(pre_winners) >= max_winners:
        await ctx.send(
            f"❌ Already {max_winners} pre-selected winners (max for this giveaway)."
        )
        return

    pre_winners.append(str(member.id))
    giveaway["pre_winners"] = pre_winners
    save_giveaways(giveaways)

    prize = giveaway.get("prize", "the prize")
    embed = discord.Embed(
        title="✅ Pre-Winner Added",
        description=f"{member.mention} has been pre-selected as a winner for **{prize}**!\n\nPre-selected: {len(pre_winners)}/{max_winners}",
        color=discord.Color.green(),
    )
    await ctx.send(embed=embed)


@bot.command(name="gremovewinner")
async def gremovewinner(ctx, member: discord.Member = None, message_id: str = None):
    if ctx.author.id != OWNER_ID:
        await ctx.message.delete()
        await ctx.send("❌ Invalid command.", delete_after=3)
        return

    if not member:
        await ctx.send(f"❌ Usage: `!gremovewinner @user [message_id]`")
        return

    giveaways = load_giveaways()

    if message_id:
        key = f"{ctx.guild.id}_{message_id}"
    else:
        active = [
            (k, v)
            for k, v in giveaways.items()
            if str(v.get("guild_id")) == str(ctx.guild.id) and not v.get("ended")
        ]
        if not active:
            await ctx.send("❌ No active giveaways found.")
            return
        key, _ = active[0]

    if key not in giveaways:
        await ctx.send("❌ Giveaway not found.")
        return

    giveaway = giveaways[key]
    pre_winners = giveaway.get("pre_winners", [])

    if str(member.id) not in pre_winners:
        await ctx.send(f"⚠️ {member.mention} is not a pre-selected winner.")
        return

    pre_winners.remove(str(member.id))
    giveaway["pre_winners"] = pre_winners
    save_giveaways(giveaways)

    embed = discord.Embed(
        title="✅ Pre-Winner Removed",
        description=f"{member.mention} has been removed from pre-selected winners.",
        color=discord.Color.red(),
    )
    await ctx.send(embed=embed)

    log_embed = discord.Embed(
        title="🗑️ Pre-Winner Removed",
        color=discord.Color.red(),
        timestamp=datetime.utcnow(),
    )
    log_embed.add_field(name="User", value=member.mention, inline=True)
    log_embed.add_field(name="Removed By", value=ctx.author.mention, inline=True)
    log_embed.add_field(
        name="Giveaway ID",
        value=str(message_id or giveaways[key]["message_id"]),
        inline=True,
    )
    await log_to_channel(ctx.guild, embed=log_embed)


@bot.command(name="setlog")
@commands.has_permissions(manage_guild=True)
async def setlog(ctx, channel: discord.TextChannel = None):
    if not channel:
        await ctx.send("❌ Usage: `!setlog #channel`")
        return

    config = load_config()
    guild_id = str(ctx.guild.id)
    if guild_id not in config:
        config[guild_id] = {}

    config[guild_id]["log_channel"] = str(channel.id)
    save_config(config)

    embed = discord.Embed(
        title="✅ Log Channel Set",
        description=f"Giveaway logs ab {channel.mention} me aayenge!\n\nJo log milega:\n• Giveaway start hone pe\n• Har baar koi join kare\n• Giveaway end hone pe (winners + poori participant list)",
        color=discord.Color.green(),
    )
    await ctx.send(embed=embed)
    await channel.send(
        f"✅ Yeh channel **{ctx.guild.name}** ka **Giveaway Log Channel** set ho gaya hai!"
    )


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.emoji != "🎉":
        return

    giveaways = load_giveaways()
    key = f"{reaction.message.guild.id}_{reaction.message.id}"

    if key not in giveaways:
        return

    giveaway = giveaways[key]
    if giveaway.get("ended"):
        return

    log_embed = discord.Embed(
        title="👤 New Participant Joined",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow(),
    )
    log_embed.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
    log_embed.add_field(
        name="Prize", value=giveaway.get("prize", "Unknown"), inline=True
    )
    log_embed.add_field(name="Giveaway ID", value=str(reaction.message.id), inline=True)
    log_embed.set_thumbnail(url=user.display_avatar.url)
    await log_to_channel(reaction.message.guild, embed=log_embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tumhare paas permission nahi hai.", delete_after=5)
    else:
        print(f"Command error: {error}")


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    try:
        if isinstance(error, app_commands.errors.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.errors.NotFound):
                return
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Kuch error aa gaya, dobara try karo.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Kuch error aa gaya, dobara try karo.", ephemeral=True
            )
    except Exception:
        pass
    print(f"App command error: {error}")


@bot.event
async def on_disconnect():
    print("⚠️ Bot disconnected from Discord, reconnecting...")


@bot.event
async def on_resumed():
    print("✅ Bot reconnected successfully!")


import asyncio
import signal


def handle_sigterm(signum, frame):
    print("⚠️ SIGTERM received — restarting bot...")
    raise SystemExit(0)


signal.signal(signal.SIGTERM, handle_sigterm)


async def main():
    while True:
        try:
            print("🚀 Bot starting...")
            async with bot:
                await bot.start(TOKEN)
        except discord.errors.LoginFailure:
            print("❌ Invalid token! Check DISCORD_TOKEN secret.")
            break
        except (SystemExit, KeyboardInterrupt):
            print("🔄 Restarting bot in 3 seconds...")
            await asyncio.sleep(3)
        except discord.errors.HTTPException as e:
            print(f"⚠️ HTTP error: {e} — retrying in 10 seconds...")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"❌ Bot crashed: {e} — restarting in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN not found!")
    else:
        asyncio.run(main())

# update
