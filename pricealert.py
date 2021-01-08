import telegram
from time import sleep
import requests
import time
from math import floor, log10
def readIds(filename):
    token_file = open(filename, 'r')
    lines = token_file.readlines()
    token_to_id = dict()
    for line in lines:
        items = line.strip().split(',')
        token_to_id[items[0]] = items[1]
    prices = getPriceInfo(token_to_id)
    return prices


def getData(symbol_id_token, cutoff, prevCounted):
    data = []
    for name in symbol_id_token:
        item = symbol_id_token[name]
        change = get_percentage_change(item['id'], 1, item['price'], 23/24)
        if name == 'Curve DAO Token':
            print(item['price'], change)
        

        #lambda function to round to n digits
        round_to_n = lambda x, n: round(x, -int(floor(log10(x))) + (n - 1))
        if change.is_integer() and int(change) == 0: 
            roundedC = 0
        elif (change < 0):
            #round to 3 decimal places
            roundedC = round_to_n(change * -1, 3) * -1
        else:
            #round to 3 decimal places
            roundedC = round_to_n(change, 3)
        roundedPrice = round_to_n(item['price'], 3)
        #percent change of more than 5.0% over past hour
        # print(name)
        if name in prevCounted:
            if abs(roundedC) > prevCounted[name][1] * cutoff:
                data.append({
                    'name': name,
                    'price': roundedPrice,
                    'id': item['id'],
                    'symbol': item['symbol'],
                    'change': roundedC
                })
                prevCounted[name][1] = prevCounted[name][1] + 1
            
        elif abs(roundedC) > cutoff:
            data.append({
                'name': name,
                'price': roundedPrice,
                'id': item['id'],
                'symbol': item['symbol'],
                'change': roundedC
            })
            prevCounted[name] = [1, 2]
    keysList = prevCounted.keys()
    dictCopy = prevCounted.copy()
    for token in keysList:
        dictCopy[token][0] = dictCopy[token][0] + 1
        # print(token, prevCounted[token][0])
        # resets every hour (5 min loop * 12)
        if dictCopy[token][0] == 12:
            dictCopy.pop(token, None)   
        # print(roundedC)
    return data, dictCopy


#gets market cap info for each token
def getPriceInfo(token_to_id):
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
            'symbol': token['symbol'],
            'id': token['id']
        }
        parsedInfo[token['name']] = tokenInfo
    return parsedInfo

#get request on coin gecko with specified query and endpoint
def coin_gecko_info(endpoint, query):
    response = requests.get(endpoint, params=query)
    if response.status_code == 200:
        return response.json()
    else:
        time.sleep(10)
        print('failed rq')
        return coin_gecko_info(endpoint,query)
    #grabs all coin gecko information

#cutoffFactor used for granularity and approximations (such as hour)
def get_percentage_change(tokenid, days, currentPrice, cutoffFactor):
    chart = get_market_chart(tokenid, {'vs_currency': 'usd',
                                'days': days})
    oldPrices = chart['prices']
    cutoff = int(cutoffFactor*len(oldPrices))
    oldPrice = oldPrices[cutoff][1]
    change = 100 * (currentPrice - oldPrice) / oldPrice
    return change

#gets more price data granularity
def get_market_chart(tokenid, query):
    #prices go from date queried till current time
    endpoint = "https://api.coingecko.com/api/v3/coins/" + tokenid + "/market_chart"
    response = requests.get(endpoint, params=query)
    if response.status_code == 200:
        return response.json()
    else:
        time.sleep(10)
        print('failed rq')
        return get_market_chart(tokenid,query)

def startBot(token, channel_id, data):
    q = []
    for item in data:
        q.append("<b>" + item['symbol'].upper() + "</b>")
        q.append("Current Price: $" + str(item['price']))
        q.append("1H Change: " + str(item['change']) + "%")
        q.append("\n")
    bot = telegram.Bot(token)
    bot.send_message(
        chat_id=channel_id,
        text= "\n".join(q),
        parse_mode=telegram.ParseMode.HTML,
        disable_notification=True,
        disable_web_page_preview=True
    )
def main():
    #Post to Price Alerts (personal)
    chat_id = "-382521543"
    token = "1583616459:AAHG-9054g8ncshTDyr6EN4afHXt5PAtRRs"
    prevCounted = {}
    # while True:
    #     symbol_id_token = readIds('tokens.txt')
    #     data, prevCounted = getData(symbol_id_token, 5, prevCounted)
    #     if data:
    #         startBot(token, chat_id, data)
    #     #updates every 5 mins
    #     sleep(5*60)
    #     # sleep(1)
    symbol_id_token = readIds('tokens.txt')
    data, prevCounted = getData(symbol_id_token, 5, prevCounted)
    if data:
        startBot(token, chat_id, data)

main()


