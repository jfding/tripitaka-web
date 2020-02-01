#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@desc: 任务Handler。
一、mode 任务模式
1. do。用户做任务时，进入该模式
2. update。用户完成任务后，可以通过update模式进行修改
3. view。非任务所有者可以通过view模式来查看任务
4. browse。管理员可以通过browse模式来逐条浏览任务
5. edit。edit提供给专家用户修改数据使用
二、 url
如：/task/(do/update/browse)/@task_type/5e3139c6a197150011d65e9d
或  /task/@task_type/5e3139c6a197150011d65e9d

@time: 2019/10/16
"""
import re
import random
from datetime import datetime
from bson.objectid import ObjectId
from controller import errors as e
from controller.task.task import Task
from controller.task.lock import Lock
from controller.base import BaseHandler
from controller.helper import get_url_param


class TaskHandler(BaseHandler, Task, Lock):
    def __init__(self, application, request, **kwargs):
        """ 参数说明
        :param mode: 包括do/update/view/browse等几种模式，如前述
        :param readonly: 是否只读。view/browse模式下，默认是只读。update模式下，如果没有数据锁，也是只读
        :param has_lock: 是否有数据锁。详见controller.task.lock
        """
        super(TaskHandler, self).__init__(application, request, **kwargs)
        self.task_type = self.task_id = self.doc_id = self.message = ''
        self.mode = self.has_lock = self.readonly = self.is_api = None
        self.task = self.steps = self.doc = {}

    def prepare(self):
        """ 设置任务相关参数，检查任务是否存在、任务权限以及任务锁
        如果非任务的url请求需要使用该handler，则需要重载get_doc_id/get_task_type函数。
        prepare函数中将会根据task_type/doc_id这两个参数设置任务步骤、数据以及检查数据锁。
        """
        super().prepare()
        if self.error:
            return
        self.task = {}
        self.has_lock = None
        self.mode = self.get_task_mode()
        self.task_id = self.get_task_id()
        # 检查任务
        if self.task_id:
            # 任务是否存在
            self.task, self.error = self.get_task(self.task_id)
            if not self.task:
                return self.send_error_response(self.error)
            # do和update模式下，检查任务权限
            if self.mode in ['do', 'update']:
                has_auth, self.error = self.check_task_auth(self.task)
                if not has_auth:
                    return self.send_error_response(self.error)
        # 检查数据
        self.doc_id = self.task.get('doc_id') or self.get_doc_id()
        self.task_type = self.task.get('task_type') or self.get_task_type()
        collection, id_name, input_field, shared_field = self.get_data_conf(self.task_type)
        if self.doc_id:
            # 数据是否存在
            self.doc = self.db[collection].find_one({id_name: self.doc_id})
            if not self.doc:
                return self.send_error_response(e.no_object, message='数据%s不存在' % self.doc_id)
            # do/update/edit模式下，检查数据锁
            if self.mode in ['do', 'update', 'edit']:
                self.has_lock, error = self.check_data_lock(self.doc_id, self.get_shared_field(self.task_type))
                # 获取数据锁失败，直接报错返回
                if self.has_lock is False:
                    return self.send_error_response(error)
        # 设置其它参数
        self.steps = self.init_steps(self.task, self.task_type)
        self.readonly = self.mode in ['view', 'browse']

    def get_task(self, task_id):
        """ 根据task_id/to以及相关条件查找任务"""
        # 查找当前任务
        task = self.db.task.find_one({'_id': ObjectId(task_id)})
        if not task:
            return None, (e.task_not_existed[0], '没有找到任务%s' % task_id)
        to = self.get_query_argument('to', '')
        if not to:
            return task, None
        # 查找目标任务。to为prev时，查找前一个任务，即_id比task_id大的任务
        condition = self.get_search_condition(self.request.query)[0]
        condition.update({'_id': {'$gt' if to == 'prev' else '$lt': ObjectId(task_id)}})
        to_task = self.db.task.find_one(condition, sort=[('_id', 1 if to == 'prev' else -1)])
        if not to_task:
            error = e.task_not_existed[0], '没有找到任务%s的%s任务' % (task_id, '前一个' if to == 'prev' else '后一个')
            return None, error
        elif task['task_type'] != to_task['task_type']:
            # 如果task和to_task任务类型不一致，则切换url
            query = re.sub('[?&]to=(prev|next)', '', self.request.query)
            url = '/task/browse/%s/%s?' % (to_task['task_type'], to_task['_id']) + query
            self.redirect(url.rstrip('?'))
            return None, e.task_type_error
        return to_task, None

    def get_doc_id(self):
        """ 获取数据id。供子类重载，以便prepare函数调用"""
        pass

    def get_task_type(self):
        """ 设置任务类型。子类可以重载本函数来设置task_type"""
        s = re.search(r'/(do|update|browse)/([^/]+?)/([0-9a-z]{24})', self.request.path)
        return s.group(2) if s else ''

    def get_task_mode(self):
        return (re.findall('/(do|update|edit|browse)/', self.request.path) or ['view'])[0]

    def get_task_id(self):
        s = re.search(r'/([0-9a-z]{24})(\?|$|\/)', self.request.path)
        return s.group(1) if s else ''

    def task_name(self):
        return self.get_task_name(self.task_type)

    def step_name(self):
        return self.get_step_name(self.steps.get('current')) or ''

    def find_many(self, task_type=None, status=None, size=None, order=None):
        """ 查找任务 """
        condition = dict()
        if task_type:
            condition.update({'task_type': {'$regex': task_type} if self.is_group(task_type) else task_type})
        if status:
            condition.update({'status': status if isinstance(status, str) else {'$in': status}})
        query = self.db.task.find(condition)
        if size:
            query.limit(size)
        if order:
            o, asc = (order[1:], -1) if order[0] == '-' else (order, 1)
            query.sort(o, asc)
        return list(query)

    def find_mine(self, task_type=None, page_size=None, order=None, status=None):
        """ 查找我的任务"""
        assert status in [None, self.STATUS_PICKED, self.STATUS_FINISHED]
        condition = {'picked_user_id': self.current_user['_id']}
        if task_type:
            condition.update({'task_type': {'$regex': task_type} if self.is_group(task_type) else task_type})
        if status:
            condition.update({'status': status})
        else:
            condition.update({'status': {'$in': [self.STATUS_PICKED, self.STATUS_FINISHED]}})
        query = self.db.task.find(condition)
        if page_size:
            query.limit(page_size)
        if order:
            o, asc = (order[1:], -1) if order[0] == '-' else (order, 1)
            query.sort(o, asc)
        return list(query)

    def find_lobby(self, task_type, page_size=None, q=None):
        """ 按优先级排序后随机获取任务大厅的任务列表"""

        def get_random_skip():
            condition.update(dict(priority=3))
            n3 = self.db.task.count_documents(condition)
            condition.update(dict(priority=2))
            n2 = self.db.task.count_documents(condition)
            condition.pop('priority', 0)
            skip = n3 if n3 > page_size else n3 + n2 if n3 + n2 > page_size else total_count
            return random.randint(1, skip - page_size) if skip > page_size else 0

        def de_duplicate():
            """ 组任务去重"""
            _tasks, _doc_ids = [], []
            for task in tasks:
                if task.get('doc_id') not in _doc_ids:
                    _tasks.append(task)
                    _doc_ids.append(task.get('doc_id'))
            return _tasks[:page_size]

        page_size = page_size or self.prop(self.config, 'pager.page_size', 10)
        condition = {'doc_id': {'$regex': q, '$options': '$i'}} if q else {}
        if self.is_group(task_type):
            condition.update({'task_type': {'$regex': task_type}, 'status': self.STATUS_PUBLISHED})
            # 去掉同组的我的任务
            my_tasks = self.find_mine(task_type)
            if my_tasks:
                condition.update({'doc_id': {'$nin': [t['doc_id'] for t in my_tasks]}})
            total_count = self.db.task.count_documents(condition)
            skip_no = get_random_skip()
            # 按3倍量查询后去重
            tasks = list(self.db.task.find(condition).skip(skip_no).sort('priority', -1).limit(page_size * 3))
            tasks = de_duplicate()
        else:
            condition.update({'task_type': task_type, 'status': self.STATUS_PUBLISHED})
            total_count = self.db.task.count_documents(condition)
            skip_no = get_random_skip()
            tasks = list(self.db.task.find(condition).skip(skip_no).sort('priority', -1).limit(page_size))

        return tasks, total_count

    def count_task(self, task_type=None, status=None, mine=False):
        """ 统计任务数量"""
        condition = dict()
        if task_type:
            condition.update({'task_type': {'$regex': task_type} if self.is_group(task_type) else task_type})
        if status:
            condition.update({'status': {'$in': [status] if isinstance(status, str) else status}})
        if mine:
            con_status = condition.get('status') or {}
            con_status.update({'$ne': self.STATUS_RETURNED})
            condition.update({'status': con_status})
            condition.update({'picked_user_id': self.current_user['_id']})
        return self.db.task.count_documents(condition)

    def get_publish_meta(self, task_type):
        now = datetime.now()
        collection, id_name = self.get_data_conf(task_type)[:2]
        return dict(
            task_type=task_type, batch='', collection=collection, id_name=id_name, doc_id='',
            status='', priority='', steps={}, pre_tasks=[], input=None, result={},
            create_time=now, updated_time=now, publish_time=now,
            publish_user_id=self.current_user['_id'],
            publish_by=self.current_user['name']
        )

    def init_steps(self, task, task_type=None):
        """ 检查当前任务的步骤，缺省时自动填充默认设置，有误时报错"""
        steps = dict()
        current_step = self.get_query_argument('step', '')
        todo = self.prop(task, 'steps.todo') or self.get_steps(task_type) or ['']
        submitted = self.prop(task, 'steps.submitted') or ['']
        un_submitted = [s for s in todo if s not in submitted]
        if not current_step:
            current_step = un_submitted[0] if self.mode == 'do' else todo[0]
        elif current_step and current_step not in todo:
            current_step = todo[0]
        index = todo.index(current_step)
        steps['current'] = current_step
        steps['is_first'] = index == 0
        steps['is_last'] = index == len(todo) - 1
        steps['prev'] = todo[index - 1] if index > 0 else None
        steps['next'] = todo[index + 1] if index < len(todo) - 1 else None
        return steps

    def finish_task(self, task):
        """ 完成任务 """
        # 更新当前任务
        update = {'status': self.STATUS_FINISHED, 'finished_time': datetime.now()}
        self.db.task.update_one({'_id': task['_id']}, {'$set': update})
        self.release_task_lock(task, self.current_user, update_level=True)
        self.update_doc(task, self.STATUS_FINISHED)
        self.add_op_log('finish_%s' % task['task_type'], target_id=task['_id'])
        # 更新后置任务
        condition = dict(collection=task['collection'], id_name=task['id_name'], doc_id=task['doc_id'])
        tasks = list(self.db.task.find(condition))
        finished_types = [t['task_type'] for t in tasks if t['status'] == self.STATUS_FINISHED]
        for _task in tasks:
            # 检查任务task的所有pre_tasks的状态
            pre_tasks = self.prop(_task, 'pre_tasks', {})
            pre_tasks.update({p: self.STATUS_FINISHED for p in pre_tasks if p in finished_types})
            update = {'pre_tasks': pre_tasks}
            # 如果当前任务为悬挂，且所有前置任务均已完成，则修改状态为已发布
            unfinished = [v for v in pre_tasks.values() if v != self.STATUS_FINISHED]
            if _task['status'] == self.STATUS_PENDING and not unfinished:
                update.update({'status': self.STATUS_PUBLISHED})
                self.update_doc(_task, self.STATUS_PUBLISHED)
            self.db.task.update_one({'_id': _task['_id']}, {'$set': update})

    def update_doc(self, task, status=None):
        """ 更新任务所关联的数据"""
        if task['doc_id']:
            collection, id_name = self.get_data_conf(task['task_type'])[:2]
            condition = {id_name: task['doc_id']}
            if status:
                self.db[collection].update_one(condition, {'$set': {'tasks.' + task['task_type']: status}})
            else:
                self.db[collection].update_one(condition, {'$unset': {'tasks.' + task['task_type']: ''}})

    def update_docs(self, doc_ids, task_type, status):
        """ 更新数据的任务状态"""
        collection, id_name = self.get_data_conf(task_type)[:2]
        self.db[collection].update_many({id_name: {'$in': list(doc_ids)}}, {'$set': {'tasks.' + task_type: status}})

    def check_task_auth(self, task, mode=None):
        """ 检查当前用户是否拥有相应的任务权限"""
        mode = self.get_task_mode() if not mode else mode
        error = (None, '')
        if mode in ['do', 'update']:
            if task.get('picked_user_id') != self.current_user.get('_id'):
                error = e.task_unauthorized_locked
            elif mode == 'do' and task['status'] != self.STATUS_PICKED:
                error = e.task_can_only_do_picked
            elif mode == 'update' and task['status'] != self.STATUS_FINISHED:
                error = e.task_can_only_update_finished
        has_auth = error[0] is None
        return has_auth, error

    def check_data_lock(self, doc_id=None, shared_field=None, mode=None):
        """ 检查当前用户是否拥有相应的数据锁。
        has_lock为None表示不需要数据锁，False表示获取失败，True表示获取成功
        """
        mode = self.mode if not mode else mode
        has_lock, error = None, (None, '')
        # do模式下，检查是否有任务锁
        if shared_field and mode == 'do':
            lock = self.get_data_lock_and_level(doc_id, shared_field)[0]
            assert lock
            has_lock = self.current_user['_id'] == self.prop(lock, 'locked_user_id')
            error = e.data_is_locked
        # update/模式下，尝试分配临时数据锁
        if shared_field and mode in ['update', 'edit']:
            r = self.assign_temp_lock(doc_id, shared_field, self.current_user)
            has_lock = r is True
            error = (None, '') if has_lock else r
        return has_lock, error

    @staticmethod
    def get_search_condition(request_query):
        """ 获取任务的查询条件"""
        condition, params = dict(), dict()
        for field in ['task_type', 'collection', 'status', 'priority']:
            value = get_url_param(field, request_query)
            if value:
                params[field] = value
                condition.update({field: value})
        for field in ['batch', 'doc_id', 'remark']:
            value = get_url_param(field, request_query)
            if value:
                params[field] = value
                condition.update({field: {'$regex': value, '$options': '$i'}})
        picked_user_id = get_url_param('picked_user_id', request_query)
        if picked_user_id:
            params['picked_user_id'] = picked_user_id
            condition.update({'picked_user_id': ObjectId(picked_user_id)})
        publish_start = get_url_param('publish_start', request_query)
        if publish_start:
            params['publish_start'] = publish_start
            condition['publish_time'] = {'$gt': datetime.strptime(publish_start, '%Y-%m-%d %H:%M:%S')}
        publish_end = get_url_param('publish_end', request_query)
        if publish_end:
            params['publish_end'] = publish_end
            condition['publish_time'] = condition.get('publish_time') or {}
            condition['publish_time'].update({'$lt': datetime.strptime(publish_end, '%Y-%m-%d %H:%M:%S')})
        picked_start = get_url_param('picked_start', request_query)
        if picked_start:
            params['picked_start'] = picked_start
            condition['picked_time'] = {'$gt': datetime.strptime(picked_start, '%Y-%m-%d %H:%M:%S')}
        picked_end = get_url_param('picked_end', request_query)
        if picked_end:
            params['picked_end'] = picked_end
            condition['picked_time'] = condition.get('picked_time') or {}
            condition['picked_time'].update({'$lt': datetime.strptime(picked_end, '%Y-%m-%d %H:%M:%S')})
        finished_start = get_url_param('finished_start', request_query)
        if finished_start:
            params['finished_start'] = finished_start
            condition['picked_time'] = {'$gt': datetime.strptime(finished_start, '%Y-%m-%d %H:%M:%S')}
        finished_end = get_url_param('finished_end', request_query)
        if finished_end:
            params['finished_end'] = finished_end
            condition['finished_time'] = condition.get('finished_time') or {}
            condition['finished_time'].update({'$lt': datetime.strptime(finished_end, '%Y-%m-%d %H:%M:%S')})
        return condition, params
