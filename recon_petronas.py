# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 16:41:22 2024

@author: ck
"""

import streamlit as st
import pandas as pd
from io import StringIO

def load_and_prepare_data(file1, file2):
    # Load the two CSV files
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)

    # Convert 'Transaction Date' and 'Transaction Time' to datetime format for df1
    df1['Date Time'] = pd.to_datetime(df1['Date Time'], format='%d/%m/%Y %H:%M', errors='coerce')
    df1 = df1.dropna(subset=['Date Time'])
    df1['Transaction Date'] = df1['Date Time'].dt.date
    df1['Transaction Time'] = df1['Date Time'].dt.time
    df1['TransactionDateTime'] = pd.to_datetime(df1['Transaction Date'].astype(str) + ' ' + df1['Transaction Time'].astype(str), errors='coerce')

    # Convert 'Transaction Date' and 'Transaction Time' to datetime format for df2
    df2['Transaction Date'] = pd.to_datetime(df2['TransactionDate'], format='%d/%m/%Y', errors='coerce')
    df2['Transaction Time'] = pd.to_datetime(df2['TransactionTime'], format='%H:%M:%S', errors='coerce').dt.time
    df2.dropna(subset=['Transaction Date', 'Transaction Time'], inplace=True)
    df2['TransactionDateTime'] = pd.to_datetime(df2['Transaction Date'].astype(str) + ' ' + df2['Transaction Time'].astype(str), errors='coerce')
    df2.dropna(subset=['TransactionDateTime'], inplace=True)

    # Convert numeric columns to float
    df1['Transaction Amount (RM)'] = pd.to_numeric(df1['Transaction Amount (RM)'], errors='coerce')
    df2['Amount'] = pd.to_numeric(df2['Amount'], errors='coerce')

    


    # Filter necessary columns for matching
    df1_filtered = df1[['TransactionDateTime', 'Transaction Amount (RM)', 'Vehicle Number']]

    # Rename columns for clarity
    df1_filtered.rename(columns={'Transaction Amount (RM)': 'Amount1', 'Vehicle Number': 'VehicleNumber1'}, inplace=True)
    df2_filtered = df2[['TransactionDateTime', 'Amount', 'VehicleRegistrationNo', 'TransactionNo']]
    df2_filtered.rename(columns={'Amount': 'Amount2', 'VehicleRegistrationNo': 'VehicleNumber2'}, inplace=True)
    
    # Debug print to verify final column names
    print(f"df1_filtered columns: {df1_filtered.columns}")
    print(f"df2_filtered columns: {df2_filtered.columns}")
    
    return df1, df2, df1_filtered, df2_filtered

def match_transactions(df1_filtered, df2_filtered, time_buffer_hours=1):
    # Create an empty DataFrame to store matched transactions
    matched_transactions = pd.DataFrame(columns=['TransactionDateTime', 'Amount1', 'VehicleNumber1', 'Amount2', 'VehicleNumber2', 'TransactionNo'])

    # Create time buffer
    time_buffer = pd.Timedelta(hours=time_buffer_hours)

    # Loop through each row in the first DataFrame
    for index1, row1 in df1_filtered.iterrows():
        # Find rows in the second DataFrame that match the vehicle number and time buffer
        df2_time_match = df2_filtered[
            (df2_filtered['VehicleNumber2'] == row1['VehicleNumber1']) &
            (df2_filtered['TransactionDateTime'] >= (row1['TransactionDateTime'] - time_buffer)) &
            (df2_filtered['TransactionDateTime'] <= (row1['TransactionDateTime'] + time_buffer)) &
            (abs(df2_filtered['Amount2'] - row1['Amount1']) < 0.01)  # Allow for minor differences in amounts
        ]

        # Append matched transactions to the matched_transactions DataFrame
        for index2, row2 in df2_time_match.iterrows():
            new_match = pd.DataFrame({
                'TransactionDateTime': [row1['TransactionDateTime']],
                'Amount1': [row1['Amount1']],
                'VehicleNumber1': [row1['VehicleNumber1']],
                'Amount2': [row2['Amount2']],
                'VehicleNumber2': [row2['VehicleNumber2']],
                'TransactionNo': [row2['TransactionNo']]
            })
            matched_transactions = pd.concat([matched_transactions, new_match], ignore_index=True)
    
    return matched_transactions

def match_transactions1(df2_filtered, df1_filtered, time_buffer_hours=1):
    # Create an empty DataFrame to store matched transactions
    matched_transactions1 = pd.DataFrame(columns=['TransactionDateTime', 'Amount2', 'VehicleNumber2', 'Amount1', 'VehicleNumber1', 'TransactionNo'])

    # Create time buffer
    time_buffer = pd.Timedelta(hours=time_buffer_hours)

    # Loop through each row in the first DataFrame
    for index1, row1 in df2_filtered.iterrows():
        # Find rows in the second DataFrame that match the vehicle number and time buffer
        df1_time_match = df1_filtered[
            (df1_filtered['VehicleNumber1'] == row1['VehicleNumber2']) &
            (df1_filtered['TransactionDateTime'] >= (row1['TransactionDateTime'] - time_buffer)) &
            (df1_filtered['TransactionDateTime'] <= (row1['TransactionDateTime'] + time_buffer)) &
            (abs(df1_filtered['Amount1'] - row1['Amount2']) < 0.01)  # Allow for minor differences in amounts
        ]

        # Append matched transactions to the matched_transactions DataFrame
        for index2, row2 in df1_time_match.iterrows():
            new_match = pd.DataFrame({
                'TransactionDateTime': [row1['TransactionDateTime']],
                'Amount2': [row1['Amount2']],
                'VehicleNumber2': [row1['VehicleNumber2']],
                'Amount1': [row2['Amount1']],
                'VehicleNumber1': [row2['VehicleNumber1']],
                'TransactionNo': [row1['TransactionNo']]
            })
            matched_transactions1 = pd.concat([matched_transactions1, new_match], ignore_index=True)
    
    return matched_transactions1



def main():
    st.title("Soliduz Lite Petronas Transaction Matching Application")

    # Upload files
    file1 = st.file_uploader("Upload the fleetcard CSV file from Petronas", type="csv")
    file2 = st.file_uploader("Upload the transaction CSV file from Soliduz Lite", type="csv")

    if file1 and file2:
        # Time buffer slider
        time_buffer_hours = st.slider("Select time buffer in hours", min_value=0, max_value=24, value=1, step=1)

        # Process files
        df1, df2, df1_filtered, df2_filtered = load_and_prepare_data(file1, file2)
        
        matched_transactions = match_transactions(df1_filtered, df2_filtered, time_buffer_hours)
        matched_transactions1 = match_transactions1(df2_filtered, df1_filtered, time_buffer_hours)

        # Add matched column and Receipt No. to df1
        df1['Matched'] = df1['TransactionDateTime'].isin(matched_transactions['TransactionDateTime'])
        df1 = df1.merge(matched_transactions[['TransactionDateTime', 'TransactionNo']], on='TransactionDateTime', how='left')

        # Add Receipt No. from df1 to df2 for matched transactions
        #df2_filtered = df2_filtered.merge(matched_transactions[['TransactionDateTime', 'ReceiptNo1']], on='TransactionDateTime', how='left')
        #df2_filtered.rename(columns={'ReceiptNo1': 'Receipt No.'}, inplace=True)
        
        df2['Matched'] = df2['TransactionDateTime'].isin(matched_transactions1['TransactionDateTime'])
        df2 = df2.merge(matched_transactions1[['TransactionDateTime']], on='TransactionDateTime', how='left')
        #df2.rename(columns={'ReceiptNo1': 'Receipt No.'}, inplace=True)
        
        
        # Display total transactions and matched transactions
        total_transactions_file1 = df1_filtered.shape[0]
        total_transactions_file2 = df2_filtered.shape[0]
        total_matched_transactions = matched_transactions.shape[0]
        st.write(f"Total transactions in Petronas file: {total_transactions_file1}")
        st.write(f"Total transactions in Soliduz Lite file: {total_transactions_file2}")
        st.write(f"Total matched transactions: {total_matched_transactions}")

        # Display the first file with matched column and mismatch reasons
        st.subheader("Petronas File with Matched Column, Mismatch Reasons, and TransactionNo")
        st.dataframe(df1)

        # Download button for updated file1
        st.download_button(
            label="Download Petronas File with TransactionNo",
            data=df1.to_csv(index=False).encode('utf-8'),
            file_name='PetronListing_with_Transaction_no.csv',
            mime='text/csv'
        )
        
        # Download button for updated file2
        st.download_button(
            label="Download Soliduz Lite File",
            data=df2.to_csv(index=False).encode('utf-8'),
            file_name='SoliduzListing_with_receipt_no.csv',
            mime='text/csv'
        )

if __name__ == "__main__":
    main()
