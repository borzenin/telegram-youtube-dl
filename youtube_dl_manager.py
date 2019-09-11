import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Union, Optional

from youtube_dl import YoutubeDL

from utils import random_string


class YoutubeManager:

    def __init__(
            self,
            loop: asyncio.AbstractEventLoop,
            max_threads=3):

        self.loop = loop
        self.executor = ThreadPoolExecutor(max_workers=max_threads)
        self.logger = logging.getLogger('youtube_dl')
        self._downloads = []

    def add_download_flag(self, id_: Union[str, int]):
        self._downloads.append(str(id_))

    def is_downloading(self, id_: Union[str, int]) -> bool:
        return str(id_) in self._downloads

    def remove_download_flag(self, id_: Union[str, int]):
        try:
            self._downloads.remove(str(id_))
        except ValueError:
            pass

    async def get_info(self, url: str) -> Optional[dict]:
        future = self.loop.create_future()
        self.loop.run_in_executor(self.executor, self._get_info, url, future, self.logger)
        return await future

    @staticmethod
    def _get_info(url: str, future: asyncio.Future, logger: logging.Logger):
        try:
            with YoutubeDL({'logger': logger}) as ydl:
                data = ydl.extract_info(url, download=False)
                title = data.get('title', 'No title')
                duration = data.get('duration', 0)
                formats = data.get('formats', None)

                good_formats = {}
                for format in formats:
                    format_id = format.get('format_id', None)
                    ext = format.get('ext', None)
                    format_note = format.get('format_note', None)
                    filesize = format.get('filesize', None)
                    vcodec = format.get('vcodec', None)

                    if ext != 'mp4' or format_id is None or format_note is None or filesize is None:
                        continue

                    if not vcodec.startswith('avc1'):
                        continue

                    if not format_note.endswith('p') or not format_note[:-1].isdigit():
                        continue

                    if good_formats.get(format_note, None) is not None and good_formats[format_note]['filesize'] > int(
                            filesize):
                        continue

                    good_formats[format_note] = {'format_id': format_id, 'filesize': int(filesize)}

            future.set_result({'title': title, 'formats': good_formats, 'duration': duration})

        except Exception:
            future.set_result(None)

    async def download_video(self, url: str, format_id: str, chat_id: Union[str, int] = None) -> Optional[str]:
        """
        :return: path
        """
        future = self.loop.create_future()
        if chat_id is None:
            self.logger.info('Downloading video without chat_id registering')
        else:
            self.add_download_flag(chat_id)

        try:
            self.loop.run_in_executor(self.executor, self._download_video, url, format_id, future, self.logger)
            result = await future
        finally:
            if chat_id is not None:
                self.remove_download_flag(chat_id)

        return result

    @staticmethod
    def _download_video(url: str, format_id: str, future: asyncio.Future, logger: logging.Logger):
        def hook(d: dict):
            if d['status'] == 'finished':
                future.set_result(d['filename'])

        ydl_opts = {
            'format': format_id,
            'outtmpl': 'media/{}.%(ext)s'.format(random_string(16)),
            'logger': logger,
            'progress_hooks': [hook]
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        except Exception:
            future.set_result(None)
        else:
            if not future.done():
                future.set_result(None)
