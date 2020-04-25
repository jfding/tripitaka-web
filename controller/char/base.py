#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from .char import Char
from controller import auth
from controller import helper as hp
from controller.task.base import TaskHandler


class CharHandler(TaskHandler, Char):
    box_level = {
        'task': dict(cut_proof=1, cut_review=10),
        'role': dict(切分校对员=1, 切分审定员=10, 切分专家=100),
    }

    txt_level = {
        'task': dict(cluster_proof=1, cluster_review=10, separate_proof=20, separate_review=30),
        'role': dict(聚类校对员=1, 聚类审定员=10, 分类校对员=20, 分类审定员=30, 文字专家=100),
    }

    def __init__(self, application, request, **kwargs):
        super(CharHandler, self).__init__(application, request, **kwargs)

    def prepare(self):
        super().prepare()

    @classmethod
    def get_box_level(cls, kind, task_or_role):
        return hp.prop(cls.box_level, kind + '.' + task_or_role, 0)

    @classmethod
    def get_txt_level(cls, kind, task_or_role):
        return hp.prop(cls.txt_level, kind + '.' + task_or_role, 0)

    @classmethod
    def get_role_level(cls, field, roles):
        assert field in ['box', 'txt']
        user_roles = auth.get_all_roles(roles)
        if field == 'box':
            return max([cls.get_box_level('role', r) for r in user_roles]) or 0
        if field == 'txt':
            return max([cls.get_txt_level('role', r) for r in user_roles]) or 0

    @classmethod
    def get_task_level(cls, field, task_type):
        assert field in ['box', 'txt']
        if field == 'box':
            return cls.get_box_level('task', task_type) or 0
        if field == 'txt':
            return cls.get_txt_level('task', task_type) or 0

    @staticmethod
    def get_user_level(self, field, edit_type):
        """ 获取用户的数据等级"""
        assert field in ['box', 'txt']
        if edit_type == 'raw_edit':
            return self.get_role_level(field, self.current_user['roles'])
        else:
            return self.get_task_level(field, edit_type)

    @staticmethod
    def get_user_point(self, task_type):
        """ 针对指定的任务类型，获取用户积分"""
        counts = list(self.db.task.aggregate([
            {'$match': {'task_type': task_type, 'picked_user_id': self.user_id, 'status': self.STATUS_FINISHED}},
            {'$group': {'count': {'$sum': 1}}},
        ]))
        return counts[0]['count']

    @staticmethod
    def get_required_point(char, field):
        """ 获取修改char的box、txt所需的积分"""
        assert field in ['box', 'txt']
        ratio = {'cut_proof': 1000, 'cut_review': 500, 'cluster_proof': 1000, 'cluster_review': 500,
                 'separate_proof': 1000, 'separate_review': 500}
        if field == 'box':
            for task_type in ['cut_review', 'cut_proof']:
                count = hp.prop(char, 'task_count.' + task_type)
                if count:
                    return task_type, count * ratio.get(task_type)
            return 'cut_proof', 1000
        else:
            for task_type in ['separate_review', 'separate_proof', 'cluster_review', 'cluster_proof']:
                count = hp.prop(char, 'task_count.' + task_type)
                if count:
                    return task_type, count * ratio.get(task_type)
            return 'cluster_proof', 1000
