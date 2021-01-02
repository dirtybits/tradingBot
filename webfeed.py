import websockets, json, asyncio

# Check currency price using websockets
# kind of slow, using API snapshot instead
async def check_pricefeed():
    # Add currency variable
    # ws = create_connection("wss://ws-feed.pro.coinbase.com/")
    async with websockets.connect("wss://ws-feed.pro.coinbase.com/") as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "product_ids" : [
                "BTC-USD",
                "ETH-USD",
                "LINK-USD"
            ],
            "channels": [
                {
                    "name": "ticker",
                    "product_ids": [
                        "BTC-USD",
                        "ETH-USD",
                        "LINK-USD"
                    ]
                }
            ]
        }))

    price_dict = {}
    try:
        while len(price_dict) < 4:
            result = await ws.recv()
            result = json.loads(result)
            print(result['type'])
            if result['type'] == 'ticker':
                market = result['product_id']
                price = float(result['price'])
                timestamp = result['time']
                price_dict.update({market: price})
                print(price_dict)
                print ("Received '%s'" % result)
            else:
                # time.sleep(1)
                await asyncio.sleep(3)
                await ws.close()
                continue
        price_dict.update({"time":timestamp})
    except:   
        price_dict.update({"time":timestamp})
        return price_dict
    # time.sleep(10)
    ws.close()
    price_dict.update({"time":timestamp})
    return price_dict

# try:
#     price_dict = asyncio.get_event_loop().run_until_complete(check_price())
#     print(price_dict)
# except(websockets.exceptions.ConnectionClosedOK):
#     pass

# price_dict = asyncio.get_event_loop().run_until_complete(check_pricefeed())
# print(price_dict)

