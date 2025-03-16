import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from io import StringIO
import json
import yfinance as yf
from quant_report import create_report
import tempfile
import os
import streamlit.components.v1 as components

# Set page configuration
st.set_page_config(
    page_title="Mutual Fund Analyzer",
    page_icon="📊",
    layout="wide"
)

# Function to get all mutual funds
@st.cache_data(ttl=3600)  # Cache the data for 1 hour
def get_all_funds():
    try:
        response = requests.get("https://api.mfapi.in/mf")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch data: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Error fetching fund list: {e}")
        return []

# Function to get fund details by scheme code
@st.cache_data(ttl=1800)  # Cache the data for 30 minutes
def get_fund_details(scheme_code):
    try:
        response = requests.get(f"https://api.mfapi.in/mf/{scheme_code}")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch fund details: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error fetching fund details: {e}")
        return None

# Function to get benchmark data from Yahoo Finance
@st.cache_data(ttl=3600)  # Cache the data for 1 hour
def get_benchmark_data(start_date, end_date, ticker="^BSESN"):
    try:
        # Convert dates to the format yfinance expects
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')  # Add one day to include end_date
        
        # Download benchmark data
        benchmark_data = yf.download(ticker, start=start_date_str, end=end_date_str)
        
        if benchmark_data.empty:
            st.warning(f"No benchmark data available for {ticker} in the specified date range.")
            return None
            
        # Reset index to make 'Date' a column
        benchmark_data = benchmark_data.reset_index()
        
        # Keep only the necessary columns
        benchmark_data = benchmark_data[['Date', 'Close']]
        benchmark_data.columns = ['date', 'close']
        
        return benchmark_data
    except Exception as e:
        st.error(f"Error fetching benchmark data: {e}")
        return None

# Main app header
st.title("Mutual Fund Analyzer")
st.markdown("---")

# Step 1: Load all funds and create a search box with suggestions
with st.container():
    st.subheader("Step 1: Search for a Mutual Fund")
    
    # Initialize or get session state for funds
    if 'all_funds' not in st.session_state:
        with st.spinner("Loading all mutual funds..."):
            st.session_state.all_funds = get_all_funds()
    
    # Search functionality
    search_term = st.text_input("Type to search for a fund:", key="search_box")
    
    if search_term:
        # Filter funds based on search term (case-insensitive)
        filtered_funds = [
            fund for fund in st.session_state.all_funds
            if search_term.lower() in fund['schemeName'].lower()
        ]
        
        # Display total matches
        if filtered_funds:
            st.info(f"Found {len(filtered_funds)} matches")
            
            # Create a selection box for filtered funds
            fund_names = [f"{fund['schemeName']} (Code: {fund['schemeCode']})" for fund in filtered_funds]
            selected_fund_name = st.selectbox("Select a fund:", fund_names)
            
            # Extract the selected scheme code
            if selected_fund_name:
                selected_scheme_code = int(selected_fund_name.split("(Code: ")[1].split(")")[0])
                
                # Set session state for selected fund
                st.session_state.selected_scheme_code = selected_scheme_code
                st.session_state.selected_fund_name = next(
                    (fund['schemeName'] for fund in filtered_funds if fund['schemeCode'] == selected_scheme_code),
                    "Unknown Fund"
                )
        else:
            st.warning("No funds match your search term.")
    else:
        st.info("Start typing to search for mutual funds.")

# Step 2 & 3: Display fund details if a fund is selected
if 'selected_scheme_code' in st.session_state:
    st.markdown("---")
    st.subheader(f"Step 2 & 3: Fund Details - {st.session_state.selected_fund_name}")
    
    with st.spinner("Loading fund details..."):
        fund_details = get_fund_details(st.session_state.selected_scheme_code)
    
    if fund_details:
        # Create two columns for fund metadata and performance stats
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Fund Information")
            meta = fund_details.get('meta', {})
            
            # Create a more readable format for metadata
            meta_df = pd.DataFrame([
                {"Field": "Fund House", "Value": meta.get('fund_house', 'N/A')},
                {"Field": "Scheme Type", "Value": meta.get('scheme_type', 'N/A')},
                {"Field": "Scheme Category", "Value": meta.get('scheme_category', 'N/A')},
                {"Field": "Scheme Code", "Value": meta.get('scheme_code', 'N/A')},
                {"Field": "Scheme Name", "Value": meta.get('scheme_name', 'N/A')},
                {"Field": "ISIN (Growth)", "Value": meta.get('isin_growth', 'N/A')},
                {"Field": "ISIN (Dividend Reinvestment)", "Value": meta.get('isin_div_reinvestment', 'N/A') or 'N/A'}
            ])
            
            st.table(meta_df)
        
        # Step 4: Display NAV data and graph
        st.markdown("---")
        st.subheader("Step 4: Historical NAV Analysis")
        
        # Get NAV data
        nav_data = fund_details.get('data', [])
        
        if nav_data:
            # Convert to DataFrame
            df = pd.DataFrame(nav_data)
            
            # Convert date strings to datetime objects
            df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
            
            # Convert NAV to float
            df['nav'] = df['nav'].astype(float)
            
            # Sort by date (ascending)
            df = df.sort_values('date')
            
            # Display statistics in the second column
            with col2:
                st.markdown("### Performance Statistics")
                
                # Calculate basic statistics
                latest_nav = df['nav'].iloc[-1]
                start_nav = df['nav'].iloc[0]
                
                # Calculate returns for different periods
                if len(df) > 1:
                    latest_date = df['date'].iloc[-1]
                    
                    # 1-day return (if available)
                    if len(df) >= 2:
                        one_day_return = ((df['nav'].iloc[-1] / df['nav'].iloc[-2]) - 1) * 100
                    else:
                        one_day_return = 0
                    
                    # 1-week return (approx. 7 days)
                    week_df = df[df['date'] >= (latest_date - pd.Timedelta(days=7))]
                    if len(week_df) > 0:
                        one_week_return = ((latest_nav / week_df['nav'].iloc[0]) - 1) * 100
                    else:
                        one_week_return = None
                    
                    # 1-month return (approx. 30 days)
                    month_df = df[df['date'] >= (latest_date - pd.Timedelta(days=30))]
                    if len(month_df) > 0:
                        one_month_return = ((latest_nav / month_df['nav'].iloc[0]) - 1) * 100
                    else:
                        one_month_return = None
                    
                    # 1-year return (approx. 365 days)
                    year_df = df[df['date'] >= (latest_date - pd.Timedelta(days=365))]
                    if len(year_df) > 0:
                        one_year_return = ((latest_nav / year_df['nav'].iloc[0]) - 1) * 100
                    else:
                        one_year_return = None
                    
                    # Total return since beginning of available data
                    total_return = ((latest_nav / start_nav) - 1) * 100
                    
                    # Create DataFrame for returns
                    returns_df = pd.DataFrame([
                        {"Period": "Latest NAV", "Value": f"₹{latest_nav:.4f}"},
                        {"Period": "1-Day Return", "Value": f"{one_day_return:.2f}%" if one_day_return is not None else "N/A"},
                        {"Period": "1-Week Return", "Value": f"{one_week_return:.2f}%" if one_week_return is not None else "N/A"},
                        {"Period": "1-Month Return", "Value": f"{one_month_return:.2f}%" if one_month_return is not None else "N/A"},
                        {"Period": "1-Year Return", "Value": f"{one_year_return:.2f}%" if one_year_return is not None else "N/A"},
                        {"Period": "Total Return", "Value": f"{total_return:.2f}%"},
                        {"Period": "Date Range", "Value": f"{df['date'].iloc[0].date()} to {df['date'].iloc[-1].date()}"}
                    ])
                    
                    st.table(returns_df)
            
            # Time period selection for the graph
            time_periods = {
                "1 Month": 30,
                "3 Months": 90,
                "6 Months": 180,
                "1 Year": 365,
                "3 Years": 1095,
                "5 Years": 1825,
                "All Time": None
            }
            
            selected_period = st.selectbox("Select time period for graph:", list(time_periods.keys()))
            days = time_periods[selected_period]
            
            if days:
                filtered_df = df[df['date'] >= (df['date'].max() - pd.Timedelta(days=days))]
            else:
                filtered_df = df
            
            # Get benchmark data for comparison
            benchmark_ticker = "BSE-500.BO"  # BSE 500 Index
            
            # Get start and end dates from the filtered dataframe
            start_date = filtered_df['date'].min()
            end_date = filtered_df['date'].max()
            
            with st.spinner(f"Loading benchmark data ({benchmark_ticker})..."):
                benchmark_data = get_benchmark_data(start_date, end_date, benchmark_ticker)
            
            print(f"start date {start_date} end date {end_date}")
            #save data
            filtered_df.to_csv(f"fund_data.csv", index=False)
            benchmark_data.to_csv("benchmark_data.csv", index=False)
            
            # Create a figure with multiple traces for comparison
            fig = go.Figure()
            
            # Add fund NAV trace
            fig.add_trace(go.Scatter(
                x=filtered_df['date'],
                y=filtered_df['nav'],
                mode='lines',
                name=f"{st.session_state.selected_fund_name}",
                line=dict(color='blue')
            ))
            
            # Add benchmark trace if data is available
            if benchmark_data is not None and not benchmark_data.empty:
                # Normalize benchmark data to match fund's starting point for fair comparison
                benchmark_data_filtered = benchmark_data[(benchmark_data['date'] >= start_date) & (benchmark_data['date'] <= end_date)]
                
                if not benchmark_data_filtered.empty:
                    # Calculate normalized values (percentage change from first day)
                    first_nav = filtered_df.iloc[0]['nav']
                    first_benchmark = benchmark_data_filtered.iloc[0]['close']
                    
                    # Create normalized series
                    normalized_nav = filtered_df['nav'] / first_nav * 100
                    normalized_benchmark = benchmark_data_filtered['close'] / first_benchmark * 100
                    
                    # Clear previous figure and create new comparison chart
                    fig = go.Figure()
                    
                    # Add normalized fund NAV trace
                    fig.add_trace(go.Scatter(
                        x=filtered_df['date'],
                        y=normalized_nav,
                        mode='lines',
                        name=f"{st.session_state.selected_fund_name}",
                        line=dict(color='blue')
                    ))
                    
                    # Add normalized benchmark trace
                    fig.add_trace(go.Scatter(
                        x=benchmark_data_filtered['date'],
                        y=normalized_benchmark,
                        mode='lines',
                        name=f"BSE 500 Index",
                        line=dict(color='red')
                    ))
                    
                    # Show comparison table
                    st.subheader("Fund vs. Benchmark Performance")
                    
                    # Calculate returns for both
                    fund_return = ((filtered_df['nav'].iloc[-1] / filtered_df['nav'].iloc[0]) - 1) * 100
                    benchmark_return = ((benchmark_data_filtered['close'].iloc[-1] / benchmark_data_filtered['close'].iloc[0]) - 1) * 100
                    
                    # Display comparison metrics
                    comparison_df = pd.DataFrame([
                        {"Metric": "Total Return", "Fund": f"{fund_return:.2f}%", "BSE 500": f"{benchmark_return:.2f}%", 
                         "Difference": f"{(fund_return - benchmark_return):.2f}%"}
                    ])
                    
                    st.table(comparison_df)
            
            # Update layout
            fig.update_layout(
                title=f"Performance Comparison ({selected_period})",
                xaxis_title="Date",
                yaxis_title="Normalized Value (Base = 100)",
                hovermode="x unified",
                height=500,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Show the comparison chart
            st.plotly_chart(fig, use_container_width=True)
            
            # Also provide the raw NAV chart option
            show_raw_nav = st.checkbox("Show Raw NAV Values")
            if show_raw_nav:
                raw_fig = px.line(
                    filtered_df,
                    x='date',
                    y='nav',
                    title=f"NAV History for {st.session_state.selected_fund_name} ({selected_period})",
                    labels={'date': 'Date', 'nav': 'NAV Value (₹)'}
                )
                
                raw_fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="NAV (₹)",
                    hovermode="x unified",
                    height=500,
                    legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
                )
                
                st.plotly_chart(raw_fig, use_container_width=True)
            
                # Show data tables with download options
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Historical NAV Data")
                    
                    # Add a download button for the fund CSV data
                    csv_data = filtered_df.to_csv(index=False)
                    st.download_button(
                        label="Download Fund Data as CSV",
                        data=csv_data,
                        file_name=f"{st.session_state.selected_fund_name}_NAV_data.csv",
                        mime="text/csv"
                    )
                    
                    # Show the fund data table
                    st.dataframe(filtered_df.sort_values('date', ascending=False), use_container_width=True, height=400)
                
                # Show benchmark data if available
                with col2:
                    st.subheader("Benchmark Data (BSE 500)")
                    
                    # Get benchmark data covering the full fund history
                    full_start_date = df['date'].min()
                    full_end_date = df['date'].max()
                    
                    benchmark_full = get_benchmark_data(full_start_date, full_end_date, "BSE-500.BO")
                    
                    if benchmark_full is not None and not benchmark_full.empty:
                        # Add a download button for the benchmark CSV data
                        benchmark_csv = benchmark_full.to_csv(index=False)
                        st.download_button(
                            label="Download Benchmark Data as CSV",
                            data=benchmark_csv,
                            file_name="BSE_500_benchmark_data.csv",
                            mime="text/csv"
                        )
                        
                        # Filter to match the selected time period
                        benchmark_filtered = benchmark_full[
                            (benchmark_full['date'] >= filtered_df['date'].min()) &
                            (benchmark_full['date'] <= filtered_df['date'].max())
                        ]
                        
                        # Show the benchmark data table
                        st.dataframe(benchmark_filtered.sort_values('date', ascending=False), use_container_width=True, height=400)
                    else:
                        st.warning("Benchmark data is not available for the selected period.")
            else:
                st.warning("Select Checkbox to view historic NAV Values")
        else:
            st.error("Failed to load fund details. Please try again.")

# Advanced Analysis Section
st.markdown("---")
st.subheader("Advanced Performance Analysis")

# Show the advanced analysis only if both fund and benchmark data are available
if 'selected_scheme_code' in st.session_state and fund_details:
    # Calculate rolling returns if we have sufficient data
    if len(df) > 90:  # Only calculate if we have at least 3 months of data
        st.markdown("### Rolling Returns Analysis")
        
        # Create tabs for different rolling return periods
        rolling_tab1, rolling_tab2, rolling_tab3 = st.tabs(["1-Month Rolling", "3-Month Rolling", "6-Month Rolling"])
        
        # Calculate rolling returns for the fund
        df['1m_rolling'] = df['nav'].pct_change(periods=30) * 100
        df['3m_rolling'] = df['nav'].pct_change(periods=90) * 100
        df['6m_rolling'] = df['nav'].pct_change(periods=180) * 100
        
        # Get benchmark data for the full period
        full_benchmark = get_benchmark_data(df['date'].min(), df['date'].max(), "BSE-500.BO")
        
        if full_benchmark is not None and not full_benchmark.empty:
            # Calculate rolling returns for benchmark
            full_benchmark['1m_rolling'] = full_benchmark['close'].pct_change(periods=30) * 100
            full_benchmark['3m_rolling'] = full_benchmark['close'].pct_change(periods=90) * 100
            full_benchmark['6m_rolling'] = full_benchmark['close'].pct_change(periods=180) * 100
            
            # 1-Month Rolling Returns
            with rolling_tab1:
                # Create a figure for 1-month rolling returns
                roll_fig1 = go.Figure()
                
                # Add fund trace
                roll_fig1.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['1m_rolling'],
                    mode='lines',
                    name=f"{st.session_state.selected_fund_name}",
                    line=dict(color='blue')
                ))
                
                # Add benchmark trace
                roll_fig1.add_trace(go.Scatter(
                    x=full_benchmark['date'],
                    y=full_benchmark['1m_rolling'],
                    mode='lines',
                    name="BSE 500 Index",
                    line=dict(color='red')
                ))
                
                roll_fig1.update_layout(
                    title="1-Month Rolling Returns",
                    xaxis_title="Date",
                    yaxis_title="Return (%)",
                    hovermode="x unified",
                    height=400,
                    legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
                )
                
                st.plotly_chart(roll_fig1, use_container_width=True)
                
                # Calculate outperformance statistics
                common_dates = set(df['date']).intersection(set(full_benchmark['date']))
                if common_dates:
                    # Create merged dataframe for comparison
                    merged_1m = pd.merge(
                        df[['date', '1m_rolling']],
                        full_benchmark[['date', '1m_rolling']],
                        on='date',
                        suffixes=('_fund', '_benchmark')
                    )
                    
                    # Calculate outperformance
                    merged_1m['outperformance'] = merged_1m['1m_rolling_fund'] - merged_1m['1m_rolling_benchmark']
                    
                    # Calculate statistics
                    outperf_pct = (merged_1m['outperformance'] > 0).mean() * 100
                    avg_outperf = merged_1m['outperformance'].mean()
                    
                    st.metric(
                        label="Fund Outperformance (1-Month)",
                        value=f"{outperf_pct:.1f}% of periods",
                        delta=f"Avg: {avg_outperf:.2f}%"
                    )
            
            # 3-Month Rolling Returns
            with rolling_tab2:
                # Create a figure for 3-month rolling returns
                roll_fig3 = go.Figure()
                
                # Add fund trace
                roll_fig3.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['3m_rolling'],
                    mode='lines',
                    name=f"{st.session_state.selected_fund_name}",
                    line=dict(color='blue')
                ))
                
                # Add benchmark trace
                roll_fig3.add_trace(go.Scatter(
                    x=full_benchmark['date'],
                    y=full_benchmark['3m_rolling'],
                    mode='lines',
                    name="BSE 500 Index",
                    line=dict(color='red')
                ))
                
                roll_fig3.update_layout(
                    title="3-Month Rolling Returns",
                    xaxis_title="Date",
                    yaxis_title="Return (%)",
                    hovermode="x unified",
                    height=400,
                    legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
                )
                
                st.plotly_chart(roll_fig3, use_container_width=True)
                
                # Calculate outperformance statistics
                merged_3m = pd.merge(
                    df[['date', '3m_rolling']],
                    full_benchmark[['date', '3m_rolling']],
                    on='date',
                    suffixes=('_fund', '_benchmark')
                )
                
                # Calculate outperformance
                merged_3m['outperformance'] = merged_3m['3m_rolling_fund'] - merged_3m['3m_rolling_benchmark']
                
                # Calculate statistics
                outperf_pct = (merged_3m['outperformance'] > 0).mean() * 100
                avg_outperf = merged_3m['outperformance'].mean()
                
                st.metric(
                    label="Fund Outperformance (3-Month)",
                    value=f"{outperf_pct:.1f}% of periods",
                    delta=f"Avg: {avg_outperf:.2f}%"
                )
            
            # 6-Month Rolling Returns
            with rolling_tab3:
                # Create a figure for 6-month rolling returns
                roll_fig6 = go.Figure()
                
                # Add fund trace
                roll_fig6.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['6m_rolling'],
                    mode='lines',
                    name=f"{st.session_state.selected_fund_name}",
                    line=dict(color='blue')
                ))
                
                # Add benchmark trace
                roll_fig6.add_trace(go.Scatter(
                    x=full_benchmark['date'],
                    y=full_benchmark['6m_rolling'],
                    mode='lines',
                    name="BSE 500 Index",
                    line=dict(color='red')
                ))
                
                roll_fig6.update_layout(
                    title="6-Month Rolling Returns",
                    xaxis_title="Date",
                    yaxis_title="Return (%)",
                    hovermode="x unified",
                    height=400,
                    legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
                )
                
                st.plotly_chart(roll_fig6, use_container_width=True)
                
                # Calculate outperformance statistics
                merged_6m = pd.merge(
                    df[['date', '6m_rolling']],
                    full_benchmark[['date', '6m_rolling']],
                    on='date',
                    suffixes=('_fund', '_benchmark')
                )
                
                # Calculate outperformance
                merged_6m['outperformance'] = merged_6m['6m_rolling_fund'] - merged_6m['6m_rolling_benchmark']
                
                # Calculate statistics
                outperf_pct = (merged_6m['outperformance'] > 0).mean() * 100
                avg_outperf = merged_6m['outperformance'].mean()
                
                st.metric(
                    label="Fund Outperformance (6-Month)",
                    value=f"{outperf_pct:.1f}% of periods",
                    delta=f"Avg: {avg_outperf:.2f}%"
                )
        
        
                
        # Risk Metrics Section
        st.markdown("### Risk Analysis")
        
        # Create tabs for different risk metrics
        risk_tab1, risk_tab2 = st.tabs(["Volatility Analysis", "Drawdown Analysis"])
        
        # Get benchmark data for risk analysis if not already fetched
        if full_benchmark is None:
            full_benchmark = get_benchmark_data(df['date'].min(), df['date'].max(), "BSE-500.BO")
        
        if full_benchmark is not None and not full_benchmark.empty:
            # Volatility Analysis
            with risk_tab1:
                # Calculate rolling volatility (standard deviation of returns)
                # For monthly volatility, use daily returns and a 30-day window
                df['daily_return'] = df['nav'].pct_change() * 100
                df['volatility_30d'] = df['daily_return'].rolling(window=30).std() * (252 ** 0.5)  # Annualized
                
                full_benchmark['daily_return'] = full_benchmark['close'].pct_change() * 100
                full_benchmark['volatility_30d'] = full_benchmark['daily_return'].rolling(window=30).std() * (252 ** 0.5)  # Annualized
                
                # Create volatility comparison chart
                vol_fig = go.Figure()
                
                # Add fund volatility trace
                vol_fig.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['volatility_30d'],
                    mode='lines',
                    name=f"{st.session_state.selected_fund_name}",
                    line=dict(color='blue')
                ))
                
                # Add benchmark volatility trace
                vol_fig.add_trace(go.Scatter(
                    x=full_benchmark['date'],
                    y=full_benchmark['volatility_30d'],
                    mode='lines',
                    name="BSE 500 Index",
                    line=dict(color='red')
                ))
                
                vol_fig.update_layout(
                    title="30-Day Rolling Volatility (Annualized)",
                    xaxis_title="Date",
                    yaxis_title="Volatility (%)",
                    hovermode="x unified",
                    height=400,
                    legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
                )
                
                st.plotly_chart(vol_fig, use_container_width=True)
                
                # Calculate average volatility
                avg_fund_vol = df['volatility_30d'].mean()
                avg_benchmark_vol = full_benchmark['volatility_30d'].mean()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="Avg. Fund Volatility",
                        value=f"{avg_fund_vol:.2f}%"
                    )
                with col2:
                    st.metric(
                        label="Avg. Benchmark Volatility",
                        value=f"{avg_benchmark_vol:.2f}%",
                        delta=f"{avg_fund_vol - avg_benchmark_vol:.2f}%"
                    )
            
            # Drawdown Analysis
            with risk_tab2:
                # Calculate drawdowns for fund
                df['running_max'] = df['nav'].cummax()
                df['drawdown'] = ((df['nav'] / df['running_max']) - 1) * 100
                
                # Calculate drawdowns for benchmark
                full_benchmark['running_max'] = full_benchmark['close'].cummax()
                full_benchmark['drawdown'] = ((full_benchmark['close'] / full_benchmark['running_max']) - 1) * 100
                
                # Create drawdown comparison chart
                dd_fig = go.Figure()
                
                # Add fund drawdown trace
                dd_fig.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['drawdown'],
                    mode='lines',
                    name=f"{st.session_state.selected_fund_name}",
                    line=dict(color='blue')
                ))
                
                # Add benchmark drawdown trace
                dd_fig.add_trace(go.Scatter(
                    x=full_benchmark['date'],
                    y=full_benchmark['drawdown'],
                    mode='lines',
                    name="BSE 500 Index",
                    line=dict(color='red')
                ))
                
                dd_fig.update_layout(
                    title="Historical Drawdowns",
                    xaxis_title="Date",
                    yaxis_title="Drawdown (%)",
                    hovermode="x unified",
                    height=400,
                    legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
                )
                
                st.plotly_chart(dd_fig, use_container_width=True)
                
                # Calculate maximum drawdown statistics
                max_fund_dd = df['drawdown'].min()
                max_benchmark_dd = full_benchmark['drawdown'].min()
                
                # Display drawdown metrics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="Maximum Fund Drawdown",
                        value=f"{max_fund_dd:.2f}%"
                    )
                with col2:
                    st.metric(
                        label="Maximum Benchmark Drawdown",
                        value=f"{max_benchmark_dd:.2f}%",
                        delta=f"{max_fund_dd - max_benchmark_dd:.2f}%"
                    )
                
                # Calculate additional drawdown statistics
                # Recovery periods for significant drawdowns (>5%)
                df['is_recovery'] = df['drawdown'] == 0
                df['recovery_period'] = df['is_recovery'].astype(int)
                
                # Get current drawdown
                current_dd = df['drawdown'].iloc[-1]
                
                st.markdown("### Drawdown Statistics")
                st.metric(
                    label="Current Drawdown",
                    value=f"{current_dd:.2f}%"
                )
        st.header("Quantstats Report")
        if st.button("Download Quant Report"):
                #print(f"start date {start_date} end date {end_date}")
                #save data
                #filtered_df.to_csv(f"fund_data.csv", index=False)
                #benchmark_data.to_csv("benchmark_data.csv", index=False)
                
                st.markdown("### Report Saved ")
                
                curr_dir = os.path.dirname(os.path.abspath(__file__))
                
                # NOTE: use mkstemp will have permission issue: PermissionError: [WinError 32] The process cannot access the file because it is being used by another process
                temp_file_name = tempfile.mktemp(suffix=f"_{st.session_state.selected_fund_name}.html", dir=os.path.join(curr_dir, "temp"))

                st.header("Quantstats Report")
                title = st.text_input("Report Title", "Strategy Tearsheet")
                report_download = st.empty()
                with st.spinner("Generating Detail Report..."):
                    # TODO: customize output title, etc.
                    create_report(fund_df=filtered_df, benchmark_df=benchmark_data, fund_name = st.session_state.selected_fund_name, benchmark_name="BSE 500 Index",temp_file_name=temp_file_name)
                    with open(temp_file_name, "r") as fp:
                        html = fp.read()
                    components.html(html, scrolling=True, height=800)
                
                report_download.download_button(
                    "Download Report HTML",
                    html,
                    file_name= f"{st.session_state.selected_fund_name}_report.html",
                )

                os.remove(temp_file_name)
                
            
            
                
                
                
                