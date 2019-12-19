#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@time: 2018/10/23
"""

import random
import smtplib
import logging
from os import path
from email.header import Header
from email.mime.text import MIMEText
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from datetime import datetime, timedelta
from bson import json_util
from bson.objectid import ObjectId
from controller import errors
import controller.helper as hlp
import controller.validate as v
from controller.base import BaseHandler, DbError
from tornado.options import options


class LoginApi(BaseHandler):
    URL = '/api/user/login'

    def post(self):
        """ 登录 """
        user = self.get_request_data()
        rules = [
            (v.not_empty, 'phone_or_email', 'password'),
        ]
        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)
        try:
            # 检查是否多次登录失败
            login_fail = {
                'type': 'login-fail',
                'create_time': {'$gt': datetime.now() + timedelta(seconds=-1800)},
                'context': user.get('phone_or_email')
            }
            times = self.db.log.count_documents(login_fail)
            if times >= 20:
                return self.send_error_response(errors.unauthorized, message='登录失败，请半小时后重试，或者申请重置密码')

            login_fail['create_time']['$gt'] = datetime.now() + timedelta(seconds=-60)
            times = self.db.log.count_documents(login_fail)
            if times >= 5:
                return self.send_error_response(errors.unauthorized, message='登录失败，请一分钟后重试')

            # 尝试登录，成功后清除登录失败记录，设置为当前用户
            self.login(self, user.get('phone_or_email'), user.get('password'))

        except DbError as error:
            return self.send_db_error(error)

    @staticmethod
    def login(self, phone_or_email, password, report_error=True, send_response=True):
        user = self.db.user.find_one({
            '$or': [
                {'email': phone_or_email},
                {'phone': phone_or_email}
            ]
        })
        if not user:
            if report_error:
                self.add_op_log('login_no_user', context=phone_or_email)
                return send_response and self.send_error_response(errors.no_user)
            return
        if user['password'] != hlp.gen_id(password):
            if report_error:
                self.add_op_log('login_fail', context=phone_or_email)
                return send_response and self.send_error_response(errors.incorrect_password)
            return

        # 清除登录失败记录
        ResetUserPasswordApi.remove_login_fails(self, phone_or_email)

        user['roles'] = user.get('roles', '')
        user['login_md5'] = hlp.gen_id(user['roles'])
        self.current_user = user
        self.set_secure_cookie('user', json_util.dumps(user), expires_days=2)

        self.add_op_log('login_ok', context=phone_or_email + ': ' + user['name'], username=user['name'])
        logging.info('login id=%s, name=%s, phone_or_email=%s, roles=%s' %
                     (user['_id'], user['name'], phone_or_email, user['roles']))

        if send_response:
            self.send_data_response(user)
        return user


class LogoutApi(BaseHandler):
    URL = '/api/user/logout'

    def post(self):
        """ 注销 """
        if self.current_user:
            self.clear_cookie('user')
            self.current_user = None
            self.add_op_log('logout')
        self.send_data_response()


class RegisterApi(BaseHandler):
    URL = '/api/user/register'

    def post(self):
        """ 注册 """
        user = self.get_request_data()
        rules = [
            (v.not_empty, 'name', 'password'),
            (v.not_both_empty, 'email', 'phone'),
            (v.is_name, 'name'),
            (v.is_email, 'email'),
            (v.is_phone, 'phone'),
            (v.is_password, 'password'),
            (v.not_existed, self.db.user, 'phone', 'email')]
        if not options.testing and user.get('email') and self.config['email']['key'] not in ['', None, '待配置']:
            rules.append((v.not_empty, 'email_code'))
            rules.append((v.code_verify_timeout, self.db.verify, 'email', 'email_code'))
        if not options.testing and user.get('phone'):
            rules.append((v.not_empty, 'phone_code'))
            rules.append((v.code_verify_timeout, self.db.verify, 'phone', 'phone_code'))

        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)

        try:
            roles = self.config.get('role', {}).get('init', '')
            user['roles'] = '用户管理员' if not self.db.user.find_one() else roles  # 如果是第一个用户，则设置为用户管理员
            r = self.db.user.insert_one(dict(
                name=user['name'], email=user.get('email'), phone=user.get('phone'),
                gender=user.get('gender'), roles=user['roles'], img=user.get('img'),
                password=hlp.gen_id(user['password']),
                create_time=datetime.now()
            ))
            user['_id'] = r.inserted_id
            self.add_op_log('register', context='%s, %s, %s' % (user.get('email'), user.get('phone'), user['name']),
                            username=user['name'])
            user['login_md5'] = hlp.gen_id(user['roles'])
            self.current_user = user
            self.set_secure_cookie('user', json_util.dumps(user), expires_days=2)
            logging.info('register id=%s, name=%s, email=%s' % (user['_id'], user['name'], user.get('email')))
            self.send_data_response(user)

        except DbError as error:
            return self.send_db_error(error)


class ChangeUserProfileApi(BaseHandler):
    URL = r'/api/user/profile'

    def post(self):
        """ 修改用户基本信息: 姓名，手机，邮箱，性别"""
        user = self.get_request_data()
        rules = [
            (v.not_empty, 'name'),
            (v.not_both_empty, 'email', 'phone'),
            (v.is_name, 'name'),
            (v.is_email, 'email'),
            (v.is_phone, 'phone'),
            (v.not_existed, self.db.user, ObjectId(user['_id']), 'phone', 'email')
        ]
        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)

        try:
            info = {f: user.get(f) for f in ['name', 'phone', 'email', 'gender']}
            r = self.db.user.update_one(dict(_id=ObjectId(user['_id'])), {'$set': info})
            if not r.matched_count:
                return self.send_error_response(errors.no_user, id=user['_id'])
            self.add_op_log('change_user_profile', target_id=user['_id'], context=str(info))
            self.send_data_response(dict(info=info))

        except DbError as error:
            return self.send_db_error(error)


class ChangeUserRoleApi(BaseHandler):
    URL = r'/api/user/role'

    def post(self):
        """ 修改用户角色 """

        user = self.get_request_data()
        rules = [(v.not_empty, '_id')]
        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)

        try:
            old_user = self.db.user.find_one(dict(_id=ObjectId(user['_id'])))
            if not old_user:
                return self.send_error_response(errors.no_user, id=user['_id'])

            user['roles'] = user.get('roles') or ''
            r = self.db.user.update_one(dict(_id=ObjectId(user['_id'])), {'$set': dict(roles=user['roles'])})
            if not r.matched_count:
                return self.send_error_response(errors.no_user)
            self.add_op_log('change_role', target_id=user['_id'],
                            context='%s: %s' % (old_user['name'], user.get('roles')))
            self.send_data_response({'roles': user['roles']})

        except DbError as error:
            return self.send_db_error(error)


class ForgetPasswordApi(BaseHandler):
    URL = '/api/user/forget_pwd'

    def post(self):
        """将密码发送到注册时的邮箱或手机上"""

        info = self.get_request_data()
        rules = [
            (v.not_empty, 'name', 'phone_or_email'),
            (v.is_phone_or_email, 'phone_or_email')]
        err = v.validate(info, rules)
        if err:
            return self.send_error_response(err)

        phone_or_email = info['phone_or_email']
        user = self.db.user.find_one({
            '$or': [
                {'email': phone_or_email},
                {'phone': phone_or_email}
            ]
        })
        if not user:
            return self.send_error_response(errors.no_user)
        if user['name'] != info['name']:
            return self.send_error_response(errors.no_user, message='姓名不匹配')

        pwd = ResetUserPasswordApi.reset_pwd(self, user)
        if '@' in phone_or_email:
            r = SendUserEmailCodeApi.send_email(self, phone_or_email, """<html>
                <span style='font-size:16px;margin-right:10px'>密码：%s </span>
                <a href='http://%s/user/login'>返回登录页面</a>
                </html>
                """ % (pwd, self.config['site']['domain']))
        else:
            r = SendUserPhoneCodeApi.send_sms(self, phone_or_email, '密码: ' + pwd)

        if r:
            self.send_data_response()


class ResetUserPasswordApi(BaseHandler):
    URL = r'/api/user/reset_pwd'

    def post(self):
        """ 重置用户密码 """

        user = self.get_request_data()
        rules = [(v.not_empty, '_id')]
        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)

        try:
            pwd = self.reset_pwd(self, user)
            if pwd:
                self.send_data_response({'password': pwd})

        except DbError as error:
            return self.send_db_error(error)

    @staticmethod
    def reset_pwd(self, user):
        pwd = '%s%d' % (chr(random.randint(97, 122)), random.randint(10000, 99999))
        oid = ObjectId(user['_id'])
        r = self.db.user.update_one(dict(_id=oid), {'$set': dict(password=hlp.gen_id(pwd))})
        if not r.matched_count:
            return self.send_error_response(errors.no_user)

        user = self.db.user.find_one(dict(_id=oid))
        ResetUserPasswordApi.remove_login_fails(self, user['_id'])
        self.add_op_log('reset_password', target_id=user['_id'], context=user['name'])

        return pwd

    @staticmethod
    def remove_login_fails(self, context):
        self.db.log.delete_many({
            'type': 'login_fail',
            'create_time': {'$gt': datetime.now() + timedelta(seconds=-3600)},
            'context': context
        })


class DeleteUserApi(BaseHandler):
    URL = r'/api/user/delete'

    def post(self):
        """ 删除用户 """
        user = self.get_request_data()
        rules = [(v.not_empty, '_id')]
        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)

        try:
            old_user = self.db.user.find_one(dict(_id=ObjectId(user['_id'])))
            if not old_user:
                return self.send_error_response(errors.no_user, id=user['_id'])
            if user['_id'] == self.current_user['_id']:  # 判断删除的用户是否为自己
                return self.send_error_response(errors.cannot_delete_self)
            r = self.db.user.delete_one(dict(_id=ObjectId(user['_id'])))
            if r.deleted_count < 1:
                return self.send_error_response(errors.no_user)
            self.add_op_log('delete_user', target_id=user['_id'], context=old_user['name'])
            self.send_data_response()

        except DbError as error:
            return self.send_db_error(error)


class ChangeMyPasswordApi(BaseHandler):
    URL = '/api/user/my/pwd'

    def post(self):
        """ 修改我的密码 """
        user = self.get_request_data()
        rules = [
            (v.not_empty, 'password', 'old_password'),
            (v.not_equal, 'password', 'old_password'),
            (v.is_password, 'password')
        ]
        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)

        try:
            u = self.db.user.find_one(dict(_id=self.current_user['_id']))
            if u.get('password') != hlp.gen_id(user['old_password']):
                return self.send_error_response(errors.incorrect_old_password)
            self.db.user.update_one(
                dict(_id=self.current_user['_id']),
                {'$set': dict(password=hlp.gen_id(user['password']))}
            )
            self.add_op_log('change_my_password')
            logging.info('change password %s' % self.current_user['name'])
            self.send_data_response()

        except DbError as error:
            return self.send_db_error(error)


class ChangeMyProfileApi(BaseHandler):
    URL = '/api/user/my/profile'

    def post(self):
        """ 修改我的个人信息，包括姓名、性别等 """
        user = self.get_request_data()
        rules = [
            (v.not_empty, 'name'),
            (v.not_both_empty, 'email', 'phone'),
            (v.is_name, 'name'),
            (v.is_email, 'email'),
            (v.is_phone, 'phone'),
            (v.not_existed, self.db.user, self.current_user['_id'], 'phone', 'email')
        ]
        err = v.validate(user, rules)
        if err:
            return self.send_error_response(err)

        try:
            self.current_user['name'] = user.get('name') or self.current_user['name']
            self.current_user['gender'] = user.get('gender') or self.current_user.get('gender')
            self.current_user['email'] = user.get('email') or self.current_user['email']
            self.current_user['phone'] = user.get('phone') or self.current_user.get('phone')

            r = self.db.user.update_one(dict(_id=self.current_user['_id']), {
                '$set': dict(
                    name=self.current_user['name'],
                    gender=self.current_user.get('gender'),
                    email=self.current_user.get('email'),
                    phone=self.current_user.get('phone')
                )
            })
            if not r.modified_count:
                return self.send_error_response(errors.not_changed)

            self.set_secure_cookie('user', json_util.dumps(self.current_user), expires_days=2)
            self.add_op_log('change_my_profile')
            logging.info('change profile %s' % (user.get('name')))
            self.send_data_response()

        except DbError as error:
            return self.send_db_error(error)


class UploadUserAvatarApi(BaseHandler):
    URL = '/api/user/my/avatar'

    def post(self):
        """上传用户头像"""
        try:
            upload_img = self.request.files.get('img')
            img_name = str(self.current_user['_id']) + path.splitext(upload_img[0]['filename'])[-1]
            img_path = path.join(self.application.BASE_DIR, 'static', 'upload', 'avatar')
            img = 'upload/avatar/' + img_name
            with open(path.join(img_path, img_name), 'wb') as f:
                f.write(upload_img[0]['body'])
            self.db.user.update_one(dict(_id=self.current_user['_id']), {'$set': dict(img=img)})
            self.current_user['img'] = img
            self.send_data_response()

        except DbError as error:
            return self.send_db_error(error)


class SendUserEmailCodeApi(BaseHandler):
    URL = '/api/user/email_code'

    def post(self):
        """用户注册时，发送邮箱验证码"""
        try:
            data = self.get_request_data()
            rules = [(v.not_empty, 'email')]
            err = v.validate(data, rules)
            if err:
                return self.send_error_response(err)

            email = data.get('email')
            code = hlp.random_code()
            if not self.send_email(self, email, code):
                return self.send_error_response(errors.email_send_failed)

            self.db.verify.find_one_and_update(
                dict(type='email', data=email), {'$set': dict(code=code, stime=datetime.now())}, upsert=True
            )
            self.send_data_response()

        except DbError as error:
            return self.send_db_error(error)

    @staticmethod
    def send_email(self, receiver, code, subject="如是我闻古籍数字化平台"):
        """ email_list邮件列表，content邮件内容，subject发送标题 """

        try:
            content = code if '<html' in code else """<html>
                    <span style='font-size:16px;margin-right:10px'>您的验证码是：%s </span>
                    <a href='http://%s/user/register'>返回注册页面</a>
                    </html>
                    """ % (code, self.config['site']['domain'])

            msg = MIMEText(content, 'html', 'utf-8')
            account = self.config['email']['account']
            pwd = self.config['email']['key']
            host = self.config['email']['host']
            port = self.config['email'].get('port', 465)
            msg['From'] = account
            msg['to'] = receiver
            msg['Subject'] = Header(subject, 'utf-8')

            server = smtplib.SMTP_SSL(host, port)
            server.login(account, pwd)
            server.sendmail(account, receiver, msg.as_string())
            server.quit()
            return True

        except Exception as error:
            self.send_error_response(errors.verify_failed, message='发送邮件失败: [%s] %s' % (
                error.__class__.__name__, str(error)))


class SendUserPhoneCodeApi(BaseHandler):
    URL = '/api/user/phone_code'

    def post(self):
        """用户注册时，发送手机验证码"""
        data = self.get_request_data()
        rules = [(v.not_empty, 'phone')]
        err = v.validate(data, rules)
        if err:
            return self.send_error_response(err)

        phone = data['phone']
        code = "%04d" % random.randint(1000, 9999)
        if not self.send_sms(self, phone, code):
            return
        try:
            self.db.verify.find_one_and_update(
                dict(type='phone', data=phone), {'$set': dict(code=code, stime=datetime.now())}, upsert=True
            )
            self.send_data_response()

        except DbError as error:
            return self.send_db_error(error)

    @staticmethod
    def send_sms(self, phone, code):
        """发送手机验证码"""
        try:
            account = self.config['phone']['accessKey']
            key = self.config['phone']['accessKeySecret']
            template_code = self.config['phone']['template_code']
            sign_name = self.config['phone']['sign_name']

            client = AcsClient(account, key, 'default')
            request = CommonRequest()
            request.set_domain('dysmsapi.aliyuncs.com')
            request.set_action_name('SendSms')
            request.set_version('2017-05-25')
            request.add_query_param('SignName', sign_name)
            request.add_query_param('PhoneNumbers', phone)
            request.add_query_param('TemplateCode', template_code)
            request.add_query_param('TemplateParam', '{"code": ' + code + '}')
            response = client.do_action_with_exception(request)
            response = response.decode()
            return response

        except Exception as error:
            self.send_error_response(errors.verify_failed, message='发送邮件失败: [%s] %s' % (
                error.__class__.__name__, str(error)))


class UsersOfTaskTypeApi(BaseHandler):
    URL = '/api/user/@task_type'

    def post(self, task_type):
        """ 获取可访问某个任务类型的用户列表 """
        try:
            from controller.auth import get_route_roles
            roles = get_route_roles('/api/task/pick/' + task_type, 'POST')
            condition = {'roles': {'$regex': '.*(%s).*' % '|'.join(roles)}}
            q = self.get_body_argument('q', '')
            if q:
                condition.update({'name': {'$regex': '.*%s.*' % q}})
            size = 10
            cur_page = int(self.get_body_argument('page', 1))
            total_count = self.db.user.count_documents(condition)
            users = self.db.user.find(condition).sort('_id', 1).skip((cur_page - 1) * size).limit(size)
            users = [dict(id=str(u['_id']), text=u['name']) for u in list(users)]
            self.send_data_response(dict(results=list(users), pagination=dict(more=total_count > cur_page * size)))

        except Exception as error:
            return self.send_db_error(error)
