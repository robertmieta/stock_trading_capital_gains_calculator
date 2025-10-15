CommSec Capital Gains Calculator
================================

A minimal program with a GUI that calculates your capital gains for latest tax year provided.

Overview
========

- Run the program
- Select CSV's with buy and sell transactions
- It's built to work right out of the box with CommSec EOFY transaction summary CSV's
- It will also work for any CSV as long as it's in the following format (header names must be the same, except N/A which is ignored)

Code | N/A  | Date       | Type | Quantity | N/A | N/A | N/A | N/A | N/A | Total Value
-----|------|------------|------|----------|-----|-----|-----|-----|-----|--- 
NVDA | ...  | 15/10/2025 | Buy  | 200      | ... | ... | ... | ... | ... | 10000
NVDA | ...  | 16/10/2025 | Sell | 200      | ... | ... | ... | ... | ... | 12000

- Select **FIFO** if you want capital gains calculated on a First In First Out Buy/Sell basis
- Select **Minimize CGT** if you want the algorithm to minimize capital gains buy cancelling out highest buy price transactions preceding a sell transaction
- Check box **12 Month Rule** if you live in Australia or another country with the 50% reduction in capital gains after 12 months rule
- A CSV summary of capital gains and txt file containing a transaction summery for the calculations will be generated

Notes
=====

- For Windows download: **commsec_cgt_calculator.exe**
- For Mac download: **commsec_cgt_calculator.app**
- For Linux download: **commsec_cgt_calculator.bin**