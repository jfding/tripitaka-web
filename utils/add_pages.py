#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 导入页面文件到文档库，可导入页面图到 static/img 供本地调试用
# 本脚本的执行结果相当于在“数据管理-页数据”中提供了图片、OCR切分数据、文本，是任务管理中发布切分和文字审校任务的前置条件。
# python utils/add_pages.py --json_path=切分文件路径 [--img_path=页面图路径] [--txt_path=经文路径] [--kind=藏经类别码]


import re
import sys
import json
import shutil
import pymongo
from tornado.util import PY3
from datetime import datetime
from os import path, listdir, mkdir

BASE_DIR = path.dirname(path.dirname(__file__))
sys.path.append(BASE_DIR)

from controller.helper import prop
from controller.data.data import Page
from controller.cut.reorder import char_reorder

data = dict(count=0)


def create_dir(dirname):
    if not path.exists(dirname):
        mkdir(dirname)


def load_json(filename):
    if not path.exists(filename):
        return
    try:
        with open(filename, encoding='UTF-8') if PY3 else open(filename) as f:
            return json.load(f)
    except Exception as error:
        sys.stderr.write('invalid file %s: %s\n' % (filename, str(e)))


def scan_dir(src_path, kind, db, ret, use_local_img=False, update=False,
             source=None, reorder=False, only_check=False):
    if not path.exists(src_path):
        sys.stderr.write('%s not exist\n' % (src_path,))
        return []
    for fn in sorted(listdir(src_path)):
        filename = path.join(src_path, fn)
        if path.isdir(filename):
            fn2 = fn if re.match(r'^[A-Z]{2}$', fn) else kind
            if not kind or kind == fn2:
                scan_dir(filename, fn2, db, ret, use_local_img=use_local_img, update=update,
                         source=source, reorder=reorder, only_check=only_check)
        elif not kind or fn[:2] == kind:
            if fn.endswith('.json') and fn[:-5] not in ret:  # 相同名称的页面只导入一次
                info = load_json(filename)
                if info:
                    name = info.get('img_name') or info.get('imgname') or info.get('name')
                    if name != fn[:-5] or not re.match(r'^[A-Z]{2}(_\d+)+$', name):
                        sys.stderr.write('invalid img_name %s, %s\n' % (filename, name))
                        continue
                    if add_page(name, info, db, use_local_img=use_local_img, update=update,
                                source=source, reorder=reorder, only_check=only_check):
                        ret.add(name)


def add_page(name, info, db, img_name=None, use_local_img=False, update=False,
             source=None, reorder=False, only_check=False):
    exist = db.page.find_one(dict(name=name))
    if only_check and exist:
        print('%s exist' % name)
        return
    if update or not exist:
        meta = Page.metadata()
        width = int(prop(info, 'imgsize.width') or prop(info, 'img_size.width') or prop(info, 'width') or 0)
        height = int(prop(info, 'imgsize.height') or prop(info, 'img_size.height') or prop(info, 'height') or 0)
        page_code = Page.name2pagecode(name)
        meta.update(dict(
            name=name, width=width, height=height, page_code=page_code, blocks=prop(info, 'blocks', []),
            columns=prop(info, 'columns', []), chars=prop(info, 'chars', []),
        ))
        if not width or not height:
            assert exist
            meta.pop('width')
            meta.pop('height')
        if info.get('ocr'):
            if isinstance(info['ocr'], list):
                meta['ocr'] = '|'.join(info['ocr']).replace('\u3000', '|').replace(' ', '')
            else:
                meta['ocr'] = info['ocr'].replace('\n', '|')
        if info.get('text'):
            if isinstance(info['text'], list):
                meta['text'] = '|'.join(info['text']).replace('\u3000', '|').replace(' ', '')
            else:
                meta['text'] = info['text'].replace('\n', '|')
        if img_name:
            meta['img_name'] = img_name
        if use_local_img:
            meta['use_local_img'] = True
        for field in ['source', 'create_time']:
            if info.get(field):
                meta[field] = info[field]
        if source:
            meta['source'] = source
        meta['layout'] = prop(info, 'layout') or ['上下一栏', '上下一栏', '上下两栏', '上下三栏'][len(info['blocks'])]

        if reorder:
            try:
                meta['columns'] = char_reorder(meta['chars'], blocks=meta['blocks'],
                                               sort=True, remove_outside=True, img_file=name)
            except AssertionError as e:
                sys.stderr.write('%s %s' % (name, str(e)))

        data['count'] += 1
        print('%s:\t%d x %d blocks=%d columns=%d chars=%d' % (
            name, width, height, len(meta['blocks']), len(meta['columns']), len(meta['chars'])
        ))

        info.pop('id', 0)
        if only_check:
            r = meta
        elif exist:
            meta.pop('create_time', 0)
            r = update and db.page.update_one(dict(name=name), {'$set': meta})
            info['id'] = str(exist['_id'])
        else:
            if not meta.get('create_time'):
                meta['create_time'] = datetime.now()
            elif isinstance(meta['create_time'], str):
                meta['create_time'] = datetime.strptime(meta['create_time'], '%Y-%m-%d %H:%M:%S')
            r = db.page.insert_one(meta)
            info['id'] = str(r.inserted_id)

        return r


def add_texts(src_path, pages, db):
    if not path.exists(src_path):
        return
    for fn in listdir(src_path):
        filename = path.join(src_path, fn)
        if path.isdir(filename):
            add_texts(filename, pages, db)
        elif (fn.endswith('.ocr') or fn.endswith('.txt')) and fn[:-4] in pages:
            with open(filename, encoding='UTF-8') if PY3 else open(filename) as f:
                text = f.read().strip().replace('\n', '|')
            cond = {'$or': [dict(name=fn[:-4]), dict(img_name=fn[:-4])]}
            r = list(db.page.find(cond))
            if r and not r[0].get('text'):
                text = re.sub(r'[<>]', '', text)
                db.page.update_many(cond, {'$set': dict(ocr=text)})


def copy_img_files(src_path, pages):
    if not path.exists(src_path):
        return
    img_path = path.join(BASE_DIR, 'static', 'img')
    create_dir(img_path)
    for fn in listdir(src_path):
        filename = path.join(src_path, fn)
        if path.isdir(filename):
            copy_img_files(filename, pages)
        elif fn.endswith('.jpg') and fn[:-4] in pages:
            dst_file = path.join(img_path, fn[:2])
            create_dir(dst_file)
            dst_file = path.join(dst_file, fn)
            if not path.exists(dst_file):
                shutil.copy(filename, dst_file)


def main(json_path='', img_path='img', txt_path='txt', kind='', db_name='tripitaka', uri='localhost',
         reset=False, use_local_img=False, update=False, reorder=False, only_check=False, source=None):
    """
    页面导入的主函数
    :param json_path: 页面JSON文件的路径，如果遇到是两个大写字母的文件夹就视为藏别，json_path为空则取为data目录
    :param img_path: 页面图路径，json_path为空时取为data目录，可在不同的子目录下放图片文件(*.jpg)
    :param txt_path: 页面文本文件的路径，json_path为空时取为data目录，可在不同的子目录下放图片文件(*.txt)
    :param kind: 可指定要导入的藏别
    :param db_name: 数据库名
    :param uri: 数据库服务器的地址，可为localhost或mongodb://user:password@server
    :param reset: 是否先清空page表
    :param use_local_img: 是否让页面强制使用本地的页面图，默认是使用OSS上的高清图（如果在app.yml配置了OSS）
    :param update: 已存在的页面是否更新
    :param reorder: 是否重新对字框和列框排序
    :param only_check: 是否仅校验数据而不插入数据
    :param source: 导入批次名称
    :return: 新导入的页面的个数
    """
    conn = pymongo.MongoClient(uri)
    db = conn[db_name]
    if reset:
        db.page.delete_many({})

    if not json_path:
        txt_path = json_path = img_path = path.join(BASE_DIR, 'meta', 'sample')
    pages = set()
    scan_dir(json_path, kind, db, pages, use_local_img=use_local_img, update=update,
             reorder=reorder, only_check=only_check, source=source)
    copy_img_files(img_path, pages)
    add_texts(txt_path, pages, db)
    return data['count']


if __name__ == '__main__':
    import fire

    fire.Fire(main)