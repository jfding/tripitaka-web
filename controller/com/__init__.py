#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 在 controller.com 包实现页面响应类，生成前端页面，modules 为重用网页片段的渲染类

from . import module, view

views = [
    view.HomeHandler, view.HelpHandler, view.AnnounceHandler
]

handlers = [
]

modules = {
    'ComLeft': module.ComLeft, 'ComHead': module.ComHead, 'Pager': module.Pager,
    'ComTable': module.ComTable, 'ComModal': module.ComModal,
}