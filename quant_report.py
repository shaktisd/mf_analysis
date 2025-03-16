import json
from pprint import pprint
from datetime import datetime
import pandas as pd

import matplotlib.pyplot as plt
import yfinance as yf
import quantstats as qs

import logging
logging.getLogger('matplotlib.font_manager').setLevel(level=logging.CRITICAL)
import warnings
warnings.filterwarnings('ignore')

def create_report(fund_df, benchmark_df, fund_name, benchmark_name,temp_file_name):
    
    fund_data = fund_df.copy()
    benchmark_data = benchmark_df.copy()
    fund_data['date'] = pd.to_datetime(fund_data['date'])
    benchmark_data['date'] = pd.to_datetime(benchmark_data['date'])
    

    #fund_data = pd.read_csv("fund_data.csv", parse_dates=['date'])
    #benchmark_data = pd.read_csv("benchmark_data.csv", parse_dates=['date'])
    #fund_data['Date'] = pd.to_datetime(df['Date'])
    fund_data = fund_data.set_index(['date'], drop=True)
    benchmark_data = benchmark_data.set_index(['date'], drop=True)
    # Get common dates using index intersection
    common_dates = fund_data.index.intersection(benchmark_data.index)
    # Filter both dataframes to keep only common dates
    fund_data = fund_data.loc[common_dates]
    benchmark_data = benchmark_data.loc[common_dates]

    fund_data = fund_data.pct_change().dropna()
    fund_data = fund_data.iloc[:,0] # convert to series

    benchmark_data = benchmark_data.pct_change().dropna()
    benchmark_data = benchmark_data.iloc[:,0] # convert to series

    # Verify they have same shape now
    print("Fund data shape:", fund_data.shape)
    print("Benchmark data shape:", benchmark_data.shape)
    qs.reports.html(fund_data, benchmark_data,
                    title=fund_name,
                    benchmark_title=benchmark_name,
                    strategy_title=fund_name,
                    #download_filename=f'{fund_df.name}.html',
                    #output=f'{fund_name}.html'
                    output=temp_file_name
                    )

