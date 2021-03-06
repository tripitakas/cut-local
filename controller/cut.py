#!/usr/bin/env python
# -*- coding: utf-8 -*-

from controller.base import load_json, save_json, get_date_time, BaseHandler
from tornado.options import options
import logging
from os import path, listdir, remove
import json
import random
import time
import codecs
import zipfile


BASE_DIR = path.dirname(path.dirname(__file__))
pos_types = dict(block='切栏', column='切列', char='切字', proof='文字')
kind_types = {'GL': '高丽藏', 'JX': '嘉兴藏', 'QL': '乾隆藏', 'YB': '永乐北藏'}
indexes = load_json(path.join('static', 'index.json'))
kinds = {k: {t: kind_types[t] for t in v} for k, v in indexes.items()}


class MainHandler(BaseHandler):
    URL = r'/'

    def get(self):
        if 0:
            with open('page_codes.txt') as f:
                lines = f.read().split('\n')
            proof = {"QL": [], "YB": []}
            for t in lines:
                proof[t[:2]].append(t)
            save_json(proof, 'proof.json')
        self.render('index.html', kinds=kinds, index=indexes, pos='char')


class PagesHandler(BaseHandler):
    URL = [r'/(block|column|char|proof)/([A-Z]{2}|me)/?',
           r'/(block|column|char|proof)/(me)/(\w+)']

    @staticmethod
    def get_my_pages(pos, username):
        pages = []
        me = '\n' + username + '\n'
        lock_path = path.join(BASE_DIR, 'data', 'lock', pos)
        for fn in listdir(lock_path):
            filename = path.join(lock_path, fn)
            if '_' in fn and '.' not in fn:
                with open(filename) as f:
                    text = f.read()
                if me in text and fn not in pages:
                    pages.append(fn)
        return sorted(pages)

    def get(self, pos, kind, username=None):
        def get_icon(p):
            if options.debug:
                return '/static/' + '/'.join(['img', *p.split('_')[:-1], p + '.jpg'])
            base_url = 'http://tripitaka-img.oss-cn-beijing.aliyuncs.com/pages'
            url = '/'.join([base_url, *p.split('_')[:-1], p + '_' + page_codes.get(p) + '.jpg'])
            return url + '?x-oss-process=image/resize,m_lfit,h_300,w_300'

        def get_info(p):
            filename = path.join(BASE_DIR, 'static', 'pos', pos, *p.split('_')[:-1], p + '.json')
            return load_json(filename)

        page_codes = load_json(path.join(BASE_DIR, 'static/pagecode_hash.json'))
        pos_type = pos_types[pos]
        cur_user = self.current_user or self.get_ip()
        username = username or cur_user
        me = '\n' + username + '\n'
        self.unlock_timeout(pos, me)

        if kind == 'me':
            pages = self.get_my_pages(pos, username)
            return self.render('my_pages.html', kinds=kinds, pages=pages, count=len(pages), username=username,
                               pos_type=pos_type, pos=pos, kind=kind, get_icon=get_icon, get_info=get_info)

        field = pos + ('_invalid' if self.get_query_argument('invalid', 0) == '1' else '')
        pages, count = self.pick_pages(pos, indexes[field].get(kind, []), 12)
        html = 'block_pages.html' if pos == 'block' else 'char_pages.html'
        if pos == 'block':
            [CutHandler.lock_page(self, pos, name) for name in pages]

        self.render(html, kinds=kinds, pages=pages, count=count, username=username, invalids={},
                    pos_type=pos_type, pos=pos, kind=kind, get_icon=get_icon, get_info=get_info)

    @staticmethod
    def unlock_timeout(pos, me):
        lock_path = path.join(BASE_DIR, 'data', 'lock', pos)
        now = time.time()
        for fn in listdir(lock_path):
            filename = path.join(lock_path, fn)
            if '_' in fn and '.' not in fn:
                with open(filename) as f:
                    text = f.read()
                if 'saved' not in text:
                    t = path.getctime(filename)
                    if now - t > 60 * 30 or me in text:
                        remove(filename)
                        logging.warning('%s unlocked: %s' % (fn, text.replace('\n', '|')))

    @staticmethod
    def get_lock_file(pos, name):
        return path.join(BASE_DIR, 'data', 'lock', pos, name)

    @staticmethod
    def pick_pages(pos, pages, count):
        pages = [p for p in pages if not path.exists(PagesHandler.get_lock_file(pos, p))]
        random.shuffle(pages)
        return sorted(pages[:count]), len(pages)


class CutHandler(BaseHandler):
    URL = r'/(block|char)/([A-Z]{2})/(\w{4,20}|all)'
    html_files = dict(block='block_cut.html', column='column_cut.html', char='char_cut.html', proof='proofread.html')

    def get(self, pos, kind, name):
        # 获取page_code对应的文本
        def get_txt(p):
            txt_path = '/'.join(['./static/txt', *p.split('_')[:-1], p + '.txt'])
            if not path.exists(txt_path):
                return 'file not exist.'
            with codecs.open(txt_path, 'r', 'utf-8') as f:
                return ''.join(f.readlines())
        
        # 获取page_code对应的hash值
        def get_hash(p):
            with open('./static/pagecode_hash.json', 'r') as f:
                dct = json.load(f)
            return dct.get(p)

        # 获取page_code对应的图像路径
        def get_img(p):
            if options.debug:
                return '/static/' + '/'.join(['img', *p.split('_')[:-1], p + '.jpg'])
            base_url = 'http://tripitaka-img.oss-cn-beijing.aliyuncs.com/pages'
            return '/'.join([base_url, *p.split('_')[:-1], p+'_'+get_hash(p)+'.jpg'])

        def load_render(p):
            if not p.startswith(kind):
                p = kind + '_' + p
            filename = path.join(BASE_DIR, 'static', 'pos', pos, *p.split('_')[:-1], p + '.json')
            page = load_json(filename)
            if not page:
                return self.write('error: {0} 页面不存在'.format(p))
            if pos in 'char|column|block':
                if pos + 's' in page:
                    page[pos + 's'] = json.dumps(page[pos + 's'])
                else:
                    page[pos + 's'] = []

            readonly = test or self.get_query_argument('readonly', None) or self.lock_page(self, pos, p, False) != p
            r = self.do_render(p, self.html_files[pos], pos_type=pos_types[pos], readonly=readonly,
                               test=test, messages=messages,
                               page=page, pos=pos, kind=kind, **page, get_img=get_img, txt=get_txt(p))
            if isinstance(r, dict):
                if self.get_query_argument('fix', None):
                    page = load_json(filename)
                    page['chars'] = r['chars']
                    save_json(page, filename + '~')
                elif 'force_layout_type' in r:
                    page = load_json(filename)
                    page['layout_type'] = r['force_layout_type']
                    save_json(page, filename)
                elif export:
                    mismatch = r.get('mismatch_lines')
                    if mismatch:
                        msg = '跳过 %s\t有%d个不匹配\t%s' % (p, len(mismatch), ','.join(mismatch))
                        messages.append(msg)
                        logging.warning(msg)
                    else:
                        page = load_json(filename)
                        page['chars'] = r['chars']
                        logging.info('export ' + p)
                        export[0] += 1
                    arc.writestr('/'.join([*p.split('_')[:-1], p + '.json']), json.dumps(page, ensure_ascii=False))

        test = name == 'all'
        export = test and self.get_query_argument('export', None) and [1]
        messages = []
        if test:
            base_path = path.dirname(path.dirname(__file__))
            zip_file = path.join(base_path, 'static', 'download',
                                 '_'.join([pos, kind, get_date_time('%d%H%M')[:-1] + '.zip']))
            arc = export and zipfile.ZipFile(zip_file, 'w', compression=zipfile.ZIP_DEFLATED)

            pages = indexes[pos][kind] + indexes.get(pos + '_invalid', {}).get(kind, [])
            for name in pages:  # 在 do_render 中传入 test=True 可遍历所有页面
                load_render(name)
            if export:
                arc.close()
                export = '<a href="%s" target="_blank">下载 %s 校对结果</a> %d 个页面\n' % (
                    zip_file.replace(base_path, ''), kind, export[0] - 1)
            self.write((export or '') + '<ol>' + '\n'.join('<li>' + p + '</li>' for p in messages) + '</ol>')
        else:
            load_render(name)

    def do_render(self, name, template_name, **params):
        self.render(template_name, **params)

    @staticmethod
    def lock_page(self, pos, name, fail_write=True):
        lock_file = PagesHandler.get_lock_file(pos, name)
        if path.exists(lock_file):
            with open(lock_file) as f:
                text = f.read()
                if text and self.get_ip() not in text and (self.current_user or '匿名') not in text \
                        and 'saved' not in text:
                    return fail_write and self.write('error:别人已锁定了本页面，请返回选择其他页面。')
        if not path.exists(lock_file):
            with open(lock_file, 'w') as f:
                f.write('\n'.join([self.get_ip(), self.current_user, get_date_time()]))
        return name

    def post(self, pos, kind, name):
        """
        保存一个或多个页面的切分校对数据.
        保存一个页面时 name 为页名，请求体中需要有 boxes 框数组. 保存多个页面时 name 为空，请求体的 boxes 为[页,框数组]的数组.
        如果在请求体中指定了 submit 属性，则会输出下一个校对任务的页名（jump:name 格式，无藏别）.
        :param pos: 校对类型，block 为栏切分，column 为列切分，char 为字框切分
        :param kind: 藏别，例如 GL、JX
        :param name: 页名，例如 GL_1047_1_5，请求体中需要有 boxes 框数组. 如果页名为空，则 boxes 为[[name,boxes], ...]数组
        :return: None
        """
        submit = self.get_body_argument('submit', 0)
        rollback = submit == 'rollback'
        submit = submit == 'true'
        layout_type = int(self.get_body_argument('layout_type', 0))

        if rollback:
            lock_file = PagesHandler.get_lock_file(pos, name)
            if path.exists(lock_file):
                with open(lock_file) as f:
                    text = f.read()
                if 'saved' not in text:
                    remove(lock_file)
                    logging.info('%s unlocked' % lock_file)
        else:
            boxes = json.loads(self.get_body_argument('boxes', '[]'))
            assert name or type(boxes) == dict
            if name == 'all':
                for name, arr in boxes:
                    self.save(kind, pos, name, arr)
            else:
                field = self.get_body_argument('is_column', 0) and 'columns' or \
                        self.get_body_argument('is_block', 0) and 'blocks'
                self.save(kind, pos, name, boxes, field, layout_type=layout_type)

            txt = self.get_body_argument('txt', 0)
            txt = json.loads(txt) if txt and txt.startswith('"') else txt
            if txt:
                with codecs.open('/'.join(['./static/txt/', *name.split('_')[:-1], name + '.txt']), 'w', 'utf-8') as f:
                    f.write(txt.strip('\n'))

        if submit:
            pages = PagesHandler.pick_pages(pos, indexes[pos][kind], 1)[0]
            self.write('jump:' + pages[0][3:] if pages else 'error:本类切分已全部校对完成。')
        self.write('')

    def save(self, kind, pos, name, boxes, field=None, layout_type=0):
        filename = path.join(BASE_DIR, 'static', 'pos', pos, *name.split('_')[:-1], name + '.json')
        page = load_json(filename)
        assert page and isinstance(boxes, list)
        field = field or ('chars' if pos == 'proof' else pos + 's')
        saved = page.get('layout_type', 0) != layout_type or (page[field] != boxes and boxes)
        if layout_type:
            page['layout_type'] = layout_type
        if page[field] != boxes and boxes:
            page[field] = boxes
        if saved:
            save_json(page, filename)
            logging.info('%d boxes saved: %s' % (len(boxes), name))

        lock_file = PagesHandler.get_lock_file(pos, name)
        text = []
        if path.exists(lock_file):
            with open(lock_file) as f:
                text = f.read()
                if 'saved' in text:
                    text = text.split('\n')
                else:
                    text = []
        with open(lock_file, 'w') as f:
            text += [self.get_ip(), self.current_user, get_date_time(), 'saved']
            f.write('\n'.join(text))
