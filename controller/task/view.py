#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@desc: 任务管理
@time: 2018/12/26
"""
import random
from datetime import datetime
from bson.objectid import ObjectId
from controller import errors as e
from controller.helper import get_date_time
from controller.task.base import TaskHandler


class TaskAdminHandler(TaskHandler):
    URL = '/task/admin/@task_type'

    def is_mod_enabled(self, mod):
        disabled_mods = self.prop(self.config, 'modules.disabled_mods')
        return not disabled_mods or mod not in disabled_mods

    def get(self, task_type):
        """ 任务管理/任务列表 """

        def statistic():
            doc_count = int(pager['doc_count'])
            q = self.get_query_argument('q', '')
            if q:
                condition['$or'] = [{k: {'$regex': q, '$options': '$i'}} for k in search_fields]
            if 'status' in condition:
                return {condition['status']: dict(count=doc_count, ratio=1)}
            result = dict()
            for status, name in self.task_statuses.items():
                condition.update({'status': status})
                count = self.db.task.count_documents(condition)
                if count:
                    result[status] = dict(count=count, ratio='%4d' % (count / doc_count))
            return result

        try:
            condition = {}
            task_meta = self.get_task_meta(task_type)
            is_group = self.prop(task_meta, 'groups')
            if self.get_query_argument('task_type', ''):
                condition.update({'task_type': self.get_query_argument('task_type', '')})
            elif is_group:
                condition.update({'task_type': {'$regex': task_type}})
            else:
                condition.update({'task_type': task_type})
            if self.get_query_argument('status', ''):
                condition.update({'status': self.get_query_argument('status', '')})
            search_tip, search_fields, template = self.search_tip, self.search_fields, 'task_admin.html'
            if task_type == 'import_image':
                template = 'task_admin_import.html'
                search_tip = '请搜索网盘名称或导入文件夹'
                search_fields = ['input.pan_name', 'input.import_dir']
            tasks, pager, q, order = self.find_by_page(self, condition, search_fields)
            self.render(
                template, task_type=task_type, tasks=tasks, pager=pager, order=order, q=q, task_meta=task_meta,
                search_tip=search_tip, task_types=self.all_task_types(), is_mod_enabled=self.is_mod_enabled,
                pan_name=self.prop(self.config, 'pan.name'), modal_fields=self.modal_fields,
                statistic=statistic(),
            )
        except Exception as error:
            return self.send_db_error(error)


class TaskLobbyHandler(TaskHandler):
    URL = '/task/lobby/@task_type'

    @staticmethod
    def get_lobby_tasks_by_type(self, task_type, page_size=None, q=None):
        """ 按优先级排序后随机获取任务大厅/任务列表"""

        def get_random_skip():
            condition.update({'priority': 3})
            n3 = self.db.task.count_documents(condition)
            condition.update({'priority': 2})
            n2 = self.db.task.count_documents(condition)
            condition.pop('priority', 0)
            skip = n3 if n3 > page_size else n3 + n2 if n3 + n2 > page_size else total_count
            return random.randint(1, skip - page_size) if skip > page_size else 0

        def de_duplicate():
            _tasks, _doc_ids = [], []
            for task in tasks:
                if task.get('doc_id') not in _doc_ids:
                    _tasks.append(task)
                    _doc_ids.append(task.get('doc_id'))
            return _tasks[:page_size]

        assert task_type in self.all_task_types()
        task_meta = self.get_task_meta(task_type)
        page_size = page_size or int(self.config['pager']['page_size'])
        condition = {'doc_id': {'$regex': q, '$options': '$i'}} if q else {}
        if task_meta.get('groups'):
            condition.update({'task_type': {'$regex': task_type}, 'status': self.STATUS_OPENED})
            my_tasks, count = MyTaskHandler.get_my_tasks_by_type(self, task_type, un_limit=True)
            if count:
                condition.update({'doc_id': {'$nin': [t['doc_id'] for t in my_tasks]}})
            total_count = self.db.task.count_documents(condition)
            skip_no = get_random_skip()
            tasks = list(self.db.task.find(condition).skip(skip_no).sort('priority', -1).limit(page_size * 3))
            tasks = de_duplicate()
        else:
            condition.update({'task_type': task_type, 'status': self.STATUS_OPENED})
            total_count = self.db.task.count_documents(condition)
            skip_no = get_random_skip()
            tasks = list(self.db.task.find(condition).skip(skip_no).sort('priority', -1).limit(page_size))

        return tasks, total_count

    def get(self, task_type):
        """ 任务大厅 """
        try:
            q = self.get_query_argument('q', '')
            tasks, total_count = self.get_lobby_tasks_by_type(self, task_type, q=q)
            self.render('task_lobby.html', tasks=tasks, task_type=task_type, total_count=total_count)
        except Exception as error:
            return self.send_db_error(error)


class MyTaskHandler(TaskHandler):
    URL = '/task/my/@task_type'

    @staticmethod
    def get_my_tasks_by_type(self, task_type=None, q=None, order=None, page_size=0, page_no=1, un_limit=None):
        """获取我的任务/任务列表"""
        task_meta = self.get_task_meta(task_type)
        status = [self.STATUS_PICKED, self.STATUS_FINISHED]
        condition = {'status': {'$in': status}, 'picked_user_id': self.current_user['_id']}
        if q:
            condition.update({'doc_id': {'$regex': q, '$options': '$i'}})
        if task_type:
            condition.update({'task_type': {'$regex': task_type} if task_meta.get('groups') else task_type})

        total_count = self.db.task.count_documents(condition)
        query = self.db.task.find(condition)
        if order:
            o, asc = (order[1:], -1) if order[0] == '-' else (order, 1)
            query.sort(o, asc)
        if not un_limit:
            page_size = page_size or self.config['pager']['page_size']
            page_no = page_no if page_no >= 1 else 1
            query.skip(page_size * (page_no - 1)).limit(page_size)
        return list(query), total_count

    def get(self, task_type):
        """ 我的任务 """
        try:
            q = self.get_query_argument('q', '')
            order = self.get_query_argument('order', '-picked_time')
            page_size = int(self.config['pager']['page_size'])
            cur_page = int(self.get_query_argument('page', 1))
            tasks, total_count = self.get_my_tasks_by_type(
                self, task_type=task_type, q=q, order=order, page_size=page_size, page_no=cur_page
            )
            pager = dict(cur_page=cur_page, doc_count=total_count, page_size=page_size)
            self.render('my_task.html', task_type=task_type, tasks=tasks, pager=pager, order=order)

        except Exception as error:
            return self.send_db_error(error)


class TaskPageInfoHandler(TaskHandler):
    URL = '/task/page/@page_name'

    @classmethod
    def format_info(cls, key, value):
        """ 格式化任务信息"""
        if isinstance(value, datetime):
            value = get_date_time('%Y-%m-%d %H:%M', value)
        elif key == 'task_type':
            value = cls.get_task_name(value)
        elif key == 'status':
            value = cls.get_status_name(value)
        elif key == 'pre_tasks':
            value = '/'.join([cls.get_task_name(t) for t in value])
        elif key == 'steps':
            value = '/'.join([cls.get_step_name(t) for t in value.get('todo', [])])
        elif key == 'priority':
            value = cls.get_priority_name(int(value))
        elif isinstance(value, dict):
            value = value.get('error') or value.get('message')
            value = value or '<br/>'.join(['%s: %s' % (k, v) for k, v in value.items()])
        return value

    def get(self, page_name):
        """ Page的任务详情 """
        from functools import cmp_to_key

        try:
            page = self.db.page.find_one({'name': page_name})
            if not page:
                return self.send_error_response(e.no_object, message='页面%s不存在' % page_name)

            tasks = list(self.db.task.find({'collection': 'page', 'doc_id': page_name}))
            order = ['upload_cloud', 'ocr_box', 'cut_proof', 'cut_review', 'ocr_text', 'text_proof_1',
                     'text_proof_2', 'text_proof_3', 'text_review', 'text_hard']
            tasks.sort(key=cmp_to_key(lambda a, b: order.index(a['task_type']) - order.index(b['task_type'])))
            display_fields = ['doc_id', 'task_type', 'status', 'pre_tasks', 'steps', 'priority',
                              'updated_time', 'finished_time', 'publish_by', 'publish_time',
                              'picked_by', 'picked_time', 'message']
            self.render('task_page_info.html', page=page, tasks=tasks, format_info=self.format_info,
                        display_fields=display_fields)

        except Exception as error:
            return self.send_db_error(error)


class TaskInfoHandler(TaskHandler):
    URL = '/task/info/@task_id'

    def get(self, task_id):
        """ 任务详情 """
        try:
            # 检查参数
            task = self.db.task.find_one({'_id': ObjectId(task_id)})
            if not task:
                self.send_error_response(e.no_object, message='没有找到该任务')

            display_fields = ['doc_id', 'task_type', 'status', 'priority', 'pre_tasks', 'steps',
                              'publish_time', 'publish_by', 'picked_time', 'picked_by',
                              'updated_time', 'finished_time', 'message', ]
            self.render('task_info.html', task=task, display_fields=display_fields,
                        format_info=TaskPageInfoHandler.format_info)

        except Exception as error:
            return self.send_db_error(error)
