#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from controller.model import Model
from controller import helper as h
from controller import validate as v


class Char(Model):
    collection = 'char'
    fields = [
        {'id': 'name', 'name': '字编码'},
        {'id': 'page_name', 'name': '页编码'},
        {'id': 'char_id', 'name': 'char_id'},
        {'id': 'uid', 'name': 'uid', 'remark': 'page_name和char_id的整型值'},
        {'id': 'cid', 'name': 'cid'},
        {'id': 'source', 'name': '分类'},
        {'id': 'has_img', 'name': '是否已有字图'},
        {'id': 'img_need_updated', 'name': '是否需要更新字图'},
        {'id': 'cc', 'name': '置信度'},
        {'id': 'sc', 'name': '相似度'},
        {'id': 'pos', 'name': '坐标'},
        {'id': 'column', 'name': '所属列'},
        {'id': 'ocr_txt', 'name': '字框OCR'},
        {'id': 'col_txt', 'name': '列框OCR'},
        {'id': 'cmp_txt', 'name': '比对文字'},
        {'id': 'alternatives', 'name': 'OCR候选'},
        {'id': 'txt', 'name': '正字'},
        {'id': 'ori_txt', 'name': '原字'},
        {'id': 'txt_type', 'name': '类型'},
        {'id': 'box_level', 'name': '切分等级'},
        {'id': 'box_logs', 'name': '切分校对历史'},
        {'id': 'txt_level', 'name': '文字等级'},
        {'id': 'txt_logs', 'name': '文字校对历史'},
        {'id': 'task_count', 'name': '校对任务次数'},
        {'id': 'remark', 'name': '备注'},
    ]
    rules = [
        (v.is_page, 'page_name'),
    ]
    primary = 'name'

    txt_types = {'': '正字', 'Y': '广义异体字', 'X': '狭义异体字', 'M': '模糊或残损', 'N': '不确定', '*': '不认识'}
    # search_fields在这里定义，这样find_by_page时q参数才会起作用
    search_tips = '请搜索字编码、分类、文字'
    search_fields = ['name', 'source', 'txt', 'ocr_txt', 'ori_txt']

    @classmethod
    def get_char_search_condition(cls, request_query):
        def c2int(c):
            return int(float(c) * 1000)

        condition, params = dict(), dict()
        for field in ['txt', 'ocr_txt', 'txt_type']:
            value = h.get_url_param(field, request_query)
            if value:
                params[field] = value
                condition.update({field: value})
        for field in ['name', 'source', 'remark']:
            value = h.get_url_param(field, request_query)
            if value:
                params[field] = value
                condition.update({field: {'$regex': value, '$options': '$i'}})
        for field in ['cc', 'sc']:
            value = h.get_url_param(field, request_query)
            if value:
                params[field] = value
                m1 = re.search(r'^([><]=?)(0|1|[01]\.\d+)$', value)
                m2 = re.search(r'^(0|1|[01]\.\d+),(0|1|[01]\.\d+)$', value)
                if m1:
                    op = {'>': '$gt', '<': '$lt', '>=': '$gte', '<=': '$lte'}.get(m1.group(1))
                    condition.update({field: {op: c2int(m1.group(2))} if op else value})
                elif m2:
                    condition.update({field: {'$gte': c2int(m2.group(1)), '$lte': c2int(m2.group(2))}})
        return condition, params
