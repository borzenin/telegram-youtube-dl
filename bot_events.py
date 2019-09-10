from functools import wraps
from typing import Optional

from telethon import events


class Handler:
    handlers = []

    @classmethod
    def register(cls, event):
        event.incoming = True
        filter_function = event.func
        event.func = lambda e: cls.whitelist_guard(e, filter_function)

        def _register(func):
            wrapper = events.register(event)(func)
            cls.handlers.append(wrapper)
            return wrapper

        return _register

    @staticmethod
    def whitelist_guard(event, func):
        if not event.is_private:
            return False

        whitelist: Optional[set] = event.client.whitelist
        if whitelist is None:
            return True

        username = event.sender.username
        if username is None:
            return False

        if username not in whitelist:
            return False

        if func is None:
            return True

        return func(event)

    @classmethod
    def add_self(cls, bot):
        def _add_self(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                await func(bot, *args, **kwargs)

            return wrapper

        return _add_self

    @classmethod
    def add_handlers_to_bot(cls, bot):
        for handler in cls.handlers:
            bot.client.add_event_handler(cls.add_self(bot)(handler))
