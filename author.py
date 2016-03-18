# -*- coding: utf-8 -*-

import functools
import re
import math
from datetime import datetime
from requests import Session
from bs4 import BeautifulSoup
from requests.packages.urllib3.util import Retry
import pdfcrowd
import os

import time
import sys
import pickle

ZH_url = 'https://www.zhihu.com'

Default_Header = {'X-Requested-With': 'XMLHttpRequest',
                  'Referer': 'http://www.zhihu.com',
                  'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; '
                                'rv:39.0) Gecko/20100101 Firefox/39.0',
                  'Host': 'www.zhihu.com'}

re_author_url = re.compile(r'^https?://www\.zhihu\.com/people/[^/]+/?$')
re_ans_url = re.compile(r'^https?://www\.zhihu\.com/question/\d+/answer/\d+/?$')

def class_common_init(url_re, allowed_none=True, trailing_slash=True):
    def real(func):
        @functools.wraps(func)
        def wrapper(self, url, *args, **kwargs):
            if url is None and not allowed_none:
                raise ValueError('Invalid Url: ' + url)
            if url is not None:
                if url_re.match(url) is None:
                    raise ValueError('Invalid URL: ' + url)
                if not url.endswith('/') and trailing_slash:
                    url += '/'
            if 'session' not in kwargs.keys() or kwargs['session'] is None:
                kwargs['session'] = Session()
                kwargs['session'].mount('https://', Retry(5))
                kwargs['session'].mount('http://', Retry(5))
            self.soup = None
            return func(self, url, *args, **kwargs)
        return wrapper
    return real

#用的是pdfcrowd试用版，一个月只有100次权限,so...
def htmltopdf(html,pdfname):
        try:
            # create an API client instance
            #client = pdfcrowd.Client("deshenkong", "30658dd7b6000c089b4c42fe47233f2b")
            name = os.path.join('d:\\','PythonCode',pdfname)
            with open(name, 'wb') as output_file:
                print(name)
                # convert a web page and store the generated PDF into a pdf variable
                #pdf = client.convertURI(html,output_file)

        except pdfcrowd.Error:
            print('Failed: {}')


class BaseZhihu:
    def _gen_soup(self, content):
        self.soup = BeautifulSoup(content)

    def _get_content(self):
        resp = self._session.get(self.url)
        return resp.content

    def _make_soup(self):
        self._gen_soup(self._get_content())

    def refresh(self):
        # refresh self.soup's content
        self._gen_soup(self._get_content())

#TODO:这个全局变量的设计极其糟糕
answers_dict = {} #存放url:content

class Answers(BaseZhihu):
    @class_common_init(re_ans_url)
    def __init__(self, url, short_url, title, votecount, session=None):
        self.url = url
        self._short_url = short_url
        self._title = title
        self._votecount = votecount
        self._session = session
        self._session = Session()
        self._session.headers.update(Default_Header)


    def get_content(self):
        super()._make_soup()
        zm_content = self.soup.find('div',class_ = 'zm-item-answer  zm-item-expanded')
        print(datetime.fromtimestamp(int(zm_content['data-created'])))
        html_content = zm_content.find('div', 'zm-editable-content clearfix')
        #先把url和content做成dict，然后存到文件里面
        if self._short_url not in answers_dict:
            answers_dict[self._short_url]=html_content





class Author(BaseZhihu):
    @class_common_init(re_author_url, True)
    def __init__(self, url, session=None):
        """
        :param str url: 用户主页url
        :param Session session: 使用的网络会话，为空则使用新会话。
        :return: 用户对象
        :rtype: Author
        """
        self.url = url
        self._session = Session()
        self._session.headers.update(Default_Header)


    def get_info(self):
        """
        获取用户的简单信息
        """
        super()._make_soup()
        self._name = self.soup.find('div',class_ = 'title-section ellipsis').span.text
        self._bio = self.soup.find('div',class_ = 'title-section ellipsis').find_all('span')[1].text
        self._follower_num = self.soup.find('div',class_ = 'zm-profile-side-following zg-clear')\
            .find_all('a')[1].strong.text
        self._agree_num = self.soup.find('div', class_ = 'zm-profile-header-info-list')\
            .find_all('span')[1].strong.text
        self._thanks_num = self.soup.find('div', class_ = 'zm-profile-header-info-list')\
            .find_all('span')[3].strong.text#[3]是因为各个层都搜索span
        asks_tags = self.soup.find('div',class_='profile-navbar clearfix').find_all('a')[1]
        self._asklink = asks_tags['href']
        self._asks = asks_tags.span.text
        answers_tags = self.soup.find('div',class_='profile-navbar clearfix').find_all('a')[2]
        self._answerlink = 'answers'
        self._answers = answers_tags.span.text
        post_tags = self.soup.find('div',class_='profile-navbar clearfix').find_all('a')[3]
        self._postlink = post_tags['href']
        self._posts = post_tags.span.text
        print(self._name+' '+self._bio+' '+self._follower_num+' '+self._agree_num+' '+self._thanks_num)
        print(self._asks+' '+self._answers+' '+self._posts)



    def get_answers(self,mode = 0):
        """
        两种答案的排序方式
        按时间：https://www.zhihu.com/people/douzishushu/answers?order_by=created&page=1
        按票数：https://www.zhihu.com/people/douzishushu/answers?order_by=vote_num&page=1
        """
        if mode == 0:
            modelink = '?order_by=vote_num&page='
        else:
            modelink = '?order_by=created&page='
        pages = math.ceil(int(self._answers) / 20)
        for page in range(pages):
            #page = 3
            self.url = self.url+self._answerlink+modelink+str(page+1)
            print(self.url)
            super()._make_soup()
            answers_list= self.soup.find('div', id='zh-profile-answer-list-outer').find_all('div', class_ ='zm-item')
            for x in range(len(answers_list)):
                #x = 7
                answer = answers_list[x]
                answer_title = answer.h2.a.text
                answer_href = answer.h2.a['href']
                answer_votecount = answer.find('div',class_="zm-item-vote-info ")['data-votecount']
                #下面的方法不可行，因为只有部分文字
                #zm_content = content.find('div', class_='zm-item-rich-text js-collapse-body').div.text
                #下面的方法也不行，会把上面的soup给毁了，只能加个类了...
                # self.url = ZH_url+answer_href
                # super()._make_soup()
                print(answer_title +' '+answer_href +' '+ answer_votecount)
                real_answer =Answers(ZH_url+answer_href, answer_href, answer_title, answer_votecount)
                real_answer.get_content()
                time.sleep(1)
            time.sleep(10)

        print(len(answers_dict))
        f = open('d://py-code//html_content', 'w')
        #pickle.dump(answers_dict, f)#json and pickle转换html有问题
        f.close()

"""
个人页面过于麻烦，如何抽象？-->先整页面解析，再分层解析
1.基本信息
2.获取回答
3.获取提问
2和3其实都是一样解析，先不管评论
"""
if __name__ == '__main__':
    sys.setrecursionlimit(1000000) #解决递归深度问题，默认为999，设置为100w
    #url='https://www.zhihu.com/people/douzishushu'
    url='https://www.zhihu.com/people/SONG-OF-SIREN'
    author = Author(url)
    author.get_info()
    author.get_answers(1)
    print('finish!')

