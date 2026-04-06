import discord
from discord import app_commands
from discord.ext import commands, tasks

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
