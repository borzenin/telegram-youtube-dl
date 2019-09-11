import asyncio
import json
import logging
from math import ceil
from pathlib import Path
from typing import Sequence

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telethon import Button
from telethon import TelegramClient
from telethon.events import NewMessage, CallbackQuery
from telethon.sessions import StringSession

from bot_events import Handler
from database import ImprovedSession, use_session
from models import (Base, Session, User, Download, DownloadType)
from utils import random_string
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

    @Handler.register(NewMessage(pattern=r'^http'))
    async def on_url(self, event: NewMessage.Event):
        if self.youtube_manager.is_downloading(event.chat_id):
            self.logger.debug('Already downloading for {}'.format(event.chat_id))
            await event.respond('Something already downloading. Please wait')
            return

        url: str = event.raw_text
        self.logger.debug('Url received: {}'.format(url))
        target_message = await event.respond('Checking...')
        info = await self.youtube_manager.get_info(url)
        if info is None:
            self.logger.debug('Video was not found')
            await event.respond('Video was not found', buttons=Button.clear())
            return

        download_id = random_string(16)
        with use_session(self.session_cls, autocommit=True) as db_session:
            download = Download(
                event.chat_id,
                download_id,
                url,
                info['title'],
                info['duration'],
                json.dumps(info['formats'])
            )
            db_session.insert_or_replace(download)

        self.logger.debug('Download object was created for {}'.format(info['title'][:30]))
        await event.client.delete_messages(event.chat_id, [event.message.id, target_message.id])

        await event.respond('<b>{}</b>\nChoose download type:'.format(info['title']), buttons=[
            Button.inline('Video', data=f'type_{download_id}_{DownloadType.VIDEO.name}'),
            Button.inline('Audio (default)', data=f'type_{download_id}_{DownloadType.AUDIO_DEFAULT.name}'),
            Button.inline('Audio (custom)', data=f'type_{download_id}_{DownloadType.AUDIO_CUSTOM.name}')
        ])

    @Handler.register(CallbackQuery(pattern=rb'^type_'))
    async def on_download_type_picked(self, event: CallbackQuery.Event):
        download_type = '_'.join(event.data.decode().split('_')[2:])
        self.logger.debug('Download type was picked: {}'.format(download_type))
        await event.delete()

        if download_type == DownloadType.VIDEO.name:
            return await self.on_type_video_picked(event)
        elif download_type == DownloadType.AUDIO_DEFAULT.name:
            return await self.on_type_audio_default_picked(event)
        elif download_type == DownloadType.AUDIO_CUSTOM.name:
            return await self.on_type_audio_custom_picked(event)

        self.logger.error('Invalid type was received: {}'.format(download_type))

    async def on_type_video_picked(self, event: CallbackQuery.Event):
        download_id = event.data.decode().split('_')[1]
        with use_session(self.session_cls) as db_session:
            download = db_session.query(Download).filter(Download.chat_id == event.chat_id).one_or_none()

        if download is None or download.download_id != download_id:
            self.logger.error('Download object was not exists. Skip.')
            await event.delete()
            return

        formats = sorted(
            json.loads(download.video_format_list).items(),
            key=lambda x: int(x[0][:-1])
        )

        # matrix generation
        buttons = [
            [
                Button.inline(
                    '{} ({} Mb)'.format(key, round(value['filesize'] / 1000000, 1)),
                    data='video_{}_{}'.format(download_id, value['format_id'])
                )
                for key, value in formats[i * 3: (i + 1) * 3]
            ]
            for i in range(ceil(len(formats) / 3))
        ]
        await event.respond(
            '<b>{}</b>\nChoose quality (if less then 10 Mb, GIF will be sent): '.format(download.title),
            buttons=buttons
        )

    async def on_type_audio_default_picked(self, event: NewMessage.Event):
        pass

    async def on_type_audio_custom_picked(self, event: NewMessage.Event):
        pass

    @Handler.register(CallbackQuery(pattern=rb'^video_'))
    async def on_video_format_picked(self, event: CallbackQuery.Event):
        splitted_data = event.data.decode().split('_')
        download_id = splitted_data[1]
        format_id = '_'.join(splitted_data[2:])
        self.logger.debug('Video format id was picked: {}'.format(format_id))

        with use_session(self.session_cls) as db_session:
            download = db_session.query(Download).filter(Download.chat_id == event.chat_id).one_or_none()

        if download is None or download.download_id != download_id:
            self.logger.error('Download object was not exists. Skip.')
            await event.delete()
            return

        await event.delete()
        self.logger.debug('Start downloading {}'.format(download.url))
        target_message = await event.respond(
            '<b>{}</b>\nStart downloading. Please wait'.format(download.title),
            buttons=Button.clear()
        )

        video_path = await self.youtube_manager.download_video(download.url, format_id, chat_id=event.chat_id)
        await event.client.delete_messages(event.chat_id, target_message)

        if video_path is None:
            self.logger.error('Cannot download. Error occurred')
            await event.respond('<b>{}</b>\nCannot download. Something wrong'.format(download.title))
            return

        self.logger.debug('Successfully downloaded. Start sending')
        target_message = await event.respond(
            '<b>{}</b>\nSuccessfully downloaded. Start sending'.format(download.title)
        )
        video_message = await event.client.send_file(event.chat_id, video_path)
        await event.client.delete_messages(event.chat_id, target_message)

        if Path(video_path).exists():
            Path(video_path).unlink()

        self.logger.debug('Successfully sent')
        await event.respond(
            '<b>{}</b>\n0:00'.format(download.title),
            reply_to=video_message
        )
