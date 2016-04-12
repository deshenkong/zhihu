# -*- coding: utf-8 -*-

import functools
import re
import math
import requests
import datetime
from bs4 import BeautifulSoup
from bs4 import Tag, NavigableString
from requests.packages.urllib3.util import Retry
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

#TODO:全局变量的设计极其糟糕
all_url = {} #存放url
aid_url = {} #存放author_id - author
author_info = {}#存放author:[answers,post]


SAVE_PATH = 'd://PythonCode//'
AINFO_PATH =  'd://PythonCode//author_info'
FILTER_PATH = 'd://PythonCode//all_url'
COOKIE_PATH = 'd://PythonCode//cookies'

PROTOCOL = ''
PIC_PROTOCOL = 'https://pic2.zhimg.com/'

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

def save_to_file(name, mode, html):
    #windows文件编码为gbk，网页一般是utf-8，所以要ignore一些转码错误
    if mode == 'html':
        with open(name+'.html', 'w',encoding='gbk', errors='ignore') as f:
            f.write(html)
    else:
        with open(name+'.md', 'w',encoding='gbk', errors='ignore') as f:
            import html2text
            h2t = html2text.HTML2Text()
            h2t.body_width = 0
            f.write(h2t.handle(html))

def process_symbol(string):
    string = re.sub("[\s+\.\!\/_,$%^*(+\"\']+|[+——！，。？?、~@#￥%……&*（）]+", " ",string)
    return string

#目前url不算多，不打算用布隆过滤器
def load_url_filter():
    if os.path.isfile(FILTER_PATH):
        global all_url
        f = open(FILTER_PATH, 'r')
        all_url = json.load(f)
        f.close()

def save_url_filter():
    f = open(FILTER_PATH, 'w')
    json.dump(all_url, f)
    f.close()

def update_url_filter(href, x):
    """
    如果url不在filter里面，就更新filter，并返回ture。反之亦然
    """
    global all_url
    if href not in all_url:
        all_url[href] = x
        return True
    else:
        return False

#用户信息
def load_author_info():
    if os.path.isfile(AINFO_PATH):
        global author_info
        f = open(AINFO_PATH, 'r')
        author_info = json.load(f)
        f.close()

def save_author_info():
    f = open(AINFO_PATH, 'w')
    json.dump(author_info, f)
    f.close()

def update_author_info(name, list):
    global author_info
    author_info[name] = list

def get_author_oldinfo(name):
    if name in author_info:
        return author_info[name]
    else:
        return False



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

def content_process(content, mode):
    content = clone_bs4_elem(content)
    del content['class']
    soup = BeautifulSoup(
        '<html><head></head><body></body></html>')
    soup.body.append(content)
    no_script_list = soup.find_all("noscript")
    for no_script in no_script_list:
        no_script.extract()
    if mode == 'answer':
        img_list = soup.find_all("img", class_=["origin_image", "content_image"])
    elif mode == 'post':
        img_list = soup.find_all("img")
    for img in img_list:
        if mode == 'answer':
            if "content_image" in img['class']:
                img['data-original'] = img['data-actualsrc']
            new_img = soup.new_tag('img', src=PROTOCOL + img['data-original'])
        elif mode == 'post':
            #原图的话就不需要replace
            new_img = soup.new_tag('img', src=PIC_PROTOCOL + img['src'].replace('.jpg','_b.jpg'))
        img.replace_with(new_img)
        if img.next_sibling is None:
            new_img.insert_after(soup.new_tag('br'))
    useless_list = soup.find_all("i", class_="icon-external")
    for useless in useless_list:
        useless.extract()
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

class Answers(BaseZhihu):
    @class_common_init(re_ans_url)
    def __init__(self, url, short_url, title, votecount, session=None):
        self.url = url
        self._short_url = short_url
        self._title = title
        self._votecount = votecount
        if Gobal_Session is not None:
            self._session = Gobal_Session
        else:
            self._session = session
            self._session = requests.Session()
            self._session.headers.update(Default_Header)


    def get_content(self):
        """
        """
        super()._make_soup()
        zm_content = self.soup.find('div',class_ = 'zm-item-answer')
        #print(datetime.fromtimestamp(int(zm_content['data-created'])))#TODO:有的页面没这个参数
        html_content = zm_content.find('div', 'zm-editable-content clearfix')
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
        if Gobal_Session is not None:
            self._session = Gobal_Session
        else:
            self._session = requests.Session()
            self._session.headers.update(Default_Header)


    def update_info(self):
        """
        更新用户的简单信息
        """
        super()._make_soup()
        self._id = self.url.split('/')[-2]#-2是因为结尾加了/
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
        # print(self._name+' '+self._bio+' '+self._follower_num+' '+self._agree_num+' '+self._thanks_num)
        print(self._asks+' '+self._answers+' '+self._posts)

        aulist = get_author_oldinfo(self._name)
        if aulist is not False:
            self._oldanswers = aulist[0]
            self._oldposts = aulist[1]
        else:
            self._oldanswers = 0
            self._oldposts = 0
        #保存 name : [answes,post]
        update_author_info(self._name, [self._answers, self._posts])
        save_author_info()

    def _save_answers(self, save_path):
        """
        两种答案的排序方式
        按时间：https://www.zhihu.com/people/douzishushu/answers?order_by=created&page=1
        按票数：https://www.zhihu.com/people/douzishushu/answers?order_by=vote_num&page=1
        """
        #如果按票数来排序的话，就得逐个检测才知道页面是否爬过
        # if mode == 0:
        #     modelink = '?order_by=vote_num&page='
        # else:
        modelink = '?order_by=created&page='
        new_page = int(self._answers)-int(self._oldanswers)
        pages = math.ceil((new_page) / 20)#20这个数目可能会有变动
        for page in range(pages):
            #page = 2
            self.url = self.url+self._answerlink+modelink+str(page+1)
            #print(self.url)
            super()._make_soup()
            answers_list= self.soup.find('div', id='zh-profile-answer-list-outer').find_all('div', class_ ='zm-item')
            #一般来说如果list比新页多，那就只要读新页就好了
            #如果新页比list多，那就读完这个list再判断
            if new_page < len(answers_list):
                a_list = new_page
            else:
                a_list = len(answers_list)
                new_page = new_page - a_list#这里必然不会出现负数
            # print(a_list)
            for x in range(a_list):
                #x = 7
                answer = answers_list[x]
                answer_title = answer.h2.a.text
                answer_href = answer.h2.a['href']
                answer_votecount_tag = answer.find('div',class_="zm-item-vote-info ")
                if answer_votecount_tag is None:
                    answer_votecount = 0
                else:
                    answer_votecount = answer_votecount_tag['data-votecount']
                print(answer_title + ' '+answer_href + ' ' + str(answer_votecount))
                if update_url_filter(answer_href,x):#filter url-votenumber
                    real_answer =Answers(ZH_url+answer_href, answer_href, answer_title, answer_votecount)
                    html_content = real_answer.get_content()
                    # all_content[answer_title] = html_content
                    html = content_process(html_content, 'answer')
                    time.sleep(20)
                    save_to_file(save_path + '//' + process_symbol(answer_title),'html',html)
            #time.sleep(20)
        save_url_filter()

    def _save_posts(self,save_path):
        """
        获取专栏
        """
        if self._posts is None:
            print('%s do not have posts.',self._name)
            return

        origin_host = self._session.headers.get('Host')
        new_posts = int(self._posts) - int(self._oldposts)
        for offset in range(0, math.ceil( new_posts/ 10)):
            self._session.headers.update(Host='zhuanlan.zhihu.com')
            url = 'http://zhuanlan.zhihu.com/api/columns/{0}/posts?limit=10&offset={1}'.\
                    format((self._id).replace('-',''), offset * 10)
            res = self._session.get(url)
            post_json = res.json()
            self._session.headers.update(Host=origin_host)
            for post in post_json:#这里不做posts的个数控制了，因为不知道post_json的长度是多少。
                p_title = post['title']
                p_name = post['author']['name']
                p_url = 'http://zhuanlan.zhihu.com'+ post['url']
                if update_url_filter(p_url,p_name):
                    #TODO:这里会丢弃一些格式，特别是数学公式
                    p_cont = content_process(BeautifulSoup(post['content']), 'post')
                    filename = save_path + p_title
                    save_to_file(filename, 'html', p_cont)
        save_url_filter()


def get_cookies(session):
    _session = session
    email = input('email: ')
    password = input('password: ')
    _xsrf = BeautifulSoup(_session.get('https://www.zhihu.com/#signin').content)\
        .find('input', attrs={'name': '_xsrf'})['value']
    data = {'email': email,
            'password': password,
            'remember_me': 'true',
            '_xsrf':_xsrf
            }
    resp= _session.post('https://www.zhihu.com/login/email', data=data).json()
    code = int(resp['r'])
    message = resp['msg']
    print(message)
    if code == 0:#成功
        cookies_str = json.dumps(_session.cookies.get_dict())
        with open(COOKIE_PATH, 'w') as f:
            f.write(cookies_str)
        return cookies_str
    else:
        return None


def log_in():
    _session = requests.Session()
    _session.headers.update(Default_Header)

    if os.path.isfile(COOKIE_PATH):
        with open(COOKIE_PATH) as f:
            cookies = f.read()
    else:
        cookies = get_cookies(_session)
        if cookies is None:
            return
    cookies_dict = json.loads(cookies)
    _session.cookies.update(cookies_dict)
    return _session

'''
这里最大的问题是个人的ID和专栏的ID不是一一对应的
从个人页面拿专栏ID其实挺麻烦的
如果从专栏页面拿个人ID倒是简单
不过为了解耦回答和专栏，这里处理还是挺麻烦的
'''
def create_author(aid, url, mode):
    if mode == 'post':
        p_append = '//posts'
    else:
        p_append =''
    if aid in aid_url:
        author = aid_url[aid]#保存起来，避免重复解析个人页面
    else:
        author = Author(url)
        aid_url[aid] = author
        author.update_info()

    today = datetime.date.today()
    save_path = SAVE_PATH + (author._name).replace(' ','') + '//'+str(today) + p_append
    if os.path.exists(save_path) is not True:
        os.makedirs(save_path)

    return (author, save_path)

def save_answers(answers_url):
    global SAVE_PATH
    global aid_url

    if len(answers_url) > 0:
        for url in answers_url:
            aid = url.split('/')[-1]
            ret = create_author(aid, url, 'answer')
            ret[0]._save_answers(ret[1])

def save_posts(post_url):
    global SAVE_PATH
    global aid_url
    if len(post_url) > 0:
        for url in post_url:
            id = url.split('/')[-1]
            origin_host = Gobal_Session.headers.get('Host')
            Gobal_Session.headers.update(Host='zhuanlan.zhihu.com')
            res = Gobal_Session.get('http://zhuanlan.zhihu.com/api/columns/{0}'.format(id))
            Gobal_Session.headers.update(Host=origin_host)
            author_json = res.json()
            aid = author_json['creator']['slug']
            ret = create_author(aid, url, 'post')
            ret[0]._save_posts(ret[1])



"""
尽量不给知乎服务器添麻烦。只实现单用户单进程的爬取。毕竟目前也只是需要爬一些感兴趣的回答和专栏。
"""
Gobal_Session = None

if __name__ == '__main__':

    sys.setrecursionlimit(1000000) #解决递归深度问题，默认为999，设置为100w
    Gobal_Session = log_in()
    load_url_filter()
    load_author_info()
    answers_url=[]
    answers_url.append('https://www.zhihu.com/people/samuel-kong')
    answers_url.append('https://www.zhihu.com/people/wu-mu-gui')
    save_answers(answers_url)

    post_url=[]
    post_url.append('http://zhuanlan.zhihu.com/hemingke')
    save_posts(post_url)

    print('finish!')

