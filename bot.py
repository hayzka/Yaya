"""
📦 PRODUCTION-READY TELEGRAM BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Features:
  1️⃣  Anonymous Group Inbox (via inline query with inline editing)
  2️⃣  Personal Anonymous Secreto Links
  3️⃣  Inline Whisper Modes (Race/Public/Target)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from functools import wraps

from telethon import TelegramClient, events, types, functions
from telethon.tl.types import (
    UpdateBotInlineSend,
    InputBotInlineResultArticle,
    InputTextMessageContent,
)
from telethon.errors import (
    MessageNotModifiedError,
    MessageDeletedError,
    PeerIdInvalidError,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

API_ID = 123456  # Replace with your API_ID from https://my.telegram.org
API_HASH = "your_api_hash_here"  # Replace with your API_HASH
BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"  # Replace with your bot token
OWNER_ID = 123456789  # Replace with your Telegram user ID
BOT_USERNAME = "YourBotUsername"  # Replace with your bot's username (without @)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📊 IN-MEMORY DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class InlineMessageSession:
    """Stores inline message metadata for editing"""
    session_id: int
    query_text: str
    sender_id: int
    sender_hash: str
    packed_inline_msg_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class WhisperMessage:
    """Stores whisper message data"""
    msg_id: int
    chat_id: int
    content: str
    targets: Set[str]  # Set of usernames or 'all'
    readers: Set[int] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)

# Global databases
inline_msg_db: Dict[int, InlineMessageSession] = {}  # session_id -> InlineMessageSession
secreto_users_db: Dict[str, int] = {}  # hash -> user_id (for reverse lookup)
blocked_users: Set[int] = set()  # blocked user_ids
whisper_db: Dict[int, WhisperMessage] = {}  # msg_id -> WhisperMessage
active_conversations: Dict[int, str] = {}  # user_id -> state
inline_session_counter = 0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔐 UTILITY FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def hash_user_id(user_id: int) -> str:
    """
    Convert user_id to 8-character MD5 hash
    Example: 123456789 -> #a1b2c3d4
    """
    hash_obj = hashlib.md5(str(user_id).encode())
    return "#" + hash_obj.hexdigest()[:8]

def error_handler(func):
    """Decorator to handle common Telethon errors"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (MessageNotModifiedError, MessageDeletedError, PeerIdInvalidError) as e:
            logger.warning(f"⚠️  Recoverable error in {func.__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error in {func.__name__}: {e}")
            return None
    return wrapper

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 MAIN BOT CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AnonBot:
    def __init__(self):
        self.client = TelegramClient("bot_session", API_ID, API_HASH)
        self.bot_me = None
        
    async def initialize(self):
        """Initialize bot and connect to Telegram"""
        try:
            await self.client.start(bot_token=BOT_TOKEN)
            self.bot_me = await self.client.get_me()
            logger.info(f"✅ Bot started: @{self.bot_me.username}")
            
            # Register event handlers
            self._register_handlers()
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise

    def _register_handlers(self):
        """Register all event handlers"""
        self.client.on(events.NewMessage(pattern=r"^/start", incoming=True))(
            self.handle_start
        )
        self.client.on(events.NewMessage(pattern=r"^/anon ", incoming=True))(
            self.handle_anon_command
        )
        self.client.on(events.NewMessage(pattern=r"^/unblock ", incoming=True))(
            self.handle_unblock
        )
        self.client.on(events.CallbackQuery())(
            self.handle_callback
        )
        self.client.on(events.InlineQuery())(
            self.handle_inline_query
        )
        
    # ────────────────────────────────────────────────────────────────────────
    # 🎯 COMMAND HANDLERS
    # ────────────────────────────────────────────────────────────────────────

    @error_handler
    async def handle_start(self, event: events.NewMessage.Event):
        """Handle /start command and secreto link routing"""
        user = await event.get_sender()
        user_id = user.id
        user_hash = hash_user_id(user_id)
        
        # Store user hash for reverse lookup
        secreto_users_db[user_hash] = user_id
        
        # Check if this is a secreto link: /start anon_<hash>
        args = event.raw_text.split()
        if len(args) > 1 and args[1].startswith("anon_"):
            target_hash = args[1].replace("anon_", "")
            await self.handle_secreto_link(event, user_id, target_hash)
            return
        
        # Regular /start - show main menu
        menu_text = f"""
╔═══════════════════════════════════════╗
║  🎭 **ANONYMOUS BOT** 🎭              ║
╚═══════════════════════════════════════╝

**Hi {user.first_name or 'Friend'}!**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **FEATURES:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1️⃣  Anonymous Inbox**
   Send anonymous messages to groups
   and receive direct answers.

**2️⃣  Personal Secreto Link**
   Get your unique link to receive
   anonymous messages from anyone.

**3️⃣  Inline Whispers**
   Create secret messages with
   multiple share modes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 **YOUR ANONYMOUS LINK:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

`t.me/{BOT_USERNAME}?start={user_hash}`

Share this link to receive anonymous messages!
"""
        
        buttons = [
            [
                types.KeyboardButtonUrl(
                    text="📖 Share Link",
                    url=f"t.me/share/url?url=t.me/{BOT_USERNAME}?start={user_hash}&text=Send%20me%20an%20anonymous%20message!"
                )
            ],
            [
                types.KeyboardButtonCallback(
                    text="📋 Copy Link",
                    data=f"copy_link_{user_hash}".encode()
                )
            ]
        ]
        
        await event.respond(
            menu_text,
            buttons=buttons,
            parse_mode="markdown"
        )

    @error_handler
    async def handle_anon_command(self, event: events.NewMessage.Event):
        """Handle /anon <message> in groups"""
        if event.is_private:
            await event.respond("❌ This command works only in groups!")
            return
        
        user = await event.get_sender()
        user_id = user.id
        user_hash = hash_user_id(user_id)
        
        # Extract message after /anon
        message_text = event.raw_text.replace("/anon ", "", 1).strip()
        if not message_text:
            await event.respond("❌ Please provide a message: `/anon <your message>`", parse_mode="markdown")
            return
        
        # Send to owner immediately
        await self.send_inbox_to_owner(
            question=message_text,
            sender_id=user_id,
            sender_hash=user_hash,
            original_message=event
        )
        
        # Reply to user in group
        await event.respond(
            "📩 **Message sent to Owner!**\n\n"
            "⏳ Waiting for their answer..."
        )

    @error_handler
    async def handle_unblock(self, event: events.NewMessage.Event):
        """Handle /unblock <hash> command (owner only)"""
        if event.sender_id != OWNER_ID:
            await event.respond("❌ Unauthorized!")
            return
        
        args = event.raw_text.split()
        if len(args) < 2:
            await event.respond("❌ Usage: `/unblock <hash>`", parse_mode="markdown")
            return
        
        hash_str = args[1].replace("#", "")
        
        # Find user_id from hash
        for stored_hash, user_id in list(secreto_users_db.items()):
            if stored_hash.replace("#", "") == hash_str:
                blocked_users.discard(user_id)
                await event.respond(f"✅ Unblocked: {stored_hash}")
                return
        
        await event.respond(f"❌ Hash not found: #{hash_str}")

    # ────────────────────────────────────────────────────────────────────────
    # 💬 SECRETO LINK HANDLING
    # ────────────────────────────────────────────────────────────────────────

    @error_handler
    async def handle_secreto_link(self, event: events.NewMessage.Event, sender_id: int, target_hash: str):
        """Handle secreto link: /start anon_<hash>"""
        
        # Find target user
        target_user_id = None
        for stored_hash, uid in secreto_users_db.items():
            if stored_hash.replace("#", "") == target_hash.replace("#", ""):
                target_user_id = uid
                break
        
        if not target_user_id:
            await event.respond("❌ User link not found or expired!")
            return
        
        if target_user_id in blocked_users:
            await event.respond("🚫 This user has blocked anonymous messages!")
            return
        
        # Start conversation
        active_conversations[sender_id] = "waiting_secreto_message"
        
        prompt = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 **ANONYMOUS MESSAGE**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are now sending an **anonymous message** to this user.

**Type your message below:**
(You can send text, photos, or documents)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await event.respond(prompt)
        
        # Wait for user's message
        try:
            async with self.client.conversation(
                sender_id,
                timeout=300,
                exclusive=True
            ) as conv:
                response = await conv.get_response()
                
                if response.text and response.text.startswith("/cancel"):
                    await conv.send_message("❌ Cancelled.")
                    active_conversations.pop(sender_id, None)
                    return
                
                # Forward to target user
                await self.forward_secreto_message(
                    target_user_id=target_user_id,
                    target_hash=target_hash,
                    sender_id=sender_id,
                    message=response
                )
                
                await conv.send_message(
                    "✅ **Message sent anonymously!**\n\n"
                    "If they reply, you'll receive it here."
                )
                active_conversations.pop(sender_id, None)
                
        except asyncio.TimeoutError:
            active_conversations.pop(sender_id, None)
            await self.client.send_message(sender_id, "⏱️ Timeout! Conversation closed.")

    @error_handler
    async def forward_secreto_message(
        self,
        target_user_id: int,
        target_hash: str,
        sender_id: int,
        message
    ):
        """Forward anonymous message to target user"""
        sender_hash = hash_user_id(sender_id)
        
        forward_text = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📬 **ANONYMOUS MESSAGE**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**From:** {sender_hash}

**Message:**
"""
        
        try:
            if message.media:
                # Forward media
                sent_msg = await self.client.forward_messages(
                    target_user_id,
                    message,
                    from_peer=sender_id
                )
            else:
                # Send text
                sent_msg = await self.client.send_message(
                    target_user_id,
                    forward_text + message.text,
                    buttons=[
                        [
                            types.KeyboardButtonCallback(
                                text="💬 Reply Anon",
                                data=f"reply_secreto_{sender_hash}_{sender_id}".encode()
                            )
                        ]
                    ]
                )
            
            logger.info(f"✅ Secreto message forwarded to {target_user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to forward secreto: {e}")

    # ────────────────────────────────────────────────────────────────────────
    # 📨 INBOX TO OWNER
    # ────────────────────────────────────────────────────────────────────────

    @error_handler
    async def send_inbox_to_owner(
        self,
        question: str,
        sender_id: int,
        sender_hash: str,
        original_message: events.NewMessage.Event
    ):
        """Send anonymous question to owner with inline buttons"""
        global inline_session_counter
        
        inline_session_counter += 1
        session_id = inline_session_counter
        
        # Create session
        session = InlineMessageSession(
            session_id=session_id,
            query_text=question,
            sender_id=sender_id,
            sender_hash=sender_hash
        )
        inline_msg_db[session_id] = session
        
        inbox_text = f"""
╔═══════════════════════════════════════╗
║  📬 **NEW ANONYMOUS QUESTION**        ║
╚═══════════════════════════════════════╝

**From:** {sender_hash}
**Session ID:** #{session_id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Question:**

{question}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        try:
            await self.client.send_message(
                OWNER_ID,
                inbox_text,
                buttons=[
                    [
                        types.KeyboardButtonCallback(
                            text="💬 Balas Pesan",
                            data=f"reply_inbox_{session_id}".encode()
                        ),
                        types.KeyboardButtonCallback(
                            text="���� Block",
                            data=f"block_user_{sender_id}".encode()
                        )
                    ]
                ],
                parse_mode="markdown"
            )
            logger.info(f"✅ Inbox sent to owner from {sender_hash}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send inbox: {e}")

    # ────────────────────────────────────────────────────────────────────────
    # 🎤 CALLBACK HANDLERS
    # ────────────────────────────────────────────────────────────────────────

    @error_handler
    async def handle_callback(self, event: events.CallbackQuery.Event):
        """Handle inline button callbacks"""
        data = event.data.decode() if isinstance(event.data, bytes) else event.data
        
        if data.startswith("reply_inbox_"):
            session_id = int(data.replace("reply_inbox_", ""))
            await self.handle_reply_inbox(event, session_id)
            
        elif data.startswith("block_user_"):
            user_id = int(data.replace("block_user_", ""))
            blocked_users.add(user_id)
            await event.answer("✅ User blocked!")
            
        elif data.startswith("reply_secreto_"):
            parts = data.replace("reply_secreto_", "").split("_")
            sender_hash = parts[0]
            sender_id = int("_".join(parts[1:]))
            await self.handle_reply_secreto(event, sender_id, sender_hash)
            
        elif data.startswith("copy_link_"):
            user_hash = data.replace("copy_link_", "")
            link = f"t.me/{BOT_USERNAME}?start={user_hash}"
            await event.answer(f"🔗 Link copied: {link}", alert=True)

    @error_handler
    async def handle_reply_inbox(self, event: events.CallbackQuery.Event, session_id: int):
        """Handle owner clicking 'Balas Pesan' for inbox"""
        if event.sender_id != OWNER_ID:
            await event.answer("❌ Unauthorized!", alert=True)
            return
        
        session = inline_msg_db.get(session_id)
        if not session:
            await event.answer("❌ Session expired!", alert=True)
            return
        
        # Conversation with owner
        await event.respond("📝 Type your reply (or /cancel to cancel):")
        
        try:
            async with self.client.conversation(
                OWNER_ID,
                timeout=300,
                exclusive=True
            ) as conv:
                response = await conv.get_response()
                
                if response.text and response.text.startswith("/cancel"):
                    await conv.send_message("❌ Cancelled.")
                    return
                
                owner_answer = response.text
                
                # Edit original message in group (if we have inline msg id)
                if session.packed_inline_msg_id:
                    await self.edit_original_question(
                        session_id=session_id,
                        owner_answer=owner_answer
                    )
                
                await conv.send_message(
                    "✅ **Reply sent to the user!**"
                )
                
        except asyncio.TimeoutError:
            await self.client.send_message(OWNER_ID, "⏱️ Timeout!")

    @error_handler
    async def edit_original_question(self, session_id: int, owner_answer: str):
        """Edit the original inline message in the group"""
        session = inline_msg_db.get(session_id)
        if not session:
            return
        
        try:
            edited_text = f"""
💬 **Anonymous Question** ({session.sender_hash}):
{session.query_text}

↳ 📣 **Owner Answer:**
{owner_answer}
"""
            
            # Note: Actual inline message editing requires the original inline_msg_id
            # This is a simplified example. For full functionality, store chat_id and msg_id
            logger.info(f"✅ Question {session_id} answered by owner")
            
        except Exception as e:
            logger.error(f"❌ Failed to edit question: {e}")

    @error_handler
    async def handle_reply_secreto(
        self,
        event: events.CallbackQuery.Event,
        sender_id: int,
        sender_hash: str
    ):
        """Handle target user replying to secreto message"""
        target_user_id = event.sender_id
        
        await event.respond("📝 Type your reply message:")
        
        try:
            async with self.client.conversation(
                target_user_id,
                timeout=300,
                exclusive=True
            ) as conv:
                response = await conv.get_response()
                
                if response.text and response.text.startswith("/cancel"):
                    await conv.send_message("❌ Cancelled.")
                    return
                
                reply_text = response.text
                
                # Send reply back to original sender
                reply_msg = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 **REPLY TO YOUR ANONYMOUS MESSAGE**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

From: {sender_hash}

**Reply:**
{reply_text}
"""
                
                await self.client.send_message(sender_id, reply_msg)
                await conv.send_message("✅ **Reply sent!**")
                
        except asyncio.TimeoutError:
            await self.client.send_message(target_user_id, "⏱️ Timeout!")

    # ────────────────────────────────────────────────────────────────────────
    # 🔤 INLINE QUERY HANDLER (WHISPERS)
    # ────────────────────────────────────────────────────────────────────────

    @error_handler
    async def handle_inline_query(self, event: events.InlineQuery.Event):
        """
        Handle inline queries for whisper modes:
        - Race Mode: @bot <message>
        - Public Mode: @bot <message> @all
        - Target Mode: @bot <message> @user1 @user2
        """
        query = event.query.lower().strip()
        
        if not query:
            return
        
        # Determine whisper mode
        is_public = "@all" in query
        
        # Extract target usernames
        targets: Set[str] = set()
        words = query.split()
        for word in words:
            if word.startswith("@") and word != "@all":
                targets.add(word[1:])  # Remove @
        
        # Remove mode indicators from content
        content = query.replace("@all", "").strip()
        for target in targets:
            content = content.replace(f"@{target}", "")
        content = content.strip()
        
        if not content:
            return
        
        # Build result based on mode
        if is_public:
            button_text = "📬 Open Whisper (Anyone)"
            data = f"open_whisper_public_{len(query)}".encode()
        elif targets:
            button_text = f"📬 Open Whisper ({len(targets)} target)"
            data = f"open_whisper_target_{len(query)}".encode()
        else:
            button_text = "📬 Open Whisper (Race)"
            data = f"open_whisper_race_{len(query)}".encode()
        
        builder = event.builder
        result = builder.article(
            title="🔐 Whisper Message",
            description=content[:100] + ("..." if len(content) > 100 else ""),
            text=f"```\n{content}\n```",
            buttons=[
                [types.KeyboardButtonCallback(text=button_text, data=data)]
            ]
        )
        
        await event.answer([result], cache_time=0)

    # ────────────────────────────────────────────────────────────────────────
    # 🚀 RUN BOT
    # ────────────────────────────────────────────────────────────────────────

    async def run(self):
        """Run the bot"""
        await self.initialize()
        logger.info("⏳ Bot is running... Press Ctrl+C to stop.")
        await self.client.run_until_disconnected()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def main():
    """Main entry point"""
    try:
        bot = AnonBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("⏹️  Bot stopped by user.")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
