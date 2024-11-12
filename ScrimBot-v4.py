import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import pytz

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store available scrims in memory
available_scrims = []

# Channel IDs (replace with actual channel IDs)
SCHEDULE_SCRIM_CHANNEL_ID = 1303676128174805023
LF_SCRIMS_CHANNEL_ID = 1303676104011288678
SCRIM_REQUESTS_CHANNEL_ID = 1303676191747866654

# Create embed for LF-scrims channel
def create_scrim_embed():
    embed = discord.Embed(title="Scrimmage Schedule", color=0x00ff00)
    if available_scrims:
        for idx, scrim in enumerate(available_scrims):
            embed.add_field(
                name=f"Scrim Slot {idx + 1} - {scrim['datetime']}",
                value=f"**Status:** {scrim['status']}",
                inline=False
            )
    else:
        embed.description = "No available scrims. Please check back later."
    return embed

# Update static scrim message in LF-scrims
async def update_scrim_message():
    channel = bot.get_channel(LF_SCRIMS_CHANNEL_ID)
    if channel is None:
        print("LF-scrims channel not found.")
        return
    
    async for message in channel.history(limit=10):
        if message.author == bot.user:
            await message.delete()
    
    scrim_embed = create_scrim_embed()
    view = ScrimView()
    await view.add_accept_buttons()  # Add accept buttons dynamically based on available scrims
    await channel.send(embed=scrim_embed, view=view)

# View with buttons in LF-scrims
class ScrimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Refresh", custom_id="refresh", style=discord.ButtonStyle.secondary))

    async def add_accept_buttons(self):
        # Dynamically add Accept buttons for each available scrim
        if available_scrims:
            for idx, scrim in enumerate(available_scrims):
                if scrim['status'] == "Available":
                    button = discord.ui.Button(label="Accept", custom_id=f"accept_{idx}", style=discord.ButtonStyle.primary)
                    button.callback = self.create_scrim_request_callback(idx)  # Link to specific callback
                    self.add_item(button)

    def create_scrim_request_callback(self, idx):
        async def accept_scrim(interaction: discord.Interaction):
            scrim = available_scrims[idx]
            if scrim['status'] == "Available":
                scrim['status'] = "Pending"
                scrim['captain'] = interaction.user.name
                await update_scrim_message()
                
                channel = bot.get_channel(SCRIM_REQUESTS_CHANNEL_ID)
                if channel:
                    request_message = await channel.send(
                        f"**{interaction.user.name}** has requested a scrim on **{scrim['datetime']}**.",
                        view=ScrimRequestView(idx)
                    )
                    print("Scrim request sent to scrim-requests channel.")
                    await interaction.response.send_message("Scrim request submitted.", ephemeral=True)
                else:
                    print("Scrim-requests channel not found.")
                    await interaction.response.send_message("Scrim-requests channel not found.", ephemeral=True)
            else:
                await interaction.response.send_message("This scrim slot is already pending.", ephemeral=True)
        return accept_scrim

# View for accept/deny buttons in scrim-requests
class ScrimRequestView(discord.ui.View):
    def __init__(self, scrim_id):
        super().__init__(timeout=None)
        self.scrim_id = scrim_id
        self.add_item(discord.ui.Button(label="Accept", custom_id=f"accept_request_{scrim_id}", style=discord.ButtonStyle.success))
        self.add_item(discord.ui.Button(label="Deny", custom_id=f"deny_request_{scrim_id}", style=discord.ButtonStyle.danger))

    @discord.ui.button(label="Accept", custom_id="accept_request", style=discord.ButtonStyle.success)
    async def accept_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        scrim = available_scrims[self.scrim_id]
        scrim['status'] = "Confirmed"
        await update_scrim_message()
        print("Scrim accepted and status updated to Confirmed.")
        await interaction.response.send_message("Scrim confirmed.", ephemeral=True)

    @discord.ui.button(label="Deny", custom_id="deny_request", style=discord.ButtonStyle.danger)
    async def deny_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        scrim = available_scrims[self.scrim_id]
        scrim['status'] = "Available"
        await update_scrim_message()
        print("Scrim denied and status updated back to Available.")
        await interaction.response.send_message("Scrim denied.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"{bot.user} is now running!")
    await update_scrim_message()

@bot.command(name="addscrim")
async def add_scrim(ctx, *, date_time: str):
    """Command to add a scrim slot from schedule-scrim channel."""
    if ctx.channel.id != SCHEDULE_SCRIM_CHANNEL_ID:
        return await ctx.send("You can only add scrims in the schedule-scrim channel.", delete_after=5)

    try:
        # Attempt to parse date and time
        date_time_parsed = datetime.strptime(date_time, "%Y-%m-%d %I:%M %p")
        
        est = pytz.timezone("America/New_York")
        date_time_est = est.localize(date_time_parsed)

        date_time_utc = date_time_est.astimezone(pytz.utc)
        
        date_markdown = f"<t:{int(date_time_parsed.timestamp())}:F>"  # Format to Discord markdown
        available_scrims.append({"datetime": date_markdown, "status": "Available", "captain": None})
        await ctx.send("Scrim added successfully. Confirming to LF-scrims channel...", delete_after=5)
        await update_scrim_message()  # Update the LF-scrims channel with the new scrim
    except ValueError:
        await ctx.send("Could not parse the date and time. Please use YYYY-MM-DD HH:MM format.", delete_after=5)

@bot.command(name="deletescrim")
async def delete_scrim(ctx, index: int):
    """Command to delete a scrim slot by its index in schedule-scrim channel."""
    if ctx.channel.id != SCHEDULE_SCRIM_CHANNEL_ID:
        return await ctx.send("You can only delete scrims in the schedule-scrim channel.", delete_after=5)

    try:
        # Adjust index for 0-based list access
        scrim_to_delete = index - 1
        if scrim_to_delete < 0 or scrim_to_delete >= len(available_scrims):
            await ctx.send("Invalid scrim slot number.", delete_after=5)
            return
        
        # Remove the scrim from the list
        deleted_scrim = available_scrims.pop(scrim_to_delete)
        print(f"Scrim on {deleted_scrim['datetime']} has been deleted.")

        # Notify the user and update the scrim list in LF-scrims
        await ctx.send(f"Scrim on {deleted_scrim['datetime']} has been deleted.", delete_after=5)
        await update_scrim_message()

    except Exception as e:
        print(f"An error occurred while deleting scrim: {e}")
        await ctx.send("An error occurred. Please try again.", delete_after=5)
        
bot.run("token")
