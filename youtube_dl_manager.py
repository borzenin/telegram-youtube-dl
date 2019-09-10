import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Union


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
