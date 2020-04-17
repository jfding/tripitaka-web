#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import json
from bson import json_util
from .page import Page
from .base import PageHandler
from controller import errors as e
from controller import helper as h
from controller import validate as v


class PageTaskPublishApi(PageHandler):
    URL = r'/api/page/task/publish'

    def post(self):
        """ 发布任务"""
        try:
            log = dict()
            self.get_page_names(log)
            rules = [
                (v.not_empty, 'page_names', 'task_type', 'priority', 'force', 'batch'),
                (v.in_list, 'task_type', list(self.task_types.keys())),
                (v.in_list, 'pre_tasks', list(self.task_types.keys())),
                (v.is_priority, 'priority'),
            ]
            self.validate(self.data, rules)
            log = self.check_and_publish(log)
            self.add_op_log(self.db, 'publish_task', log, self.username)
            return self.send_data_response(log)

        except self.DbError as error:
            return self.send_db_error(error)

    def get_page_names(self, log):
        """ 获取页码"""
        page_names = self.data.get('page_names')
        if page_names:
            if isinstance(page_names, str):
                self.data['page_names'] = page_names.split(',')
            return
        names_file = self.request.files.get('names_file')
        if names_file:
            names_str = str(names_file[0]['body'], encoding='utf-8').strip('\n')
            try:
                page_names = json.loads(names_str)
            except json.decoder.JSONDecodeError:
                ids_str = re.sub(r'\n+', '|', names_str)
                page_names = ids_str.split(r'|')
            pages = list(self.db.page.find({'name': {'$in': page_names}}, {'name': 1}))
            log['un_existed'] = set(page_names) - set([page['name'] for page in pages])
            page_names = [page['name'] for page in pages]
        elif self.data.get('prefix'):
            condition = {'name': {'$regex': self.data['prefix'], '$options': '$i'}}
            page_names = [page['name'] for page in list(self.db.page.find(condition, {'name': 1}))]
        elif self.data.get('search'):
            condition = Page.get_page_search_condition(self.data['search'])[0]
            query = self.db.page.find(condition, {'name': 1})
            page = h.get_url_param('page', self.data['search'])
            if page:
                s = h.get_url_param('page_size', self.data['search']) or self.prop(self.config, 'pager.page_size', 10)
                query = query.skip((int(page) - 1) * int(s)).limit(int(s))
            page_names = [page['name'] for page in list(query)]
        self.data['page_names'] = page_names

    def check_and_publish(self, log):
        """ 检查页码并发布任务"""
        # 去掉已发布和进行中的页码
        page_names, task_type, num = self.data['page_names'], self.data['task_type'], self.data.get('num')
        if page_names:
            status = [self.STATUS_PUBLISHED, self.STATUS_PENDING, self.STATUS_PICKED]
            cond = dict(task_type=task_type, num=num, status={'$in': status}, doc_id={'$in': list(page_names)})
            log['published_before'] = set(t['doc_id'] for t in self.db.task.find(cond, {'doc_id': 1}))
            page_names = set(page_names) - log['published_before']

        # 去掉已完成的页码（如果不重新发布）
        if not int(self.data['force']) and page_names:
            cond = dict(task_type=task_type, num=num, status=self.STATUS_FINISHED, doc_id={'$in': list(page_names)})
            log['finished_before'] = set(t['doc_id'] for t in self.db.task.find(cond, {'doc_id': 1}))
            page_names = set(page_names) - log['finished_before']

        # 剩下的页码，发布新任务
        if page_names:
            pre_tasks = self.data['pre_tasks']
            if pre_tasks:
                pre_tasks = [pre_tasks] if isinstance(pre_tasks, str) else pre_tasks
                db_pre_tasks = list(self.db.task.find(
                    {'collection': 'page', 'doc_id': {'$in': list(page_names)}, 'task_type': {'$in': pre_tasks}},
                    {'task_type': 1, 'num': 1, 'status': 1, 'doc_id': 1}
                ))
                # 前置任务未发布、未完成的情况，发布为PENDING
                un_published = set(page_names) - set(t['doc_id'] for t in db_pre_tasks)
                un_finished = set(t['doc_id'] for t in db_pre_tasks if t['status'] != self.STATUS_FINISHED)
                self.create_tasks(set(un_finished | un_published), self.STATUS_PENDING, {t: None for t in pre_tasks})
                log['pending'] = set(un_finished | un_published)
                # 前置任务未完成的情况，发布为PENDING
                page_names = set(page_names) - log['pending']
                if page_names:
                    self.create_tasks(page_names, self.STATUS_PUBLISHED, {t: self.STATUS_FINISHED for t in pre_tasks})
                    log['published'] = page_names
            else:
                self.create_tasks(page_names, self.STATUS_PUBLISHED)
                log['published'] = page_names

        return {k: v for k, v in log.items() if v}

    def create_tasks(self, page_names, status, pre_tasks=None):
        def get_task(page_name):
            steps = self.data.get('steps') and dict(todo=self.data['steps'])
            return dict(task_type=self.data['task_type'], num=self.data.get('num'), batch=self.data['batch'],
                        collection='page', id_name='name', doc_id=page_name, status=status, steps=steps,
                        priority=self.data['priority'], pre_tasks=pre_tasks, params=None, result={},
                        create_time=self.now(), updated_time=self.now(), publish_time=self.now(),
                        publish_user_id=self.user_id, publish_by=self.username)

        if page_names:
            self.db.task.insert_many([get_task(name) for name in page_names], ordered=False)


class PageTaskAdminHandler(PageHandler):
    URL = '/page/task/admin'

    page_title = '页任务管理'
    search_tips = '请搜索页编码、批次号或备注'
    search_fields = ['doc_id', 'batch', 'remark']
    table_fields = [
        {'id': '_id', 'name': '主键'},
        {'id': 'doc_id', 'name': '页编码'},
        {'id': 'batch', 'name': '批次号'},
        {'id': 'task_type', 'name': '类型', 'filter': PageHandler.task_types},
        {'id': 'status', 'name': '状态', 'filter': PageHandler.task_statuses},
        {'id': 'priority', 'name': '优先级', 'filter': PageHandler.priorities},
        {'id': 'steps', 'name': '步骤'},
        {'id': 'pre_tasks', 'name': '前置任务'},
        {'id': 'return_reason', 'name': '退回理由'},
        {'id': 'create_time', 'name': '创建时间'},
        {'id': 'updated_time', 'name': '更新时间'},
        {'id': 'publish_time', 'name': '发布时间'},
        {'id': 'publish_by', 'name': '发布人'},
        {'id': 'picked_time', 'name': '领取时间'},
        {'id': 'picked_by', 'name': '领取人'},
        {'id': 'finished_time', 'name': '完成时间'},
        {'id': 'remark', 'name': '备注'},
    ]
    operations = [
        {'operation': 'bat-remove', 'label': '批量删除', 'url': '/task/delete'},
        {'operation': 'bat-assign', 'label': '批量指派', 'data-target': 'assignModal'},
        {'operation': 'bat-batch', 'label': '更新批次'},
        {'operation': 'btn-search', 'label': '综合检索', 'data-target': 'searchModal'},
        {'operation': 'btn-statistic', 'label': '结果统计', 'groups': [
            {'operation': 'picked_user_id', 'label': '按用户'},
            {'operation': 'task_type', 'label': '按类型'},
            {'operation': 'status', 'label': '按状态'},
        ]},
    ]
    actions = [
        {'action': 'btn-nav', 'label': '浏览'},
        {'action': 'btn-detail', 'label': '详情'},
        {'action': 'btn-history', 'label': '历程'},
        {'action': 'btn-delete', 'label': '删除'},
        {'action': 'btn-republish', 'label': '重新发布', 'disabled': lambda d: d['status'] not in ['picked', 'failed']},
    ]
    hide_fields = ['_id', 'return_reason', 'create_time', 'updated_time', 'publish_by']
    update_fields = []

    def get(self):
        """ 任务管理-页任务管理"""
        try:
            kwargs = self.get_template_kwargs()
            key = re.sub(r'[\-/]', '_', self.request.path.strip('/'))
            hide_fields = json_util.loads(self.get_secure_cookie(key) or '[]')
            kwargs['hide_fields'] = hide_fields if hide_fields else kwargs['hide_fields']
            condition, params = self.get_task_search_condition(self.request.query, 'page')
            p = {f: 0 for f in ['input', 'result']}
            docs, pager, q, order = self.find_by_page(self, condition, self.search_fields, '-_id', p)
            self.render(
                'task_admin_page.html', docs=docs, pager=pager, order=order, q=q, params=params,
                format_value=self.format_value, **kwargs,
            )
        except Exception as error:
            return self.send_db_error(error)


class PageTaskStatHandler(PageHandler):
    URL = '/page/task/statistic'

    def get(self, collection):
        """ 根据用户、任务类型或任务状态统计页任务"""
        try:
            kind = self.get_query_argument('kind', '')
            if kind not in ['picked_user_id', 'task_type', 'status']:
                return self.send_error_response(e.statistic_type_error, message='只能按用户、任务类型或任务状态统计')

            condition = self.get_task_search_condition(self.request.query, collection)[0]
            counts = list(self.db.task.aggregate([
                {'$match': condition},
                {'$group': {'_id': '$%s' % kind, 'count': {'$sum': 1}}},
            ]))

            trans = {}
            if kind == 'picked_user_id':
                users = list(self.db.user.find({'_id': {'$in': [c['_id'] for c in counts]}}))
                trans = {u['_id']: u['name'] for u in users}
            elif kind == 'task_type':
                trans = self.task_names()
            elif kind == 'status':
                trans = self.task_statuses
            label = dict(picked_user_id='用户', task_type='任务类型', status='任务状态')[kind]

            self.render('task_statistic.html', counts=counts, kind=kind, label=label, trans=trans)

        except Exception as error:
            return self.send_db_error(error)


class PageTaskResumeHandler(PageHandler):
    URL = '/page/task/resume/@page_name'

    order = [
        'upload_cloud', 'ocr_box', 'cut_proof', 'cut_review', 'ocr_text', 'text_proof_1',
        'text_proof_2', 'text_proof_3', 'text_review', 'text_hard'
    ]
    display_fields = [
        'doc_id', 'task_type', 'status', 'pre_tasks', 'steps', 'priority',
        'updated_time', 'finished_time', 'publish_by', 'publish_time',
        'picked_by', 'picked_time', 'message'
    ]

    def get(self, page_name):
        """ 页任务简历"""
        from functools import cmp_to_key
        try:
            page = self.db.page.find_one({'name': page_name}) or dict(name=page_name)
            tasks = list(self.db.task.find({'collection': 'page', 'doc_id': page_name}))
            tasks.sort(key=cmp_to_key(lambda a, b: self.order.index(a['task_type']) - self.order.index(b['task_type'])))
            self.render('task_resume.html', page=page, tasks=tasks, display_fields=self.display_fields)

        except Exception as error:
            return self.send_db_error(error)


class PageTaskLobbyHandler(PageHandler):
    URL = '/task/lobby/@page_task'

    def get(self, task_type):
        """ 任务大厅"""

        try:
            q = self.get_query_argument('q', '')
            tasks, total_count = self.find_lobby(task_type, q=q)
            collection = self.get_data_collection(task_type)
            fields = [('doc_id', '页编码'), ('priority', '优先级')] if collection == 'page' else [
                ('txt_kind', '字种'), ('char_count', '单字数量')]
            self.render('task_lobby.html', tasks=tasks, task_type=task_type, total_count=total_count,
                        fields=fields, format_value=self.format_value)
        except Exception as error:
            return self.send_db_error(error)


class PageTaskMyHandler(PageHandler):
    URL = '/task/my/@page_task'

    search_tips = '请搜索页编码'
    search_fields = ['doc_id']
    operations = []
    img_operations = []
    actions = [
        {'action': 'my-task-view', 'label': '查看'},
        {'action': 'my-task-do', 'label': '继续', 'disabled': lambda d: d['status'] == 'finished'},
        {'action': 'my-task-update', 'label': '更新', 'disabled': lambda d: d['status'] == 'picked'},
    ]
    table_fields = [
        {'id': 'doc_id', 'name': '页编码'},
        {'id': 'task_type', 'name': '类型'},
        {'id': 'status', 'name': '状态'},
        {'id': 'picked_time', 'name': '领取时间'},
        {'id': 'finished_time', 'name': '完成时间'},
    ]
    hide_fields = ['task_type']
    info_fields = ['doc_id', 'task_type', 'status', 'picked_time', 'finished_time']
    update_fields = []

    def get(self, task_type):
        """ 我的任务"""
        try:
            condition = {
                'task_type': {'$regex': task_type} if self.is_group(task_type) else task_type,
                'status': {'$in': [self.STATUS_PICKED, self.STATUS_FINISHED]},
                'picked_user_id': self.user_id
            }
            docs, pager, q, order = self.find_by_page(self, condition, default_order='-picked_time')
            kwargs = self.get_template_kwargs()
            self.render('task_my.html', docs=docs, pager=pager, q=q, order=order,
                        format_value=self.format_value, **kwargs)

        except Exception as error:
            return self.send_db_error(error)
