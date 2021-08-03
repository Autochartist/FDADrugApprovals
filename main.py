import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from datetime import datetime
from calendar import monthrange
from time import sleep

webhook = 'https://hooks.zapier.com/hooks/catch/2964702/bu3w9g5/'

def get_date_params():
    day= datetime.now().day
    month= datetime.now().month
    year= datetime.now().year

    if day==1:
        if month==1:
            month=12
            year -=1
  
        else:
            month -=1
            day= monthrange(year, month)[1]
    else:
        day -=1 # account always for the previous day
    return day, month, year

def send_request(url, payload= None):
    userAgent= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'
    headers = {'User-Agent': userAgent}
    
    session = requests.Session()
    if payload:
        response= session.post(url,headers=headers,data=payload)
    else:
        response= session.get(url,headers=headers)
    return response



def get_link(ingredient):
    url= f'https://www.webmd.com/drugs/2/search?type=drugs&query={ingredient}'
    
    response= send_request(url)
    soup= BeautifulSoup(response.content, features="lxml")
    print(f'Grabbing {ingredient} URL')
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

    response= send_request(url)

    soup= BeautifulSoup(response.content, features="lxml")
    print(f'Getting uses from {url}')
    try:
        res= soup.find("div", {'class': 'monograph-content'}).text.strip()
    except Exception as e:
        try:
            res= ' '.join([r.text.strip() for r in soup.find_all("p")[:4]])
        except Exception as e:
            print(f'error grabbing uses from {url}:{e}')
            res= ''
    return res.strip()


def search_duck(keyword):
    url= f'https://duckduckgo.com/html/?q={"%20".join(keyword.split(" "))}%20ticker%20yahoo'
    counter= 0
    myresponse= 'error-lite@duckduckgo.com'
    while 'error-lite@duckduckgo.com' in myresponse:
        counter+=1
        response= send_request(url)
        print(f'Trial No {counter} getting ticker for {keyword}')
        soup= BeautifulSoup(response.content, features="lxml")
        myresponse= response.content.decode('UTF-8')
        sleep(5)
        if counter>10:
            print(f'Max number of trials for {keyword}. Apparently the request is blocked')
            break
    # sleep(2)

    try:
        if soup.select_one("a[href*='https://finance.yahoo.com/quote/']")['href'][-1]=='/':
            ticker= soup.select_one("a[href*='https://finance.yahoo.com/quote/']")['href'].split('/')[-2]
        else:
            ticker= soup.select_one("a[href*='https://finance.yahoo.com/quote/']")['href'].split('/')[-1]
        ticker= ticker.split('?')[0]
        meta= get_ticker_info(ticker)
        price= get_price(meta)
        try:
            exchange= get_exchange(meta)
        except Exception as e:
            print(f'Error in finding the exact exchange for {keyword}', e)
            exchange= None
    except Exception as e:
        print(f'Error: wasnt able to find proper ticker url for {keyword}', e)
        price= None
        ticker= None
        exchange= None


    return ticker, price, exchange

def get_ticker_info(ticker):
    url= f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?region=US&lang=en-US&includePrePost=false&interval=2m&useYfid=true&range=1d&corsDomain=finance.yahoo.com&.tsrc=finance'

    response= send_request(url)
    meta= json.loads(response.content).get('chart').get('result')[0].get('meta')
    return meta
def get_price(meta): # Get Sock Price
    price= f'{meta.get("regularMarketPrice")} {meta.get("currency")}' 
    return price
def get_exchange(meta): # Get the Exchange symobl
    exchange= f'{meta.get("exchangeName")}' 
    return exchange        

def insert_data(df): # Insert data into the records
    records= []
    for idx, row in df.iterrows():

        ingredients= row['Active Ingredients'].split(';')
        if len(ingredients)>1:
            row['url']=[]
            row['uses']=[]
            for ingredient in row['Active Ingredients'].split(';'):
                row['url'].append(urls[ingredient.strip()])
                row['uses'].append(uses[urls[ingredient.strip()]])
        else:
            row['url']= urls[ingredients[0].strip()]
            row['uses']= uses[urls[ingredients[0].strip()]]
        records.append(dict(row))
    return records

day, month, year= get_date_params() # Get yesdterday's Date


payload = {
    'reportSelectMonth':month,
    'reportSelectYear':year,
    'rptName':0
}
url= 'https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=reportsSearch.process'

print('# Getting data from FDA website ...')   
response= send_request(url, payload)

print('-> Data Retrieved')
df= pd.read_html(response.content)[0] # reading the table from the webpage via pandas
df = df[df['Submission Status']=='Approval'] # filtering only fully approved submissions
df= df[df['Approval Date']==f'{month:02}/{day:02}/{year}'] # Filter only the dat before
print('* Data Filtered')



print('# Getting uses url and data for the active ingredients ...')
active_ingredients= []
[active_ingredients.extend([j.strip() for j in i.split(';')]) for i in df['Active Ingredients'].unique() ]
active_ingredients= list(set(active_ingredients)) # unique set of ingredients
urls= {}
uses= {}

# Get the uses url
for active_ingredient in active_ingredients:
    urls[active_ingredient]= get_link(active_ingredient)

# Get the uses Text from the URL
for active_ingredient,url in urls.items():
    uses[url]= get_uses(url)

print('-> Uses retrieved')

df = df.where(pd.notnull(df), '') # set None as empty to be able to concatinate in IDs
df= df.rename(columns={'Submission Classification *': 'Submission Classification'})

records= insert_data(df)

print('#searching company tickers via DuckduckGo ...')
companies= set([record['Company']for record in records]) # getting a unique set of companies

ticker, price, exchange= {}, {}, {}
for company in companies:
    ticker[company], price[company], exchange[company]= search_duck(company)

for record in records:
    record['ticker'], record['price'], record['Exchange']= ticker[record['Company']], price[record['Company']], exchange[record['Company']]

print('# modifying records format')
myrecords= []
for record in records:
    r= {}
    for key in record.keys():
        if not key.lower() in ['company', 'ticker', 'price', 'uses', 'url', 'exchange', 'active ingredients']:
            r[key]= record[key]
    r['company']= {}
    r['company']['name']= record['Company']
    r['company']['Exchange']= record['Exchange']
    r['company']['ticker']= record['ticker']
    r['company']['price']= record['price']
    r['uses']= {}
    if len(record['Active Ingredients'].split(';'))>1: # If there are multiple active ingredients
        r['uses']=[]

        for i, ingredient in enumerate(record['Active Ingredients'].split(';')):
            d= {
                'about': record['uses'][i],
                'url': record['url'][i],
                'Active Ingredients': ingredient.strip()
            }
            r['uses'].append(d)
    else:  # Assuming one active ingredient
        r['uses']=[] 
        d= {
            'about': record['uses'],
            'url': record['url'],
            'Active Ingredients': record['Active Ingredients'].strip()
        }
        r['uses'].append(d)
    r['id']= '_'.join([record['Approval Date'], record['Drug Name'], record['Submission'], record['Active Ingredients'], record['Submission Classification'], record['Submission Status']])

    myrecords.append(r)

print(f'# Saving the file {month:02}-{day:02}-{year}.json')
with open(f'{month:02}-{day:02}-{year}.json', 'w') as f:
    json.dump(myrecords, f, indent=4)

r = requests.post(webhook, data = json.dumps(myrecords, indent=4), headers={'Content-Type': 'application/json'})



