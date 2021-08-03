# %%
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from datetime import datetime
from calendar import monthrange


# %%
def get_link(ingredient):
    userAgent= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'
    headers = {'User-Agent': userAgent}

    url= f'https://www.webmd.com/drugs/2/search?type=drugs&query={ingredient}'
    session = requests.Session()
    response= session.get(url,headers=headers)
    soup= BeautifulSoup(response.content, features="lxml")
    print(ingredient)
    # sleep(2)
    try:
        res= soup.find_all("div", {"class": "drugs-exact-search-list-section"})[0].find_all("a", href=True)[0]
        return f'https://www.webmd.com{res["href"]}'
    except:
        try:
            res= soup.find_all("div", {"class": "drugs-partial-search-list-section"})[0].find_all("a", href=True)[0]
            return f'https://www.webmd.com{res["href"]}'
        except:
            return f'https://en.wikipedia.org/wiki/{ingredient.lower()}'   

def get_uses(url):
    userAgent= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'
    headers = {'User-Agent': userAgent}
    session = requests.Session()
    response= session.get(url,headers=headers)
    soup= BeautifulSoup(response.content, features="lxml")
    print(url)
    try:
        res= soup.find("div", {'class': 'monograph-content'}).text.strip()
    except Exception as e:
        try:
            res= ' '.join([r.text.strip() for r in soup.find_all("p")[:4]])
        except Exception as e:
            print(f'error:{e}')
            res= ''
    return res.strip()


def search_duck(keyword):
    userAgent= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'
    headers = {'User-Agent': userAgent}

    url= f'https://duckduckgo.com/html/?q={"%20".join(keyword.split(" "))}%20ticker%20yahoo'
    print(url)
    session = requests.Session()
    response= session.get(url,headers=headers)
    # print(response.content)
    soup= BeautifulSoup(response.content, features="lxml")
    print(keyword)
    print(response.content)
    #print(soup)
    # sleep(2)

    try:
        if soup.select_one("a[href*='https://finance.yahoo']")['href'][-1]=='/':
            ticker= soup.select_one("a[href*='https://finance.yahoo']")['href'].split('/')[-2]
        else:
            ticker= soup.select_one("a[href*='https://finance.yahoo']")['href'].split('/')[-1]
        ticker= ticker.split('?')[0]
        print(ticker)
        print(soup.select_one("a[href*='https://finance.yahoo']")['href'])
        print(f'ticker:{ticker}')
        meta= get_ticker_info(ticker)
        price= get_price(meta)
        print('got price')
        try:
            exchange= get_exchange(meta)
        except Exception as e:
            print('Error in finding the exact exchange', e)
            exchange= None
    except Exception as e:
        print('Error: wasnt able to find proper ticker url', e)
        price= None
        ticker= None
        exchange= None


    return ticker, price, exchange

def get_ticker_info(ticker):
    userAgent= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'
    headers = {'User-Agent': userAgent}
    session = requests.Session()
    url= f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?region=US&lang=en-US&includePrePost=false&interval=2m&useYfid=true&range=1d&corsDomain=finance.yahoo.com&.tsrc=finance'

    response= session.get(url,headers=headers)
    print(json.loads(response.content))
    meta= json.loads(response.content).get('chart').get('result')[0].get('meta')
    return meta
def get_price(meta):
    print(meta)
    price= f'{meta.get("regularMarketPrice")} {meta.get("currency")}' 
    return price
def get_exchange(meta):
    exchange= f'{meta.get("exchangeName")}' 
    return exchange      

print(search_duck('MERCK'))