import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pickle
import os.path
import time
from datetime import datetime, timedelta, date
from math import log10, floor

spreadsheetid = '1fAGE_pNOn--rgrGd7NUQYUFCaGi7n1h_fTBBx5t519U'
# use creds to create a client to interact with the Google Drive API
scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
client = gspread.authorize(creds)
exponents = ['K', 'M', 'B', 'T']

def isfloat(value):
  try:
    float(value)
    return True
  except ValueError:
    return False

#gets market cap info for each token
def getMCInfo(tokenFile):
    token_to_id = readTokens(tokenFile)
    ids = ''
    for tokenid in token_to_id.values():
        ids += tokenid + ', '
    ids = ids[:len(ids)-2]
    endpoint = 'https://api.coingecko.com/api/v3/coins/markets'
    query = {'ids': ids, 'vs_currency': 'usd'}
    responseJSON = coin_gecko_info(endpoint, query)
    
    parsedInfo = {}
    for token in responseJSON:
        tokenInfo = {
            'price': token['current_price'],
            'market_cap': token['market_cap'],
            'total_supply': token['total_supply'],
            'circulating_supply': token['circulating_supply'],
            'volume': token['total_volume'],
            'symbol': token['symbol'],
            'id': token['id'],
            '24h': token['price_change_percentage_24h']
        }
        parsedInfo[token['name']] = tokenInfo
    return parsedInfo

#reads token to ids in from tokens.txt
def readTokens(tokenFile):
    token_file = open(tokenFile, 'r')
    lines = token_file.readlines()
    token_to_id = dict()
    for line in lines:
        items = line.strip().split(',')
        token_to_id[items[0]] = items[1]
    return token_to_id


#get request on coin gecko with specified query and endpoint
def coin_gecko_info(endpoint, query):
    response = requests.get(endpoint, params=query)
    if response.status_code == 200:
        return response.json()
    else:
        print('failed rq')
        time.sleep(10)
        
        return coin_gecko_info(endpoint,query)
    #grabs all coin gecko information

#gets historical price of a token by id & date
def get_historical_price(tokenid, query):
    endpoint = "https://api.coingecko.com/api/v3/coins/" + tokenid + "/history"
    response = requests.get(endpoint, params=query)
    if response.status_code == 200:
        return response.json()
    else:
        print('failed rq')
        time.sleep(10)

        return get_historical_price(tokenid,query)

#gets more price data granularity
def get_market_chart(tokenid, query):
    #prices go from date queried till current time
    endpoint = "https://api.coingecko.com/api/v3/coins/" + tokenid + "/market_chart"
    response = requests.get(endpoint, params=query)
    if response.status_code == 200:
        time.sleep(0.5)
        return response.json()
    else:
        print('failed rq')
        time.sleep(10)

        return get_market_chart(tokenid,query)

#cutoffFactor used for granularity and approximations (such as hour)
def get_percentage_change(tokenid, days, currentPrice, cutoffFactor):
    chart = get_market_chart(tokenid, {'vs_currency': 'usd',
                                'days': days})
    oldPrices = chart['prices']
    cutoff = int(cutoffFactor*len(oldPrices))
    oldPrice = oldPrices[cutoff][1]
    change = 100 * (currentPrice - oldPrice) / oldPrice
    return change

def ytd_days():
        today = date.today()
        d1 = date(today.year, 1, 1)
        delta = today - d1
        return delta.days
def writeToPriceSheet(info, sheetFile):
    # Find a workbook by name and open the first sheet
    # Make sure you use the right name here.
    # Writes to sheet1
    sheet = client.open(sheetFile).sheet1

    rind = 2
    insertMatrix = []
    
    for tokenName in sorted(info.keys()):
        print(tokenName)
        tokenInfo = info[tokenName]
        if tokenInfo['price'] == None:
            continue
        currentPrice = float(tokenInfo['price'])

        # approximately one hour ago for the prices granularity
        onehourchange = get_percentage_change(tokenInfo['id'], 1, currentPrice, 23/24)
        onedaychange = get_percentage_change(tokenInfo['id'], 1, currentPrice, 0)

        #price difference from 1w ago
        oneweekchange = get_percentage_change(tokenInfo['id'], 7, currentPrice, 0)

        insertList = [
            tokenName,
            tokenInfo['symbol'],
            tokenInfo['price'],
            onehourchange,
            onedaychange,
            oneweekchange
            
        ]
        
        for i in range(len(insertList)):
            
            if type(insertList[i]) is float:
                # print(insertList[i])
                if insertList[i].is_integer() and int(insertList[i]) == 0: 
                    roundedVal = 0

                elif (insertList[i] < 0):

                    #lambda function to round to n digits
                    round_to_n = lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))
                    #round to 5 decimal places
                    roundedVal = round_to_n(insertList[i] * -1, 5) * -1
                else:

                    #lambda function to round to n digits
                    round_to_n = lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))
                    #round to 5 decimal places
                    roundedVal = round_to_n(insertList[i], 5)

                # insertList[i] = '{:,}'.format(roundedVal)
                insertList[i] = roundedVal

        insertMatrix.append(insertList)
        
        colstart = chr(ord('@')+1)
        colend = chr(ord('@')+len(insertList))
        rind += 1
    #sort by 24h change
    sortedInsertMatrix = sortMatrix(insertMatrix, 3)
    # print(sortedInsertMatrix)
    updateSheet(sheet, colstart, colend, sortedInsertMatrix)
    for i in range(len(insertMatrix)):
        for j in range(len(insertMatrix[i])):
            if isinstance(str(insertMatrix[i][j]), str):
                insertMatrix[i][j] = str(insertMatrix[i][j]).replace(',','')
                if isfloat(insertMatrix[i][j]):
                    insertMatrix[i][j] = float(insertMatrix[i][j])
    
    # print(insertMatrix)
    return insertMatrix
def writeToDeFiSheet(info, sheetFile):
    
    # Find a workbook by name and open the first sheet
    # Make sure you use the right name here.
    # Writes to sheet1
    sheet = client.open(sheetFile).sheet1

    rind = 2
    insertMatrix = []
    
    for tokenName in sorted(info.keys()):
        print(tokenName)
        tokenInfo = info[tokenName]
        if tokenInfo['price'] == None:
            continue
        currentPrice = float(tokenInfo['price'])

        # approximately one hour ago for the prices granularity
        onehourchange = get_percentage_change(tokenInfo['id'], 1, currentPrice, 23/24)

        #price difference from 1d ago
        onedaychange = get_percentage_change(tokenInfo['id'], 1, currentPrice, 0)

        #price difference from 1w ago
        oneweekchange = get_percentage_change(tokenInfo['id'], 7, currentPrice, 0)

        #price difference from 1mo ago
        onemonthchange = get_percentage_change(tokenInfo['id'], 30, currentPrice, 0)

        #price difference from 90d ago
        threemonthchange = get_percentage_change(tokenInfo['id'], 90, currentPrice, 0)

        #price difference YTD
        ytdchange = get_percentage_change(tokenInfo['id'], ytd_days(), currentPrice, 0)
        
        

        # calculating total & circulating supply in dollars
        if tokenInfo['total_supply']:
            totalSupplyDollars = tokenInfo['total_supply'] * tokenInfo['price']
        else:
            totalSupplyDollars = ''
        circulatingSupplyDollars = tokenInfo['circulating_supply'] * tokenInfo['price']

        insertList = [
            tokenName,
            tokenInfo['symbol'],
            tokenInfo['price'],
            onehourchange,
            onedaychange,
            oneweekchange,
            onemonthchange,
            threemonthchange,
            ytdchange,
            tokenInfo['total_supply'],
            totalSupplyDollars,
            tokenInfo['circulating_supply'],
            circulatingSupplyDollars,
            tokenInfo['market_cap'],
            tokenInfo['volume']
        ]
        
        for i in range(len(insertList)):
            
            if type(insertList[i]) is float:
                # print(insertList[i])
                if insertList[i].is_integer() and int(insertList[i]) == 0: 
                    roundedVal = 0

                elif (insertList[i] < 0):

                    #lambda function to round to n digits
                    round_to_n = lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))
                    #round to 5 decimal places
                    roundedVal = round_to_n(insertList[i] * -1, 5) * -1
                else:

                    #lambda function to round to n digits
                    round_to_n = lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))
                    #round to 5 decimal places
                    roundedVal = round_to_n(insertList[i], 5)

                # insertList[i] = '{:,}'.format(roundedVal)
                insertList[i] = roundedVal

        insertMatrix.append(insertList)
        
        colstart = chr(ord('@')+1)
        colend = chr(ord('@')+len(insertList))
        rind += 1
    #sort by 24h change
    sortedInsertMatrix = sortMatrix(insertMatrix, 4)
    # print(sortedInsertMatrix)
    updateSheet(sheet, colstart, colend, sortedInsertMatrix)
    for i in range(len(insertMatrix)):
        for j in range(len(insertMatrix[i])):
            if isinstance(str(insertMatrix[i][j]), str):
                insertMatrix[i][j] = str(insertMatrix[i][j]).replace(',','')
                if isfloat(insertMatrix[i][j]):
                    insertMatrix[i][j] = float(insertMatrix[i][j])
    
    # print(insertMatrix)
    return insertMatrix

def addTokenRatioSheets(info, sheet, ratioToken, sheetMatrix):
    
    

    rind = 2
    insertMatrix = []
    ratioTokenInfo = info[ratioToken]
    ratioTokenPrice = float(ratioTokenInfo['price'])
    hRTokenChange = float(get_percentage_change(ratioTokenInfo['id'], 1, ratioTokenPrice, 23/24))
    dRTokenChange = float(get_percentage_change(ratioTokenInfo['id'], 1, ratioTokenPrice, 0))
    wRTokenChange = float(get_percentage_change(ratioTokenInfo['id'], 7, ratioTokenPrice, 0))
    mRTokenChange = float(get_percentage_change(ratioTokenInfo['id'], 30, ratioTokenPrice, 0))
    tmRTokenChange = float(get_percentage_change(ratioTokenInfo['id'], 90, ratioTokenPrice, 0))
    yRTokenChange = float(get_percentage_change(ratioTokenInfo['id'], ytd_days(), ratioTokenPrice, 0))
    
    for i in range(len(sheetMatrix)):
        # print(sheetMatrix[i][0])
        if sheetMatrix[i][2] == None:
            continue
        # for j in range(len(sheetMatrix[i])):
        #     # print(sheetMatrix[gi][8])
        #     if isinstance(str(sheetMatrix[i][j]), str):
        #         sheetMatrix[i][j] = str(sheetMatrix[i][j]).strip(',')
        currentPrice = float(sheetMatrix[i][2])
        priceRatio = currentPrice / ratioTokenPrice


        # approximately one hour ago for the prices granularity
        onehourchange = float(sheetMatrix[i][3])
        hRatio = ((1+onehourchange/100) / (1+hRTokenChange/100)) * 100 - 100

        #price difference from 1d ago
        onedaychange = float(sheetMatrix[i][4])
        dRatio = ((1+onedaychange/100) / (1+dRTokenChange/100)) * 100 - 100
        #price difference from 1w ago
        oneweekchange = float(sheetMatrix[i][5])
        wRatio = ((1+oneweekchange/100) / (1+wRTokenChange/100)) * 100 - 100
        #price difference from 1mo ago
        onemonthchange = float(sheetMatrix[i][6])
        mRatio = ((1+onemonthchange/100) / (1+mRTokenChange/100)) * 100 - 100
        #price difference from 90d ago
        threemonthchange = float(sheetMatrix[i][7])
        tmRatio = ((1+threemonthchange/100) / (1+tmRTokenChange/100)) * 100 - 100
        #price difference YTD
        ytdchange = float(sheetMatrix[i][8])
        yRatio = ((1+ytdchange/100) / (1+yRTokenChange/100)) * 100 - 100
        

        insertList = [
            sheetMatrix[i][0],
            sheetMatrix[i][1],
            priceRatio,
            hRatio,
            dRatio,
            wRatio,
            mRatio,
            tmRatio,
            yRatio
        ]
        
        for i in range(len(insertList)):
            
            if type(insertList[i]) is float:
                # print(insertList[i])
                if insertList[i].is_integer() and int(insertList[i]) == 0: 
                    roundedVal = 0

                elif (insertList[i] < 0):

                    #lambda function to round to n digits
                    round_to_n = lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))
                    #round to 5 decimal places
                    roundedVal = round_to_n(insertList[i] * -1, 5) * -1
                else:

                    #lambda function to round to n digits
                    round_to_n = lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))
                    #round to 5 decimal places
                    roundedVal = round_to_n(insertList[i], 5)

                # insertList[i] = '{:,}'.format(roundedVal)
                insertList[i] = roundedVal

        insertMatrix.append(insertList)
        
        colstart = chr(ord('@')+1)
        colend = chr(ord('@')+len(insertList))
        time.sleep(0.5)
        rind += 1
    #sort by 24h change
    sortedInsertMatrix = sortMatrix(insertMatrix, 4)
    # print(sortedInsertMatrix)
    updateSheet(sheet, colstart, colend, sortedInsertMatrix)

def sortMatrix(insertMatrix, ind):
    return sorted(insertMatrix, key = lambda x: x[ind], reverse = True)

def updateSheet(sheet, colstart, colend, insertMatrix):
    try:
        sheet.update(colstart+str(2)+':'+colend+str(2 + len(insertMatrix)), insertMatrix)
    except:
        time.sleep(30)
        addTokenRatioSheets(info, sheet, ratioToken, sheetMatrix)

def priceSheet(tokenFile, sheetFile):
    while True:
        parsedInfo = getMCInfo(tokenFile)
        insertMatrix = writeToPriceSheet(parsedInfo, sheetFile)
        print('updated')
        time.sleep(60*1)

def main(tokenFile, sheetFile, ethbtcratios):
    while True:
        parsedInfo = getMCInfo(tokenFile)
        insertMatrix = writeToDeFiSheet(parsedInfo, sheetFile)
        if ethbtcratios:
            btcSheet = client.open('BTC vs DeFi').sheet1
            ethSheet = client.open('ETH vs DeFi').sheet1
            addTokenRatioSheets(parsedInfo, btcSheet, 'Bitcoin', insertMatrix)
            print('bitcoin inserted')
            addTokenRatioSheets(parsedInfo, ethSheet, 'Ethereum', insertMatrix)
            print('eth inserted')
        print('updated')
        time.sleep(60*30)

