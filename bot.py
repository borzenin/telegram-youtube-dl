import asyncio
import logging
from typing import Sequence

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telethon import Button
from telethon import TelegramClient
from telethon.events import NewMessage
from telethon.sessions import StringSession

from bot_events import Handler
from database import ImprovedSession, use_session
from models import (Base, Session, User)
from youtube_dl_manager import YoutubeManager


class YoutubeDownloaderBot:

    def __init__(
            self,
            api_id: int,
            api_hash: str,
            bot_token: str,
            *,
            db_name: str = 'main',
            whitelist: Sequence = None,
            loop: asyncio.AbstractEventLoop = None,
            max_threads=3,
            client: TelegramClient = None):
        """

        :param api_id: application ID
        :param api_hash: application hash
        :param bot_token: Bot Token obtained by @BotFather
        :param db_name: database name (default: 'main')
        :param whitelist: username whitelist
        :param loop: custom event loop
        :param client: custom TelegramClient instance, if provided, other parameters don't matter
        """

        engine = create_engine('sqlite:///{}.db'.format(db_name))
        self.session_cls = sessionmaker(bind=engine, class_=ImprovedSession)
        Base.metadata.create_all(bind=engine)

        self.logger = logging.getLogger('telegram-youtube-dl.bot')
        self.loop = loop or asyncio.get_event_loop()
        self.youtube_manager = YoutubeManager(self.loop, max_threads)
        if whitelist is not None:
            whitelist = set(whitelist)

        if client is not None:
            client.whitelist = whitelist
            self.client = client
            self.client.parse_mode = 'html'
            self.loop = client.loop
            return

        with use_session(self.session_cls) as db_session:
            bot_session = db_session.query(Session.data).filter(Session.bot_token == bot_token).scalar()

            client = TelegramClient(
                StringSession(bot_session),
                api_id,
                api_hash,
                loop=loop
            ).start(bot_token=bot_token)

            if bot_session is None:
                db_session.add(Session(
                    bot_token,
                    api_id,
                    api_hash,
                    client.session.save()
                ))
                db_session.commit()

        client.whitelist = whitelist
        self.client = client
        self.client.parse_mode = 'html'

    async def start(self):
        async with self.client as client:
            Handler.add_handlers_to_bot(self)
            await client.disconnected

    @Handler.register(NewMessage(pattern=r'^/start$'))
    async def on_start(self, event: NewMessage.Event):
        chat_id = event.chat_id
        with use_session(self.session_cls) as db_session:
            exists = db_session.query(db_session.query(User).filter(User.chat_id == chat_id).exists()).scalar()
            if not exists:
                db_session.add(User(chat_id))
                self.logger.debug('New user ({}) was inserted into db'.format(chat_id))
                db_session.commit()

        await event.respond('Welcome to Youtube Downloader Bot!', buttons=Button.clear())
