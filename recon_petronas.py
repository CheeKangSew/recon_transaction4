# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 16:41:22 2024

@author: ck
"""

import streamlit as st
import pandas as pd
from io import StringIO
import os

def load_and_prepare_data(file1, file2):
    # Load the two CSV files
    df1 = pd.read_csv(file1)
    # df1 = pd.read_excel(file1)
    df2 = pd.read_csv(file2)
    # df2 = pd.read_excel(file2)

    # Convert 'Transaction Date' and 'Transaction Time' to datetime format for df2
    df2['Date Time'] = pd.to_datetime(df2['Date Time'], format='%d/%m/%Y %H:%M', errors='coerce')
    # Drop rows with NaT in 'Date Time'
    df2 = df2.dropna(subset=['Date Time'])
    df2['Transaction Date'] = df2['Date Time'].dt.date
    df2['Transaction Time'] = df2['Date Time'].dt.time
    df2['CreationDateTime'] = pd.to_datetime(df2['Transaction Date'].astype(str) + ' ' + df2['Transaction Time'].astype(str), errors='coerce')
    
    
    # Convert 'Transaction Date' and 'Transaction Time' to datetime format for df1
    df1['Transaction Date'] = pd.to_datetime(df1['CreationDate'], format='%d/%m/%Y', errors='coerce')
    df1['Transaction Time'] = pd.to_datetime(df1['CreationTime'], format='%H:%M:%S', errors='coerce').dt.time
    df1 = df1.dropna(subset=['Transaction Date', 'Transaction Time'])
    df1['CreationDateTime'] = pd.to_datetime(df1['Transaction Date'].astype(str) + ' ' + df1['Transaction Time'].astype(str), errors='coerce')

    # Convert numeric columns to float
    df2['Transaction Amount (RM)'] = pd.to_numeric(df2['Transaction Amount (RM)'], errors='coerce')
    df1['Amount'] = pd.to_numeric(df1['Amount'], errors='coerce')

    # Remove spaces in 'Vehicle License Number' and store in 'VehicleNumber1'
    df2['Vehicle Number'] = df2['Vehicle Number'].str.replace(r'\s+', '', regex=True)
    df2['VehicleNumber2'] = df2['Vehicle Number'].str.replace(r'\s+', '', regex=True)

    # Remove spaces in 'VehicleRegistrationNo' and store in 'VehicleNumber2'
    df1['VehicleNumber1'] = df1['VehicleRegistrationNo'].str.replace(r'\s+', '', regex=True)
    
    # Ensure 'Receipt Number' is treated as a string (prevent numeric conversion)
    # df2['Receipt Number'] = df2['Receipt Number'].astype(str)

    # Filter necessary columns for matching
    df2_filtered = df2[['CreationDateTime', 'Transaction Amount (RM)', 'VehicleNumber2', 'Station Name']]
    df1_filtered = df1[['CreationDateTime', 'Amount', 'VehicleNumber1', 'PetrolStationName']]

    # Rename columns for clarity
    df2_filtered.rename(columns={'Transaction Amount (RM)': 'Amount2', 'Vehicle Number': 'VehicleNumber2'}, inplace=True)
    df1_filtered.rename(columns={'Amount': 'Amount1', 'VehicleRegistrationNo': 'VehicleNumber1'}, inplace=True)

    return df1, df1_filtered, df2_filtered

def match_transactions(df1_filtered, df2_filtered, time_buffer_hours=1):
    # Create an empty DataFrame to store matched transactions
    matched_transactions = pd.DataFrame(columns=['CreationDateTime', 'Amount1', 'VehicleNumber1', 'PetrolStationName', 'Amount2', 'VehicleNumber2', 'Station Name'])

    # Create time buffer
    time_buffer = pd.Timedelta(hours=time_buffer_hours)

    # Loop through each row in the first DataFrame
    for index1, row1 in df1_filtered.iterrows():
        # Find rows in the second DataFrame that match the vehicle number, site name, and time buffer
        df2_time_match = df2_filtered[
            (df2_filtered['VehicleNumber2'] == row1['VehicleNumber1']) &
            (df2_filtered['CreationDateTime'] >= (row1['CreationDateTime'] - time_buffer)) &
            (df2_filtered['CreationDateTime'] <= (row1['CreationDateTime'] + time_buffer)) &
            (df2_filtered['Station Name'] == row1['PetrolStationName']) &
            (abs(df2_filtered['Amount2'] - row1['Amount1']) < 0.01)  # Allow for minor differences in amounts
        ]

        # Append matched transactions to the matched_transactions DataFrame
        for index2, row2 in df2_time_match.iterrows():
            new_match = pd.DataFrame({
                'CreationDateTime': [row1['CreationDateTime']],
                'Amount1': [row1['Amount1']],
                'VehicleNumber1': [row1['VehicleNumber1']],
                'PetrolStationName': [row1['PetrolStationName']],
                'Amount2': [row2['Amount2']],
                'VehicleNumber2': [row2['VehicleNumber2']],
                'Station Name': [row2['Station Name']]
            })
            matched_transactions = pd.concat([matched_transactions, new_match], ignore_index=True)

    return matched_transactions

def count_transactions(df1_filtered, df2_filtered, matched_transactions):
    total_transactions_file1 = df1_filtered.shape[0]
    total_transactions_file2 = df2_filtered.shape[0]
    total_matched_transactions = matched_transactions.shape[0]

    return total_transactions_file1, total_transactions_file2, total_matched_transactions

def add_matched_column(df1, matched_transactions):
    # Create a new column in df2 to indicate whether the transaction is matched and add TransactionNo where applicable
    df1['Matched'] = df1.apply(
        lambda row: any(
            (matched_transactions['CreationDateTime'] == row['CreationDateTime']) &
            (matched_transactions['Amount1'] == row['Amount']) &
            (matched_transactions['VehicleNumber1'] == row['VehicleRegistrationNo']) &
            (matched_transactions['PetrolStationName'] == row['PetrolStationName'])
        ), axis=1
    )
    
    # Append TransactionNo from matched_transactions to df2 where matched

    
    return df1

def find_mismatch_reasons(df1_filtered, df2_filtered, matched_transactions, time_buffer_hours=1):
    # Create time buffer
    time_buffer = pd.Timedelta(hours=time_buffer_hours)

    mismatched_transactions = df1_filtered.copy()
    mismatched_transactions['MismatchReason'] = ''

    for index1, row1 in mismatched_transactions.iterrows():
        # Check for vehicle number mismatch
        df2_vehicle_match = df2_filtered[df2_filtered['VehicleNumber2'] == row1['VehicleNumber1']]
        if df2_vehicle_match.empty:
            mismatched_transactions.at[index1, 'MismatchReason'] = 'Vehicle Mismatch'
            continue
        
        # Check for time mismatch
        df2_time_match = df2_vehicle_match[
            (df2_vehicle_match['CreationDateTime'] >= (row1['CreationDateTime'] - time_buffer)) &
            (df2_vehicle_match['CreationDateTime'] <= (row1['CreationDateTime'] + time_buffer))
        ]
        if df2_time_match.empty:
            mismatched_transactions.at[index1, 'MismatchReason'] = 'Time Mismatch'
            continue
        
        # Check for site name mismatch
        df2_site_match = df2_time_match[df2_time_match['Station Name'] == row1['PetrolStationName']]
        if df2_site_match.empty:
            mismatched_transactions.at[index1, 'MismatchReason'] = 'Site Name Mismatch'
            continue
        
        # Check for amount mismatch
        df2_amount_match = df2_site_match[abs(df2_site_match['Amount2'] - row1['Amount1']) < 0.01]
        if df2_amount_match.empty:
            mismatched_transactions.at[index1, 'MismatchReason'] = 'Amount Mismatch'
    
    # Filter to only mismatched transactions
    mismatched_transactions = mismatched_transactions[mismatched_transactions['MismatchReason'] != '']
    
    return mismatched_transactions

def main():
    st.title("Soliduz & Petronas Transaction Matching Application")

    # Upload files
    # file1 = st.file_uploader("Upload the Soliduz file in excel", type="csv")
    file1 = st.file_uploader("Upload the Soliduz file in CSV format", type=["csv", "xlsx", "xls"])
    # file2 = st.file_uploader("Upload the Shell file in excel", type="csv")
    file2 = st.file_uploader("Upload the Petronas file in CSV format", type=["csv", "xlsx", "xls"])

    if file1 and file2:
        # Time buffer slider
        time_buffer_hours = st.slider("Select time buffer in hours", min_value=0, max_value=24, value=1, step=1)

        # Process files
        df1, df1_filtered, df2_filtered = load_and_prepare_data(file1, file2)
        
        matched_transactions = match_transactions(df1_filtered, df2_filtered, time_buffer_hours)

        total_transactions_file1, total_transactions_file2, total_matched_transactions = count_transactions(df1_filtered, df2_filtered, matched_transactions)
        
        st.write(f"Total transactions in Soliduz file: {total_transactions_file1}")
        st.write(f"Total transactions in Petronas file: {total_transactions_file2}")
        st.write(f"Total matched transactions: {total_matched_transactions}")

        # Add matched column and TransactionNo to df2
        df1_with_matched = add_matched_column(df1, matched_transactions)
        
        # Display matched transactions
        st.subheader("Matched Transactions")
        st.dataframe(matched_transactions)
        
        # Find and display mismatched transactions with reasons
        mismatched_transactions = find_mismatch_reasons(df1_filtered, df2_filtered, matched_transactions, time_buffer_hours)
        
        # Combine matched and mismatched transactions into the original DataFrame
        df1_with_matched['MismatchReason'] = ''
        for index, row in mismatched_transactions.iterrows():
            df1_with_matched.loc[(df1_with_matched['CreationDateTime'] == row['CreationDateTime']) &
                                 (df1_with_matched['Amount'] == row['Amount1']) &
                                 (df1_with_matched['VehicleRegistrationNo'] == row['VehicleNumber1']), 'MismatchReason'] = row['MismatchReason']
        
        # Display the first file with matched column and mismatch reasons
        st.subheader("Soliduz File with Transactions")
        st.dataframe(df1_with_matched)
        
        # Remove unnecessary columns for the downloadable file
        # Fix for 'ReferenceReceiptNo' column (treating it as string)
        # df1_with_matched['ReferenceReceiptNo'] = df1_with_matched['ReferenceReceiptNo'].astype(str)
        df1_downloadable = df1_with_matched.drop(columns=['Transaction Date', 'Transaction Time', 'CreationDateTime', 'VehicleNumber1'])

        # Download buttons
        st.download_button(
            label="Download Matched Transactions",
            data=matched_transactions.to_csv(index=False).encode('utf-8'),
            file_name='matched_transactions.csv',
            mime='text/csv'
        )

        st.download_button(
            label="Download Soliduz File with processed transaction",
            data=df1_downloadable.to_csv(index=False).encode('utf-8'),
            file_name='TransactionListing_with_matched_and_reasons.csv',
            mime='text/csv'
        )

if __name__ == "__main__":
    main()
