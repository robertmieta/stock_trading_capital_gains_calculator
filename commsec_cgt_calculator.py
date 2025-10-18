# Install pyinstaller if you want to convert to .exe (run command in cmd: pip install pyinstaller)
# To compile to .exe run command in cmd: pyinstaller -F --noconsole "C:\Path\to\commsec_cgt_calculator.py"
# Or if the above doesn't work, try: python -m PyInstaller -F --noconsole "C:\Path\to\commsec_cgt_calculator.py"
# The .exe will be in \dist\

# The format of the CSV should be as follows (with exact same header names, except for N/A which is ignored and doesn't matter):
# Code | N/A |    Date    | Type | Quantity | N/A | N/A | N/A | N/A | N/A | Total Value
# NVDA | ... | 15/10/2025 |  Buy |   200    | ... | ... | ... | ... | ... | 10000
# NVDA | ... | 16/10/2025 | Sell |   200    | ... | ... | ... | ... | ... | 12000

# Code: The stock ticker code
# Date: the date in dd/mm/YYYY format
# Type: Buy or Sell
# Quantity: the number of stocks purchased
# Total Value: if 'Buy'  - the total cost of share purchase + brokerage fee (otherwise known as 'Base Cost')
#              if 'Sell' - the total cost of share purchase (not including brokerage fee)

import math
import tkinter as tk
from functools import reduce
from datetime import datetime, date
from typing import Any, Dict, List
from tkinter import ttk, filedialog, messagebox
from dateutil.relativedelta import relativedelta

def select_files():
    files = filedialog.askopenfilenames(
        title="Select CSV Files",
        filetypes=[("CSV Files", "*.csv")]
    )
    if files:
        file_list.config(state="normal")
        file_list.delete("1.0", tk.END)
        for f in files:
            file_list.insert(tk.END, f + "\n")
        file_list.config(state="disabled")
        global selected_files
        selected_files = files


# -------------------------------
# Data Processing Functions
# -------------------------------

def normalize_header(header: str) -> str:
    """Normalize header text by removing '($)', replacing '+' with '_',
    then lowercasing, trimming, and replacing spaces with underscores."""
    header = header.replace("($)", "").replace("+", "_")
    header = header.strip().lower().replace(" ", "_")
    return header


def convert_value(value: str) -> date | int | float | str:
    """Try to convert a string value to date, int, or float if possible, else keep as string."""
    # Convert to absolute value if required first by removing '-'
    value = value.strip().replace("-", "")
    if not value:
        raise ValueError("Invalid value in csv")
    elif value.isdigit():
        return int(value)
    elif '.' in value:
        return float(value)
    else:
        try:
            return datetime.strptime(value, "%d/%m/%Y").date()
        except ValueError:
            # Return string by default
            return value.lower()


def process_csv(csv_files: List[str] | None) -> Dict[str, List[Dict[str, Any]]]:
    """Process all CSV files in a given folder into a single dictionary with transaction data."""
    data_dict: Dict[str, List[Dict[str, Any]]] = {}

    for filename in csv_files:
        # If it's not a csv or is a previously exported result, ignore
        if not filename.lower().endswith(".csv") or "capital_gains_summary" in filename:
            continue

        with open(filename, newline='', encoding='utf-8-sig') as csvfile:
            # Skip rows without data (by looking for a decimal point)
            previous_row_data = csvfile.readline()
            row_data = csvfile.readline()
            while not '.' in row_data:
                previous_row_data = row_data
                row_data = csvfile.readline()

            # Get the header row as a string
            header_row: List[str]  = previous_row_data.strip().replace('"', '').replace("'", "").split(',')
            selected_indices: List[int] = [2, 3, 4, 10]  # Columns used (0 indexed)

            if len(header_row) < 11:
                messagebox.showinfo("Info", "Incorrect column format")
                return {}

            normalized_headers: List[str] = [normalize_header(header_row[i]) for i in selected_indices]

            # We only ever expect newlines at the end
            row: List[str]  = row_data.rstrip().replace('"', '').replace("'", "").split(',')

            # We stop when it's an empty line
            while len(row) == 11 and row[0]:
                stock_name: str = row[0].strip()
                transaction: Dict[str, Any] = {}

                # Base data conversion
                for idx, header_name in zip(selected_indices, normalized_headers):
                    val: date | int | float | str = convert_value(row[idx])
                    transaction[header_name] = val

                transaction["remaining_shares"] = transaction["quantity"]

                # Merge entry
                if stock_name not in data_dict:
                    data_dict[stock_name] = []
                data_dict[stock_name].append(transaction)

                # Read the next line
                row = csvfile.readline().rstrip().replace('"', '').replace("'", "").split(',')

    return data_dict


def sort_dict_ascending_by_date(data_dict: Dict[str, List[Dict[str, Any]]]) -> None:
    """Sort entries by date."""
    for stock_name, transactions in data_dict.items():
        if transactions:
            transactions.sort(key=lambda transaction: transaction.get("date"))


# -------------------------------
# Capital Gains Calculation
# -------------------------------

def calculate_latest_tax_year(data_dict: Dict[str, List[Dict[str, Any]]]) -> tuple[date | None, date | None]:
    """Determine the latest Australian tax year period based on the latest date in the data."""
    latest_date = None

    for transactions in data_dict.values():
        if transactions:
            # Get date of most recent Sell transaction
            for i in range(len(transactions) -1, -1, -1):
                if transactions[i].get("type") == "sell":
                    d = transactions[i].get("date")
                    if latest_date is None or d > latest_date:
                        latest_date = d
                    break

    if latest_date is None:
        messagebox.showinfo("Info", "No valid dates found in column")
        return None, None

    # Determine Australian tax year boundaries
    if latest_date.month >= 7:  # On or after July
        start_date = date(latest_date.year, 7, 1)
        end_date = date(latest_date.year + 1, 6, 30)
    else:  # Before July
        start_date = date(latest_date.year - 1, 7, 1)
        end_date = date(latest_date.year, 6, 30)

    return start_date, end_date


def filter_for_latest_tax_year(data_dict: Dict[str, List[Dict[str, Any]]], start_date: date, end_date: date) -> Dict[str, List[Dict[str, Any]]]:
    """Filter out stocks that don't have any sell transactions in the latest tax year."""
    filtered_dict: Dict[str, List[Dict[str, Any]]] = {}

    for stock_name, transactions in data_dict.items():
        # Iterate in reverse since it's in ascending order by date
        for i in range(len(transactions) - 1, -1, -1):
            if transactions[i].get("type") == "sell":
                d = transactions[i].get("date")
                # If it's within the tax year
                if start_date <= d <= end_date:
                    filtered_dict[stock_name] = transactions.copy()
                break

    return filtered_dict


def calculate_capital_gains(data_dict: Dict[str, List[Dict[str, Any]]], start_date: date, apply_twelve_month_rule: bool, minimize_capital_gains: bool) -> tuple[Dict[str, Any], str]:
    """Calculate total capital gains/losses for the latest tax year using FIFO matching."""
    gains_by_stock_twelve_month_split: Dict[str, Dict[str, float]] = {}
    transaction_records_str: str = ""

    for stock_name, transactions in data_dict.items():
        gains_by_stock_twelve_month_split[stock_name] = {"twelve_months": 0.0, "under_twelve_months": 0.0}
        i = 0

        while i < len(transactions):
            if transactions[i].get("type") != "sell":
                i += 1
                continue

            sell_transaction = transactions[i]
            remaining_to_sell = sell_transaction.get("remaining_shares")

            if minimize_capital_gains:
                # The buy transactions preceding a sell need to be re-sorted every time we look at a new sell transaction
                if apply_twelve_month_rule:
                    # Re-sort by minimum capital gains possible including the 12-month rule
                    transactions[0:i] = sorted(transactions[0:i], key=lambda transaction: ((sell_transaction.get("total_value") / sell_transaction.get("quantity")) - (transaction.get("total_value") / transaction.get("quantity"))) / 2 if (relativedelta(sell_transaction["date"], transaction["date"]).years >= 1 and (sell_transaction.get("total_value") / sell_transaction.get("quantity")) > (transaction.get("total_value") / transaction.get("quantity"))) else (sell_transaction.get("total_value") / sell_transaction.get("quantity")) - (transaction.get("total_value") / transaction.get("quantity")))
                else:
                    # Re-sort all buys preceding a sell by highest price per stock unit
                    transactions[0:i] = sorted(transactions[0:i], key=lambda transaction: (transaction.get("total_value") / transaction.get("quantity")), reverse=True)

            if sell_transaction.get("date") >= start_date:
                transaction_records_str += f"\n{remaining_to_sell} shares of {stock_name} sold on {sell_transaction['date'].strftime('%d/%m/%Y')} for ${sell_transaction['total_value']:.2f} (brokerage fee not included).\n"

            j = 0
            while j < i and remaining_to_sell > 0:
                if transactions[j].get("type") != "buy" or transactions[j].get("remaining_shares") <= 0:
                    j += 1
                    continue

                buy_transaction = transactions[j]
                share_diff = buy_transaction["remaining_shares"] - remaining_to_sell
                twelve_months_or_more: bool = relativedelta(sell_transaction["date"], buy_transaction["date"]).years >= 1

                if share_diff < 0:
                    share_diff = abs(share_diff)
                    # Sell consumes more than this buy transaction
                    # Since we're not adding capital gains outside this tax year
                    if sell_transaction.get("date") >= start_date:
                        # Round purchase price down to two decimal places, and sell price up two decimal places
                        # and result up to nearest two decimal places to give us the most capital gain
                        # aka worst tax outcome for us rounding-wise to prevent any tax complaints from ATO :'(
                        partial_purchase_price: float = math.floor(buy_transaction.get("remaining_shares") * 100 * buy_transaction.get("total_value") / buy_transaction.get("quantity")) / 100.0
                        partial_sell_price: float = math.ceil(buy_transaction.get("remaining_shares") * 100 * sell_transaction.get("total_value") / sell_transaction.get("quantity")) / 100.0
                        capital_gain: float = math.ceil((partial_sell_price - partial_purchase_price) * 100) / 100.0

                        transaction_records_str += f"  {buy_transaction['remaining_shares']} shares of which were bought on {buy_transaction['date'].strftime('%d/%m/%Y')} for "
                        if buy_transaction["remaining_shares"] != buy_transaction["quantity"]:
                            transaction_records_str += f"approx ${partial_purchase_price:.2f} (fractional cost including brokerage fee)."
                        else:
                            transaction_records_str += f"${partial_purchase_price:.2f} (cost including brokerage fee)."

                        if capital_gain >= 0:
                            transaction_records_str += f" Capital Gain: ${capital_gain:.2f}"
                            if twelve_months_or_more:
                                transaction_records_str += f" (or ${(capital_gain / 2):.2f} after 12 month 50% discount for tax purposes)\n"
                            else:
                                transaction_records_str += "\n"
                        else:
                            transaction_records_str += f" Capital Loss: -${abs(capital_gain):.2f}\n"

                        if twelve_months_or_more:
                            gains_by_stock_twelve_month_split[stock_name]["twelve_months"] += capital_gain
                        else:
                            gains_by_stock_twelve_month_split[stock_name]["under_twelve_months"] += capital_gain

                    remaining_to_sell = share_diff
                    # Remove the buy transaction from the list
                    transactions.pop(j)
                    i -= 1
                else:
                    # Buy covers entire sell quantity
                    # Since we're not adding capital gains outside this tax year
                    if sell_transaction.get("date") >= start_date:
                        # Round purchase price down to two decimal places, and sell price up two decimal places
                        # and result up to nearest two decimal places to give us the most capital gain
                        # aka worst tax outcome for us rounding-wise to prevent any tax complaints from ATO :'(
                        partial_purchase_price: float = math.floor(remaining_to_sell * 100 * buy_transaction.get("total_value") / buy_transaction.get("quantity")) / 100.0
                        partial_sell_price: float = math.ceil(remaining_to_sell * 100 * sell_transaction.get("total_value") / sell_transaction.get("quantity")) / 100.0
                        capital_gain: float = math.ceil((partial_sell_price - partial_purchase_price) * 100) / 100.0

                        transaction_records_str += f"  {remaining_to_sell} shares of which were bought on {buy_transaction['date'].strftime('%d/%m/%Y')} for "
                        if buy_transaction["remaining_shares"] != buy_transaction["quantity"] or buy_transaction["remaining_shares"] != remaining_to_sell:
                            transaction_records_str += f"approx ${partial_purchase_price:.2f} (fractional cost including brokerage fee)."
                        else:
                            transaction_records_str += f"${partial_purchase_price:.2f} (cost including brokerage fee)."

                        if capital_gain >= 0:
                            transaction_records_str += f" Capital Gain: ${capital_gain:.2f}"
                            if twelve_months_or_more:
                                transaction_records_str += f" (or ${(capital_gain / 2):.2f} after 12 month 50% discount for tax purposes)\n"
                            else:
                                transaction_records_str += "\n"
                        else:
                            transaction_records_str += f" Capital Loss: -${abs(capital_gain):.2f}\n"

                        if twelve_months_or_more:
                            gains_by_stock_twelve_month_split[stock_name]["twelve_months"] += capital_gain
                        else:
                            gains_by_stock_twelve_month_split[stock_name]["under_twelve_months"] += capital_gain

                    remaining_to_sell = 0
                    transactions[j]["remaining_shares"] = share_diff
                    # Remove the sell transaction from the list
                    transactions.pop(i)
                    if share_diff == 0:
                        # Remove the buy transaction from the list
                        transactions.pop(j)
                        i -= 1

            if remaining_to_sell > 0:
                messagebox.showinfo("Info", f"You have somehow sold more shares than you own in {stock_name}. Remaining unsold shares: {remaining_to_sell}")
                return {}, ""

    return gains_by_stock_twelve_month_split, transaction_records_str


def calculate_total_capital_gains(gains_by_stock_twelve_month_split: Dict[str, Dict[str, float]] , apply_twelve_month_rule: bool) -> tuple[Dict[str, float], float]:
    """Calculate the total capital gains for the latest tax year."""
    # Total for shares held for longer than 12 months
    more_than_twelve_month_total: float = reduce(lambda summed_value, stock: summed_value + stock["twelve_months"], gains_by_stock_twelve_month_split.values(), 0)
    if apply_twelve_month_rule:
        more_than_twelve_month_total /= 2

    # Total for shares held less than 12 months
    less_than_twelve_month_total: float = reduce(lambda summed_value, stock: summed_value + stock["under_twelve_months"], gains_by_stock_twelve_month_split.values(), 0)

    # Combined for the sake of each stock
    combined_gains_per_stock: Dict[str, float] = {k: v["twelve_months"] + v["under_twelve_months"] for k, v in gains_by_stock_twelve_month_split.items()}

    return combined_gains_per_stock, more_than_twelve_month_total + less_than_twelve_month_total


def shares_you_still_own(transactions_dict: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Use this as a verification step, to compare to your actual portfolio."""
    current_portfolio = {}

    for stock_name, transactions in transactions_dict.items():
        current_portfolio[stock_name] = 0
        for transaction in transactions:
            if transaction.get("type") == "buy": # This is technically redundant but I'm paranoid
                current_portfolio[stock_name] += transaction.get("remaining_shares")

    return current_portfolio


def print_results(gains_by_stock_total: Dict[str, Any], total_gains: float, current_portfolio: Dict[str, Any], transactions_str: str, start_date: date, end_date: date, twelve_month_rule: bool) -> None:
    """Print out the results to console and CSV."""

    ### Store Summary to txt file ###
    txt_content_str = "Use the below to verify it matches your portfolio.\n"
    txt_content_str += "Current portfolio - number of shares held\n"
    txt_content_str += "(only displaying stocks sold in last financial year):\n"
    for stock_name, num_shares in current_portfolio.items():
        txt_content_str += f"    {stock_name}: {num_shares}\n"

    txt_content_str += f"\nTransactions relevant to tax year: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}\n"
    txt_content_str += transactions_str

    txt_content_str += "\nCapital Gains per Stock Breakdown:\n"
    for stock_name, capital_gain in gains_by_stock_total.items():
        if capital_gain < 0:
            txt_content_str += f"    {stock_name}: -${abs(capital_gain):.2f}\n"
        else:
            txt_content_str += f"    {stock_name}: ${capital_gain:.2f}\n"

    twelve_month_rule_str = ""
    total_gains_str = ""

    if twelve_month_rule:
        twelve_month_rule_str = " (includes 12 month 50% CGT reductions)"
    if total_gains < 0:
        total_gains_str = f"-${abs(total_gains):.2f}"
    else:
        total_gains_str = f"${total_gains:.2f}"

    txt_content_str += f"\nTotal Capital Gains (for tax purposes): " + total_gains_str + twelve_month_rule_str

    ### Store tabular data to CSV file ##
    csv_content_str = "Stock Name,Capital Gain ($)\n"
    for stock, gain in gains_by_stock_total.items():
        csv_content_str += stock + "," + f"{gain:.2f}\n"

    # Add the total sum in last row
    csv_content_str += "\n"
    csv_content_str += "Total," + f"{total_gains:.2f}"

    # Dump to txt file
    txt_filename = f"capital_gains_summary_{start_date.strftime('%d%m%Y')}-{end_date.strftime('%d%m%Y')}.txt"
    with open(txt_filename, mode="w", newline="", encoding="utf-8") as file:
        file.write(txt_content_str)

    # Dump to CSV file
    csv_filename = f"capital_gains_summary_{start_date.strftime('%d%m%Y')}-{end_date.strftime('%d%m%Y')}.csv"
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        file.write(csv_content_str)

    # Let the user know where it is
    messagebox.showinfo("Info", f"Calculation transaction summary exported to: {txt_filename}\nCapital gains tabular summary exported to: {csv_filename}")


# -------------------------------
# Main Execution
# -------------------------------

def calculate():
    ### Get user input from GUI ###
    csv_files = selected_files if selected_files else []

    if not csv_files:
        messagebox.showinfo("Info", "No CSV files selected")
        return

    # Instead of FIFO approach, try to minimize the capital gains for tax
    minimize_capital_gains_tax = strategy_var.get() == "Minimize CGT"

    # Shares held longer than 12 months are subject to 50% relief on capital gains tax
    twelve_month_rule = rule_var.get()

    # Convert CSV files in to a Dict of transactions and sord by date
    data: Dict[str, List[Dict[str, Any]]] = process_csv(csv_files)
    
    if not data:
        return

    sort_dict_ascending_by_date(data)

    # Find the latest Financial Year period from all CSV's
    start, end = calculate_latest_tax_year(data)

    if not start or not end:
        return

    # Remove any stocks from the dict that don't have a sell transaction in the latest found financial year
    filtered_data: Dict[str, List[Dict[str, Any]]] = filter_for_latest_tax_year(data, start, end)

    # If there's any capital gains calculations to do
    if filtered_data:
        gains_per_stock_dict, transaction_records = calculate_capital_gains(filtered_data, start, twelve_month_rule, minimize_capital_gains_tax)
        total_gains_per_stock_dict, total_capital_gain = calculate_total_capital_gains(gains_per_stock_dict, twelve_month_rule)
        current_holdings = shares_you_still_own(filtered_data)

        # Export tabular data to a CSV file and calculation step summary to a txt file
        print_results(total_gains_per_stock_dict, total_capital_gain, current_holdings, transaction_records, start, end, twelve_month_rule)
    else:
        messagebox.showinfo("Info", "No Capital gains to report for this financial year.")


# --- Main window setup ---
root = tk.Tk()
root.title("CommSec CGT Calculator")
root.geometry("500x165")
root.resizable(False, False)

# --- Dark VS Code–like colors ---
BG_COLOR = "#1e1e1e"
PANEL_BG = "#252526"
FG_COLOR = "#d4d4d4"
ACCENT = "#007acc"
BORDER = "#333333"
BTN_BG = "#2d2d2d"
BTN_HOVER = "#3a3d41"
BTN_ACTIVE = "#005f9e"

root.configure(bg=BG_COLOR)

# --- ttk Style setup ---
style = ttk.Style()
style.theme_use("clam")

# Frame style
style.configure("TFrame", background=BG_COLOR)

# Radiobuttons and checkboxes
style.configure(
    "TRadiobutton",
    background=BG_COLOR,
    foreground=FG_COLOR,
)
style.configure(
    "TCheckbutton",
    background=BG_COLOR,
    foreground=FG_COLOR,
)

# Button style
style.configure(
    "TButton",
    background=BTN_BG,
    foreground=FG_COLOR,
    bordercolor=BORDER,
    focusthickness=3,
    padding=(10, 5),
    relief="flat"
)
style.map(
    "TButton",
    background=[("active", BTN_HOVER), ("pressed", BTN_ACTIVE)],
    relief=[("pressed", "sunken")],
    foreground=[("active", FG_COLOR)]
)

# --- Variables ---
selected_files = []
strategy_var = tk.StringVar(value="FIFO")
rule_var = tk.BooleanVar(value=False)

# --- Layout frames ---
top_frame = ttk.Frame(root)
top_frame.pack(pady=8)

bottom_frame = ttk.Frame(root)
bottom_frame.pack(pady=4)

# --- Scrollbars ---
scroll_y = ttk.Scrollbar(top_frame, orient="vertical")
scroll_x = ttk.Scrollbar(top_frame, orient="horizontal")

# --- Text box ---
file_list = tk.Text(
    top_frame,
    width=40,
    height=2,
    wrap="none",
    bg=PANEL_BG,
    fg=FG_COLOR,
    insertbackground=FG_COLOR,
    xscrollcommand=scroll_x.set,
    yscrollcommand=scroll_y.set,
    state="disabled",
    relief="flat",
    highlightbackground=BORDER,
    highlightthickness=1,
    bd=0
)
file_list.grid(row=0, column=0, padx=(10, 0))

scroll_y.config(command=file_list.yview)
scroll_y.grid(row=0, column=1, sticky="ns")

scroll_x.config(command=file_list.xview)
scroll_x.grid(row=1, column=0, sticky="ew")

# --- Select Files button ---
select_btn = ttk.Button(top_frame, text="Select Files", command=select_files)
select_btn.grid(row=0, column=2, padx=(10, 8))

# --- Radio buttons and checkbox ---
fifo_radio = ttk.Radiobutton(bottom_frame, text="FIFO", variable=strategy_var, value="FIFO")
min_radio = ttk.Radiobutton(bottom_frame, text="Minimize CGT", variable=strategy_var, value="Minimize CGT")
fifo_radio.pack(side="left", padx=5)
min_radio.pack(side="left", padx=5)

rule_check = ttk.Checkbutton(bottom_frame, text="12 Month Rule", variable=rule_var)
rule_check.pack(side="left", padx=5)

# --- Calculate button ---
calculate_btn = ttk.Button(root, text="Calculate", command=calculate)
calculate_btn.pack(pady=6)

# --- Rounded corners & hover highlight ---
def on_enter(e):
    e.widget.configure(style="Hover.TButton")
def on_leave(e):
    e.widget.configure(style="TButton")

style.configure(
    "Hover.TButton",
    background=BTN_HOVER,
    relief="flat",
    bordercolor=ACCENT,
)

for btn in (select_btn, calculate_btn):
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)

root.mainloop()
