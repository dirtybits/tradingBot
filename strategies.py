# Here we can do stuff like if the current price is below 50 on the RSI, start buying, if it's above 70, start selling.
# send alerts (or make a different class for that)

# https://www.youtube.com/watch?v=SeHiVKuwiiI
import time
import talib
import numpy
# t = time.localtime()
current_time = time.strftime("%H:%M:%S %D", time.localtime())
print(current_time)