import os


def curjoin(_file: str) -> str:  # return filepath relative to __file__ (this file)
    return os.path.join(os.path.dirname(__file__), _file)
