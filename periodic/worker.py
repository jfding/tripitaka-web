#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@desc: 任务处理基类
@time: 2019/11/3
"""
import sys
import time
import logging
import pymongo
import traceback
from random import randint
from os import path, remove
from datetime import datetime
from bson.errors import BSONError
from pymongo.errors import PyMongoError

sys.path.append(path.dirname(path.dirname(__file__)))
from controller.app import Application as App

MongoError = (PyMongoError, BSONError)


def connect_db():
    cfg = App.load_config().get('database')
    if cfg.get('user'):
        uri = 'mongodb://{0}:{1}@{2}:{3}/admin'
        uri.format(cfg.get('user'), cfg.get('password'), cfg.get('host'), cfg.get('port', 27017))
    else:
        uri = 'mongodb://{0}:{1}/'.format(cfg.get('host'), cfg.get('port', 27017))
    conn = pymongo.MongoClient(uri, connectTimeoutMS=2000, serverSelectionTimeoutMS=2000,
                               maxPoolSize=10, waitQueueTimeoutMS=5000)
    return conn[cfg['name']]


class Worker(object):
    def __init__(self, db=None):
        self.db = db or connect_db()

    def add_log(self, op_type, target_id='', context=''):
        logging.info('%s,context=%s' % (op_type, context))
        self.db.log.insert_one(dict(type=op_type, target_id=target_id, context=context, create_time=datetime.now()))

    def work(self, **kwargs):
        pass

    def run(self, **kwargs):
        log_path = path.join(path.dirname(path.dirname(__file__)), 'log')
        filename = '%s_%d.wk' % (datetime.now().strftime('%Y%m%d%H%M%S'), randint(109, 999))
        watch_file = not kwargs.get('no_log') and path.join(log_path, filename)
        if watch_file and not path.exists(watch_file):
            open(watch_file, 'w').close()
            self.add_log('worker_started', context=filename)

        ret = None
        try:
            while True:
                try:
                    self.work(**kwargs)
                except Exception as e:
                    traceback.print_exc()
                    msg = str(e) + ('' if 'Traceback' in str(e) else traceback.format_exc())
                    self.add_log('worker_exception', context='[%s] %s' % (e.__class__.__name__, msg))

                if kwargs.get('once_break'):
                    self.add_log('worker_break')
                    break

                if watch_file and not path.exists(watch_file):
                    self.add_log('worker_stopped')
                    break

                time.sleep(float(kwargs.get('interval', 3600)))

        except KeyboardInterrupt:
            pass

        if watch_file and path.exists(watch_file):
            remove(watch_file)

        return ret
