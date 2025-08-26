"""Main entry point for the Pydantic AI Telegram Bot - 100% Async Architecture."""

import asyncio
import logging
import signal
import sys
from typing import Optional

# Load environment variables before importing other modules
from dotenv import load_dotenv
load_dotenv()

from src.bot.telegram_bot import TelegramBot
from src.config.settings import Settings
from src.agent.ai_agent import AIAgent


class AsyncApplication:
    """Fully async application class that orchestrates the bot and agent."""

    def __init__(self):
        self.settings = Settings()
        self.ai_agent: Optional[AIAgent] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize the AI agent and Telegram bot asynchronously."""
        try:
            logging.info("Initializing application components...")
            
            # Initialize AI agent
            self.ai_agent = AIAgent(self.settings)
            await self.ai_agent.initialize()

            # Initialize Telegram bot
            self.telegram_bot = TelegramBot(self.settings, self.ai_agent)
            await self.telegram_bot.initialize()

            logging.info("Application initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize application: {e}")
            raise

    async def start(self) -> None:
        """Start the application asynchronously."""
        try:
            await self.initialize()
            self.running = True
            
            # Set up signal handling for graceful shutdown
            self._setup_signal_handlers()
            
            logging.info("Starting async application...")

            # Start the Telegram bot polling in a separate task
            polling_task = asyncio.create_task(self.telegram_bot.start_polling_async())
            
            # Wait for shutdown signal or polling task to complete
            try:
                # Create a task for the shutdown event
                shutdown_task = asyncio.create_task(self._shutdown_event.wait())
                
                # Wait for either the polling task or shutdown event to complete
                done, pending = await asyncio.wait(
                    [polling_task, shutdown_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel any pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                        
            except Exception as e:
                logging.error(f"Error during task management: {e}")
                # Cancel the polling task if it's still running
                if not polling_task.done():
                    polling_task.cancel()
                    try:
                        await polling_task
                    except asyncio.CancelledError:
                        pass

        except asyncio.CancelledError:
            logging.info("Application cancelled")
        except Exception as e:
            logging.error(f"Failed to start application: {e}")
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        if not self.running:
            return

        logging.info("Initiating graceful shutdown...")
        self.running = False

        try:
            # Shutdown components in reverse order
            if self.telegram_bot:
                await self.telegram_bot.shutdown()

            if self.ai_agent:
                await self.ai_agent.shutdown()

            logging.info("Application shutdown complete")
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")

    def _setup_signal_handlers(self) -> None:
        """Set up async signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self._handle_shutdown_signal())

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

    async def _handle_shutdown_signal(self) -> None:
        """Handle shutdown signal asynchronously."""
        self._shutdown_event.set()
        # Set running to False to trigger graceful shutdown
        self.running = False


async def main():
    """Fully async main function."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log', mode='a')
        ]
    )

    # Create and start the async application
    app = AsyncApplication()
    await app.start()


if __name__ == "__main__":
    """Entry point for 100% async architecture."""
    try:
        # Run the fully async application
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
    except Exception as e:
        logging.error(f"Application failed: {e}")
        sys.exit(1)
