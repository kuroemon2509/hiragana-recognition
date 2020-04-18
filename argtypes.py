# extension for argparse (argument types)
import os
import json
import traceback
from argparse import ArgumentTypeError

from constants import *
from logger import *
from serializable import *


def positive_int(string: str):
    # reference https://docs.python.org/3/library/argparse.html#type
    value = int(string)
    if value < 1:
        raise ArgumentTypeError(f'{repr(string)} is not a positive integer!')  # noqa

    return value


def directory(string: str):
    if not os.path.exists(string):
        raise ArgumentTypeError(f'{repr(string)} does not exist!')
    elif not os.path.isdir(string):
        raise ArgumentTypeError(f'{repr(string)} is not a directory!')

    return string


def valid_filename(string: str):
    for c in INVALID_FILENAME_CHARS:
        if c in string:
            raise ArgumentTypeError(f'Filename contains {c} character!')

    return string


def labelfile_compatible_json(string: str) -> LabelFile:
    if not os.path.exists(string):
        raise ArgumentTypeError(f'{repr(string)} does not exist!')
    elif not os.path.isfile(string):
        raise ArgumentTypeError(f'{repr(string)} is not a file!')

    try:
        with open(string, mode='r', encoding='utf-8') as infile:
            obj = json.load(infile)

        return LabelFile.parse_obj(obj)

    except Exception as ex:
        error(repr(ex))
        raise ArgumentTypeError(f'{repr(string)} has some problems!')


def metadatafile_compatible_json(string: str) -> DatasetMetadata:
    if not os.path.exists(string):
        raise ArgumentTypeError(f'{repr(string)} does not exist!')
    elif not os.path.isfile(string):
        raise ArgumentTypeError(f'{repr(string)} is not a file!')

    try:
        with open(string, mode='r', encoding='utf-8') as infile:
            obj = json.load(infile)

        return DatasetMetadata.parse_obj(obj)

    except Exception as ex:
        error(repr(ex))
        raise ArgumentTypeError(f'{repr(string)} has some problems!')


def valid_port_number(string: str):
    try:
        port_number = int(string)
        if port_number < 1024 and port_number > (2**16 - 1):
            raise ArgumentTypeError(f'Port number ({port_number}) must be between 1024 and 65535!')  # noqa

        return port_number
    except ValueError as ex:
        # traceback.print_exc()
        error(repr(ex))
        raise ArgumentTypeError(repr(ex))
