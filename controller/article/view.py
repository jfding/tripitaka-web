#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@time: 2019/11/17
"""
from controller import errors
from controller.base import BaseHandler
from controller.article.article import Article


class ListArticleHandler(BaseHandler):
    URL = '/article'

    def get(self):
        """ 文章管理"""
        try:
            docs, pager, q, order = Article.find_by_page(self)
            self.render('article_list.html', docs=docs, pager=pager, order=order, fields=Article.fields, q=q,
                        operations=Article.operations, actions=Article.actions, search_tip=Article.search_tip,
                        title=Article.page_title)

        except Exception as error:
            return self.send_db_error(error)


class ArticleAddOrUpdateHandler(BaseHandler):
    URL = ['/article/add', '/article/update/@article_id']

    def get(self, article_id=None):
        """ 新建或修改文章"""
        try:
            article = article_id and self.db.article.find_one({'article_id': article_id}) or {}
            if article_id and not article:
                return self.send_error_response(errors.no_object, message='文章%s不存在' % article_id)
            self.render('article_edit.html', article=article, article_id=article_id or '')
        except Exception as error:
            return self.send_db_error(error)


class ArticleViewHandler(BaseHandler):
    URL = '/article/@article_id'

    def get(self, article_id):
        """ 查看文章"""
        try:
            article = self.db.article.find_one({'article_id': article_id})
            if not article:
                return self.send_error_response(errors.no_object, message='文章%s不存在' % article_id)
            self.render('article_view.html', article=article, article_id=article_id)

        except Exception as error:
            return self.send_db_error(error)
