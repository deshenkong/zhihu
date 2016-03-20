# -*- coding: utf-8 -*-

import functools
import re
import math
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from bs4 import Tag, NavigableString
from requests.packages.urllib3.util import Retry
import pdfcrowd
import os

import time
import sys
import json

ZH_url = 'https://www.zhihu.com'

Default_Header = {
    'Connection': 'keep-alive',
    'Accept': 'text/html, application/xhtml+xml, */*',
    'Accept-Language': 'zh-CN,zh;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.zhihu.com',
    'Origin': 'https://www.zhihu.com',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://www.zhihu.com/',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
}

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
                kwargs['session'] = requests.Session()
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

def clone_bs4_elem(el):
    """Clone a bs4 tag before modifying it.

    Code from `http://stackoverflow.com/questions/23057631/clone-element-with
    -beautifulsoup`
    """
    if isinstance(el, NavigableString):
        return type(el)(el)

    copy = Tag(None, el.builder, el.name, el.namespace, el.nsprefix)
    # work around bug where there is no builder set
    # https://bugs.launchpad.net/beautifulsoup/+bug/1307471
    copy.attrs = dict(el.attrs)
    for attr in ('can_be_empty_element', 'hidden'):
        setattr(copy, attr, getattr(el, attr))
    for child in el.contents:
        copy.append(clone_bs4_elem(child))
    return copy

def answer_content_process(content):
    content = clone_bs4_elem(content)
    del content['class']
    soup = BeautifulSoup(
        '<html><head><meta charset="utf-8"></head><body></body></html>')
    soup.body.append(content)
    # no_script_list = soup.find_all("noscript")
    # for no_script in no_script_list:
    #     no_script.extract()
    # img_list = soup.find_all(
    #     "img", class_=["origin_image", "content_image"])
    # for img in img_list:
    #     if "content_image" in img['class']:
    #         img['data-original'] = img['data-actualsrc']
    #     new_img = soup.new_tag('img', src=PROTOCOL + img['data-original'])
    #     img.replace_with(new_img)
    #     if img.next_sibling is None:
    #         new_img.insert_after(soup.new_tag('br'))
    # useless_list = soup.find_all("i", class_="icon-external")
    # for useless in useless_list:
    #     useless.extract()
    return soup.prettify()

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
all_url = {} #存放url
all_content = {} #存放author - html

class Answers(BaseZhihu):
    @class_common_init(re_ans_url)
    def __init__(self, url, short_url, title, votecount, session=None):
        self.url = url
        self._short_url = short_url
        self._title = title
        self._votecount = votecount
        self._session = session
        self._session = requests.Session()
        self._session.headers.update(Default_Header)


    def get_content(self):
        """
        1.保存所有的url，防止重复解析
        2.当次运行的回来的内存保存到pdf文件里面
        """
        super()._make_soup()
        zm_content = self.soup.find('div',class_ = 'zm-item-answer  zm-item-expanded')
        print(datetime.fromtimestamp(int(zm_content['data-created'])))
        html_content = zm_content.find('div', 'zm-editable-content clearfix')
        #html_content = answer_content_process(html_content)
        return  html_content




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
        self._session = requests.Session()
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
            #page = 2
            self.url = self.url+self._answerlink+modelink+str(page+1)
            print(self.url)
            #super()._make_soup()
            content = super()._get_content()
            super()._gen_soup(content)
            answers_list= self.soup.find('div', id='zh-profile-answer-list-outer').find_all('div', class_ ='zm-item')
            for x in range(len(answers_list)):
                #x = 7
                answer = answers_list[x]
                answer_title = answer.h2.a.text
                answer_href = answer.h2.a['href']
                answer_votecount_tag = answer.find('div',class_="zm-item-vote-info ")
                if answer_votecount_tag is None:
                    answer_votecount = 0
                else:
                    answer_votecount = answer_votecount_tag['data-votecount']
                print(answer_title +' '+answer_href +' '+ str(answer_votecount))
                if answer_href in all_url:
                    print('the url already be crewled'+answer_href)
                else:
                    all_url[answer_href]= x#随便填点东西
                    real_answer =Answers(ZH_url+answer_href, answer_href, answer_title, answer_votecount)
                    a_content = real_answer.get_content()
                    time.sleep(2)
            time.sleep(10)

        print(len(all_url))
        f = open('d://all_url', 'w')
        json.dump(all_url, f)
        f.close()

class Login(object):
    def __init__(self, cookies=None):
        self._session = requests.Session()
        self._session.headers.update(Default_Header)

    def log_in(self):
        email = input('email: ')
        password = input('password: ')
        _xsrf = BeautifulSoup(self._session.get('https://www.zhihu.com/#signin').content)\
            .find('input', attrs={'name': '_xsrf'})['value']
        data = {'email': email,
                'password': password,
                'remember_me': 'true',
                '_xsrf':_xsrf
                }
        resp= self._session.post('https://www.zhihu.com/login/email', data=data).content
        print(resp)





"""
个人页面过于麻烦，如何抽象？-->先整页面解析，再分层解析
1.基本信息
2.获取回答
3.获取提问
2和3其实都是一样解析，先不管评论
"""
if __name__ == '__main__':
    sys.setrecursionlimit(1000000) #解决递归深度问题，默认为999，设置为100w

    if os.path.isfile('d://all_url'):
        f = open('d://all_url', 'r')
        all_url= json.load(f)
        f.close()

    #url='https://www.zhihu.com/people/samuel-kong'
    url = 'https://www.zhihu.com/people/douzishushu'
    # client = Login()
    # client.log_in()
    #url='https://www.zhihu.com/people/xlzd'
    #url = 'https://www.zhihu.com/people/SONG-OF-SIREN'
    author = Author(url)
    author.get_info()
    author.get_answers(1)
    print('finish!')

