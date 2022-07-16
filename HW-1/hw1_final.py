# -*- coding: utf-8 -*-

# Import required libraries
import datetime
import time
import polygon
from sqlalchemy import create_engine 
from sqlalchemy import text
import pandas as pd
from math import sqrt
from math import isnan
import matplotlib.pyplot as plt
from numpy import mean
from numpy import std
from math import floor

# import currency conversion classes from library which we have created

from currency_conversion import AUDUSD_return, GBPEUR_return, USDCAD_return, USDJPY_return, USDMXN_return, \
    EURUSD_return, USDCNY_return, USDCZK_return, USDPLN_return, USDINR_return


# We can buy, sell, or do nothing each time we make a decision.
# This class defies a nobject for keeping track of our current investments/profits for each currency pair
class portfolio(object):
    def __init__(self,from_,to):
        # Initialize the 'From' currency amont to 1
        self.amount = 1
        self.curr2 = 0
        self.from_ = from_
        self.to = to
        # We want to keep track of state, to see what our next trade should be
        self.Prev_Action_was_Buy = False
    
    # This defines a function to buy the 'To' currency. It will always buy the max amount, in whole number
    # increments
    def buy_curr(self, price):
        if self.amount >= 1:
            num_to_buy = floor(self.amount)
            self.amount -= num_to_buy
            self.Prev_Action_was_Buy = True
            self.curr2 += num_to_buy*price
            print("Bought %d worth of the target currency (%s). Our current profits and losses in the original currency (%s) are: %f." % (num_to_buy,self.to,self.from_,(self.amount-1)))
        else:
            print("There was not enough of the original currency (%s) to make another buy." % self.from_)
    # This defines a function to sell the 'To' currency. It will always sell the max amount, in a whole number
    # increments
    def sell_curr(self, price):
        if self.curr2 >= 1:
            num_to_sell = floor(self.curr2)
            self.amount += num_to_sell * (1/price)
            self.Prev_Action_was_Buy = False
            self.curr2 -= num_to_sell
            print("Sold %d worth of the target currency (%s). Our current profits and losses in the original currency (%s) are: %f." % (num_to_sell,self.to,self.from_,(self.amount-1)))
        else:
            print("There was not enough of the target currency (%s) to make another sell." % self.to)

# Function slightly modified from polygon sample code to format the date string 
def ts_to_datetime(ts):
    return datetime.datetime.fromtimestamp(ts / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

# Function which clears the raw data tables once we have aggregated the data in a 6 minute interval
def reset_raw_data_tables(engine,currency_pairs):
    with engine.begin() as conn:
        for curr in currency_pairs:
            conn.execute(text("DROP TABLE "+curr[0]+curr[1]+"_raw;"))
            conn.execute(text("CREATE TABLE "+curr[0]+curr[1]+"_raw(ticktime text, fxrate  numeric, inserttime text);"))

# This creates a table for storing the raw, unaggregated price data for each currency pair in the SQLite database
def initialize_raw_data_tables(engine,currency_pairs):
    with engine.begin() as conn:
        for curr in currency_pairs:
            conn.execute(text("CREATE TABLE "+curr[0]+curr[1]+"_raw(ticktime text, fxrate  numeric, inserttime text);"))

# This creates a table for storing the (6 min interval) aggregated price data for each currency pair in the SQLite database            
def initialize_aggregated_tables(engine,currency_pairs):
    with engine.begin() as conn:
        for curr in currency_pairs:
            conn.execute(text("CREATE TABLE "+curr[0]+curr[1]+"_agg(inserttime text, avgfxrate  numeric, stdfxrate numeric);"))

# This function is called every 6 minutes to aggregate the data, store it in the aggregate table, 
# and then delete the raw data
def aggregate_raw_data_tables(engine,currency_pairs):
    with engine.begin() as conn:
        for curr in currency_pairs:
            result = conn.execute(text("SELECT AVG(fxrate) as avg_price, COUNT(fxrate) as tot_count FROM "+curr[0]+curr[1]+"_raw;"))
            for row in result:
                avg_price = row.avg_price
                tot_count = row.tot_count
            std_res = conn.execute(text("SELECT SUM((fxrate - "+str(avg_price)+")*(fxrate - "+str(avg_price)+"))/("+str(tot_count)+"-1) as std_price FROM "+curr[0]+curr[1]+"_raw;"))
            for row in std_res:
                std_price = sqrt(row.std_price)
            date_res = conn.execute(text("SELECT MAX(ticktime) as last_date FROM "+curr[0]+curr[1]+"_raw;"))
            for row in date_res:
                last_date = row.last_date
            conn.execute(text("INSERT INTO "+curr[0]+curr[1]+"_agg (inserttime, avgfxrate, stdfxrate) VALUES (:inserttime, :avgfxrate, :stdfxrate);"),[{"inserttime": last_date, "avgfxrate": avg_price, "stdfxrate": std_price}])
            
            # This calculates and stores the return values
            exec("curr[2].append("+curr[0]+curr[1]+"_return(last_date,avg_price))")
            #exec("print(\"The return for "+curr[0]+curr[1]+" is:"+str(curr[2][-1].hist_return)+" \")")
            
            if len(curr[2]) > 5:
                try:
                    avg_pop_value = curr[2][-6].hist_return
                except:
                    avg_pop_value = 0
                if isnan(avg_pop_value) == True:
                    avg_pop_value = 0
            else:
                avg_pop_value = 0
            # Calculate the average return value and print it/store it
            curr_avg = curr[2][-1].get_avg(avg_pop_value)
            #exec("print(\"The average return for "+curr[0]+curr[1]+" is:"+str(curr_avg)+" \")")
            
            # Now that we have the average return, loop through the last 5 rows in the list to start compiling the 
            # data needed to calculate the standard deviation
            for row in curr[2][-5:]:
                row.add_to_running_squared_sum(curr_avg)
            
            # Calculate the standard dev using the avg
            curr_std = curr[2][-1].get_std()
            #exec("print(\"The standard deviation of the return for "+curr[0]+curr[1]+" is:"+str(curr_std)+" \")")
            
            # Calculate the average standard dev
            if len(curr[2]) > 5:
                try:
                    pop_value = curr[2][-6].std_return
                except:
                    pop_value = 0
            else:
                pop_value = 0
            curr_avg_std = curr[2][-1].get_avg_std(pop_value)
            #exec("print(\"The average standard deviation of the return for "+curr[0]+curr[1]+" is:"+str(curr_avg_std)+" \")")
            
            # -------------------Investment Strategy-----------------------------------------------
            try:
                return_value = curr[2][-1].hist_return
            except:
                return_value = 0
            if isnan(return_value) == True:
                return_value = 0

            try:
                return_value_1 = curr[2][-2].hist_return
            except:
                return_value_1 = 0
            if isnan(return_value_1) == True:
                return_value_1 = 0

            try:
                return_value_2 = curr[2][-3].hist_return
            except:
                return_value_2 = 0
            if isnan(return_value_2) == True:
                return_value_2 = 0

            try:
                upp_band = curr[2][-1].avg_return + (1.5 * curr[2][-1].std_return)
                if return_value >= upp_band and curr[3].Prev_Action_was_Buy == True and return_value != 0: #  (return_value > 0) and (return_value_1 > 0) and   
                    curr[3].sell_curr(avg_price)
            except:
                pass

            try:
                loww_band = curr[2][-1].avg_return - (1.5 * curr[2][-1].std_return)
                if return_value <= loww_band and curr[3].Prev_Action_was_Buy == False and return_value != 0: # and  (return_value < 0) and (return_value_1 < 0)
                    curr[3].buy_curr(avg_price)
            except:
                pass
            
            
            
# This main function repeatedly calls the polygon api every 1 seconds for 24 hours 
# and stores the results.
def main(currency_pairs):
    # The api key given by the professor
    key = "beBybSi8daPgsTp5yx5cHtHpYcrjp5Jq"
    
    # Number of list iterations - each one should last about 1 second
    count = 0
    agg_count = 0

    # Create an engine to connect to the database; setting echo to false should stop it from logging in std.out
    engine = create_engine("sqlite:///final.db", echo=False, future=True)
    # engine = create_engine("sqlite+pysqlite:///sqlite/final.db", echo=False, future=True)

    # Create the needed tables in the database
    initialize_raw_data_tables(engine,currency_pairs)
    initialize_aggregated_tables(engine,currency_pairs)
    
    # Open a RESTClient for making the api calls
    with polygon.ForexClient(key) as forex_client:
        # Loop that runs until the total duration of the program hits 24 hours. 
        while count < 86400: # 86400 seconds = 24 hours
            
            # Make a check to see if 6 minutes has been reached or not
            if agg_count == 360:
                # Aggregate the data and clear the raw data tables
                aggregate_raw_data_tables(engine,currency_pairs)
                reset_raw_data_tables(engine,currency_pairs)
                agg_count = 0
            
            # Only call the api every 1 second, so wait here for 0.75 seconds, because the 
            # code takes about .15 seconds to run
            time.sleep(0.75)
            
            # Increment the counters
            count += 1
            agg_count +=1

            # Loop through each currency pair
            for currency in currency_pairs:
                # Set the input variables to the API
                from_ = currency[0]
                to = currency[1]

                # Call the API with the required parameters
                try:
                    resp = client.forex_currencies_real_time_currency_conversion(from_, to, amount=100, precision=2)
                except:
                    continue

                # This gets the Last Trade object defined in the API Resource
                last_trade = resp.last

                # Format the timestamp from the result
                dt = ts_to_datetime(last_trade["timestamp"])

                # Get the current time and format it
                insert_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Calculate the price by taking the average of the bid and ask prices
                avg_price = (last_trade['bid'] + last_trade['ask'])/2

                # Write the data to the SQLite database, raw data tables
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO "+from_+to+"_raw(ticktime, fxrate, inserttime) VALUES (:ticktime, :fxrate, :inserttime)"),[{"ticktime": dt, "fxrate": avg_price, "inserttime": insert_time}])

# A dictionary defining the set of currency pairs we will be pulling data for
currency_pairs = [["AUD","USD",[],portfolio("AUD","USD")],
                  ["GBP","EUR",[],portfolio("GBP","EUR")],
                  ["USD","CAD",[],portfolio("USD","CAD")],
                  ["USD","JPY",[],portfolio("USD","JPY")],
                  ["USD","MXN",[],portfolio("USD","MXN")],
                  ["EUR","USD",[],portfolio("EUR","USD")],
                  ["USD","CNY",[],portfolio("USD","CNY")],
                  ["USD","CZK",[],portfolio("USD","CZK")],
                  ["USD","PLN",[],portfolio("USD","PLN")],
                  ["USD","INR",[],portfolio("USD","INR")]]

# Run the main data collection loop
main(currency_pairs)

"""# The following code blocks were used on historical data to fomulate a strategy"""

# Historical data used the russian ruble, but the live data no longer uses it. So we define a class 
# for it here. 
# Define the USDRUB_return class - each instance will store one row from the dataframe
class USDRUB_return(object):
    # Variable to store the total number of instantiated objects in this class
    num = 0
    # Variable to store the running sum of the return
    run_sum = 0
    run_squared_sum = 0
    run_sum_of_std = 0
    last_price = -1
    
    # Init all the necessary variables when instantiating the class
    def __init__(self, tick_time, avg_price):
        
        # Store each column value into a variable in the class instance
        self.tick_time = tick_time
        #self.price = avg_price
        
        if USDRUB_return.last_price == -1:
            hist_return = float('NaN')
        else:
            hist_return = (avg_price - USDRUB_return.last_price) / USDRUB_return.last_price
        
        self.hist_return = hist_return
        if isnan(hist_return):
            USDRUB_return.run_sum = 0
        else:
            # Increment the counter
            if USDRUB_return.num < 5:
                USDRUB_return.num += 1
            USDRUB_return.run_sum += hist_return
        USDRUB_return.last_price = avg_price
        
    def add_to_running_squared_sum(self,avg):
        if isnan(self.hist_return) == False:
            USDRUB_return.run_squared_sum += (self.hist_return - avg)**2
    
    def get_avg(self,pop_value):
        if isnan(self.hist_return) == False:
            USDRUB_return.run_sum -= pop_value
            avg = USDRUB_return.run_sum/(USDRUB_return.num)
            self.avg_return = avg
            return avg
    
    def get_std(self):
        if isnan(self.hist_return) == False:
            std = sqrt(USDRUB_return.run_squared_sum/(USDRUB_return.num))
            self.std_return = std
            USDRUB_return.run_sum_of_std += std
            USDRUB_return.run_squared_sum = 0
            return std
    
    def get_avg_std(self,pop_value):
        if isnan(self.hist_return) == False:
            USDRUB_return.run_sum_of_std -= pop_value
            avg_std = USDRUB_return.run_sum_of_std/(USDRUB_return.num)
            self.avg_of_std_return = avg_std 
            return avg_std

# This function is called every 6 minutes to aggregate the data, make the necessary calculations, 
# and make a decision about buying
def offline_aggregate_raw_data_tables(engine,currency_pairs):
    with engine.begin() as conn:
        for curr in currency_pairs:
            result = conn.execute(text("SELECT inserttime, avgfxrate FROM "+curr[0]+curr[1]+"_agg;"))
            for row in result:
                avg_price = row.avgfxrate
                last_date = row.inserttime
                
                # This calculates and stores the return values
                exec("curr[2].append("+curr[0]+curr[1]+"_return(last_date,avg_price))")
                #exec("print(\"The return for "+curr[0]+curr[1]+" is:"+str(curr[2][-1].hist_return)+" \")")

                if len(curr[2]) > 5:
                    try:
                        avg_pop_value = curr[2][-6].hist_return
                    except:
                        avg_pop_value = 0
                    if isnan(avg_pop_value) == True:
                        avg_pop_value = 0
                else:
                    avg_pop_value = 0
                # Calculate the average return value and print it/store it
                curr_avg = curr[2][-1].get_avg(avg_pop_value)
                #exec("print(\"The average return for "+curr[0]+curr[1]+" is:"+str(curr_avg)+" \")")

                # Now that we have the average return, loop through the last 5 rows in the list to start compiling the 
                # data needed to calculate the standard deviation
                for row in curr[2][-5:]:
                    row.add_to_running_squared_sum(curr_avg)

                # Calculate the standard dev using the avg
                curr_std = curr[2][-1].get_std()
                #exec("print(\"The standard deviation of the return for "+curr[0]+curr[1]+" is:"+str(curr_std)+" \")")

                # Calculate the average standard dev
                if len(curr[2]) > 5:
                    try:
                        pop_value = curr[2][-6].std_return
                    except:
                        pop_value = 0
                else:
                    pop_value = 0
                curr_avg_std = curr[2][-1].get_avg_std(pop_value)
                #exec("print(\"The average standard deviation of the return for "+curr[0]+curr[1]+" is:"+str(curr_avg_std)+" \")")

                # -------------------Investment Strategy-----------------------------------------------
                try:
                    return_value = curr[2][-1].hist_return
                except:
                    return_value = 0
                if isnan(return_value) == True:
                    return_value = 0

                try:
                    return_value_1 = curr[2][-2].hist_return
                except:
                    return_value_1 = 0
                if isnan(return_value_1) == True:
                    return_value_1 = 0

                try:
                    return_value_2 = curr[2][-3].hist_return
                except:
                    return_value_2 = 0
                if isnan(return_value_2) == True:
                    return_value_2 = 0
                
                try:
                    upp_band = curr[2][-1].avg_return + (1.5 * curr[2][-1].std_return)
                    if return_value >= upp_band and curr[3].Prev_Action_was_Buy == True and return_value != 0: #  (return_value > 0) and (return_value_1 > 0) and   
                        curr[3].sell_curr(avg_price)
                except:
                    pass
                
                try:
                    loww_band = curr[2][-1].avg_return - (1.5 * curr[2][-1].std_return)
                    if return_value <= loww_band and curr[3].Prev_Action_was_Buy == False and return_value != 0: # and  (return_value < 0) and (return_value_1 < 0)
                        curr[3].buy_curr(avg_price)
                except:
                    pass

# A dictionary defining the set of currency pairs we will be pulling data for
currency_pairs = [["AUD","USD",[],portfolio("AUD","USD")],
                  ["GBP","EUR",[],portfolio("GBP","EUR")],
                  ["USD","CAD",[],portfolio("USD","CAD")],
                  ["USD","JPY",[],portfolio("USD","JPY")],
                  ["USD","MXN",[],portfolio("USD","MXN")],
                  ["EUR","USD",[],portfolio("EUR","USD")],
                  ["USD","RUB",[],portfolio("USD","RUB")],
                  ["USD","CZK",[],portfolio("USD","CZK")],
                  ["USD","PLN",[],portfolio("USD","PLN")],
                  ["USD","INR",[],portfolio("USD","INR")]]

# Function to run the necessary testing on offline data
def main_offline(currency_pairs):
    # Create an engine to connect to the database
    engine = create_engine("sqlite+pysqlite:///sqlite/offline.db", echo=False, future=True)
    offline_aggregate_raw_data_tables(engine,currency_pairs)

main_offline(currency_pairs)

# This section plots the historical returns with their corressponding bollinger bands. It also
# prints the total profits/losses for each currency pair, and the total across all currency pairs. 

# Create a subplot
fig, axs = plt.subplots(10,figsize=(10,40))
fig.tight_layout()

# Variable to keep track of the total profit across currency pairs. 
tot_profit = 0

# Loop through the currency pairs
for ind, currency in enumerate(currency_pairs):
    
    from_ = currency[0]
    to = currency[1]
    
    # The sublists in the following list represent each of the following:
    # hist_return, avg_return, std_return, avg_of_std_return, upper bollinger, lower bollinger
    returns_array = [[],[],[],[],[],[]]
    
    # Extract the data from the classes and put it into a single list for plotting
    for row in currency[2]:
        returns_array[0].append(row.hist_return)
        try:
            returns_array[1].append(row.avg_return)
        except:
            returns_array[1].append(0)
        try:
            returns_array[2].append(row.std_return)
        except:
            returns_array[2].append(0)
        try:
            returns_array[3].append(row.avg_of_std_return)
        except:
            returns_array[3].append(0)
        try:
            returns_array[4].append(row.avg_return + (1.5 * row.std_return))
        except:
            returns_array[4].append(0)
        try:
            returns_array[5].append(row.avg_return - (1.5 * row.std_return))
        except:
            returns_array[5].append(0)
            
    print("The profit/losses for "+from_+to+" calculated with numpy is: %f" % (currency[3].amount -1))
    tot_profit += currency[3].amount - 1
    
    # Plot the line graphs with bollinger bands using the propper formatting
    axs[ind].plot(range(0,len(returns_array[0])),returns_array[0]) # plot the historical returns
    axs[ind].plot(range(0,len(returns_array[4])),returns_array[4]) # plot the upper bollinger band for returns
    axs[ind].plot(range(0,len(returns_array[5])),returns_array[5]) # plot the lower bollinger band for returns
    axs[ind].set(xlabel='Time',ylabel='Return')
    axs[ind].set_title(from_+to+'  Returns Over Time')
    
# Extra formatting to make sure the axis labels do not overlap the titles
plt.subplots_adjust(left=0.1,
                    bottom=0.1, 
                    right=0.9, 
                    top=0.9, 
                    wspace=0.4, 
                    hspace=0.4)

print("Total profit across currencies is: %f" % tot_profit)

