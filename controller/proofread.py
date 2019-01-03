#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.escape import url_escape
from controller.cut import CutHandler
import re
import json
from .layout.main import calc


class ProofreadHandler(CutHandler):
    URL = r'/(proof)/([A-Z]{2})/(\w{4,20})'

    def do_render(self, name, template_name, **params):
        def get_column_boxes(block_no, line_no):
            return [c for c in chars if c['char_id'].startswith('b%dc%dc' % (block_no, line_no))]

        def gen_segments(txt):
            def apply_span():
                if items:
                    segments.append(dict(block_no=1 + blk_i, line_no=line_no, type='same', ocr=items))
                    
            segments = []
            txt = re.sub(r'\S*<!--.+-->\S*', '\n', txt, flags=re.S)  # 修正从其他网站贴入的音释内容
            for blk_i, block in enumerate(txt.split('\n\n\n')):
                col_diff = 1
                for col_i, column in enumerate(block.strip().split('\n')):
                    column = column.strip()
                    line_no = col_diff + col_i
                    if not column:
                        segments.append(dict(block_no=1 + blk_i, line_no=line_no, type='emptyline', ocr=''))
                        continue
                    while col_diff < 50 and not get_column_boxes(1 + blk_i, line_no):
                        col_diff += 1
                        line_no = col_diff + col_i
                    boxes = get_column_boxes(1 + blk_i, line_no)
                    if len(boxes) != len(re.sub(r'\s', '', column)):
                        params['mismatch_lines'].append('b%dc%d' % (1 + blk_i, line_no))
                    column = [url_escape(c) for c in list(column)]
                    items = []
                    for c in column:
                        if len(c) > 9:
                            apply_span()
                            items = []
                            segments.append(dict(block_no=1 + blk_i, line_no=line_no, type='variant', ocr=[c], cmp=''))
                        else:
                            items.append(c)
                    apply_span()
            return {'segments': segments}

        chars = params['chars']
        params['order_changed'] = len([c for c in chars if c.get('order_changed')])
        if not params['order_changed'] or self.get_query_argument('layout', 0) == '1':
            new_chars = calc(chars, params['blocks'], params['columns'])
            for i, c in enumerate(new_chars):
                chars[i]['char_id'] = 'b%dc%dc%d' % (c['block_id'], c['column_id'], c['column_order'])
                if 'line_no' in chars[i]:
                    chars[i]['char_no'] = c['column_order']
        params['zero_char_id'] = [c['char_id'] for c in chars if 'c0' in c['char_id']]
        if params['zero_char_id']:
            print(name, ','.join(params['zero_char_id']))
        params['origin_txt'] = params['txt'].strip().split('\n')
        params['mismatch_lines'] = []
        params['txt'] = json.dumps(gen_segments(params['txt']), ensure_ascii=False)
        return params if params.get('test') else self.render(template_name, **params)


class ColumnCheckHandler(CutHandler):
    URL = r'/(column)/([A-Z]{2})/(\w{4,20})'

    def do_render(self, name, template_name, **params):
        params['txt_lines'] = len([t for t in params['txt'].split('\n') if t])
        return params if params.get('test') else self.render(template_name, **params)
