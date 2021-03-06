#!/usr/bin/env python3
import os
import sys
import time
import re
import json
import base64
import argparse
from typing import List, Dict, Iterable, Any
import traceback

import tornado
from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler, StaticFileHandler
import numpy as np

from argtypes import *
from utils import *
from logger import *
from constants import *


datasets: List[Dataset] = []
images_cache: List[Dict[str, str]] = []


def find_dataset(name: str) -> Dataset:
    for dataset in datasets:
        if name == dataset.name:
            return dataset

    return None


def dataset_not_found(handler: RequestHandler, name: str):
    handler.clear()
    handler.set_status(404)
    handler.write({
        'message': f'Cannot find dataset {repr(name)}!'
    })


def save_metadata(metadata: DatasetMetadata, fpath: str):
    if os.path.exists(fpath):
        backup_file_by_modified_date(fpath)

    with open(fpath, mode='w', encoding='utf-8') as outfile:
        universal_dump(metadata.__dict__, outfile)


class ListAvailableDatasets(RequestHandler):
    def get(self):
        dataset_names: List[str] = list(map(lambda dataset: dataset.name, datasets))  # noqa
        # put dataset with name starts with alphabet first because when
        # we create multiple datasets with the same source, they will be
        # backup by appending modified time (Unix time) as prefix

        latest_datasets = list(filter(lambda x: x[0].isalpha(), dataset_names))
        remain_datasets = set(dataset_names) - set(latest_datasets)

        response_list = []
        response_list.extend(latest_datasets)
        response_list.extend(remain_datasets)
        self.write({'datasets': response_list})


class GetDatasetInfo(RequestHandler):
    def get(self, name: str):
        debug(f'Dataset name: {repr(name)}')

        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        self.write({
            'name': dataset.name,
            'metadata': {
                'source': dataset.metadata.source,
                'content': dataset.metadata.content,
                'labels': dataset.metadata.labels,
                'invalid_records': dataset.metadata.invalid_records,
                'invalid_fonts': dataset.metadata.invalid_fonts,
                'completed_labels': dataset.metadata.completed_labels,
            },
        })


class GetLabelInfo(RequestHandler):
    def get(self, name: str, label: str):

        debug(f'Getting info for {repr(label)} in {repr(name)}')

        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        records = []
        for record in dataset.metadata.records:
            if record['char'] == label:
                records.append(record)

        self.write({
            'dataset': name,
            'label': label,
            'records': records,
        })


class MarkRecordAsInvalid(RequestHandler):
    """Mark a record as invalid by its hash id."""

    def get(self, name: str, hash: str):

        info(f'Marking {hash} in {name} as invalid!')

        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        metadata = dataset.metadata
        records = metadata.records

        for record in records:
            if record['hash'] == hash:
                metadata.invalid_records.append(hash)
                save_metadata(metadata, dataset.metadata_filepath)

                self.write({
                    'record': record,
                })

                return

        self.clear()
        self.set_status(404)
        self.write({
            'message': f'Cannot find record with hash {repr(hash)}!'
        })


class MarkRecordAsValid(RequestHandler):

    def get(self, name: str, hash: str):
        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        metadata = dataset.metadata
        invalid_records = metadata.invalid_records
        metadata.invalid_records = list(filter(lambda x: x != hash, invalid_records))  # noqa
        save_metadata(metadata, dataset.metadata_filepath)

        self.write({
            'message': f'Marked {repr(hash)} as valid record.',
        })


class MarkFontAsInvalid(RequestHandler):

    def get(self, name: str, font: str):
        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        metadata = dataset.metadata
        if font not in metadata.invalid_fonts:
            metadata.invalid_fonts.append(font)
            save_metadata(metadata, dataset.metadata_filepath)

        self.write({
            'message': f'Marked {font} as invalid.',
        })


class MarkFontAsValid(RequestHandler):

    def get(self, name: str, font: str):
        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        metadata = dataset.metadata
        invalid_fonts = metadata.invalid_fonts
        metadata.invalid_fonts = list(filter(lambda x: x != font, invalid_fonts))  # noqa
        save_metadata(metadata, dataset.metadata_filepath)

        self.write({
            'message': f'Marked {font} as valid.',
        })


class MarkLabelAsCompleted(RequestHandler):

    def get(self, name: str, label: str):
        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        metadata = dataset.metadata
        if label not in metadata.completed_labels:
            metadata.completed_labels.append(label)
            save_metadata(metadata, dataset.metadata_filepath)

        self.write({
            'message': f'Marked label {repr(label)} as done.',
        })


class MarkLabelAsIncompleted(RequestHandler):

    def get(self, name: str, label: str):
        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        metadata = dataset.metadata
        completed_labels = metadata.completed_labels
        metadata.completed_labels = list(filter(lambda x: x != label, completed_labels))  # noqa
        save_metadata(metadata, dataset.metadata_filepath)

        self.write({
            'messsage': f'Marked label {repr(label)} as not fully inspected.',
        })


class GetImageByHash(RequestHandler):
    """Pull out a single image from TFRecord file."""

    def get(self, name: str, hash: str):

        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        record_info = None

        for record in dataset.metadata.records:
            if record['hash'] == hash:
                record_info = record
                break

        if record_info is not None:
            seek_start = record_info['seek_start']
            seek_end = record_info['seek_end']

            with open(dataset.serialized_dataset_filepath, mode='rb') as in_stream:
                in_stream.seek(seek_start)
                bs = in_stream.read(seek_end - seek_start)
                record_datatype = bs[0]
                record = XFormat.deserialze_obj(bs[5:])
                base64_image = base64.encodebytes(record['PNG_IMAGE']).decode('utf-8')  # noqa
                self.write({
                    'image': base64_image,
                })

        else:
            self.clear()
            self.set_status(404)

            message = f'Cannot find image with hash {repr(hash)} in dataset {name}!'
            warn(message)

            self.write({
                'message': message,
            })


class GetImagesByHashes(RequestHandler):

    def notify_bad_request(self, message: str):
        self.clear()
        self.set_status(400)  # Bad Request
        self.write({'message': message})

    def post(self, name):
        """Get images from dataset with list of image's hashes.

        name : dataset's name
        """
        body = self.request.body
        # debug(f'Request body: {body}')
        if len(body) == 0:
            self.notify_bad_request('Request body must be a list of string!')
            return

        try:
            data = tornado.escape.json_decode(body)
        except Exception as ex:
            error(ex)
            traceback.print_exc()

            self.notify_bad_request('Body data is not valid JSON data!')
            return

        if not isinstance(data, list):
            self.notify_bad_request('Body data is not a list!')
            return

        for o in data:
            if not isinstance(o, str):
                self.notify_bad_request('The list must only contain string!')
                return

        dataset = find_dataset(name)

        if dataset is None:
            dataset_not_found(self, name)
            return

        images = {hash_str: None for hash_str in data}
        remain_hashes = [hash_str for hash_str in data]

        with open(dataset.serialized_dataset_filepath, 'rb') as in_stream:
            for record in dataset.metadata.records:
                if len(remain_hashes) > 0:
                    record_hash = record['hash']
                    if record_hash in remain_hashes:
                        remain_hashes.remove(record_hash)
                        seek_start = record['seek_start']
                        seek_end = record['seek_end']

                        in_stream.seek(seek_start)
                        bs = in_stream.read(seek_end-seek_start)
                        record_datatype = bs[0]
                        serialized_record = XFormat.deserialze_obj(bs[5:], record_datatype)  # noqa
                        base64_image = base64.encodebytes(serialized_record['PNG_IMAGE']).decode('utf-8')  # noqa
                        images[record_hash] = base64_image
                else:
                    break

        image_list = [{'hash': key, 'data': images[key]} for key in images]
        self.write({'images': image_list})


class IndexHandler(RequestHandler):
    def get(self):
        self.redirect('/index.html')


def make_app():
    return Application(
        handlers=[
            (r'/api/datasets', ListAvailableDatasets),
            (r'/api/datasets/([^/]+)', GetDatasetInfo),
            (r'/api/datasets/([^/]+)/([^/]+)', GetLabelInfo),
            (r'/api/images/([^/]+)', GetImagesByHashes),
            (r'/api/record/invalid/([^/]+)/([^/]+)', MarkRecordAsInvalid),
            (r'/api/record/valid/([^/]+)/([^/]+)', MarkRecordAsValid),
            (r'/api/font/invalid/([^/]+)/([^/]+)', MarkFontAsInvalid),
            (r'/api/font/valid/([^/]+)/([^/]+)', MarkFontAsValid),
            (r'/api/label/complete/([^/]+)/([^/]+)', MarkLabelAsCompleted),
            (r'/api/label/incomplete/([^/]+)/([^/]+)', MarkLabelAsIncompleted),
            (r'/images/([^/]+)/([^/]+)', GetImageByHash),
            (r'/', IndexHandler),
            (r'/(.*)', StaticFileHandler, {'path': './static'}),
        ],
        debug=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description='Tornado web server for inspecting dataset.',
    )

    parser.add_argument(
        'port',
        default=3000,
        type=valid_port_number,
        action='store',
        nargs='?',
        help='Port to listening at [default: 3000]',
    )

    parser.add_argument(
        '-fd', '--fonts',
        dest='fonts_dir',
        type=directory,
        default=FONTS_DIR,
        required=False,
        help=(
            f'The directory that contains TrueType (.ttf) or OpenType '
            f'(.otf) font files. Default look up directory is '
            f'{repr(FONTS_DIR)}.'
        ),
    )

    parser.add_argument(
        '--datasets-dir',
        dest='datasets_dir',
        type=directory,
        default=DATASETS_DIR,
        required=False,
        help=(
            'The directory that you used to store the dataset. '
            f'Default is {repr(DATASETS_DIR)}.'
        ),
    )

    args = parser.parse_args()
    datasets_dir = args.datasets_dir
    port = args.port

    dataset_dirs = os.listdir(datasets_dir)
    for name in dataset_dirs:
        try:
            dataset_dir = os.path.join(datasets_dir, name)

            metadata_filepath = os.path.join(dataset_dir, METADATA_FILENAME)
            if not os.path.exists(metadata_filepath):
                raise Exception(f'{metadata_filepath} does not exist!')

            serialized_dataset_filepath = os.path.join(dataset_dir, SERIALIZED_DATASET_FILENAME)  # noqa
            if not os.path.exists(serialized_dataset_filepath):
                raise Exception(f'{serialized_dataset_filepath} does not exist!')  # noqa

            json_obj = json.load(open(
                metadata_filepath,
                mode='r',
                encoding='utf-8',
            ))

            metadata = DatasetMetadata.parse_obj(json_obj)

            dataset = Dataset(
                name=name,
                path=dataset_dir,
                metadata_filepath=metadata_filepath,
                serialized_dataset_filepath=serialized_dataset_filepath,
                metadata=metadata,
            )

        except Exception as ex:
            error(repr(ex))
            warn(f'Skipping {name}!')
            traceback.print_exc()
            continue

        datasets.append(dataset)

    app = make_app()
    app.listen(port)

    try:
        info(f'Server starting at http://localhost:{port}/index.html')
        IOLoop.current().start()
    except Exception as ex:
        warn(repr(ex))

    info('Shutting down server.')
    IOLoop.current().stop()


if __name__ == '__main__':
    main()
