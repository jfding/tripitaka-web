#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

page_kinds = {'GL': '高丽藏', 'JX': '嘉兴藏', 'QL': '乾隆藏', 'YB': '永乐北藏'}

op_types = {
    'visit': dict(name='页面访问'),
    'submit_ocr': dict(name='OCR提交', trends=True, msg='创建了{page_name}任务'),
    'submit_ocr_batch': dict(name='OCR批量导入', trends=True, msg='导入了{context}个页面'),
    'pick_{task_type}': dict(name='领取任务', trends=True, msg='领取了{page_kind}{task_type}任务'),
    'assign_{task_type}': dict(name='指派任务', trends=True, msg='领取了{page_kind}{task_type}任务'),
    'return_{task_type}': dict(name='退回任务', trends=True, msg='退回了{page_kind}{task_type}任务'),
    'submit_{task_type}': dict(name='提交任务', trends=True, msg='完成了{page_kind}{task_type}任务'),
    'publish_{task_type}': dict(name='发布任务', trends=True, msg='发布了{count}个{task_type}任务'),
    'save_{task_type}': dict(name='任务保存'),
    'edit_{data_field}': dict(name='数据修改保存'),
    'retrieve_{task_type}': dict(name='撤回任务', trends=True, msg='撤回了{page_name}{task_type}任务'),
    'delete_{task_type}': dict(name='删除任务', trends=True, msg='删除了{page_name}{task_type}任务'),
    'auto_unlock': dict(name='自动回收任务'),
    'login_no_user': dict(name='账号不存在'),
    'login_fail': dict(name='账号密码不对'),
    'login_ok': dict(name='登录成功', trends=True),
    'logout': dict(name='注销登录'),
    'register': dict(name='注册账号', trends=True),
    'change_user_profile': dict(name='修改用户信息'),
    'change_role': dict(name='修改用户角色'),
    'reset_password': dict(name='重置密码'),
    'delete_user': dict(name='删除用户'),
    'change_my_password': dict(name='修改个人密码'),
    'change_my_profile': dict(name='修改个人信息'),
    'add_{collection}': dict(name='新增{collection}数据'),
    'update_{collection}': dict(name='修改{collection_kind}数据'),
    'delete_{collection}': dict(name='删除{collection_kind}数据'),
    'upload_{collection}': dict(name='上传{collection_kind}数据'),
    'import_image': dict(name='导入藏经图'),
    'import_meta': dict(name='导入藏册页数据'),
}

placeholder = {
    'task_type': r'cut_[a-z]+|ocr_[a-z]+|text_[0-9a-z_]+|upload_cloud|import_image',
    'collection': r'tripitaka|sutra|volume|reel|page',
}


def get_op_def(op_type, params=None):
    re_map = []
    for o in op_types:
        o = o.replace('{task_type}', '([a-z0-9_]+)')

        re_map.append((re.compile(o), o))

    for k, v in op_types.items():
        for _k, _v in placeholder.items():
            k = k.replace('{%s}' % _k, '(%s)' % _v)
        if re.match(k, op_type):
            if params is not None:
                f = re.findall(k, op_type)
                if f and 'task_type' in k:
                    params['task_type'] = f[0]
            return v
    return op_types.get(op_type)


def get_op_name(op_type):
    r = get_op_def(op_type)
    return r and r['name']


def op_in_recent_trends(op_type):
    r = get_op_def(op_type)
    return r and r.get('trends')
