import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup, Comment
from queue import Queue
import bs4
import re
from flask import Flask, request, render_template

HTML_RE = '<[^>]+>'


def text_html_ratio_calc(element):
    len_html = 0
    htmls = re.findall(HTML_RE, element)
    if htmls:
        for html in htmls:
            len_html += len(html)
    len_text = len(element) - len_html
    return len_text / len_html, len_text


class News:
    def __init__(self, url, title, sapo, body, keywords):
        self.url = url
        self.title = title
        self.sapo = sapo
        self.body = body
        self.keywords = keywords

    def is_valid(self):
        return self.title and self.body and self.sapo


class NewsCrawler:
    def __init__(self, url, use_selenium=False):
        self.url = url
        if use_selenium:
            driver = webdriver.Firefox()
            options = Options()
            options.add_argument('--headless')
            driver.implicitly_wait(30)
            driver.get(url)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            driver.execute_script("window.scrollTo(0, 0);")
            self.page_source = BeautifulSoup(driver.page_source, 'lxml')
            driver.close()
        else:
            r = requests.get(self.url)
            r.encoding = 'utf8'
            self.page_source = BeautifulSoup(r.text, 'lxml')

    def get_body(self):
        page_source = self.page_source.select_one('body')
        [s.extract() for s in page_source(["script", "style", "h1", "h2"])]
        for element in page_source(text=lambda text: isinstance(text, Comment)):
            element.extract()
        q = Queue()
        q.put(page_source)
        max_text_html_ratio = 0
        max_ele = BeautifulSoup('', 'lxml')
        while not q.empty():
            ele = q.get()
            contents = ele.contents
            text_rate, len_text = text_html_ratio_calc(str(ele))
            if text_rate > max_text_html_ratio and len(ele.select('p')) > 3 and len_text > 1200:
                # print(text_rate)
                max_text_html_ratio = text_rate
                max_ele = ele

            for content in contents:
                if isinstance(content, bs4.element.Tag):
                    # text_rate = text_html_ratio_calc(str(ele))
                    # if text_rate > max_text_html_ratio:
                    q.put(content)
        for link in max_ele("a"):
            # if link.get('href', '').startswith('http'):
            link.extract()
            # link.replaceWithChildren()
        return max_ele

    def get_title(self):
        title = self.page_source.find("meta", property="og:title")
        return title.get('content', 'No meta title given') if title else 'No meta title given'

    def get_sapo(self):
        sapo = self.page_source.find("meta", property="og:description")
        return sapo.get('content', 'No meta description given') if sapo else 'No meta description given'

    def get_keywords(self):
        keywords = self.page_source.find("meta", attrs={'name': 'keywords'})
        return keywords.get('content', 'No keywords given') if keywords else 'No keywords given'

    def to_news(self):
        title = self.get_title()
        sapo = self.get_sapo()
        keywords = self.get_keywords()
        body = self.get_body()
        return News(self.url, title, sapo, body, keywords)

    def to_plain_news(self):
        news = self.to_news()
        body = news.body
        txt = ''
        for p in body(['p']):
            txt += p.get_text() + '\n'
        news.body = txt
        return news

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'GET':
        return render_template('index.html')
    else:
        url = request.form['url']
        news = NewsCrawler(url).to_news()
        return render_template('index.html', url=news.url, title=news.title, sapo=news.sapo, body=news.body,
                               keywords=news.keywords)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
