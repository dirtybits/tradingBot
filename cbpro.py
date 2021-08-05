import json, hmac, hashlib, time, requests, base64, os
from requests.auth import AuthBase

api_key = os.environ['CB_API_KEY']
secret_key = os.environ['CB_SECRET_KEY']
passphrase = os.environ['CB_PASSPHRASE']
    
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create custom authentication for Exchange
class CoinbaseExchangeAuth(AuthBase):
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def __call__(self, request):
        timestamp = str(time.time())
        message = timestamp + request.method + request.path_url + (request.body or '')
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode('utf-8'), hashlib.sha256).digest()
        signature_b64 = base64.encodebytes(signature).decode('utf-8').rstrip('\n')

        request.headers.update({
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        })
        return request

api_url = 'https://api.pro.coinbase.com/'
auth = CoinbaseExchangeAuth(config_dict["key"], config_dict["secret"], config_dict["passphrase"])

# Get accounts
def get_accounts():
    r = requests.get(api_url + 'accounts', auth=auth)
    return r.json()

# Get payment methods
def get_payment_methods():
    r = requests.get(api_url + 'payment-methods', auth=auth)
    print(r.json())
    return r.json()

# Make a deposit
def make_deposit(amount):
    payment = get_payment_methods()
    deposit = {
        'amount': amount,
        'currency': 'USD',
        'payment_method_id': payment[0]['id']
    }
    print(deposit)
    deposit = json.dumps(deposit)
    r = requests.post(api_url + 'deposits/payment-method', data=deposit, auth=auth)
    print(r.json())
    return r.json()

def get_currency_balance():
    pass

# Check price
def check_price(currency, quote='USD'):
    '''
    currency: the target cryptocurrencies (i.e. ['BTC', 'ETH'])
    quote: the other side of the pair (e.g. USD)
    '''
    price_dict = {}
    for ticker in currency:
        r = requests.get(api_url + 'products/'+ticker+'-'+quote+'/ticker')
        r = r.json()
        price_dict.update({ticker: float(r['price'])})

    price_dict.update({'time': r['time']})
    return price_dict

# Place LIMIT BUY order
def place_limit_buy(price_dict, ticker1, ticker2, amount, factor=.01):
    limit_price = round(float(f"{(price_dict[ticker] - (price_dict[ticker] * factor)):.2f}"),2)
    print(limit_price)
    if ticker == 'BTC': 
        amount = round(float(f"{(amount/limit_price):.8f}"),8)
    else: 
        amount = round(float(f"{(amount/limit_price):.2f}"),2)
    print(amount)
    order = {
        'size': amount,
        'price': limit_price,
        'side': 'buy',
        'product_id': ticker1+'-USD'
    }
    order = json.dumps(order)
    r = requests.post(api_url + 'orders', data=order, auth=auth)
    print(r.json())
    # {"id": "0428b97b-bec1-429e-a94c-59992926778d"}

# Place MARKET BUY order
def place_market_buy(funds, ticker1, ticker2):
    order = {
        'type': 'market',
        'funds': funds,
        'side': 'buy',
        'product_id': ticker1+'-'+ticker2
    }
    order = json.dumps(order)
    r = requests.post(api_url + 'orders', data=order, auth=auth)
    print(r.json())

# place SELL order
def place_sell_order(price_dict, ticker, amount, factor=.01):
    limit_price = round(float(f"{(price_dict[ticker] + (price_dict[ticker] * factor)):.2f}"), 2)
    print(limit_price)
    if ticker == 'BTC': 
        amount = round(float(f"{(amount/limit_price):.8f}"),8)
    else: 
        amount = round(float(f"{(amount/limit_price):.2f}"),2)
    print(amount)
    order = {
        'size': amount,
        'price': limit_price,
        'side': 'sell',
        'product_id': ticker+'-USD'
    }
    order = json.dumps(order)
    r = requests.post(api_url + 'orders', data=order, auth=auth)
    print(r.json())
    # {"id": "0428b97b-bec1-429e-a94c-59992926778d"}

def get_open_orders():
    pass

def cancel_order():
    pass

def cancel_last_order():
    pass

def cancel_all_orders():
    pass

# Cascading BUYS; buy more as price dips, sell more as price increases
def cascading_buys(price_dict, ticker, usd, rounds, factor=0.02, factor_adder=0.02):
    current_price = price_dict[ticker]
    total_cost = 0
    total_amount = 0
    for i in range(0, rounds):
        limit_price = round(float(f"{(current_price - (current_price * factor)):.2f}"), 2)
        if ticker == ('BTC' or 'ETH'): 
            amount = round(float(f"{(usd/limit_price):.8f}"), 8)
        else: 
            amount = round(float(f"{(usd/limit_price):.2f}"), 2)

        order = {
            'size': amount,
            'price': limit_price,
            'side': 'buy',
            'product_id': ticker+'-USD'
        }
        print('Order '+str(i)+':')
        print('$'+str(usd)+' BUY order for '+str(amount)+' '+ticker+' at limit price: $'+str(limit_price))
        total_cost = total_cost + usd
        total_amount = total_amount + amount
        factor = factor + factor_adder
        usd = round(float(usd + (usd * factor)), 2) + 3
        order = json.dumps(order)
        # # !!! THIS IS WHERE THE MAGIC HAPPENS !!! # #
        r = requests.post(api_url + 'orders', data=order, auth=auth)
        print(r.json())
        time.sleep(.01)
        
    print('TOTAL COST: $' + str(round(float(total_cost), 2)))
    print('AMOUNT ON ORDER: ' + str(round(float(total_amount), 2)))

def cascading_sells(price_dict, ticker, usd, rounds, factor=0.20, factor_adder=.01):
    current_price = price_dict[ticker]
    total_cost = 0
    total_amount = 0
    for i in range(0, rounds):
        limit_price = round(float(f"{(current_price + (current_price * factor)):.2f}"), 2)
        if ticker == 'BTC' or 'ETH': 
            amount = round(float(f"{(usd/limit_price):.8f}"), 8)
        else: 
            amount = round(float(f"{(usd/limit_price):.4f}"), 4)

        order = {
            'size': amount,
            'price': limit_price,
            'side': 'sell',
            'product_id': ticker+'-USD'
        }
        print('Order '+str(i)+':')
        print('$'+str(usd)+' SELL order for '+str(amount)+' '+ticker+' at limit price: $'+str(limit_price))
        total_cost = total_cost + usd
        total_amount = total_amount + amount
        factor = factor + factor_adder
        usd = round(float(usd + (usd * factor)), 2) + 3
        order = json.dumps(order)
        # !!! THIS IS WHERE THE MAGIC HAPPENS !!! # 
        r = requests.post(api_url + 'orders', data=order, auth=auth)
        print(r.json())
        time.sleep(1)
        
    print('TOTAL COST: $' + str(round(float(total_cost), 2)))
    print('AMOUNT ON ORDER: ' + str(round(float(total_amount), 2)))

# Use Indicators here

# TO-DO add logging



## main
price_dict = check_price(['BTC', 'ETH', 'LINK'])
make_deposit(20)
# time.sleep(20)
# for key in price_dict:
#     print(ke y + ': $' + str(price_dict[key]))
# place_buy_order(price_dict, 'LINK', 28, .14)
# place_sell_order(price_dict, 'LINK', 25, .01)
# cascading_buys(price_dict, 'LINK', 50, 6, .05, .005)

# AUTO DCA
hour = 3600
day = hour * 24
flag = 0                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
for i in range(0, 28):
    if flag == 0:
        place_market_buy(10, 'LINK', 'USD')
        flag = 1
    elif flag == 1:
        place_market_buy(10, 'GRT', 'USD')
        flag = 2
    elif flag == 2:
        place_market_buy(10, 'BTC', 'USD')
        flag = 0
    elif flag == 3:
        place_market_buy(10, 'ETH', 'USD')
        flag = 0
    elif flag == 4
        place_market_buy(10, 'SNX', 'USD')
        flag = 0
    print("Buy #" + str(i+1))
    current_time = time.strftime("%H:%M:%S %D", time.localtime())
    print(current_time)
    time.sleep(hour*6)
