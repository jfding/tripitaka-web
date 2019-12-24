#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@time: 2019/5/13
"""
import re
from tornado.web import UIModule
from bson.objectid import ObjectId
from controller import errors as e
from controller.text.diff import Diff
from controller.cut.cuttool import CutTool
from controller.task.base import TaskHandler
from controller.text.texttool import TextTool


class TextProofHandler(TaskHandler, TextTool):
    URL = ['/task/text_proof_@num/@task_id',
           '/task/do/text_proof_@num/@task_id',
           '/task/update/text_proof_@num/@task_id']

    def get(self, num, task_id):
        """ 文字校对页面 """
        try:
            # 检查参数
            task_type = 'text_proof_' + num
            task = self.db.task.find_one(dict(task_type=task_type, _id=ObjectId(task_id)))
            if not task:
                return self.render('_404.html')
            page = self.db.page.find_one({'name': task['doc_id']})
            if not page:
                return self.send_error_response(e.no_object, message='页面%s不存在' % task['doc_id'])
            # 检查权限
            has_auth, error = self.check_task_auth(task)
            if not has_auth:
                return self.send_error_response(error, message='%s (%s)' % (error[1], page['name']))
            # 设置步骤
            mode = self.get_task_mode()
            readonly = 'view' == mode
            steps = self.init_steps(task, mode, self.get_query_argument('step', ''))

            if steps['current'] == 'select_compare_text':
                return self.select_compare_text(task, page, mode, steps, readonly, num)
            else:
                return self.proof(task, page, mode, steps, readonly)

        except Exception as error:
            return self.send_db_error(error)

    def select_compare_text(self, task, page, mode, steps, readonly, num):
        self.render(
            'task_text_compare.html', task_type=task['task_type'], task=task, page=page,
            mode=mode, readonly=readonly, num=num, steps=steps, ocr=page.get('ocr'),
            cmp=self.prop(task, 'result.cmp'), get_img=self.get_img,
        )

    def proof(self, task, page, mode, steps, readonly):
        """ 文字校对
        文本来源有多种情况，ocr可能会输出两份数据，比对本可能有一份数据。
        """
        doubt = self.prop(task, 'result.doubt')
        CutTool.char_render(page, int(self.get_query_argument('layout', 0)))

        # 获取比对来源的文本
        cmp = self.prop(task, 'result.cmp')
        ocr, ocr_col = page.get('ocr', ''), page.get('ocr_col', '')
        texts = dict(base=re.sub(r'\|+', '\n', ocr), cmp1=ocr_col, cmp2=cmp)
        labels = dict(base='字框OCR', cmp1='列框OCR', cmp2='比对文本')

        # 检查是否已进行比对
        params = dict(mismatch_lines=[])
        cmp_data = self.prop(task, 'result.txt_html')
        if not cmp_data or self.get_query_argument('re_compare', '') == 'true':
            segments = Diff.diff(texts['base'], texts['cmp1'], texts['cmp2'])[0]
            cmp_data = self.check_segments(segments, page['chars'], params)

        self.render(
            'task_text_proof.html', page_title='文字校对', task_type=task['task_type'], task=task, page=page,
            mode=mode, readonly=readonly, texts=texts, labels=labels, cmp_data=cmp_data, doubt=doubt,
            message='', steps=steps, get_img=self.get_img, **params
        )


class TextReviewHandler(TaskHandler, TextTool):
    URL = ['/task/text_review/@task_id',
           '/task/do/text_review/@task_id',
           '/task/update/text_review/@task_id']

    @staticmethod
    def get_cmp_data(self, doc_id, page):
        """ 如果有文字校对任务，则从文字校对中获取比对文本。如果没有，则依次从text/ocr中获取比对文本"""
        has_proof, doubt, proofs = False, '', ['', '', '']
        condition = {'doc_id': doc_id, 'status': self.STATUS_FINISHED}
        for i in [1, 2, 3]:
            condition['task_type'] = 'text_proof_%s' % i
            proof_task = self.db.task.find_one(condition)
            if proof_task:
                has_proof = True
                doubt += self.prop(proof_task, 'result.doubt', '')
                proofs[i - 1] = self.html2txt(self.prop(proof_task, 'result.txt_html', ''))

        texts, labels = dict(base='', cmp1='', cmp2=''), dict(base='', cmp1='', cmp2='')
        text, ocr, ocr_col = page.get('text', ''), page.get('ocr', ''), page.get('ocr_col', '')
        if has_proof:
            texts.update(dict(base=proofs[0], cmp1=proofs[1], cmp2=proofs[2]))
            labels.update(dict(base='校一', cmp1='校一', cmp2='校三'))
        elif text:
            texts.update(dict(base=re.sub(r'\|+', '\n', text), cmp1=ocr, cmp2=ocr_col))
            labels.update(dict(base='审定文本', cmp1='字框OCR', cmp2='列框OCR'))
        elif ocr:
            texts.update(dict(base=re.sub(r'\|+', '\n', ocr), cmp1=ocr_col))
            labels.update(dict(base='字框OCR', cmp1='列框OCR'))
        elif ocr_col:
            texts.update(dict(base=re.sub(r'\|+', '\n', ocr_col)))
            labels.update(dict(base='列框OCR'))

        return texts, labels, doubt

    def get(self, task_id):
        """ 文字审定页面"""
        try:
            task_type = 'text_review'
            task = self.db.task.find_one(dict(task_type=task_type, _id=ObjectId(task_id)))
            if not task:
                return self.render('_404.html')
            page = self.db.page.find_one({'name': task['doc_id']})
            if not page:
                return self.send_error_response(e.no_object, message='页面%s不存在' % task['doc_id'])

            # 检查任务权限及数据锁
            has_auth, error = self.check_task_auth(task)
            if not has_auth:
                return self.send_error_response(error, message='%s (%s)' % (error[1], page['name']))
            has_lock, error = self.check_data_lock(task)
            message = '' if has_lock else str(error[1])

            # 字框排序
            params = dict(mismatch_lines=[])
            CutTool.char_render(page, int(self.get_query_argument('layout', 0)), **params)

            mode = self.get_task_mode()
            review_doubt = self.prop(task, 'result.doubt')
            texts, labels, proof_doubt = self.get_cmp_data(self, task['doc_id'], page)
            cmp_data = self.prop(page, 'txt_html')
            if not cmp_data:
                segments = Diff.diff(texts['base'], texts['cmp1'], texts['cmp2'])[0]
                cmp_data = self.check_segments(segments, page['chars'], params)

            self.render(
                'task_text_review.html', page_title='文字审定', task_type=task_type, task=task, page=page,
                mode=mode, readonly=not has_lock, texts=texts, labels=labels, cmp_data=cmp_data,
                doubt=review_doubt, pre_doubt=proof_doubt, message=message, get_img=self.get_img,
                steps=dict(is_first=True, is_last=True), **params,
            )

        except Exception as error:
            return self.send_db_error(error)


class TextHardHandler(TextReviewHandler):
    URL = ['/task/text_hard/@task_id',
           '/task/do/text_hard/@task_id',
           '/task/update/text_hard/@task_id']

    def get(self, task_id):
        """ 难字审定页面 """
        try:
            task_type = 'text_hard'
            task = self.db.task.find_one(dict(task_type=task_type, _id=ObjectId(task_id)))
            if not task:
                return self.render('_404.html')
            page = self.db.page.find_one({'name': task['doc_id']})
            if not page:
                return self.send_error_response(e.no_object, message='页面%s不存在' % task['doc_id'])

            # 检查任务权限及数据锁
            has_auth, error = self.check_task_auth(task)
            if not has_auth:
                return self.send_error_response(error, message='%s (%s)' % (error[1], page['name']))
            has_lock, error = self.check_data_lock(task)
            message = '' if has_lock else str(error[1])

            mode = self.get_task_mode()
            texts, labels, proof_doubt = self.get_cmp_data(self, task['doc_id'], page)
            review_task = self.db.task.find_one({'_id': self.prop(task, 'input.review_task')})
            review_doubt = self.prop(review_task, 'result.doubt') if review_task else None
            hard_doubt = self.prop(task, 'result.doubt')
            cmp_data = self.prop(page, 'txt_html')
            self.render(
                'task_text_review.html', page_title='难字审定', task_type=task_type, task=task, page=page,
                mode=mode, readonly=not has_lock, cmp_data=cmp_data, texts=texts, labels=labels,
                doubt=hard_doubt, pre_doubt=review_doubt, message=message,
                steps=dict(is_first=True, is_last=True),
                get_img=self.get_img,
            )

        except Exception as error:
            return self.send_db_error(error)


class TextEditHandler(TaskHandler, TextTool):
    URL = '/data/edit/text/@page_name'

    def get(self, page_name):
        """ 文字修改页面 """

        try:
            page = self.db.page.find_one({'name': page_name})
            if not page:
                return self.send_error_response(e.no_object)
            if not page.get('txt_html') and not page.get('text'):
                self.send_error_response(e.no_object, message='没有找到审定文本')

            r = self.assign_temp_lock(page_name, 'text')
            has_lock, message = r is True, '' if r is True else str(r[1])

            cmp_data = self.prop(page, 'txt_html', '')
            if not cmp_data and self.prop(page, 'text'):
                segments = Diff.diff(page['text'].replace('|', '\n'))[0]
                cmp_data = self.check_segments(segments, page['chars'], dict(mismatch_lines=[]))

            kwargs = dict(task_type='', task={}, texts={}, labels={}, doubt='', pre_doubt='',
                          steps=dict(is_first=True, is_last=True))
            self.render(
                'task_text_review.html', page_title='难字审定', page=page, mode='edit',
                readonly=not has_lock, cmp_data=cmp_data, message=message,
                get_img=self.get_img, **kwargs
            )

        except Exception as error:
            return self.send_db_error(error)


class TextArea(UIModule):
    """文字校对的文字区"""

    def render(self, segments, raw=False):
        cur_line_no, items, lines = 0, [], []
        blocks = [dict(block_no=1, lines=lines)]
        for item in segments:
            if 'block_no' in item and item['block_no'] != blocks[-1]['block_no']:
                lines = []
                blocks.append(dict(block_no=blocks[-1]['block_no'] + 1, lines=lines))
            if item['line_no'] != cur_line_no:
                cur_line_no = item['line_no']
                items = [item]
                lines.append(dict(line_no=cur_line_no, items=items))
                item['offset'] = 0
            elif items:
                item['offset'] = items[-1]['offset'] + len(items[-1]['base'])
                if item['base'] != '\n':
                    items.append(item)
            item['block_no'] = blocks[-1]['block_no']

        return dict(blocks=blocks) if raw else self.render_string('task_text_area.html', blocks=blocks)