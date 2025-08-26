"""Telegram bot implementation with polling mechanism."""

import asyncio
import logging
import sys
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from src.agent.ai_agent import AIAgent
from src.config.settings import Settings


logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot with polling mechanism and AI integration."""

    def __init__(self, settings: Settings, ai_agent: AIAgent):
        """Initialize the Telegram bot.

        Args:
            settings: Application configuration
            ai_agent: The AI agent for generating responses
        """
        self.settings = settings
        self.ai_agent = ai_agent
        self.application: Optional[Application] = None
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the Telegram bot application."""
        try:
            logger.info("Initializing Telegram bot...")

            # Create the application
            self.application = Application.builder().token(self.settings.telegram_bot_token).build()

            # Add command handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            
            # Conversation management commands
            self.application.add_handler(CommandHandler("clear", self.clear_history_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("history", self.history_command))

            # Add message handler for all text messages
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )

            # Add error handler
            self.application.add_error_handler(self.error_handler)

            self.initialized = True
            logger.info("Telegram bot initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            raise


    
    async def start_polling_async(self) -> None:
        """Start the bot polling for messages (fully async implementation)."""
        if not self.initialized or not self.application:
            raise RuntimeError("Bot not initialized")

        logger.info("Starting Telegram bot polling (fully async)...")
        try:
            # Use manual lifecycle management when already in an async context
            # This avoids the "event loop is already running" error
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                poll_interval=self.settings.polling_interval,
                timeout=self.settings.request_timeout
            )
            
            # Keep polling until cancelled or shutdown
            try:
                while self.initialized:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("Polling cancelled")
                        
        except asyncio.CancelledError:
            logger.info("Polling cancelled")
        except Exception as e:
            logger.error(f"Error during async polling: {e}")
            raise
        finally:
            # Stop the updater and application gracefully
            try:
                if self.application:
                    await self.application.updater.stop()
                    await self.application.stop()
                    await self.application.shutdown()
            except Exception as e:
                logger.error(f"Error during polling cleanup: {e}")

    async def shutdown(self) -> None:
        """Shutdown the bot gracefully (fully async)."""
        if self.initialized:
            logger.info("Stopping Telegram bot...")
            self.initialized = False  # This will trigger the polling loop to exit
            
            try:
                # The application context manager in start_polling_async handles shutdown
                # We just need to set the flag and let the context manager clean up
                logger.info("Telegram bot shutdown complete")
            except Exception as e:
                logger.error(f"Error during bot shutdown: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command."""
        try:
            user = update.effective_user
            welcome_message = (
                f"Hello {user.mention_html()}! 👋\n\n"
                "I'm an AI-powered bot that can help you with various questions and tasks. "
                "Just send me a message and I'll do my best to assist you!\n\n"
                "Use /help to see available commands."
            )

            await update.message.reply_html(welcome_message)

        except Exception as e:
            logger.error(f"Error handling start command: {e}")
            await self._send_error_message(update)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command."""
        try:
            help_message = (
                "🤖 <b>AI Assistant Bot</b>\n\n"
                "I'm here to help you with:\n"
                "• Answering questions\n"
                "• Providing information\n"
                "• Having conversations\n"
                "• And much more!\n\n"
                "<b>Commands:</b>\n"
                "/start - Start the bot\n"
                "/help - Show this help message\n"
                "/status - Check bot status\n"
                "/clear - Clear conversation history\n"
                "/stats - View your conversation statistics\n"
                "/history - View recent conversation history\n\n"
                "Just send me any message to get started!\n"
                "💡 <i>I remember our conversation history to provide better responses!</i>"
            )

            await update.message.reply_html(help_message)

        except Exception as e:
            logger.error(f"Error handling help command: {e}")
            await self._send_error_message(update)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /status command."""
        try:
            ai_status = "✅ Online" if self.ai_agent.is_ready() else "❌ Offline"
            bot_status = "✅ Online" if self.initialized else "❌ Offline"

            status_message = (
                "📊 <b>Bot Status</b>\n\n"
                f"🤖 AI Agent: {ai_status}\n"
                f"📱 Telegram Bot: {bot_status}\n\n"
                "Everything is working perfectly!" if self.ai_agent.is_ready() and self.initialized
                else "Some services may be unavailable."
            )

            await update.message.reply_html(status_message)

        except Exception as e:
            logger.error(f"Error handling status command: {e}")
            await self._send_error_message(update)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages."""
        try:
            if not update.message or not update.message.text:
                return

            user_id = str(update.effective_user.id) if update.effective_user else None
            message_text = update.message.text.strip()

            if not message_text:
                return

            logger.info(f"Processing message from user {user_id}: {message_text[:50]}...")

            # Show typing indicator
            await update.message.chat.send_action("typing")

            # Generate AI response
            response = await self.ai_agent.generate_response(message_text, user_id)

            # Send the response
            await update.message.reply_text(
                response,
                parse_mode=None,  # Disable HTML parsing for safety
                disable_web_page_preview=True
            )

            logger.info(f"Sent response to user {user_id}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self._send_error_message(update)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur during bot operation."""
        logger.error(f"Bot error - Update: {update}, Context: {context.error}")

        # Try to send error message to user if possible
        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Sorry, I encountered an unexpected error. Please try again later."
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    async def _send_error_message(self, update: Update) -> None:
        """Send a generic error message to the user."""
        try:
            if update.effective_chat:
                await update.effective_chat.send_message(
                    "Sorry, I encountered an error. Please try again later."
                )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def clear_history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /clear command to clear conversation history."""
        try:
            user_id = str(update.effective_user.id) if update.effective_user else None
            
            if not user_id:
                await update.message.reply_text("Error: Unable to identify user.")
                return
            
            # Check if AI agent has conversation manager
            if not hasattr(self.ai_agent, 'conversation_manager') or not self.ai_agent.conversation_manager:
                await update.message.reply_text(
                    "💡 Conversation persistence is currently disabled. "
                    "Your messages are not being stored, so there's no history to clear."
                )
                return
            
            # Clear conversation history
            success = await self.ai_agent.conversation_manager.clear_conversation_history(user_id)
            
            if success:
                await update.message.reply_html(
                    "🧹 <b>Conversation History Cleared!</b>\n\n"
                    "Your conversation history has been cleared. "
                    "Our next conversation will start fresh!"
                )
            else:
                await update.message.reply_text(
                    "ℹ️ No conversation history found to clear."
                )
                
        except Exception as e:
            logger.error(f"Error handling clear command: {e}")
            await self._send_error_message(update)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /stats command to show conversation statistics."""
        try:
            user_id = str(update.effective_user.id) if update.effective_user else None
            
            if not user_id:
                await update.message.reply_text("Error: Unable to identify user.")
                return
            
            # Check if AI agent has conversation manager
            if not hasattr(self.ai_agent, 'conversation_manager') or not self.ai_agent.conversation_manager:
                await update.message.reply_text(
                    "💡 Conversation persistence is currently disabled. "
                    "No statistics are being tracked."
                )
                return
            
            # Get user statistics
            stats = await self.ai_agent.conversation_manager.get_user_stats(user_id)
            
            if not stats:
                await update.message.reply_text("📊 No conversation statistics available.")
                return
            
            stats_message = (
                "📊 <b>Your Conversation Statistics</b>\n\n"
                f"💬 Total Conversations: {stats.total_conversations}\n"
                f"📝 Total Messages: {stats.total_messages}\n"
                f"🔄 Active Conversations: {stats.active_conversations}\n"
                f"📈 Avg Messages/Conversation: {stats.avg_messages_per_conversation:.1f}\n"
            )
            
            if stats.last_activity:
                stats_message += f"🕒 Last Activity: {stats.last_activity.strftime('%Y-%m-%d %H:%M UTC')}\n"
            
            await update.message.reply_html(stats_message)
                
        except Exception as e:
            logger.error(f"Error handling stats command: {e}")
            await self._send_error_message(update)
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /history command to show recent conversation history."""
        try:
            user_id = str(update.effective_user.id) if update.effective_user else None
            
            if not user_id:
                await update.message.reply_text("Error: Unable to identify user.")
                return
            
            # Check if AI agent has conversation manager
            if not hasattr(self.ai_agent, 'conversation_manager') or not self.ai_agent.conversation_manager:
                await update.message.reply_text(
                    "💡 Conversation persistence is currently disabled. "
                    "No conversation history is available."
                )
                return
            
            # Get recent conversation context
            context_messages = await self.ai_agent.conversation_manager.get_conversation_context(user_id)
            
            if not context_messages:
                await update.message.reply_text(
                    "📝 No conversation history found. "
                    "Start chatting with me to build up our conversation!"
                )
                return
            
            # Build history message (limit to recent messages to avoid huge messages)
            history_parts = ["📝 <b>Recent Conversation History</b>\n"]
            
            # Show last 10 messages maximum
            recent_messages = [msg for msg in context_messages 
                             if (msg.role.value if hasattr(msg.role, 'value') else str(msg.role)) != "system"][-10:]
            
            for msg in recent_messages:
                timestamp = msg.timestamp.strftime('%H:%M')
                role_value = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
                
                if role_value == "user":
                    history_parts.append(f"👤 <b>[{timestamp}] You:</b> {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")
                elif role_value == "assistant":
                    history_parts.append(f"🤖 <b>[{timestamp}] Me:</b> {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")
            
            history_message = "\n\n".join(history_parts)
            
            # Telegram has a message length limit
            if len(history_message) > 3500:
                history_message = history_message[:3500] + "\n\n<i>... (truncated)</i>"
            
            await update.message.reply_html(history_message)
                
        except Exception as e:
            logger.error(f"Error handling history command: {e}")
            await self._send_error_message(update)
    
    def is_ready(self) -> bool:
        """Check if the bot is ready to process messages."""
        return self.initialized and self.application is not None
