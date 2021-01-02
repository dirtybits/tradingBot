######### RSI Indicator ##########
# The relative strength index (RSI) 
# is computed with a two-part calculation that starts with the following formula:
# RSI_s1 = 100 - (100/1+(avg_gain/avg_loss))
# The average gain or loss used in the calculation is the average percentage gain or loss
#  during a look-back period. The formula uses a positive value for the average loss.
# The standard is to use 14 periods to calculate the initial RSI value. 
# For example, imagine the market closed higher seven out of the past 14 days with
#  an average gain of 1%. The remaining seven days all closed lower
#  with an average loss of -0.8%. 
#  The calculation for the first part of the RSI would 
#  look like the following expanded calculation:
# 55.55 = 100 - (100/1+((.01/14)/(-0.008/14))
# Once there are 14 periods of data available, the second part of the RSI formula 
# can be calculated. The second step of the calculation smooths the results.
# RSI_s2 = 100 - (100/1+(((Previous Avg Gain*13) + Current Gain)/(-(Previous Average Loss * 13) + Current Loss)
# Calculation of the RSI
# Using the formulas above, RSI can be calculated, 
# where the RSI line can then be plotted beneath an asset's price chart.
# The RSI will rise as the number and size of positive closes increase, 
# and it will fall as the number and size of losses increase.
# The second part of the calculation smooths the result, 
# so the RSI will only near 100 or 0 in a strongly trending market.