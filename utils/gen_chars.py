#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 将page['chars']中的数据同步到char表，包括增删改等
# 数据同步时，检查字框的char_id字序信息和x/y/w/h等位置信息，如果发生了改变，则进行同步
# python3 utils/extract_img.py --condition= --user_name=

import sys
import json
import math
import pymongo
from os import path
from datetime import datetime

BASE_DIR = path.dirname(path.dirname(__file__))
sys.path.append(BASE_DIR)

from controller import helper as hp
from controller.base import BaseHandler as Bh


def gen_chars(db=None, db_name='tripitaka', uri=None, reset=False,
              condition=None, page_names=None, username=None):
    """ 从页数据中导出字数据"""

    def is_changed(a, b):
        """ 检查坐标和字序是否发生变化"""
        if a['char_id'] != b['char_id']:
            return True
        for k in ['x', 'y', 'w', 'h']:
            if a['pos'][k] != b['pos'][k]:
                return True
        for k in ['x', 'y', 'w', 'h', 'cid']:
            if not a.get('column') or not b.get('column'):
                return True
            if a['column'][k] != b['column'][k]:
                return True
        return False

    db = db or uri and pymongo.MongoClient(uri)[db_name] or hp.connect_db(hp.load_config()['database'])[0]
    if reset:
        db.char.delete_many({})

    if page_names:
        page_names = page_names.split(',') if isinstance(page_names, str) else page_names
        condition = {'name': {'$in': page_names}}
    elif isinstance(condition, str):
        condition = json.loads(condition)
    elif not condition:
        condition = {}

    names = ['GL_1047_1_11', 'GL_1047_1_15', 'GL_1047_1_21', 'GL_1047_1_34', 'GL_1047_1_5', 'GL_1047_2_17',
             'GL_1047_3_15', 'GL_1047_3_5', 'GL_1047_4_35', 'GL_1048_1_19', 'GL_1048_1_22', 'GL_1048_1_25',
             'GL_1048_1_39', 'GL_1048_1_43', 'GL_1048_2_21', 'GL_1048_2_26', 'GL_1048_2_29', 'GL_1048_2_30',
             'GL_1048_2_59', 'GL_1049_1_10', 'GL_1049_1_15', 'GL_1049_1_21', 'GL_1049_1_27', 'GL_1049_1_4',
             'GL_1049_1_53', 'GL_1051_7_17', 'GL_1051_7_23', 'GL_1051_7_25', 'GL_1051_8_11', 'GL_1051_8_9',
             'GL_1054_1_11', 'GL_1054_1_12', 'GL_1054_1_13', 'GL_1054_1_14', 'GL_1054_1_19', 'GL_1054_1_23',
             'GL_1054_1_3', 'GL_1054_1_4', 'GL_1054_2_11', 'GL_1054_2_15', 'GL_1054_3_2', 'GL_1054_3_20', 'GL_1054_4_2',
             'GL_1054_4_4', 'GL_1054_4_5', 'GL_1054_4_7', 'GL_1054_5_13', 'GL_1054_5_4', 'GL_1054_5_5', 'GL_1054_6_2',
             'GL_1056_1_16', 'GL_1056_1_20', 'GL_1056_1_22', 'GL_1056_1_27', 'GL_1056_1_28', 'GL_1056_1_8',
             'GL_1056_2_10', 'GL_1056_2_17', 'GL_1056_2_18', 'GL_1056_2_20', 'GL_1056_2_21', 'GL_1056_2_22',
             'GL_1056_2_24', 'GL_1056_2_26', 'GL_1056_2_3', 'GL_1056_2_4', 'GL_1056_2_6', 'GL_1056_3_11', 'GL_1056_3_2',
             'GL_1056_3_29', 'GL_1056_3_37', 'GL_1056_4_11', 'GL_1056_4_15', 'GL_1056_4_16', 'GL_1056_4_7',
             'GL_1056_5_10', 'GL_1056_5_12', 'GL_1056_5_13', 'GL_1056_5_15', 'GL_1056_5_6', 'GL_1260_10_10',
             'GL_1260_10_6', 'GL_1260_10_7', 'GL_1260_10_8', 'GL_1260_10_9', 'GL_1260_11_11', 'GL_1260_11_12',
             'GL_1260_1_11', 'GL_1260_1_3', 'GL_1260_1_7', 'GL_1260_1_9', 'GL_1260_2_4', 'GL_1260_3_3', 'GL_1260_3_8',
             'GL_1260_4_2', 'GL_1260_4_3', 'GL_1260_4_8', 'GL_1260_4_9', 'GL_1260_5_2', 'GL_1260_5_3', 'GL_1260_5_4',
             'GL_1260_5_7', 'GL_1260_7_11', 'GL_1260_7_7', 'GL_1260_7_9', 'GL_1260_8_11', 'GL_1260_8_2', 'GL_1260_8_3',
             'GL_1260_8_4', 'GL_1260_8_8', 'GL_1260_9_3', 'GL_1260_9_5', 'GL_1260_9_7', 'GL_127_6_17', 'GL_127_7_11',
             'GL_127_7_8', 'GL_128_3_13', 'GL_128_3_15', 'GL_129_1_11', 'GL_129_1_12', 'GL_129_1_25', 'GL_129_2_23',
             'GL_129_2_25', 'GL_129_3_10', 'GL_129_3_17', 'GL_129_3_27', 'GL_131_4_5', 'GL_136_4_8', 'GL_1418_4_10',
             'GL_1418_4_3', 'GL_1418_4_7', 'GL_1418_4_9', 'GL_1425_3_9', 'GL_1426_2_8', 'GL_1434_4_15', 'GL_1434_5_10',
             'GL_1434_5_11', 'GL_1434_5_5', 'GL_1439_1_9', 'GL_143_1_20', 'GL_143_1_22', 'GL_143_2_19', 'GL_143_4_23',
             'GL_143_4_6', 'GL_1440_1_6', 'GL_1442_1_14', 'GL_1442_1_8', 'GL_1452_2_9', 'GL_1454_1_8', 'GL_1454_1_9',
             'GL_1454_2_13', 'GL_1454_2_14', 'GL_1454_3_12', 'GL_1454_3_13', 'GL_1454_3_15', 'GL_1454_3_6',
             'GL_1456_1_12', 'GL_1462_2_4', 'GL_1462_2_5', 'GL_1462_2_6', 'GL_1481_18_5', 'GL_1484_1_4', 'GL_1486_17_9',
             'GL_1486_20_6', 'GL_157_2_14', 'GL_159_1_7', 'GL_159_3_29', 'GL_165_1_12', 'GL_165_1_28', 'GL_166_2_5',
             'GL_167_1_18', 'GL_167_1_25', 'GL_174_3_3', 'GL_57_1_29', 'GL_57_5_11', 'GL_585_2_15', 'GL_61_1_15',
             'GL_62_1_15', 'GL_62_1_32', 'GL_62_1_37', 'GL_63_1_23', 'GL_70_1_8', 'GL_74_4_16', 'GL_765_1_7',
             'GL_77_2_27', 'GL_77_2_28', 'GL_78_2_15', 'GL_78_6_13', 'GL_78_6_16', 'GL_78_9_18', 'GL_807_1_12',
             'GL_807_1_14', 'GL_807_1_18', 'GL_807_1_2', 'GL_807_1_20', 'GL_807_1_21', 'GL_807_1_24', 'GL_807_1_9',
             'GL_807_2_10', 'GL_807_2_14', 'GL_807_2_15', 'GL_807_2_19', 'GL_807_2_21', 'GL_807_2_4', 'GL_807_2_5',
             'GL_807_2_7', 'GL_807_2_8', 'GL_82_1_5', 'GL_82_2_8', 'GL_89_5_19', 'GL_8_5_10', 'GL_905_1_14',
             'GL_905_1_37', 'GL_908_1_2', 'GL_914_10_10', 'GL_914_10_3', 'GL_914_10_7', 'GL_914_1_16', 'GL_914_1_20',
             'GL_914_1_9', 'GL_914_2_12', 'GL_914_2_18', 'GL_914_2_2', 'GL_914_4_15', 'GL_914_4_3', 'GL_914_5_18',
             'GL_914_5_19', 'GL_914_8_15', 'GL_914_8_19', 'GL_914_9_17', 'GL_914_9_20', 'GL_922_1_10', 'GL_922_1_12',
             'GL_922_1_14', 'GL_922_1_16', 'GL_922_1_17', 'GL_922_1_18', 'GL_922_1_21', 'GL_922_1_24', 'GL_922_1_29',
             'GL_922_1_30', 'GL_922_1_34', 'GL_922_1_4', 'GL_922_1_5', 'GL_922_1_6', 'GL_922_1_8', 'GL_922_1_9',
             'GL_922_2_21', 'GL_922_2_28', 'GL_922_2_32', 'GL_923_1_11', 'GL_923_1_12', 'GL_923_1_14', 'GL_923_1_22',
             'GL_923_1_23', 'GL_923_1_36', 'GL_923_1_40', 'GL_923_1_6', 'GL_923_1_7', 'GL_923_2_16', 'GL_923_2_17',
             'GL_923_2_20', 'GL_923_2_23', 'GL_923_2_24', 'GL_923_2_25', 'GL_923_2_30', 'GL_923_2_34', 'GL_923_2_6',
             'GL_923_2_7', 'GL_923_2_9', 'GL_924_1_10', 'GL_924_1_11', 'GL_924_1_12', 'GL_924_1_14', 'GL_924_1_18',
             'GL_924_1_19', 'GL_924_1_2', 'GL_924_1_26', 'GL_924_1_5', 'GL_924_1_7', 'GL_924_2_13', 'GL_924_2_17',
             'GL_924_2_21', 'GL_924_2_23', 'GL_924_2_26', 'GL_924_2_29', 'GL_924_2_30', 'GL_924_2_33', 'GL_924_2_35',
             'GL_924_2_5', 'GL_924_3_22', 'GL_924_3_26', 'GL_941_9_25', 'GL_959_3_15', 'GL_989_3_15', 'GL_989_3_35',
             'GL_9_1_12', 'GL_9_1_13', 'GL_9_1_16', 'GL_9_1_9', 'JX_165_7_115', 'JX_165_7_12', 'JX_165_7_135',
             'JX_165_7_18', 'JX_165_7_27', 'JX_165_7_30', 'JX_165_7_43', 'JX_165_7_70', 'JX_165_7_72', 'JX_165_7_75',
             'JX_165_7_85', 'JX_165_7_87', 'JX_245_1_130', 'JX_245_1_133', 'JX_245_1_136', 'JX_245_1_138',
             'JX_245_1_140', 'JX_245_1_146', 'JX_245_1_153', 'JX_245_1_21', 'JX_245_1_24', 'JX_245_1_44', 'JX_245_1_49',
             'JX_245_1_70', 'JX_245_2_128', 'JX_245_2_150', 'JX_245_2_151', 'JX_245_2_152', 'JX_245_2_154',
             'JX_245_2_155', 'JX_245_2_156', 'JX_245_2_157', 'JX_245_2_158', 'JX_245_2_159', 'JX_245_2_160',
             'JX_245_2_161', 'JX_245_2_162', 'JX_245_2_163', 'JX_245_2_164', 'JX_245_2_165', 'JX_245_2_167',
             'JX_245_2_168', 'JX_245_2_173', 'JX_245_2_179', 'JX_245_2_189', 'JX_245_2_19', 'JX_245_2_23',
             'JX_245_2_42', 'JX_245_2_46', 'JX_245_2_75', 'JX_245_2_84', 'JX_245_3_1', 'JX_245_3_100', 'JX_245_3_102',
             'JX_245_3_104', 'JX_245_3_111', 'JX_245_3_115', 'JX_245_3_120', 'JX_245_3_121', 'JX_245_3_126',
             'JX_245_3_130', 'JX_245_3_141', 'JX_245_3_142', 'JX_245_3_146', 'JX_245_3_148', 'JX_245_3_153',
             'JX_245_3_159', 'JX_245_3_160', 'JX_245_3_161', 'JX_245_3_164', 'JX_245_3_168', 'JX_245_3_170',
             'JX_245_3_171', 'JX_245_3_173', 'JX_245_3_174', 'JX_245_3_175', 'JX_245_3_176', 'JX_245_3_177',
             'JX_245_3_47', 'JX_245_3_48', 'JX_245_3_49', 'JX_245_3_50', 'JX_245_3_66', 'JX_245_3_67', 'JX_245_3_81',
             'JX_245_3_87', 'JX_245_3_89', 'JX_245_3_90', 'JX_245_3_91', 'JX_245_3_98', 'JX_245_3_99', 'JX_253_4_117',
             'JX_253_4_65', 'JX_254_1_167', 'JX_254_1_6', 'JX_254_1_7', 'JX_254_5_161', 'JX_254_5_164', 'JX_254_5_17',
             'JX_254_5_189', 'JX_254_5_193', 'JX_254_5_218', 'JX_254_5_219', 'JX_254_5_48', 'JX_254_5_86',
             'JX_255_6_151', 'JX_260_1_100', 'JX_260_1_101', 'JX_260_1_103', 'JX_260_1_109', 'JX_260_1_111',
             'JX_260_1_112', 'JX_260_1_113', 'JX_260_1_115', 'JX_260_1_116', 'JX_260_1_117', 'JX_260_1_119',
             'JX_260_1_120', 'JX_260_1_124', 'JX_260_1_126', 'JX_260_1_127', 'JX_260_1_128', 'JX_260_1_129',
             'JX_260_1_13', 'JX_260_1_130', 'JX_260_1_131', 'JX_260_1_132', 'JX_260_1_133', 'JX_260_1_134',
             'JX_260_1_135', 'JX_260_1_136', 'JX_260_1_137', 'JX_260_1_139', 'JX_260_1_141', 'JX_260_1_142',
             'JX_260_1_143', 'JX_260_1_144', 'JX_260_1_145', 'JX_260_1_146', 'JX_260_1_147', 'JX_260_1_148',
             'JX_260_1_15', 'JX_260_1_150', 'JX_260_1_151', 'JX_260_1_153', 'JX_260_1_157', 'JX_260_1_159',
             'JX_260_1_16', 'JX_260_1_160', 'JX_260_1_161', 'JX_260_1_163', 'JX_260_1_165', 'JX_260_1_166',
             'JX_260_1_168', 'JX_260_1_169', 'JX_260_1_17', 'JX_260_1_170', 'JX_260_1_171', 'JX_260_1_172',
             'JX_260_1_175', 'JX_260_1_176', 'JX_260_1_178', 'JX_260_1_179', 'JX_260_1_18', 'JX_260_1_180',
             'JX_260_1_181', 'JX_260_1_183', 'JX_260_1_184', 'JX_260_1_186', 'JX_260_1_187', 'JX_260_1_189',
             'JX_260_1_190', 'JX_260_1_192', 'JX_260_1_194', 'JX_260_1_197', 'JX_260_1_199', 'JX_260_1_20',
             'JX_260_1_201', 'JX_260_1_202', 'JX_260_1_204', 'JX_260_1_205', 'JX_260_1_206', 'JX_260_1_208',
             'JX_260_1_210', 'JX_260_1_212', 'JX_260_1_213', 'JX_260_1_214', 'JX_260_1_216', 'JX_260_1_217',
             'JX_260_1_218', 'JX_260_1_219', 'JX_260_1_220', 'JX_260_1_221', 'JX_260_1_222', 'JX_260_1_223',
             'JX_260_1_224', 'JX_260_1_226', 'JX_260_1_227', 'JX_260_1_228', 'JX_260_1_229', 'JX_260_1_230',
             'JX_260_1_231', 'JX_260_1_233', 'JX_260_1_234', 'JX_260_1_236', 'JX_260_1_239', 'JX_260_1_240',
             'JX_260_1_241', 'JX_260_1_246', 'JX_260_1_247', 'JX_260_1_249', 'JX_260_1_250', 'JX_260_1_251',
             'JX_260_1_253', 'JX_260_1_254', 'JX_260_1_255', 'JX_260_1_256', 'JX_260_1_257', 'JX_260_1_258',
             'JX_260_1_259', 'JX_260_1_260', 'JX_260_1_261', 'JX_260_1_263', 'JX_260_1_268', 'JX_260_1_269',
             'JX_260_1_270', 'JX_260_1_273', 'JX_260_1_275', 'JX_260_1_276', 'JX_260_1_277', 'JX_260_1_278',
             'JX_260_1_279', 'JX_260_1_280', 'JX_260_1_281', 'JX_260_1_282', 'JX_260_1_283', 'JX_260_1_284',
             'JX_260_1_285', 'JX_260_1_287', 'JX_260_1_288', 'JX_260_1_30', 'JX_260_1_32', 'JX_260_1_64', 'JX_260_1_65',
             'JX_260_1_74', 'JX_260_1_77', 'JX_260_1_78', 'JX_260_1_83', 'JX_260_1_84', 'JX_260_1_85', 'JX_260_1_87',
             'JX_260_1_88', 'JX_260_1_90', 'JX_260_1_91', 'JX_260_1_92', 'JX_260_1_93', 'JX_260_1_94', 'JX_260_1_95',
             'JX_260_1_97', 'JX_260_1_98', 'JX_260_2_11', 'JX_260_2_12', 'JX_260_2_2', 'JX_260_2_20', 'JX_260_2_21',
             'JX_260_2_22', 'JX_260_2_23', 'JX_260_2_24', 'JX_260_2_25', 'JX_260_2_26', 'JX_260_2_27', 'JX_260_2_28',
             'JX_260_2_29', 'JX_260_2_3', 'JX_260_2_30', 'JX_260_2_31', 'JX_260_2_32', 'JX_260_2_33', 'JX_260_2_34',
             'JX_260_2_35', 'JX_260_2_37', 'JX_260_2_39', 'JX_260_2_4', 'JX_260_2_40', 'JX_260_2_41', 'JX_260_2_42',
             'JX_260_2_43', 'JX_260_2_44', 'JX_260_2_45', 'JX_260_2_48', 'JX_260_2_50', 'JX_260_2_51', 'JX_260_2_52',
             'JX_260_2_53', 'JX_260_2_55', 'JX_260_2_57', 'JX_260_2_6', 'JX_260_2_7', 'JX_260_2_8', 'JX_260_2_9',
             'QL_10_145', 'QL_10_160', 'QL_10_17', 'QL_10_192', 'QL_10_208', 'QL_10_224', 'QL_10_241', 'QL_10_287',
             'QL_10_302', 'QL_10_318', 'QL_10_351', 'QL_10_397', 'QL_10_413', 'QL_10_429', 'QL_10_446', 'QL_10_462',
             'QL_10_477', 'QL_10_493', 'QL_10_509', 'QL_10_525', 'QL_10_526', 'QL_10_542', 'QL_10_556', 'QL_10_571',
             'QL_10_572', 'QL_10_588', 'QL_10_603', 'QL_10_619', 'QL_10_635', 'QL_10_651', 'QL_10_667', 'QL_10_683',
             'QL_10_699', 'QL_10_715', 'QL_11_112', 'QL_11_145', 'QL_11_16', 'QL_11_212', 'QL_11_275', 'QL_11_293',
             'QL_11_310', 'QL_11_327', 'QL_11_358', 'QL_11_375', 'QL_11_392', 'QL_11_409', 'QL_11_426', 'QL_11_443',
             'QL_11_46', 'QL_11_477', 'QL_11_510', 'QL_11_542', 'QL_11_623', 'QL_11_639', 'QL_11_655', 'QL_11_671',
             'QL_11_688', 'QL_11_706', 'QL_11_96', 'QL_12_123', 'QL_12_141', 'QL_12_159', 'QL_12_176', 'QL_12_193',
             'QL_12_210', 'QL_12_227', 'QL_12_261', 'QL_12_35', 'QL_12_449', 'QL_12_465', 'QL_12_481', 'QL_12_497',
             'QL_12_512', 'QL_12_528', 'QL_12_544', 'QL_12_561', 'QL_12_577', 'QL_12_611', 'QL_12_644', 'QL_12_660',
             'QL_12_696', 'QL_12_72', 'QL_12_729', 'QL_12_746', 'QL_12_763', 'QL_13_108', 'QL_13_124', 'QL_13_141',
             'QL_13_158', 'QL_13_174', 'QL_13_18', 'QL_13_190', 'QL_13_206', 'QL_13_221', 'QL_13_236', 'QL_13_267',
             'QL_13_284', 'QL_13_300', 'QL_13_317', 'QL_13_340', 'QL_13_349', 'QL_13_35', 'QL_13_365', 'QL_13_398',
             'QL_13_413', 'QL_13_430', 'QL_13_447', 'QL_13_481', 'QL_13_511', 'QL_13_52', 'QL_13_528', 'QL_13_543',
             'QL_13_559', 'QL_13_603', 'QL_13_617', 'QL_13_634', 'QL_13_650', 'QL_13_666', 'QL_13_682', 'QL_13_72',
             'QL_14_17', 'QL_14_33', 'QL_14_51', 'QL_14_68', 'QL_14_82', 'QL_1_176', 'QL_1_210', 'QL_1_227', 'QL_1_276',
             'QL_1_292', 'QL_1_309', 'QL_1_325', 'QL_1_342', 'QL_1_359', 'QL_1_410', 'QL_24_107', 'QL_24_149',
             'QL_24_17', 'QL_24_170', 'QL_24_182', 'QL_24_230', 'QL_24_248', 'QL_24_263', 'QL_24_281', 'QL_24_298',
             'QL_24_31', 'QL_24_314', 'QL_24_332', 'QL_24_351', 'QL_24_368', 'QL_24_386', 'QL_24_406', 'QL_24_423',
             'QL_24_440', 'QL_24_456', 'QL_24_473', 'QL_24_491', 'QL_24_50', 'QL_24_506', 'QL_24_523', 'QL_24_539',
             'QL_24_556', 'QL_24_573', 'QL_24_626', 'QL_24_642', 'QL_24_673', 'QL_24_691', 'QL_24_71', 'QL_24_88',
             'QL_25_101', 'QL_25_117', 'QL_25_132', 'QL_25_16', 'QL_25_166', 'QL_25_198', 'QL_25_213', 'QL_25_234',
             'QL_25_258', 'QL_25_280', 'QL_25_302', 'QL_25_313', 'QL_25_32', 'QL_25_324', 'QL_25_346', 'QL_25_367',
             'QL_25_384', 'QL_25_400', 'QL_25_416', 'QL_25_433', 'QL_25_465', 'QL_25_48', 'QL_25_483', 'QL_25_498',
             'QL_25_512', 'QL_25_524', 'QL_25_536', 'QL_25_549', 'QL_25_584', 'QL_25_600', 'QL_25_621', 'QL_25_641',
             'QL_25_653', 'QL_25_670', 'QL_25_686', 'QL_25_697', 'QL_25_715', 'QL_25_733', 'QL_25_749', 'QL_26_106',
             'QL_26_118', 'QL_26_135', 'QL_26_148', 'QL_26_16', 'QL_26_160', 'QL_26_175', 'QL_26_193', 'QL_26_211',
             'QL_26_223', 'QL_26_235', 'QL_26_249', 'QL_26_267', 'QL_26_287', 'QL_26_301', 'QL_26_314', 'QL_26_329',
             'QL_26_33', 'QL_26_347', 'QL_26_391', 'QL_26_407', 'QL_26_422', 'QL_26_469', 'QL_26_485', 'QL_26_503',
             'QL_26_522', 'QL_26_53', 'QL_26_543', 'QL_26_558', 'QL_26_95', 'QL_2_100', 'QL_2_189', 'QL_2_239',
             'QL_2_274', 'QL_2_290', 'QL_2_354', 'QL_2_372', 'QL_2_389', 'QL_2_405', 'QL_2_728', 'QL_2_757', 'QL_2_772',
             'QL_3_325', 'QL_3_340', 'QL_3_355', 'QL_3_385', 'QL_3_705', 'QL_3_721', 'QL_3_736', 'QL_4_31', 'QL_4_584',
             'QL_4_614', 'QL_4_629', 'QL_5_17', 'QL_5_472', 'QL_7_172', 'QL_7_249', 'QL_7_264', 'QL_7_307', 'QL_7_337',
             'QL_7_370', 'QL_7_385', 'QL_7_401', 'QL_7_480', 'QL_7_497', 'QL_7_513', 'QL_7_528', 'QL_7_544', 'QL_7_575',
             'QL_7_591', 'QL_7_657', 'QL_7_673', 'QL_7_689', 'QL_7_706', 'QL_8_115', 'QL_8_164', 'QL_8_17', 'QL_8_260',
             'QL_8_356', 'QL_8_402', 'QL_8_613', 'QL_8_703', 'QL_8_83', 'QL_9_178', 'QL_9_226', 'QL_9_351', 'QL_9_417',
             'QL_9_448', 'QL_9_48', 'QL_9_496', 'QL_9_513', 'QL_9_713', 'YB_22_346', 'YB_22_389', 'YB_22_476',
             'YB_22_555', 'YB_22_713', 'YB_22_759', 'YB_22_816', 'YB_22_916', 'YB_22_995', 'YB_23_132', 'YB_23_182',
             'YB_23_25', 'YB_23_423', 'YB_23_477', 'YB_23_542', 'YB_23_570', 'YB_23_574', 'YB_23_639', 'YB_23_711',
             'YB_23_721', 'YB_23_727', 'YB_23_839', 'YB_23_880', 'YB_23_882', 'YB_23_885', 'YB_23_890', 'YB_23_899',
             'YB_23_906', 'YB_23_911', 'YB_23_913', 'YB_23_923', 'YB_23_928', 'YB_24_110', 'YB_24_113', 'YB_24_119',
             'YB_24_126', 'YB_24_132', 'YB_24_204', 'YB_24_210', 'YB_24_215', 'YB_24_219', 'YB_24_226', 'YB_24_228',
             'YB_24_232', 'YB_24_234', 'YB_24_238', 'YB_24_24', 'YB_24_248', 'YB_24_251', 'YB_24_257']

    once_size = 300
    condition = {'name': {'$in': names}}
    total_count = db.page.count_documents(condition)
    log_id = Bh.add_op_log(db, 'gen_chars', 'ongoing', [], username)
    fields1 = ['name', 'source', 'columns', 'chars']
    fields2 = ['source', 'cid', 'char_id', 'txt', 'nor_txt', 'ocr_txt', 'ocr_col', 'cmp_txt', 'alternatives']
    for i in range(int(math.ceil(total_count / once_size))):
        pages = list(db.page.find(condition, {k: 1 for k in fields1}).skip(i * once_size).limit(once_size))
        p_names = [p['name'] for p in pages]
        print('[%s]processing %s' % (hp.get_date_time(), ','.join(p_names)))
        # 查找、分类chars
        chars, char_names, invalid_chars, invalid_pages, valid_pages = [], [], [], [], []
        for p in pages:
            try:
                id2col = {col['column_id']: {k: col[k] for k in ['cid', 'x', 'y', 'w', 'h']} for col in p['columns']}
                for c in p['chars']:
                    try:
                        char_names.append('%s_%s' % (p['name'], c['cid']))
                        m = dict(page_name=p['name'], txt_level=0, img_need_updated=True)
                        m['name'] = '%s_%s' % (p['name'], c['cid'])
                        m.update({k: c[k] for k in fields2 if c.get(k)})
                        m.update({k: int(c[k] * 1000) for k in ['cc', 'sc'] if c.get(k)})
                        m['ocr_txt'] = c.get('alternatives', '')[:1] or c.get('ocr_col') or ''
                        m['txt'] = c.get('txt') or m['ocr_txt']
                        m['pos'] = dict(x=c['x'], y=c['y'], w=c['w'], h=c['h'])
                        m['column'] = id2col.get('b%sc%s' % (c['block_no'], c['column_no']))
                        m['uid'] = hp.align_code('%s_%s' % (p['name'], c['char_id'][1:].replace('c', '_')))
                        chars.append(m)
                    except KeyError as e:
                        print(e)
                        invalid_chars.append('%s_%s' % (p['name'], c['cid']))
                valid_pages.append(p['name'])
            except KeyError:
                invalid_pages.append(p['name'])

        # 删除多余的chars
        deleted = list(db.char.find({'page_name': {'$in': p_names}, 'name': {'$nin': char_names}}, {'name': 1}))
        if deleted:
            db.char.delete_many({'_id': {'$in': [d['_id'] for d in deleted]}})
            print('delete %s records: %s' % (len(deleted), ','.join([c['name'] for c in deleted])))
        # 更新已存在的chars。检查和更新char_id、uid、pos三个字段
        chars_dict = {c['name']: c for c in chars}
        existed = list(db.char.find({'name': {'$in': [c['name'] for c in chars]}}))
        if existed:
            changed = []
            for e in existed:
                c = chars_dict.get(e['name'])
                if is_changed(e, c):
                    changed.append(c['name'])
                    update = {k: c[k] for k in ['char_id', 'uid', 'pos', 'column'] if c.get(k)}
                    db.char.update_one({'_id': e['_id']}, {'$set': {**update, 'img_need_updated': True}})
            if changed:
                print('update changed %s records: %s' % (len(changed), ','.join([c for c in changed])))
        # 插入不存在的chars
        existed_id = [c['name'] for c in existed]
        un_existed = [c for c in chars if c['name'] not in existed_id]
        if un_existed:
            db.char.insert_many(un_existed, ordered=False)
            print('insert new %s records: %s' % (len(un_existed), ','.join([c['name'] for c in un_existed])))
        log = dict(inserted_char=[c['name'] for c in un_existed], updated_char=[c['name'] for c in existed],
                   deleted_char=[c['name'] for c in deleted], invalid_char=invalid_chars,
                   valid_pages=valid_pages, invalid_pages=invalid_pages,
                   create_time=datetime.now())
        db.oplog.update_one({'_id': log_id}, {'$addToSet': {'content': log}})
    db.oplog.update_one({'_id': log_id}, {'$set': {'status': 'finished'}})


if __name__ == '__main__':
    import fire

    fire.Fire(gen_chars)
