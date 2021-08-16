from pprint import pprint
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from datetime import datetime
from calendar import monthrange
from time import sleep

webhook = 'https://hooks.zapier.com/hooks/catch/2964702/bu3w9g5/'

# ------------------------------------------------------------------------------------------------------------------

def get_date_params():
    day= datetime.now().day
    month= datetime.now().month
    year= datetime.now().year
    hour = datetime.now().hour
    minute = datetime.now().minute
    return year, month, day, hour, minute
# ------------------------------------------------------------------------------------------------------------------

def send_request(url, payload= None):
    userAgent= 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'
    headers = {'User-Agent': userAgent}
    
    session = requests.Session()
    if payload:
        response= session.post(url,headers=headers,data=payload)
    else:
        response= session.get(url,headers=headers)
    return response


# ------------------------------------------------------------------------------------------------------------------

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

# ------------------------------------------------------------------------------------------------------------------
def get_uses(url):
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


# ------------------------------------------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------------------------------------------
def get_ticker_info(ticker):
    url= f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?region=US&lang=en-US&includePrePost=false&interval=2m&useYfid=true&range=1d&corsDomain=finance.yahoo.com&.tsrc=finance'

    response= send_request(url)
    meta= json.loads(response.content).get('chart').get('result')[0].get('meta')
    return meta

# ------------------------------------------------------------------------------------------------------------------
def get_price(meta): # Get Sock Price
    price= f'{meta.get("regularMarketPrice")} {meta.get("currency")}' 
    return price

# ------------------------------------------------------------------------------------------------------------------
def get_exchange(meta): # Get the Exchange symobl
    exchange= f'{meta.get("exchangeName")}' 
    return exchange        


# ------------------------------------------------------------------------------------------------------------------
def readDictionary(filename):
    dic = {}   
    try:
        file = open(filename, "r")
        dic = json.load(file)
        file.close()
    except FileNotFoundError:
        dic = {}
    return dic


# ------------------------------------------------------------------------------------------------------------------
def saveDictionary(dic, filename):
    file = open(filename, "w")
    json.dump(dic, file, indent=4)
    
# ------------------------------------------------------------------------------------------------------------------
def getFDAData(month, year):
    payload = {
        'reportSelectMonth':month,
        'reportSelectYear':year,
        'rptName':0
    }
    url= 'https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=reportsSearch.process'
    response= send_request(url, payload)

    df= pd.read_html(response.content)[0] # reading the table from the webpage via pandas
    df = df[df['Submission Status']=='Approval'] # filtering only fully approved submissions
    df = df.where(pd.notnull(df), '') # set None as empty to be able to concatinate in IDs
    df= df.rename(columns={'Submission Classification *': 'Submission Classification'})
    df = df.fillna(' ')
    df['id'] = ''
    for idx, row in df.iterrows():
        rowid = row['Approval Date'] + '_' + row['Drug Name'] + '_' + row['Submission'] + '_' + row['Active Ingredients'] + '_' + row['Submission Classification']  + '_' + row['Submission Status']  + '_' + row['Company']
        #print(rowid)
        row['id'] = rowid

    return df

# ------------------------------------------------------------------------------------------------------------------
def filterPreviouslyProcessed(df):
    processedDic = readDictionary("processed.json")
    df = df[~df['id'].isin(processedDic)]   # removed previously processed results
    newdic = df.set_index('id').T.to_dict('list')
    processedDic = processedDic | newdic
    saveDictionary(processedDic, "processed.json")
    return df

# ------------------------------------------------------------------------------------------------------------------
def getActiveIngredients(df):
    ingredientsDic = readDictionary("ingredients.json")
    active_ingredients= []
    [active_ingredients.extend([j.strip() for j in i.split(';')]) for i in df['Active Ingredients'].unique() ]
    active_ingredients= list(set(active_ingredients)) # unique set of ingredients
    for active_ingredient in active_ingredients:
        if active_ingredient not in ingredientsDic:
            ingredientsDic[active_ingredient] = {}
            link = get_link(active_ingredient)
            ingredientsDic[active_ingredient]['name'] = active_ingredient
            ingredientsDic[active_ingredient]['link'] = link
            ingredientsDic[active_ingredient]['uses'] = get_uses(link)
    saveDictionary(ingredientsDic, "ingredients.json")
    return ingredientsDic

# ------------------------------------------------------------------------------------------------------------------
def getCompanies(df):
    companiesDic = readDictionary("companies.json")
    companies= []
    [companies.extend([j.strip() for j in i.split(';')]) for i in df['Company'].unique() ]
    companies= list(set(companies)) # unique set of companies
    for company in companies:
        companiesDic[company] = {}
        ticker, price, exchange = search_duck(company)
        companiesDic[company]['name'] = company
        companiesDic[company]['ticker'] = ticker
        companiesDic[company]['price'] = price
        companiesDic[company]['exchange'] = exchange
    saveDictionary(companiesDic, "companies.json")
    return companiesDic


# ------------------------------------------------------------------------------------------------------------------
year, month, day, hour, minute = get_date_params()

print('# Getting data from FDA website ...')   
df = getFDAData(month, year)
df = filterPreviouslyProcessed(df)

print('# Getting uses url and data for the active ingredients ...')
ingredientsDic = getActiveIngredients(df)

print('# Getting companies and their details')
companiesDic = getCompanies(df)

print('# Compiling results')
records = []
for idx, row in df.iterrows():
    r = {}
    r['id'] = row['id']
    r['approval_date'] = row['Approval Date']
    r['drug_name'] = row['Drug Name']
    r['submission'] = {}
    r['submission']['name'] = row['Submission']
    r['submission']['classification'] = row['Submission Classification']
    r['submission']['status'] = row['Submission Status']
    r['company'] = companiesDic[row['Company']]
    r['ingredients'] = []
    ingredients = [x.strip() for x in row['Active Ingredients'].split(';')]
    for ingredient in ingredients:
        r['ingredients'].append(ingredientsDic[ingredient])
    records.append(r)

if(len(records) > 0):
    print('# Posting to webhook ',webhook)
    r = requests.post(webhook, data = json.dumps(records, indent=4), headers={'Content-Type': 'application/json'})
    #filename = f'{year}{month:02}{day:02}{hour:02}{minute:02}.json'
    #print('# Saving results to file ',filename)
    #with open(filename, 'w') as f:
    #    json.dump(records, f, indent=4)


print('SUCCESS')

