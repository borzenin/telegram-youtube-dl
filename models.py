import enum
from sqlalchemy import Column, Integer, Text, Enum
from sqlalchemy.ext.declarative import declarative_base


def model_repr(instance) -> str:
    class_name = instance.__class__.__name__
    attrs = filter(lambda x: not x[0].startswith('_'), instance.__dict__.items())
    repr_ = "<{}({})>".format(
        class_name,
        ', '.join(map(lambda x: '='.join(x), attrs))
    )
    return repr_


Base = declarative_base()
setattr(Base, '__repr__', model_repr)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Text, nullable=False, unique=True)
    audio_quality = Column(Integer)
    audio_increase = Column(Integer)

    def __init__(self, chat_id, audio_quality=None, audio_increase=None):
        self.chat_id = chat_id
        self.audio_quality = audio_quality
        self.audio_increase = audio_increase


class Session(Base):
    __tablename__ = 'sessions'
    id = Column(Integer, primary_key=True)
    bot_token = Column(Text, nullable=False, unique=True)
    api_id = Column(Integer, nullable=False)
    api_hash = Column(Text, nullable=False)
    data = Column(Text, nullable=False)

    def __init__(self, bot_token, api_id, api_hash, data):
        self.bot_token = bot_token
        self.api_id = api_id
        self.api_hash = api_hash
        self.data = data


class DownloadType(enum.Enum):
    VIDEO = 'vi'
    AUDIO_DEFAULT = 'ad'
    AUDIO_CUSTOM = 'ac'


class AudioQuality(enum.Enum):
    LOW = 8
    MEDIUM = 5
    HIGH = 0


class AudioIncrease(enum.Enum):
    NONE = 0
    INCREASE_5DB = 5
    INCREASE_10DB = 10


class Download(Base):
    __tablename__ = 'downloads'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Text, nullable=False, unique=True)
    download_id = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    duration = Column(Text, nullable=False)
    type = Column(Enum(DownloadType))
    video_format_list = Column(Text)
    audio_quality = Column(Enum(AudioQuality))
    audio_increase = Column(Enum(AudioIncrease))

    def __init__(self, chat_id, download_id, url, title, duration,
                 video_format_list, type=None, audio_quality=None, audio_increase=None):
        self.chat_id = chat_id
        self.download_id = download_id
        self.url = url
        self.title = title
        self.duration = duration
        self.video_format_list = video_format_list
        self.type = type
        self.audio_quality = audio_quality
        self.audio_increase = audio_increase
