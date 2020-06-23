from bs4 import BeautifulSoup
from selenium import webdriver
import re
import os
import json
import time
import requests
from nltk.corpus import stopwords
from collections import Counter

def extract_articles(html: str) -> list:
    """

    :param http:
    :return:
    """
    soup = BeautifulSoup(html, 'html.parser')

    regex = re.compile(r"https:\/\/towardsdatascience.com\/[^@].*(?=\?source)")

    articles = []  # initialize articles list

    for a in soup.find_all('a', href=True):
        if bool(regex.match(a['href'])):
            link = regex.search(a['href']).group()
            articles.append(link)
    return list(set(articles))


def get_html(http: str, chromedriver: str='../assets/chromedriver.exe') -> str:
    """

    :param http:
    :param chromedriver:
    :return:
    """
    driver = webdriver.Chrome('../assets/chromedriver.exe')
    driver.get(http)  # open webpage

    # get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        time.sleep(0.5)  # wait to load page

        # calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    elem = driver.find_element_by_xpath("//*")  # get top level xpath
    return elem.get_attribute("outerHTML")  # return outerHTML of top level


def get_claps(soup: object) -> int:
    regex = re.compile(r'(?<=>)\d+(?=<)')  # build regex to find claps number
    regex_k = re.compile(r'(?<=>)[\d.]+(?=K<)')

    for button in soup.findAll('button'):
        if "claps" in str(button):
            break  # if we find claps break from loop

    if bool(regex.search(str(button))):
        claps = int(regex.search(str(button)).group())
    elif bool(regex_k.search(str(button))):
        # this checks for the lucky authors with claps format like 4.7K
        claps = int(float(regex_k.search(str(button)).group()) * 1e3)
    else:
        claps = 0

    return claps  # return number of claps


def get_author(soup: object) -> str:
    regex = re.compile(r'(?<=<a href="\/)@.*(?=\?source)')  # build regex to find author name

    for a in soup.findAll('a'):
        if bool(regex.search(str(a))):
            break  # if we find author name, break from loop

    author = regex.search(str(a)).group()  # get author username
    return author  # return author username


def claps_per_word(content: str, claps: int, stops: bool = False) -> dict:
    words = re.sub(r'[^a-zA-Z ]+', '', content)  # remove non-alphabet/whitespace characters
    words = words.split()  # tokenize words, splitting string on any whitespace

    if not stops:
        words = [word.lower() for word in words if word.lower() not in stopwords.words('english')]  # remove stop-words
    else:
        words = [word.lower() for word in words]

    # sometimes subtitles are entirely made up of stopwords (eg How I passed the TensorFlow Dev Cert Exam - DBourke)
    if len(words) == 0:
        return {}

    value_per_word = claps / len(words)  # calculate the value per word (for normalisation)

    counts = Counter(words)  # calculate word frequencies
    # return dictionary containing both frequencies and normalised frequencies to number of claps
    return {key: {'count': val, 'claps/word': val*value_per_word} for key, val in counts.items()}


class Article:
    def __init__(self, http: str):
        html = requests.get(http).text  # get article html as string
        self.soup = BeautifulSoup(html, 'html.parser')  # convert article html string to soup object

        article = self.soup.find('article')  # extract just the article part of the html

        h1 = article.findAll('h1')  # find all h1/header elements
        if len(h1) > 0:
            self.title = h1[0].text  # get title
            if len(h1) > 1:
                headers = article.findAll('h1')[1:]  # get list of all header elements
                self.headers = [elem.text for elem in headers]  # get list of the text from headers

        h2 = article.findAll('h2')  # find all h2/subheader elements
        if len(h2) > 0:
            self.subtitle = h2[0].text  # get subtitle
            if len(h2) > 1:
                subheaders = article.findAll('h2')[1:]  # get list of all subheader elements
                self.subheaders = [elem.text for elem in subheaders]  # get list of the text from subheaders

        content = article.findAll('p')  # get list of all p elements
        self.content = '\n'.join([elem.text for elem in content if not elem.text.startswith('http')])

        self.claps = get_claps(self.soup)  # get number of claps in article
        self.author = get_author(self.soup)  # get article author

        self.counts = {}

        self.counts['content'] = claps_per_word(self.content, self.claps)  # initialize counts dictionary
        self.counts['title'] = claps_per_word(self.title, self.claps)
        self.counts['subtitle'] = claps_per_word(self.subtitle, self.claps)


class Metrics:
    def __init__(self):
        self.authors = {}  # initialize container for author data
        self.language = {}  # initialize container for language data

    def add(self, article):
        if article.author in self.authors:
            self.authors[article.author]['claps'] += article.claps
            self.authors[article.author]['count'] += 1
        else:
            self.authors[article.author] = {
                'claps': article.claps,
                'count': 1
            }

        for section in article.counts:
            if section not in self.language:
                self.language[section] = {}
            for word in article.counts[section]:
                if word in self.language[section]:
                    self.language[section][word]['count'] += article.counts[section][word]['count']
                    self.language[section][word]['claps/word'] += article.counts[section][word]['claps/word']
                else:
                    self.language[section][word] = {
                        'count': article.counts[section][word]['count'],
                        'claps/word': article.counts[section][word]['claps/word']
                    }

    def save(self, path: str = '../data'):
        # saving language data
        with open(os.path.join(path, 'language.json'), 'w') as fp:
            json.dump(self.language, fp, indent=4, sort_keys=True)
            print(f"Language data saved to '{os.path.join(path, 'language.json')}'")
        # saving authors data
        with open(os.path.join(path, 'authors.json'), 'w') as fp:
            json.dump(self.authors, fp, indent=4, sort_keys=True)
            print(f"Authors data saved to '{os.path.join(path, 'authors.json')}'")
