#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import pymongo
from os import path
from datetime import datetime
from operator import itemgetter
from functools import cmp_to_key


def build_js(db, collection, tripitaka=None):
    if collection == 'volume':
        return build_volume_js(db, tripitaka)
    if collection == 'sutra':
        return build_sutra_js(db, tripitaka)


def get_volume_tree(volumes, store_pattern):
    if not volumes:
        return []
    if len(store_pattern.split('_')) == 4:
        volume_dict = dict()
        for item in volumes:
            envelop_no = int(item['envelop_no'])
            volume_no = int(item['volume_no'])
            if envelop_no in volume_dict:
                volume_dict[envelop_no].append(volume_no)
                volume_dict[envelop_no].sort()
            else:
                volume_dict[envelop_no] = [volume_no]
        volume_tree = [[envelop_no, volumes] for envelop_no, volumes in volume_dict.items()]
    else:
        volume_tree = [[int(item.get('volume_no')), []] for item in volumes]
    volume_tree.sort(key=itemgetter(0))
    return volume_tree


def build_volume_js(db, tripitaka=None):
    base_dir = path.dirname(path.dirname(path.realpath(__file__)))
    js_dir = path.join(base_dir, 'static', 'js', 'meta')
    if tripitaka:
        tripitaka = db.tripitaka.find_one({'tripitaka_code': tripitaka})
    tripitakas = [tripitaka] if tripitaka else db.tripitaka.find({})
    for t in tripitakas:
        print('generating %s-volume.js ...' % t.get('tripitaka_code'))
        volumes = list(db.volume.find({'tripitaka_code': t['tripitaka_code']})
                       .sort([('envelop_no', 1), ('volume_no', 1)]))
        volume_tree = get_volume_tree(volumes, t['store_pattern'])
        js_file = path.join(js_dir, '%s-volume.js' % t['tripitaka_code'])
        with open(js_file, 'w', encoding='utf-8') as fp:
            head = "/*\n"
            head += "* 图片存储结构信息。存储结构有三种模式：藏-函-册-页，藏-经-卷-页，藏-册-页。字段解释如下：\n"
            head += "* [[函1,[册1，册2...],[函2,[册1，册2...]]]\n"
            head += "* [[经1,[卷1，卷2...],[经2,[卷1，卷2...]]]\n"
            head += "* [[册1,[],[册2,[]]]\n"
            head += "* Date: %s\n" % datetime.now().strftime('%Y-%m-%d %H:%M')
            head += "*/\n\n"
            head += "var store_pattern ='%s';\n" % t['store_pattern']
            head += "var volumes ="
            fp.write(head)
            fp.write(json.dumps(volume_tree, ensure_ascii=False))
            fp.write(";")


def build_sutra_js(db, tripitaka=None):
    base_dir = path.dirname(path.dirname(path.realpath(__file__)))
    js_dir = path.join(base_dir, 'static', 'js', 'meta')
    tripitakas = db.tripitaka.find().distinct('tripitaka_code') if not tripitaka else [tripitaka]
    for t in tripitakas:
        print('generating %s-sutra.js ...' % t)
        fields = dict(sutra_code=1, sutra_name=1, due_reel_count=1, existed_reel_count=1, start_volume=1, start_page=1,
                      end_volume=1, end_page=1, _id=0)
        rows = list(db.sutra.find({'sutra_code': {'$regex': '^%s.*' % t}}, fields))
        rows.sort(key=cmp_to_key(lambda a, b: int(a['sutra_code'][3:]) - int(b['sutra_code'][3:])))
        rows = [[
            r.get('sutra_code') or '', r.get('sutra_name') or '', r.get('due_reel_count') or '',
            r.get('existed_reel_count') or '', r.get('start_volume') or '', r.get('start_page') or '',
            r.get('end_volume') or '', r.get('end_page') or '',
        ] for r in rows]
        js_file = path.join(js_dir, '%s-sutra.js' % t)
        with open(js_file, 'w', encoding='utf-8') as fp:
            head = "/*\n"
            head += "* 经目信息。字段顺序依次是：\n"
            head += "* sutra_code/sutra_name/due_reel_count/existed_reel_count/" \
                    "start_volume/start_page/end_volume/end_page\n"
            head += "* Date: %s\n" % datetime.now().strftime('%Y-%m-%d %H:%M')
            head += "*/\n\n"
            head += "var sutras ="
            fp.write(head)
            fp.write(json.dumps(rows, ensure_ascii=False))
            fp.write(";")


def main(db_name='tripitaka', uri='localhost', which='sutra,volume'):
    conn = pymongo.MongoClient(uri)
    db = conn[db_name]
    if 'volume' in which:
        build_volume_js(db)
    if 'sutra' in which:
        build_sutra_js(db)


if __name__ == '__main__':
    import fire

    fire.Fire(main)
