"""
Growcom Business Marketplace, Trade Vouches, & Admin-Validated Scammer Alert System.
- Builds and configures the Growcom Business marketplace channels & private Admin Review Queue.
- /report_scammer: Members submit scammer reports with screenshot proof to #🚨scammer-review-queue.
- ScammerReviewView: Persistent Admin/Owner buttons (✅ Approve & Publish / ❌ Reject) that publish
  validated alerts into #⚠️scammer-alert and notify the reporter via DM.
- /vouch: Members post verified trade vouches in #🤝vouches.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    is_server_manager,
    load_state,
    logger,
    save_state,
)

GROWCOM_BUSINESS_CATEGORY_ID = 1568488507406684170

BUSINESS_CHANNELS_SPEC: list[dict[str, Any]] = [
    {
        "name": "📜trading-info",
        "topic": "Official Growcom Safe Trading Rules, Middleman Guidelines, & Scam Prevention Guide.",
        "read_only": True,
        "welcome_title": "📜 Growcom Marketplace — Safe Trading & Scam Prevention Guide",
        "welcome_color": 0xF1C40F,
        "welcome_desc": (
            "Welcome to **Growcom Business**! Please read and follow these rules before buying, selling, or trading:\n\n"
            "### 🛡️ Golden Rules of Safe Trading\n"
            "1. **Always Check Item Names & Colors:** Color scams and fake item names are common in Growtopia. Hover/tap the item in the trade window before accepting!\n"
            "2. **Never Drop-Trade:** Always use the official in-game Trade Window or a Verified Vending Machine. Never drop World Locks or items outside a trade.\n"
            "3. **Check World Ownership & Locks:** When buying a World, verify there are **no hidden Small Locks / Builder's Locks** with build access enabled.\n"
            "4. **Record or Screenshot High-Value Trades:** Always take a screenshot of the trade window and chat agreement.\n\n"
            "### 🤝 Building Reputation (`#🤝vouches`)\n"
            "- After completing a legitimate trade or service, head to **#🤝vouches** and use **`/vouch`** to build your trading reputation!\n\n"
            "### 🚨 Reporting a Scammer (`/report_scammer`)\n"
            "- If someone scams or attempts to scam you, run **`/report_scammer`** in any channel and attach screenshot proof.\n"
            "- Your report will be sent privately to the **Growcom Admin Team** (`#🚨scammer-review-queue`). Once validated by an Admin or the Server Owner, an official warning will be published in **#⚠️scammer-alert**!"
        ),
    },
    {
        "name": "👕items-and-clothes",
        "topic": "Buy, sell, & trade Wearables, IOTMs, Epics, & Rare Items.",
        "read_only": False,
        "welcome_title": "👕 Items & Clothes Marketplace",
        "welcome_color": 0x3498DB,
        "welcome_desc": (
            "Post your **BUYING** and **SELLING** offers for Wearables, IOTMs, Cosmetics, and Rare Items here!\n\n"
            "- 📌 Include the **Item Name**, **Price (WLs/DLs/BGLs)**, and **World Name** (or DM instruction).\n"
            "- 💡 Use `/item` in `#🔎item-lookup` to inspect item rarity and splice recipes!"
        ),
    },
    {
        "name": "🌾farmables",
        "topic": "Buy & sell Laser Grid, Chandelier, Pepper, Sorcerer Stone, & all Farmable Blocks/Seeds.",
        "read_only": False,
        "welcome_title": "🌾 Farmables Marketplace (Seeds & Blocks)",
        "welcome_color": 0x2ECC71,
        "welcome_desc": (
            "Buy and sell **Farmable Seeds & Blocks** (Laser Grid, Chandelier, Pepper Tree, Fish Tank, etc.) here!\n\n"
            "- 📌 State your **Rate** clearly (e.g., `Selling 2,600 LGrid Seeds 40/1 WL at WORLD`).\n"
            "- 🧮 Use `/rate` in `#🧮rate-calculator` to calculate exact WL/DL/BGL totals!"
        ),
    },
    {
        "name": "🏧vend-shops",
        "topic": "Promote your Vending Machine Worlds, SSP, RSP, & Mall Shops.",
        "read_only": False,
        "welcome_title": "🏧 Vending Machine Shops & SSP/RSP Worlds",
        "welcome_color": 0x9B59B6,
        "welcome_desc": (
            "Promote your **Vending Machine Shops, SSP Worlds, RSP Worlds, and Supply Malls** here!\n\n"
            "- 🌍 Always include your **World Name**, **Featured Stock**, and **Prices**.\n"
            "- 📸 Feel free to attach screenshots of your Vending Machine prices!"
        ),
    },
    {
        "name": "🌍worlds",
        "topic": "Buy & sell Farm Worlds, Dirt Farms, Rare World Names, & Main Worlds.",
        "read_only": False,
        "welcome_title": "🌍 Worlds Marketplace (Farms, Rare Names, & Designs)",
        "welcome_color": 0x1ABC9C,
        "welcome_desc": (
            "Buy and sell **Dirt Farms, Ready-to-Harvest Farms, Rare 2/3/4-Letter World Names, and Main Worlds**!\n\n"
            "- 🔒 Buyers: Always inspect the world for hidden locks before trading via the World Key!"
        ),
    },
    {
        "name": "🛠️services",
        "topic": "Hire or offer Block Breaking, World Building, Role Quests, & Mass Producing services.",
        "read_only": False,
        "welcome_title": "🛠️ Growtopia Services (Breakers, Builders, & Quests)",
        "welcome_color": 0xE67E22,
        "welcome_desc": (
            "Offer or hire **In-Game Services** (Farms/Block Breaking, World Design, Surgery/Role Helpers, Harvest Services)!\n\n"
            "- 🤝 Always ask for and check a provider's vouches in **#🤝vouches** before hiring!"
        ),
    },
    {
        "name": "🤝vouches",
        "topic": "Use /vouch to post verified trade vouches and build your Growcom reputation!",
        "read_only": False,
        "state_key": "vouch_channel_id",
        "welcome_title": "🤝 Growcom Verified Trade Vouches",
        "welcome_color": 0x2ECC71,
        "welcome_desc": (
            "Completed a smooth trade or service with another member? Build their reputation here!\n\n"
            "### ✅ How to Vouch Someone\n"
            "Type **`/vouch`** and fill in:\n"
            "- **`trader`**: Tag the Discord member you traded with\n"
            "- **`trade_details`**: What you bought, sold, or hired them for\n"
            "- **`proof_image`** *(optional)*: Screenshot of the completed trade!"
        ),
    },
    {
        "name": "⚠️scammer-alert",
        "topic": "Official Admin-Verified Scammer Board. Use /report_scammer to submit a report for Admin review!",
        "read_only": True,
        "state_key": "scammer_alert_channel_id",
        "welcome_title": "⚠️ Official Growcom Scammer Alert Board",
        "welcome_color": 0xE74C3C,
        "welcome_desc": (
            "This board displays **Official Scammer Alerts** that have been **reviewed and validated by the Growcom Admin Team**.\n\n"
            "### 🚨 How to Report a Scammer\n"
            "1. Run **`/report_scammer`** in any channel.\n"
            "2. Enter the **Scammer's GrowID**, **Discord Username/ID** (if known), **World Name**, and **Incident Details**.\n"
            "3. Attach a **Screenshot Proof** (`proof_image`) showing the scam or chat logs.\n"
            "4. Your report goes privately to `#🚨scammer-review-queue` where an **Admin or the Server Owner** will verify the evidence and click **Approve & Publish** to post the alert here!"
        ),
    },
]


def _extract_field_value(embed: discord.Embed, name_prefix: str) -> str:
    for field in embed.fields:
        if field.name and name_prefix.lower() in field.name.lower():
            return field.value or "N/A"
    return "N/A"


class ScammerReviewView(discord.ui.View):
    """Persistent Admin/Owner validation buttons attached to every pending scammer report."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve & Publish Alert",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="growcom:scam_approve",
    )
    async def approve_report(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only **Server Administrators** or the **Server Owner** can validate scammer reports!",
                ephemeral=True,
            )
            return

        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message("❌ Could not read the report embed.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        review_embed = interaction.message.embeds[0]

        scammer_growid = _extract_field_value(review_embed, "Scammer GrowID")
        scammer_discord = _extract_field_value(review_embed, "Scammer Discord")
        world_name = _extract_field_value(review_embed, "World Name")
        reporter_text = _extract_field_value(review_embed, "Reported By")
        incident_details = review_embed.description or "No details provided."
        proof_url = review_embed.image.url if review_embed.image else None

        # Find #⚠️scammer-alert channel
        state = load_state()
        alert_channel_id = state.get("scammer_alert_channel_id")
        alert_channel: discord.TextChannel | None = None

        if interaction.guild:
            if alert_channel_id:
                ch = interaction.guild.get_channel(int(alert_channel_id))
                if isinstance(ch, discord.TextChannel):
                    alert_channel = ch
            if not alert_channel:
                for ch in interaction.guild.text_channels:
                    if "scammer-alert" in ch.name.lower():
                        alert_channel = ch
                        state["scammer_alert_channel_id"] = str(ch.id)
                        save_state(state)
                        break

        if not alert_channel:
            await interaction.followup.send(
                "⚠️ Could not find `#⚠️scammer-alert`! Please run `/setup_business_channels` or `/set_scammer_alert_channel` first.",
                ephemeral=True,
            )
            return

        # Build the public verified Scammer Alert embed
        public_embed = discord.Embed(
            title="🚨 OFFICIAL SCAMMER ALERT — VERIFIED BY ADMIN",
            description=(
                f"### 📋 Incident Summary\n"
                f"{incident_details}\n\n"
                f"⚠️ **Do NOT trade or drop items with this player!** Always double-check GrowIDs and Discord IDs before trading."
            ),
            color=0xE74C3C,
            timestamp=datetime.now(EVENT_TZ),
        )
        public_embed.add_field(name="🎮 Scammer GrowID", value=scammer_growid, inline=True)
        public_embed.add_field(name="💬 Scammer Discord", value=scammer_discord, inline=True)
        public_embed.add_field(name="🌍 World Name", value=world_name, inline=True)
        public_embed.add_field(name="🕵️ Reported By", value=reporter_text, inline=True)
        public_embed.add_field(
            name="🛡️ Validated By Admin",
            value=f"{interaction.user.mention} (`{interaction.user}`)",
            inline=True,
        )
        if proof_url:
            public_embed.set_image(url=proof_url)
        public_embed.set_footer(text=FOOTER_TEXT)

        published_msg = await alert_channel.send(embed=public_embed)

        # Update the admin queue message so staff can see it was approved
        updated_review = review_embed.copy()
        updated_review.title = "✅ [APPROVED & PUBLISHED] Scammer Report"
        updated_review.color = 0x2ECC71
        updated_review.add_field(
            name="✅ Admin Decision",
            value=f"Approved by {interaction.user.mention} • [Jump to Public Alert]({published_msg.jump_url})",
            inline=False,
        )

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        await interaction.message.edit(embed=updated_review, view=self)

        # Notify the reporting member via DM if possible
        id_match = re.search(r"<@!?(\d+)>", reporter_text)
        if id_match and interaction.guild:
            reporter_id = int(id_match.group(1))
            reporter_member = interaction.guild.get_member(reporter_id)
            if reporter_member:
                try:
                    dm_embed = discord.Embed(
                        title="✅ Your Scammer Report Was Approved!",
                        description=(
                            f"Thank you for keeping **Growcom** safe! Your scammer report against **{scammer_growid}** "
                            f"was reviewed and validated by {interaction.user.mention}.\n\n"
                            f"📢 **Public Alert Published:** {alert_channel.mention} ([View Alert]({published_msg.jump_url}))"
                        ),
                        color=0x2ECC71,
                        timestamp=datetime.now(EVENT_TZ),
                    )
                    dm_embed.set_footer(text=FOOTER_TEXT)
                    await reporter_member.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

        await interaction.followup.send(
            f"✅ Report approved and published to {alert_channel.mention}!",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Reject Report",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="growcom:scam_reject",
    )
    async def reject_report(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only **Server Administrators** or the **Server Owner** can reject scammer reports!",
                ephemeral=True,
            )
            return

        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message("❌ Could not read the report embed.", ephemeral=True)
            return

        review_embed = interaction.message.embeds[0].copy()
        review_embed.title = "❌ [REJECTED] Scammer Report"
        review_embed.color = 0x95A5A6
        review_embed.add_field(
            name="❌ Admin Decision",
            value=f"Rejected by {interaction.user.mention} (Insufficient proof or invalid report)",
            inline=False,
        )

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        await interaction.response.edit_message(embed=review_embed, view=self)


class BusinessModerationCog(commands.Cog):
    """Growcom Business channels provisioner, Trade Vouch system, and Admin-Approved Scammer Reports."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def cog_load(self) -> None:
        # Register the persistent ScammerReviewView so buttons work across restarts
        self.bot.add_view(ScammerReviewView())

    async def provision_business_and_staff_channels(self, guild: discord.Guild) -> tuple[list[str], list[str]]:
        """
        Idempotently creates the 8 Growcom Business channels and the private 🛡️ Growcom Staff
        category + #🚨scammer-review-queue channel when the bot has Manage Channels / Administrator.
        Returns (created_items, existing_items).
        """
        created: list[str] = []
        existing: list[str] = []
        state = load_state()

        # 1. Locate or create 'Growcom Business' category
        business_cat: discord.CategoryChannel | None = guild.get_channel(GROWCOM_BUSINESS_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(business_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "business" in cat.name.lower():
                    business_cat = cat
                    break
        if not business_cat:
            business_cat = await guild.create_category(
                name="💼 Growcom Business",
                reason="Growcom Business marketplace setup",
            )
            created.append(f"Category: **{business_cat.name}**")

        everyone_role = guild.default_role
        bot_member = guild.me

        # 2. Create each of the 8 Business channels inside Growcom Business
        for spec in BUSINESS_CHANNELS_SPEC:
            ch_name = spec["name"]
            slug = ch_name.lstrip("📜👕🌾🏧🌍🛠️🤝⚠️").strip().lower()

            found_ch: discord.TextChannel | None = None
            for ch in business_cat.text_channels:
                if slug in ch.name.lower():
                    found_ch = ch
                    break

            if not found_ch:
                overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}
                if spec.get("read_only"):
                    overwrites[everyone_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=False,
                        add_reactions=True,
                    )
                    if bot_member:
                        overwrites[bot_member] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            embed_links=True,
                            attach_files=True,
                            manage_messages=True,
                        )

                found_ch = await guild.create_text_channel(
                    name=ch_name,
                    category=business_cat,
                    topic=spec["topic"],
                    overwrites=overwrites,
                    reason="Growcom Business marketplace setup",
                )
                created.append(found_ch.mention)

                # Post welcome / rules card in the newly created channel
                welcome_embed = discord.Embed(
                    title=spec["welcome_title"],
                    description=spec["welcome_desc"],
                    color=spec["welcome_color"],
                    timestamp=datetime.now(EVENT_TZ),
                )
                welcome_embed.set_footer(text=FOOTER_TEXT)
                await found_ch.send(embed=welcome_embed)
            else:
                existing.append(found_ch.mention)

            if spec.get("state_key") and found_ch:
                state[spec["state_key"]] = str(found_ch.id)

        # 3. Locate or create private '🛡️ Growcom Staff' category + '#🚨scammer-review-queue'
        staff_cat: discord.CategoryChannel | None = None
        for cat in guild.categories:
            if "staff" in cat.name.lower() or "admin" in cat.name.lower():
                staff_cat = cat
                break

        staff_overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(view_channel=False),
        }
        if bot_member:
            staff_overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            )
        # Also grant view_channel=True to any role with administrator or manage_guild
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.manage_guild:
                staff_overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

        if not staff_cat:
            staff_cat = await guild.create_category(
                name="🛡️ Growcom Staff",
                overwrites=staff_overwrites,
                reason="Private Admin category for validating scammer reports",
            )
            created.append(f"Private Category: **{staff_cat.name}**")

        review_ch: discord.TextChannel | None = None
        for ch in guild.text_channels:
            if "scammer-review" in ch.name.lower():
                review_ch = ch
                break

        if not review_ch:
            review_ch = await guild.create_text_channel(
                name="🚨scammer-review-queue",
                category=staff_cat,
                topic="Private Admin Queue — Validate or reject member /report_scammer submissions here.",
                overwrites=staff_overwrites,
                reason="Private Admin channel for validating scammer reports",
            )
            created.append(f"{review_ch.mention} *(Admin-Only)*")

            queue_embed = discord.Embed(
                title="🛡️ Growcom Admin Queue — Scammer Report Validation",
                description=(
                    "This channel is **strictly private** to the Server Owner and Administrators.\n\n"
                    "- Whenever a member runs **`/report_scammer`**, their report and screenshot proof appear here.\n"
                    "- Click **`✅ Approve & Publish Alert`** to automatically post the verified warning to **#⚠️scammer-alert** and DM the reporter.\n"
                    "- Click **`❌ Reject Report`** if the report lacks valid proof."
                ),
                color=0xE67E22,
                timestamp=datetime.now(EVENT_TZ),
            )
            queue_embed.set_footer(text=FOOTER_TEXT)
            await review_ch.send(embed=queue_embed)
        else:
            existing.append(review_ch.mention)

        state["scammer_review_channel_id"] = str(review_ch.id)
        save_state(state)
        self._provisioned_guilds.add(guild.id)
        return created, existing

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and (guild.me.guild_permissions.manage_channels or guild.me.guild_permissions.administrator):
                try:
                    created, _ = await self.provision_business_and_staff_channels(guild)
                    if created:
                        logger.info("Auto-provisioned Growcom Business & Staff channels in %s: %s", guild.name, created)
                except Exception as exc:
                    logger.warning("Could not auto-provision business channels in %s: %s", guild.name, exc)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        """If the Server Owner grants Manage Channels / Administrator to the bot role, provision immediately!"""
        guild = after.guild
        if guild.id in self._provisioned_guilds:
            return
        if guild.me and (guild.me.guild_permissions.manage_channels or guild.me.guild_permissions.administrator):
            try:
                created, _ = await self.provision_business_and_staff_channels(guild)
                if created:
                    logger.info("Role updated! Provisioned Growcom Business & Staff channels in %s: %s", guild.name, created)
            except Exception as exc:
                logger.warning("Failed provisioning on role update in %s: %s", guild.name, exc)

    @app_commands.command(
        name="setup_business_channels",
        description="Admin: Automatically create all Growcom Business marketplace & Admin Scammer Review channels.",
    )
    async def setup_business_channels_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only **Server Administrators** or the **Server Owner** can run `/setup_business_channels`!",
                ephemeral=True,
            )
            return

        if not interaction.guild or not interaction.guild.me:
            await interaction.response.send_message("❌ This command can only be used inside a server.", ephemeral=True)
            return

        if not (interaction.guild.me.guild_permissions.manage_channels or interaction.guild.me.guild_permissions.administrator):
            await interaction.response.send_message(
                "⚠️ **Missing Permission!** Please go to **Server Settings → Roles → Growcom Events** and enable "
                "**`Administrator`** (or **`Manage Channels`** + **`Manage Roles`**), then run `/setup_business_channels` again!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        created, existing = await self.provision_business_and_staff_channels(interaction.guild)

        summary = []
        if created:
            summary.append(f"### ✅ Newly Created ({len(created)})\n" + "\n".join(f"- {item}" for item in created))
        if existing:
            summary.append(f"### 📌 Already Configured ({len(existing)})\n" + "\n".join(f"- {item}" for item in existing))

        embed = discord.Embed(
            title="💼 Growcom Business & Admin Review Setup Complete!",
            description="\n\n".join(summary) or "All channels are configured!",
            color=0x2ECC71,
            timestamp=datetime.now(EVENT_TZ),
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="report_scammer",
        description="Submit a scammer report with screenshot proof for Growcom Admin validation.",
    )
    @app_commands.describe(
        scammer_growid="The scammer's in-game GrowID (e.g. Scammer123)",
        details="Explain how the scam happened and what items/WLs were stolen",
        proof_image="Screenshot proof of the scam, trade window, or chat logs (Required)",
        scammer_discord="The scammer's Discord username or ID (if known)",
        world_name="The Growtopia World where the incident happened (optional)",
    )
    async def report_scammer_cmd(
        self,
        interaction: discord.Interaction,
        scammer_growid: str,
        details: str,
        proof_image: discord.Attachment,
        scammer_discord: str = "Unknown / In-Game Only",
        world_name: str = "N/A",
    ) -> None:
        if not proof_image.content_type or not proof_image.content_type.startswith("image/"):
            await interaction.response.send_message(
                "❌ Please attach a valid **image screenshot** (`PNG`, `JPG`, or `WEBP`) as `proof_image` so Admins can verify your report!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        state = load_state()
        review_channel_id = state.get("scammer_review_channel_id")
        review_channel: discord.TextChannel | None = None

        if interaction.guild:
            if review_channel_id:
                ch = interaction.guild.get_channel(int(review_channel_id))
                if isinstance(ch, discord.TextChannel):
                    review_channel = ch
            if not review_channel:
                for ch in interaction.guild.text_channels:
                    if "scammer-review" in ch.name.lower():
                        review_channel = ch
                        state["scammer_review_channel_id"] = str(ch.id)
                        save_state(state)
                        break

        if not review_channel:
            await interaction.followup.send(
                "⚠️ The Admin Review Queue channel (`#🚨scammer-review-queue`) has not been set up yet! "
                "Please ask an Admin to run `/setup_business_channels`.",
                ephemeral=True,
            )
            return

        review_embed = discord.Embed(
            title="🚨 [PENDING ADMIN REVIEW] New Scammer Report",
            description=details.strip(),
            color=0xE67E22,
            timestamp=datetime.now(EVENT_TZ),
        )
        review_embed.add_field(name="🎮 Scammer GrowID", value=f"`{scammer_growid.strip()}`", inline=True)
        review_embed.add_field(name="💬 Scammer Discord", value=scammer_discord.strip(), inline=True)
        review_embed.add_field(name="🌍 World Name", value=f"`{world_name.strip().upper()}`", inline=True)
        review_embed.add_field(
            name="🕵️ Reported By",
            value=f"{interaction.user.mention} (`{interaction.user}`)",
            inline=False,
        )
        review_embed.set_image(url=proof_image.url)
        review_embed.set_footer(text=FOOTER_TEXT)

        await review_channel.send(
            content="🛡️ **Admin Action Required:** Please review the attached evidence below and click **Approve** or **Reject**.",
            embed=review_embed,
            view=ScammerReviewView(),
        )

        confirm_embed = discord.Embed(
            title="📨 Scammer Report Submitted for Admin Validation",
            description=(
                f"Thank you, {interaction.user.mention}! Your report against **`{scammer_growid.strip()}`** "
                f"has been sent privately to the **Growcom Admin Team**.\n\n"
                f"- 🛡️ **Next Step:** An Admin or the Server Owner will inspect your screenshot proof.\n"
                f"- 📢 Once approved, it will be published on the official **#⚠️scammer-alert** board and you will receive a confirmation DM!"
            ),
            color=0x2ECC71,
            timestamp=datetime.now(EVENT_TZ),
        )
        confirm_embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

    @app_commands.command(
        name="vouch",
        description="Post a verified trade vouch for another Growcom member in #🤝vouches!",
    )
    @app_commands.describe(
        trader="The Discord member you completed a trade or service with",
        trade_details="What did you buy, sell, or hire them for? (e.g. 'Bought 2,600 LGrid seeds for 65 WL, fast!')",
        proof_image="Optional screenshot of the completed in-game trade",
    )
    async def vouch_cmd(
        self,
        interaction: discord.Interaction,
        trader: discord.Member,
        trade_details: str,
        proof_image: discord.Attachment | None = None,
    ) -> None:
        if trader.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot vouch for yourself! Ask your trading partner to run `/vouch` for you.",
                ephemeral=True,
            )
            return

        if trader.bot:
            await interaction.response.send_message(
                "❌ You cannot vouch for a bot!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🤝 Verified Growcom Trade Vouch",
            description=f"### 💬 Trade Feedback\n> {trade_details.strip()}",
            color=0x2ECC71,
            timestamp=datetime.now(EVENT_TZ),
        )
        embed.add_field(name="⭐ Vouched Trader", value=f"{trader.mention} (`{trader}`)", inline=True)
        embed.add_field(name="✍️ Vouched By", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=True)
        embed.set_thumbnail(url=trader.display_avatar.url)

        if proof_image and proof_image.content_type and proof_image.content_type.startswith("image/"):
            embed.set_image(url=proof_image.url)

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(content=f"🌟 New trade vouch for {trader.mention}!", embed=embed)

    @app_commands.command(
        name="set_vouch_channel",
        description="Admin: Lock /vouch to a specific channel (e.g. #🤝vouches).",
    )
    async def set_vouch_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return
        state = load_state()
        state["vouch_channel_id"] = str(channel.id)
        save_state(state)
        await interaction.response.send_message(
            f"✅ Locked **`/vouch`** to {channel.mention}!",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_scammer_alert_channel",
        description="Admin: Set the public #⚠️scammer-alert channel where approved reports are published.",
    )
    async def set_scammer_alert_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return
        state = load_state()
        state["scammer_alert_channel_id"] = str(channel.id)
        save_state(state)
        await interaction.response.send_message(
            f"✅ Approved scammer alerts will now be published in {channel.mention}!",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_scammer_review_channel",
        description="Admin: Set the private #🚨scammer-review-queue channel where pending reports arrive.",
    )
    async def set_scammer_review_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return
        state = load_state()
        state["scammer_review_channel_id"] = str(channel.id)
        save_state(state)
        await interaction.response.send_message(
            f"✅ Pending scammer reports will now be sent to {channel.mention} for Admin approval!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BusinessModerationCog(bot))
