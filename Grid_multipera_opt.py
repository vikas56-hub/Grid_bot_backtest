import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkcalendar import DateEntry
import pandas as pd
import ccxt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates
import mplcursors


def grid_bot_strategy(df, start_date, end_date, initial_price, lower_limit, upper_limit,
                     grid_levels, initial_capital, leverage, lower_stop_loss, upper_stop_loss,
                     stop_loss_enabled, progress_callback=None):
    """
    Executes the grid bot strategy over historical data.

    Parameters:
    - df: DataFrame containing historical OHLCV data.
    - start_date: Start date for the backtest.
    - end_date: End date for the backtest.
    - initial_price: Initial price for setting grid levels.
    - lower_limit: Lower price limit for grid levels.
    - upper_limit: Upper price limit for grid levels.
    - grid_levels: Number of grid levels.
    - initial_capital: Starting capital.
    - leverage: Leverage multiplier.
    - lower_stop_loss: Lower stop-loss price.
    - upper_stop_loss: Upper stop-loss price.
    - stop_loss_enabled: Boolean indicating if stop-loss is enabled.
    - progress_callback: Function to update progress.

    Returns:
    - trade_log_df: DataFrame containing the trade log.
    - total_pnl: Total Profit and Loss.
    - mtm_value: Mark-to-Market value of open positions.
    - total_mtm: Total MTM including PnL and costs.
    - total_cost: Total transaction costs.
    - roi: Return on Investment.
    - open_trades: Number of open trades.
    - stop_loss_triggered: Boolean indicating if SL was triggered.
    - stop_loss_trigger_date: Date when SL was triggered.
    - stop_loss_trigger_price: Price at which SL was triggered.
    """
    df['Open time'] = pd.to_datetime(df['Open time'])
    df = df[(df['Open time'] >= pd.to_datetime(start_date)) & (df['Open time'] <= pd.to_datetime(end_date))]
    df = df.sort_values(by='Open time').reset_index(drop=True)

    grid_range = (upper_limit - lower_limit) / grid_levels
    buy_levels = [initial_price - i * grid_range for i in range(1, grid_levels + 1)]
    sell_levels = [initial_price + i * grid_range for i in range(1, grid_levels + 1)]

    trade_log = []
    total_pnl = 0
    total_cost = 0
    working_capital = initial_capital * leverage

    open_positions = []
    stop_loss_triggered = False
    stop_loss_trigger_date = None
    stop_loss_trigger_price = None
    mtm_value = 0

    total_iterations = len(df)
    iteration = 0

    for _, row in df.iterrows():
        iteration += 1
        if progress_callback:
            progress_callback(iteration / total_iterations * 100)
        price = row['Close']
        date = row['Open time']

        # Monitor stop-loss triggers
        if stop_loss_enabled:
            if price >= upper_stop_loss:
                stop_loss_triggered = True
                stop_loss_trigger_date = date
                stop_loss_trigger_price = price

                # Close all open positions at the SL price
                for pos in open_positions:
                    if pos['type'] == 'Buy':
                        pnl_current = (stop_loss_trigger_price - pos['price']) * pos['quantity']
                        transaction_cost = 0.0002 * stop_loss_trigger_price * pos['quantity']
                        total_pnl += pnl_current
                        total_cost += transaction_cost
                        working_capital += pnl_current
                        trade_log.append([date, stop_loss_trigger_price, 'Sell (SL Closing)', pos['price'], stop_loss_trigger_price,
                                         round(pnl_current, 3), pos['quantity'], round(transaction_cost, 3)])
                    elif pos['type'] == 'Sell':
                        pnl_current = (pos['price'] - stop_loss_trigger_price) * pos['quantity']
                        transaction_cost = 0.0002 * stop_loss_trigger_price * pos['quantity']
                        total_pnl += pnl_current
                        total_cost += transaction_cost
                        working_capital += pnl_current
                        trade_log.append([date, stop_loss_trigger_price, 'Buy (SL Closing)', stop_loss_trigger_price, pos['price'],
                                         round(pnl_current, 3), pos['quantity'], round(transaction_cost, 3)])
                open_positions = []  # Clear all positions
                break  # Stop trading if upper stop-loss is hit

            if price <= lower_stop_loss:
                stop_loss_triggered = True
                stop_loss_trigger_date = date
                stop_loss_trigger_price = price

                # Close all open positions at the SL price
                for pos in open_positions:
                    if pos['type'] == 'Buy':
                        pnl_current = (stop_loss_trigger_price - pos['price']) * pos['quantity']
                        transaction_cost = 0.0002 * stop_loss_trigger_price * pos['quantity']
                        total_pnl += pnl_current
                        total_cost += transaction_cost
                        working_capital += pnl_current
                        trade_log.append([date, stop_loss_trigger_price, 'Sell (SL Closing)', pos['price'], stop_loss_trigger_price,
                                         round(pnl_current, 3), pos['quantity'], round(transaction_cost, 3)])
                    elif pos['type'] == 'Sell':
                        pnl_current = (pos['price'] - stop_loss_trigger_price) * pos['quantity']
                        transaction_cost = 0.0002 * stop_loss_trigger_price * pos['quantity']
                        total_pnl += pnl_current
                        total_cost += transaction_cost
                        working_capital += pnl_current
                        trade_log.append([date, stop_loss_trigger_price, 'Buy (SL Closing)', stop_loss_trigger_price, pos['price'],
                                         round(pnl_current, 3), pos['quantity'], round(transaction_cost, 3)])
                open_positions = []  # Clear all positions
                break  # Stop trading if lower stop-loss is hit

        # Manage existing positions
        for pos in open_positions[:]:
            if pos['type'] == 'Buy' and price >= pos['target_sell_level']:
                pnl_current = (price - pos['price']) * pos['quantity']
                transaction_cost = 0.0002 * price * pos['quantity']
                total_pnl += pnl_current
                total_cost += transaction_cost
                working_capital += pnl_current
                trade_log.append([date, price, 'Sell (Closing)', pos['price'], pos['target_sell_level'],
                                 round(pnl_current, 3), pos['quantity'], round(transaction_cost, 3)])
                open_positions.remove(pos)

            elif pos['type'] == 'Sell' and price <= pos['target_buy_level']:
                pnl_current = (pos['price'] - price) * pos['quantity']
                transaction_cost = 0.0002 * price * pos['quantity']
                total_pnl += pnl_current
                total_cost += transaction_cost
                working_capital += pnl_current
                trade_log.append([date, price, 'Buy (Closing)', pos['target_buy_level'], pos['price'],
                                 round(pnl_current, 3), pos['quantity'], round(transaction_cost, 3)])
                open_positions.remove(pos)

        # Grid strategy logic (Buy/Sell levels management)
        eligible_buy_levels = [level for level in buy_levels if price <= level]
        eligible_sell_levels = [level for level in sell_levels if price >= level]

        if price < initial_price and eligible_buy_levels:
            for buy_level in eligible_buy_levels:
                if not any(p['price'] == buy_level for p in open_positions):
                    quantity = working_capital / (price * grid_levels)
                    target_sell_level = buy_level + grid_range
                    transaction_cost = 0.0002 * price * quantity
                    total_cost += transaction_cost
                    open_positions.append({'type': 'Buy', 'price': buy_level, 'target_sell_level': target_sell_level,
                                           'quantity': round(quantity, 8)})
                    trade_log.append([date, price, 'Buy (Opening)', buy_level, target_sell_level, 0,
                                      round(quantity, 8), round(transaction_cost, 3)])

        elif price > initial_price and eligible_sell_levels:
            for sell_level in eligible_sell_levels:
                if not any(p['price'] == sell_level for p in open_positions):
                    quantity = working_capital / (price * grid_levels)
                    target_buy_level = sell_level - grid_range
                    transaction_cost = 0.0002 * price * quantity
                    total_cost += transaction_cost
                    open_positions.append({'type': 'Sell', 'price': sell_level, 'target_buy_level': target_buy_level,
                                           'quantity': round(quantity, 8)})
                    trade_log.append([date, price, 'Sell (Opening)', target_buy_level, sell_level, 0,
                                      round(quantity, 8), round(transaction_cost, 3)])

    # Calculate MTM value
    if stop_loss_triggered:
        mtm_price = stop_loss_trigger_price
    elif not df.empty:
        mtm_price = df.iloc[-1]['Close']
    else:
        mtm_price = initial_price

    for pos in open_positions:
        if pos['type'] == 'Buy':
            mtm_value += (mtm_price - pos['price']) * pos['quantity']
        elif pos['type'] == 'Sell':
            mtm_value += (pos['price'] - mtm_price) * pos['quantity']

    total_mtm = total_pnl + mtm_value - total_cost
    roi = (total_mtm) / initial_capital * 100

    # Create DataFrame for the trade log
    trade_log_df = pd.DataFrame(trade_log, columns=['Date', 'Price', 'B/S', 'Entry_Level', 'Target_Level',
                                                    'PNL_Current', 'Quantity', 'Transaction_Cost'])
    trade_log_df.insert(0, 'Seq', range(1, len(trade_log_df) + 1))
    trade_log_df['Cumulative_PNL'] = trade_log_df['PNL_Current'].cumsum()
    trade_log_df['Cumulative_Cost'] = trade_log_df['Transaction_Cost'].cumsum()
    trade_log_df['Net_PNL'] = trade_log_df['Cumulative_PNL'] - trade_log_df['Cumulative_Cost']

    return trade_log_df, total_pnl, mtm_value, total_mtm, total_cost, roi, len(open_positions), \
           stop_loss_triggered, stop_loss_trigger_date, stop_loss_trigger_price


class GridBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Grid Bot Strategy")
        self.root.geometry("1600x900")
        self.root.configure(bg='#2c3e50')

        title_font = ("Arial", 14, "bold")
        label_font = ("Arial", 12)
        self.summary_font = ("Arial", 12, "bold")
        entry_bg = "#1e272e"
        entry_fg = "#ecf0f1"
        entry_width = 12

        # Main frames for layout
        self.top_frame = tk.Frame(root, bg='#2c3e50')
        self.top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.summary_frame = tk.Frame(self.top_frame, bg='#2c3e50', bd=2, relief='ridge')
        self.summary_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.optimized_summary_frame = tk.Frame(self.top_frame, bg='#34495e', bd=2, relief='ridge')
        self.optimized_summary_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

        self.params_frame = tk.Frame(root, bg='#34495e', bd=2, relief='ridge')
        self.params_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Parameters Frame
        tk.Label(self.params_frame, text="Parameters", font=title_font, fg="#ecf0f1", bg="#34495e").grid(row=0, column=0, columnspan=5, pady=10)

        # Exchange Selection
        tk.Label(self.params_frame, text="Exchange:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        exchange_list = ['binance', 'kraken', 'bitfinex', 'bitstamp', 'coinbasepro']
        self.exchange_entry = ttk.Combobox(self.params_frame, values=exchange_list, width=entry_width)
        self.exchange_entry.set('binance')
        self.exchange_entry.grid(row=1, column=1, padx=5, pady=5)
        self.exchange_entry.bind("<<ComboboxSelected>>", self.update_symbols)

        # Symbol Selection
        tk.Label(self.params_frame, text="Symbol:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.symbol_entry = ttk.Combobox(self.params_frame, values=['BTC/USDT'], width=entry_width)
        self.symbol_entry.set('BTC/USDT')
        self.symbol_entry.grid(row=2, column=1, padx=5, pady=5)

        # Time Frame Selection
        tk.Label(self.params_frame, text="Time Frame:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        timeframe_list = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        self.timeframe_entry = ttk.Combobox(self.params_frame, values=timeframe_list, width=entry_width)
        self.timeframe_entry.set('1h')
        self.timeframe_entry.grid(row=3, column=1, padx=5, pady=5)

        # Start Date Selection
        tk.Label(self.params_frame, text="Start Date:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=4, column=0, sticky='e', padx=5, pady=5)
        self.start_date = DateEntry(self.params_frame, date_pattern='yyyy-mm-dd', background=entry_bg, foreground=entry_fg, width=entry_width)
        self.start_date.grid(row=4, column=1, padx=5, pady=5)
        self.start_date.bind("<<DateEntrySelected>>", self.update_initial_price)

        # End Date Selection
        tk.Label(self.params_frame, text="End Date:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.end_date = DateEntry(self.params_frame, date_pattern='yyyy-mm-dd', background=entry_bg, foreground=entry_fg, width=entry_width)
        self.end_date.grid(row=5, column=1, padx=5, pady=5)

        # Initial Price Selection
        tk.Label(self.params_frame, text="Initial Price:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        self.initial_price_mode = tk.StringVar(value="absolute")
        self.initial_price_absolute = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.initial_price_absolute.grid(row=6, column=1, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Absolute", variable=self.initial_price_mode, value="absolute", bg="#34495e", fg="#ecf0f1").grid(row=6, column=2, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="First Value", variable=self.initial_price_mode, value="first_value", bg="#34495e", fg="#ecf0f1").grid(row=6, column=3, padx=5, pady=5)

        # Lower Limit
        tk.Label(self.params_frame, text="Lower Limit:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=7, column=0, sticky='e', padx=5, pady=5)
        self.lower_limit_mode = tk.StringVar(value="percentage")
        self.lower_limit_absolute = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.lower_limit_absolute.grid(row=7, column=1, padx=5, pady=5)
        self.lower_limit_percentage = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.lower_limit_percentage.insert(0, '15%')
        self.lower_limit_percentage.grid(row=7, column=2, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Absolute", variable=self.lower_limit_mode, value="absolute", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=7, column=3, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Percentage", variable=self.lower_limit_mode, value="percentage", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=7, column=4, padx=5, pady=5)

        # Upper Limit
        tk.Label(self.params_frame, text="Upper Limit:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=8, column=0, sticky='e', padx=5, pady=5)
        self.upper_limit_mode = tk.StringVar(value="percentage")
        self.upper_limit_absolute = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.upper_limit_absolute.grid(row=8, column=1, padx=5, pady=5)
        self.upper_limit_percentage = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.upper_limit_percentage.insert(0, '15%')
        self.upper_limit_percentage.grid(row=8, column=2, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Absolute", variable=self.upper_limit_mode, value="absolute", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=8, column=3, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Percentage", variable=self.upper_limit_mode, value="percentage", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=8, column=4, padx=5, pady=5)

        # Lower Stop Loss
        tk.Label(self.params_frame, text="Lower Stop Loss:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=9, column=0, sticky='e', padx=5, pady=5)
        self.lower_stop_loss_mode = tk.StringVar(value="percentage")
        self.lower_stop_loss_absolute = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.lower_stop_loss_absolute.grid(row=9, column=1, padx=5, pady=5)
        self.lower_stop_loss_percentage = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.lower_stop_loss_percentage.insert(0, '20%')
        self.lower_stop_loss_percentage.grid(row=9, column=2, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Absolute", variable=self.lower_stop_loss_mode, value="absolute", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=9, column=3, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Percentage", variable=self.lower_stop_loss_mode, value="percentage", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=9, column=4, padx=5, pady=5)

        # Upper Stop Loss
        tk.Label(self.params_frame, text="Upper Stop Loss:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=10, column=0, sticky='e', padx=5, pady=5)
        self.upper_stop_loss_mode = tk.StringVar(value="percentage")
        self.upper_stop_loss_absolute = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.upper_stop_loss_absolute.grid(row=10, column=1, padx=5, pady=5)
        self.upper_stop_loss_percentage = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.upper_stop_loss_percentage.insert(0, '20%')
        self.upper_stop_loss_percentage.grid(row=10, column=2, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Absolute", variable=self.upper_stop_loss_mode, value="absolute", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=10, column=3, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Percentage", variable=self.upper_stop_loss_mode, value="percentage", bg="#34495e", fg="#ecf0f1", command=self.update_limits).grid(row=10, column=4, padx=5, pady=5)

        # Stop Loss Enable/Disable
        tk.Label(self.params_frame, text="Stop Loss Enabled:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=11, column=0, sticky='e', padx=5, pady=5)
        self.stop_loss_enabled = tk.BooleanVar(value=True)
        self.stop_loss_enabled_checkbox = tk.Checkbutton(self.params_frame, variable=self.stop_loss_enabled, bg="#34495e")
        self.stop_loss_enabled_checkbox.grid(row=11, column=1, padx=5, pady=5)

        # Grid Levels
        tk.Label(self.params_frame, text="Grid Levels:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=12, column=0, sticky='e', padx=5, pady=5)
        self.grid_levels_mode = tk.StringVar(value="absolute")
        self.grid_levels_absolute = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.grid_levels_absolute.insert(0, '30')
        self.grid_levels_absolute.grid(row=12, column=1, padx=5, pady=5)
        self.grid_levels_percentage = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.grid_levels_percentage.grid(row=12, column=2, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Absolute", variable=self.grid_levels_mode, value="absolute", bg="#34495e", fg="#ecf0f1", command=self.update_grid_levels).grid(row=12, column=3, padx=5, pady=5)
        tk.Radiobutton(self.params_frame, text="Percentage", variable=self.grid_levels_mode, value="percentage", bg="#34495e", fg="#ecf0f1", command=self.update_grid_levels).grid(row=12, column=4, padx=5, pady=5)

        # Initial Capital
        tk.Label(self.params_frame, text="Initial Capital:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=13, column=0, sticky='e', padx=5, pady=5)
        self.initial_capital = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.initial_capital.insert(0, '75000')
        self.initial_capital.grid(row=13, column=1, padx=5, pady=5)

        # Leverage
        tk.Label(self.params_frame, text="Leverage:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=14, column=0, sticky='e', padx=5, pady=5)
        self.leverage = tk.Entry(self.params_frame, bg=entry_bg, fg=entry_fg, width=entry_width)
        self.leverage.insert(0, '20')
        self.leverage.grid(row=14, column=1, padx=5, pady=5)

        # Status Label
        self.status_frame = tk.Frame(root, bg='#2c3e50')
        self.status_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        self.status_label = tk.Label(self.status_frame, text="", font=label_font, fg="#ecf0f1", bg="#2c3e50")
        self.status_label.pack(side=tk.LEFT, pady=5)

        # Progress Bar with Percentage
        self.progress_frame = tk.Frame(root, bg='#2c3e50')
        self.progress_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate', length=400)
        self.progress_bar.pack(side=tk.LEFT, padx=5, pady=5)
        self.progress_percentage = tk.Label(self.progress_frame, text="0%", font=label_font, fg="#ecf0f1", bg="#2c3e50")
        self.progress_percentage.pack(side=tk.LEFT, padx=5, pady=5)

        # Execution Buttons
        self.buttons_frame = tk.Frame(root, bg='#2c3e50')
        self.buttons_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.run_button = tk.Button(self.buttons_frame, text="Run Strategy", command=self.run_strategy_thread, bg="#27ae60", fg="#ecf0f1", font=("Arial", 12, "bold"), bd=2, relief='raised', padx=10, pady=5)
        self.run_button.pack(side=tk.LEFT, padx=10)

        self.optimize_button = tk.Button(self.buttons_frame, text="Optimize", command=self.optimize_strategy_thread, bg="#3498db", fg="#ecf0f1", font=("Arial", 12, "bold"), bd=2, relief='raised', padx=10, pady=5)
        self.optimize_button.pack(side=tk.LEFT, padx=10)

        self.plot_button = tk.Button(self.buttons_frame, text="Show Trade Plot", command=self.show_trade_plot, bg="#2980b9", fg="#ecf0f1", font=("Arial", 12, "bold"), bd=2, relief='raised', padx=10, pady=5)
        self.plot_button.pack(side=tk.LEFT, padx=10)

        # Equity Curve Button
        self.equity_button = tk.Button(self.buttons_frame, text="Show Equity Curve", command=self.show_equity_curve, bg="#9b59b6", fg="#ecf0f1", font=("Arial", 12, "bold"), bd=2, relief='raised', padx=10, pady=5)
        self.equity_button.pack(side=tk.LEFT, padx=10)

        # Summary Labels
        self.summary_label = tk.Label(self.summary_frame, text="Summary", font=("Arial", 16, "bold"), fg="#ecf0f1", bg="#2c3e50")
        self.summary_label.grid(row=0, column=0, columnspan=2, pady=10)

        tk.Label(self.summary_frame, text="Total Current PNL:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.total_pnl_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.total_pnl_label.grid(row=1, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="MTM Value of Open Positions:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.mtm_value_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.mtm_value_label.grid(row=2, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="Number of Total Trades:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.total_trades_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.total_trades_label.grid(row=3, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="Open Trades:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=4, column=0, sticky='e', padx=5, pady=5)
        self.open_trades_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.open_trades_label.grid(row=4, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="Total Transaction Costs:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.total_cost_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.total_cost_label.grid(row=5, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="Net PNL After Costs:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        self.net_pnl_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.net_pnl_label.grid(row=6, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="ROI:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=7, column=0, sticky='e', padx=5, pady=5)
        self.roi_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.roi_label.grid(row=7, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="Stop Loss Triggered:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=8, column=0, sticky='e', padx=5, pady=5)
        self.stop_loss_triggered_label = tk.Label(self.summary_frame, text="No", font=self.summary_font, fg="#2ecc71", bg="#2c3e50")
        self.stop_loss_triggered_label.grid(row=8, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="SL Trigger Date:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=9, column=0, sticky='e', padx=5, pady=5)
        self.stop_loss_trigger_date_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.stop_loss_trigger_date_label.grid(row=9, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.summary_frame, text="SL Trigger Price:", font=label_font, fg="#ecf0f1", bg="#2c3e50").grid(row=10, column=0, sticky='e', padx=5, pady=5)
        self.stop_loss_trigger_price_label = tk.Label(self.summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#2c3e50")
        self.stop_loss_trigger_price_label.grid(row=10, column=1, sticky='w', padx=5, pady=5)

        # Optimized Summary Labels
        self.optimized_summary_label = tk.Label(self.optimized_summary_frame, text="Optimized Summary", font=("Arial", 16, "bold"), fg="#ecf0f1", bg="#34495e")
        self.optimized_summary_label.grid(row=0, column=0, columnspan=2, pady=10)

        tk.Label(self.optimized_summary_frame, text="Best Grid Levels:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.optimized_grid_levels_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_grid_levels_label.grid(row=1, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="Best Leverage:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.optimized_leverage_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_leverage_label.grid(row=2, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="Best Lower Limit (%):", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.optimized_lower_limit_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_lower_limit_label.grid(row=3, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="Best Upper Limit (%):", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=4, column=0, sticky='e', padx=5, pady=5)
        self.optimized_upper_limit_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_upper_limit_label.grid(row=4, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="Best Stop Loss (%):", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.optimized_stop_loss_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_stop_loss_label.grid(row=5, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="Best Net PNL:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        self.optimized_net_pnl_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_net_pnl_label.grid(row=6, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="Best ROI:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=7, column=0, sticky='e', padx=5, pady=5)
        self.optimized_roi_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_roi_label.grid(row=7, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="Stop Loss Triggered:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=8, column=0, sticky='e', padx=5, pady=5)
        self.optimized_stop_loss_triggered_label = tk.Label(self.optimized_summary_frame, text="No", font=self.summary_font, fg="#2ecc71", bg="#34495e")
        self.optimized_stop_loss_triggered_label.grid(row=8, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="SL Trigger Date:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=9, column=0, sticky='e', padx=5, pady=5)
        self.optimized_stop_loss_trigger_date_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_stop_loss_trigger_date_label.grid(row=9, column=1, sticky='w', padx=5, pady=5)

        tk.Label(self.optimized_summary_frame, text="SL Trigger Price:", font=label_font, fg="#ecf0f1", bg="#34495e").grid(row=10, column=0, sticky='e', padx=5, pady=5)
        self.optimized_stop_loss_trigger_price_label = tk.Label(self.optimized_summary_frame, text="", font=self.summary_font, fg="#ecf0f1", bg="#34495e")
        self.optimized_stop_loss_trigger_price_label.grid(row=10, column=1, sticky='w', padx=5, pady=5)

        # Add a Notebook widget to create tabs for trade logs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create Frames for each tab
        self.default_log_frame = tk.Frame(self.notebook, bg='#34495e', bd=2, relief='ridge')
        self.optimized_log_frame = tk.Frame(self.notebook, bg='#34495e', bd=2, relief='ridge')

        # Add tabs to the notebook
        self.notebook.add(self.default_log_frame, text="Default Trade Logs")
        self.notebook.add(self.optimized_log_frame, text="Optimized Trade Logs")

        # Default Trade Log Frame (ttk.Treeview)
        columns = ['Seq', 'Date', 'Price', 'B/S', 'Entry_Level', 'Target_Level', 'PNL_Current', 'Quantity', 'Transaction_Cost', 'Net_PNL']

        self.trade_log_tree_default = ttk.Treeview(self.default_log_frame, columns=columns, show='headings', height=15)
        self.trade_log_tree_default.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for col in columns:
            self.trade_log_tree_default.heading(col, text=col)
            self.trade_log_tree_default.column(col, anchor='center', width=90)

        self.scrollbar_default = tk.Scrollbar(self.default_log_frame, orient=tk.VERTICAL, command=self.trade_log_tree_default.yview)
        self.trade_log_tree_default.configure(yscrollcommand=self.scrollbar_default.set)
        self.scrollbar_default.pack(side=tk.RIGHT, fill=tk.Y)

        # Optimized Trade Log Frame (ttk.Treeview)
        self.trade_log_tree_optimized = ttk.Treeview(self.optimized_log_frame, columns=columns, show='headings', height=15)
        self.trade_log_tree_optimized.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for col in columns:
            self.trade_log_tree_optimized.heading(col, text=col)
            self.trade_log_tree_optimized.column(col, anchor='center', width=90)

        self.scrollbar_optimized = tk.Scrollbar(self.optimized_log_frame, orient=tk.VERTICAL, command=self.trade_log_tree_optimized.yview)
        self.trade_log_tree_optimized.configure(yscrollcommand=self.scrollbar_optimized.set)
        self.scrollbar_optimized.pack(side=tk.RIGHT, fill=tk.Y)

    def update_symbols(self, event=None):
        try:
            exchange_name = self.exchange_entry.get()
            exchange_class = getattr(ccxt, exchange_name)()
            markets = exchange_class.load_markets()
            symbols = list(markets.keys())
            self.symbol_entry['values'] = symbols
            self.symbol_entry.set(symbols[0])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load symbols for {exchange_name}: {str(e)}")

    def update_initial_price(self, event=None):
        try:
            exchange_name = self.exchange_entry.get()
            symbol = self.symbol_entry.get()
            timeframe = self.timeframe_entry.get()
            start_date = self.start_date.get()
            exchange_class = getattr(ccxt, exchange_name)()
            start_timestamp = int(pd.to_datetime(start_date).timestamp() * 1000)
            ohlcv = exchange_class.fetch_ohlcv(symbol, timeframe, since=start_timestamp, limit=1)
            if ohlcv:
                initial_price = ohlcv[0][4]  # Close price
                self.initial_price_absolute.delete(0, tk.END)
                self.initial_price_absolute.insert(0, f"{initial_price:.2f}")
                self.update_status("Initial Price Fetched", "#2ecc71")
                self.update_limits()
            else:
                self.initial_price_absolute.delete(0, tk.END)
                self.initial_price_absolute.insert(0, "N/A")
                self.update_status("No data available for the selected start date", "#e74c3c")
        except Exception as e:
            self.update_status(str(e), "#e74c3c")

    def update_limits(self):
        try:
            initial_price = float(self.initial_price_absolute.get())

            # Update Lower Limit
            if self.lower_limit_mode.get() == "absolute":
                lower_limit = float(self.lower_limit_absolute.get())
                percentage = (initial_price - lower_limit) / initial_price * 100
                self.lower_limit_percentage.delete(0, tk.END)
                self.lower_limit_percentage.insert(0, f"{percentage:.2f}%")
            else:
                percentage = float(self.lower_limit_percentage.get().strip('%'))
                lower_limit = initial_price * (1 - percentage / 100)
                self.lower_limit_absolute.delete(0, tk.END)
                self.lower_limit_absolute.insert(0, f"{lower_limit:.2f}")

            # Update Upper Limit
            if self.upper_limit_mode.get() == "absolute":
                upper_limit = float(self.upper_limit_absolute.get())
                percentage = (upper_limit - initial_price) / initial_price * 100
                self.upper_limit_percentage.delete(0, tk.END)
                self.upper_limit_percentage.insert(0, f"{percentage:.2f}%")
            else:
                percentage = float(self.upper_limit_percentage.get().strip('%'))
                upper_limit = initial_price * (1 + percentage / 100)
                self.upper_limit_absolute.delete(0, tk.END)
                self.upper_limit_absolute.insert(0, f"{upper_limit:.2f}")

            # Update Lower Stop Loss
            if self.lower_stop_loss_mode.get() == "absolute":
                lower_stop_loss = float(self.lower_stop_loss_absolute.get())
                percentage = (initial_price - lower_stop_loss) / initial_price * 100
                self.lower_stop_loss_percentage.delete(0, tk.END)
                self.lower_stop_loss_percentage.insert(0, f"{percentage:.2f}%")
            else:
                percentage = float(self.lower_stop_loss_percentage.get().strip('%'))
                lower_stop_loss = initial_price * (1 - percentage / 100)
                self.lower_stop_loss_absolute.delete(0, tk.END)
                self.lower_stop_loss_absolute.insert(0, f"{lower_stop_loss:.2f}")

            # Update Upper Stop Loss
            if self.upper_stop_loss_mode.get() == "absolute":
                upper_stop_loss = float(self.upper_stop_loss_absolute.get())
                percentage = (upper_stop_loss - initial_price) / initial_price * 100
                self.upper_stop_loss_percentage.delete(0, tk.END)
                self.upper_stop_loss_percentage.insert(0, f"{percentage:.2f}%")
            else:
                percentage = float(self.upper_stop_loss_percentage.get().strip('%'))
                upper_stop_loss = initial_price * (1 + percentage / 100)
                self.upper_stop_loss_absolute.delete(0, tk.END)
                self.upper_stop_loss_absolute.insert(0, f"{upper_stop_loss:.2f}")

            # Update Grid Levels
            self.update_grid_levels()

        except ValueError:
            pass

    def update_grid_levels(self):
        try:
            initial_price = float(self.initial_price_absolute.get())

            if self.grid_levels_mode.get() == "absolute":
                grid_levels = int(self.grid_levels_absolute.get())
                grid_range = (float(self.upper_limit_absolute.get()) - float(self.lower_limit_absolute.get())) / grid_levels
                percentage = grid_range / initial_price * 100
                self.grid_levels_percentage.delete(0, tk.END)
                self.grid_levels_percentage.insert(0, f"{percentage:.2f}%")
            else:
                percentage = float(self.grid_levels_percentage.get().strip('%'))
                grid_range = initial_price * (percentage / 100)
                grid_levels = int((float(self.upper_limit_absolute.get()) - float(self.lower_limit_absolute.get())) / grid_range)
                self.grid_levels_absolute.delete(0, tk.END)
                self.grid_levels_absolute.insert(0, f"{grid_levels}")
        except ValueError:
            pass

    def fetch_data(self, progress_callback=None):
        exchange_name = self.exchange_entry.get()
        symbol = self.symbol_entry.get()
        timeframe = self.timeframe_entry.get()
        start_date = self.start_date.get()
        end_date = self.end_date.get()
        exchange_class = getattr(ccxt, exchange_name)()
        since = int(pd.to_datetime(start_date).timestamp() * 1000)
        end_timestamp = int(pd.to_datetime(end_date).timestamp() * 1000)
        all_ohlcv = []
        total_iterations = 0

        # Estimate total iterations based on timeframe
        timeframe_seconds = exchange_class.parse_timeframe(timeframe) * 60
        total_iterations = (end_timestamp - since) // (timeframe_seconds * 1000) + 1

        iteration = 0

        while since < end_timestamp:
            try:
                ohlcv = exchange_class.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                if not ohlcv:
                    break
                last_timestamp = ohlcv[-1][0]
                if last_timestamp == since:
                    break
                since = last_timestamp + 1
                all_ohlcv.extend(ohlcv)
                iteration += len(ohlcv)
                if progress_callback:
                    progress = min(iteration / total_iterations * 100, 100)
                    progress_callback(progress)
            except Exception as e:
                break  # Handle exceptions gracefully

        df = pd.DataFrame(all_ohlcv, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
        df = df[(df['Open time'] >= pd.to_datetime(start_date)) & (df['Open time'] <= pd.to_datetime(end_date))]
        return df

    def run_strategy_thread(self):
        threading.Thread(target=self.run_strategy, daemon=True).start()

    def run_strategy(self):
        self.update_status("Running Strategy...", "#f39c12")
        self.update_progress(0)
        try:
            self.df = self.fetch_data(progress_callback=self.update_progress)
            self.update_progress(0)

            # Determine initial price
            if self.initial_price_mode.get() == "absolute":
                initial_price = float(self.initial_price_absolute.get())
            else:
                df_on_start_date = self.df[self.df['Open time'].dt.date == pd.to_datetime(self.start_date.get()).date()]
                if df_on_start_date.empty:
                    raise ValueError(f"No data available for the selected start date: {self.start_date.get()}")
                initial_price = df_on_start_date['Close'].iloc[0]
                self.initial_price_absolute.delete(0, tk.END)
                self.initial_price_absolute.insert(0, f"{initial_price:.2f}")
                self.update_limits()

            # Determine lower limit
            if self.lower_limit_mode.get() == "absolute":
                lower_limit = float(self.lower_limit_absolute.get())
            else:
                lower_limit = initial_price * (1 - float(self.lower_limit_percentage.get().strip('%')) / 100)

            # Determine upper limit
            if self.upper_limit_mode.get() == "absolute":
                upper_limit = float(self.upper_limit_absolute.get())
            else:
                upper_limit = initial_price * (1 + float(self.upper_limit_percentage.get().strip('%')) / 100)

            # Determine lower stop loss
            if self.lower_stop_loss_mode.get() == "absolute":
                lower_stop_loss = float(self.lower_stop_loss_absolute.get())
            else:
                lower_stop_loss = initial_price * (1 - float(self.lower_stop_loss_percentage.get().strip('%')) / 100)

            # Determine upper stop loss
            if self.upper_stop_loss_mode.get() == "absolute":
                upper_stop_loss = float(self.upper_stop_loss_absolute.get())
            else:
                upper_stop_loss = initial_price * (1 + float(self.upper_stop_loss_percentage.get().strip('%')) / 100)

            # Determine grid levels
            if self.grid_levels_mode.get() == "absolute":
                grid_levels = int(self.grid_levels_absolute.get())
            else:
                grid_levels = round((upper_limit - lower_limit) / (initial_price * float(self.grid_levels_percentage.get().strip('%')) / 100))

            # Use full data within date range without price filtering
            df_filtered = self.df[(self.df['Open time'] >= pd.to_datetime(self.start_date.get())) & (self.df['Open time'] <= pd.to_datetime(self.end_date.get()))]

            if df_filtered.empty:
                raise ValueError("No data available for the given parameters after filtering. Adjust your limits or date range.")

            # Run the strategy
            self.trade_log_df_default, total_current_pnl, mtm_value, total_mtm, total_cost, roi, open_trades, \
            stop_loss_triggered, stop_loss_trigger_date, stop_loss_trigger_price = grid_bot_strategy(
                df_filtered,
                start_date=self.start_date.get(),
                end_date=self.end_date.get(),
                initial_price=initial_price,
                lower_limit=lower_limit,
                upper_limit=upper_limit,
                grid_levels=grid_levels,
                initial_capital=float(self.initial_capital.get()),
                leverage=float(self.leverage.get()),
                lower_stop_loss=lower_stop_loss,
                upper_stop_loss=upper_stop_loss,
                stop_loss_enabled=self.stop_loss_enabled.get(),
                progress_callback=self.update_progress
            )

            # Store default results for comparison
            self.default_results = {
                'total_current_pnl': total_current_pnl,
                'mtm_value': mtm_value,
                'total_mtm': total_mtm,
                'total_cost': total_cost,
                'roi': roi,
                'open_trades': open_trades,
                'stop_loss_triggered': stop_loss_triggered,
                'stop_loss_trigger_date': stop_loss_trigger_date,
                'stop_loss_trigger_price': stop_loss_trigger_price,
                'trade_log_df': self.trade_log_df_default
            }

            # Update the summary
            self.root.after(0, lambda: self.update_summary_labels_for_run(
                total_current_pnl, mtm_value, len(self.trade_log_df_default),
                open_trades, total_cost, total_mtm, roi, stop_loss_triggered,
                stop_loss_trigger_date, stop_loss_trigger_price))

            # Clear the Treeview before inserting new logs
            self.trade_log_tree_default.delete(*self.trade_log_tree_default.get_children())

            # Insert the trade log data into the Treeview
            for _, row in self.trade_log_df_default.iterrows():
                self.trade_log_tree_default.insert("", "end", values=list(row))

            self.update_status("Strategy Completed", "#2ecc71")

        except ValueError as ve:
            self.root.after(0, lambda: messagebox.showerror("Error", str(ve)))
            self.update_status("Error running strategy", "#e74c3c")
        finally:
            self.update_progress(100)

    def optimize_strategy_thread(self):
        threading.Thread(target=self.optimize_strategy, daemon=True).start()

    def optimize_strategy(self):
        self.update_status("Optimizing Strategy...", "#f39c12")
        self.update_progress(0)
        try:
            # Ensure that the default data is available
            if not hasattr(self, 'df'):
                self.df = self.fetch_data(progress_callback=self.update_progress)

            initial_price = float(self.initial_price_absolute.get())

            # Fixed parameters for optimization
            initial_capital = float(self.initial_capital.get())
            stop_loss_enabled = self.stop_loss_enabled.get()

            # Variables to store the best results
            best_params = {}
            best_pnl = -float('inf')
            best_trade_log_df = None

            # Define parameter ranges
            leverage_values = [5, 10, 15, 20]
            lower_limit_percentages = [5, 10, 15, 20]
            upper_limit_percentages = [5, 10, 15, 20]
            stop_loss_percentages = [10, 15, 20, 25]
            grid_levels_list = [20, 30, 40, 50, 60, 70, 80]

            total_iterations = (len(leverage_values) * len(lower_limit_percentages) *
                                len(upper_limit_percentages) * len(stop_loss_percentages) *
                                len(grid_levels_list))
            current_iteration = 0

            # Use full data within date range without price filtering
            df_filtered = self.df[(self.df['Open time'] >= pd.to_datetime(self.start_date.get())) & (self.df['Open time'] <= pd.to_datetime(self.end_date.get()))]

            if df_filtered.empty:
                raise ValueError("No data available for the given parameters after filtering. Adjust your limits or date range.")

            for leverage in leverage_values:
                for lower_limit_pct in lower_limit_percentages:
                    for upper_limit_pct in upper_limit_percentages:
                        for stop_loss_pct in stop_loss_percentages:
                            for grid_levels in grid_levels_list:
                                current_iteration += 1
                                progress = (current_iteration / total_iterations) * 100
                                self.update_progress(progress)

                                # Calculate absolute limits and stop-loss levels
                                lower_limit = initial_price * (1 - lower_limit_pct / 100)
                                upper_limit = initial_price * (1 + upper_limit_pct / 100)
                                lower_stop_loss = initial_price * (1 - stop_loss_pct / 100)
                                upper_stop_loss = initial_price * (1 + stop_loss_pct / 100)

                                # Run strategy
                                results = grid_bot_strategy(
                                    df_filtered,
                                    start_date=self.start_date.get(),
                                    end_date=self.end_date.get(),
                                    initial_price=initial_price,
                                    lower_limit=lower_limit,
                                    upper_limit=upper_limit,
                                    grid_levels=grid_levels,
                                    initial_capital=initial_capital,
                                    leverage=leverage,
                                    lower_stop_loss=lower_stop_loss,
                                    upper_stop_loss=upper_stop_loss,
                                    stop_loss_enabled=stop_loss_enabled
                                )

                                pnl = results[3]  # total_mtm

                                # Check if this is the best result
                                if pnl > best_pnl:
                                    best_pnl = pnl
                                    best_params = {
                                        'leverage': leverage,
                                        'lower_limit_pct': lower_limit_pct,
                                        'upper_limit_pct': upper_limit_pct,
                                        'stop_loss_pct': stop_loss_pct,
                                        'grid_levels': grid_levels,
                                        'roi': results[5],
                                        'stop_loss_triggered': results[7],
                                        'stop_loss_trigger_date': results[8],
                                        'stop_loss_trigger_price': results[9]
                                    }
                                    best_trade_log_df = results[0]

            # Update the optimized summary in a thread-safe manner
            self.root.after(0, lambda: self.update_summary_labels_for_optimize(best_params, best_pnl))

            # Update optimized trade logs
            self.root.after(0, lambda: self.update_optimized_trade_logs(best_trade_log_df))

            self.update_status(f"Optimization Completed. Best Grid Levels: {best_params['grid_levels']}", "#2ecc71")

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.update_status("Error during optimization", "#e74c3c")
        finally:
            self.update_progress(100)

    def update_summary_labels_for_run(self, total_pnl, mtm_value, total_trades, open_trades, total_cost, net_pnl, roi, stop_loss_triggered, sl_date, sl_price):
        self.total_pnl_label.config(text=f"{total_pnl:.3f}")
        self.mtm_value_label.config(text=f"{mtm_value:.3f}")
        self.total_trades_label.config(text=f"{total_trades}")
        self.open_trades_label.config(text=f"{open_trades}")
        self.total_cost_label.config(text=f"{total_cost:.3f}")
        self.net_pnl_label.config(text=f"{net_pnl:.3f}")
        self.roi_label.config(text=f"{roi:.2f}%")

        if stop_loss_triggered:
            self.stop_loss_triggered_label.config(text="Yes", fg="#e74c3c")
            self.stop_loss_trigger_date_label.config(text=sl_date.strftime('%Y-%m-%d'))
            self.stop_loss_trigger_price_label.config(text=f"{sl_price:.2f}")
            self.stop_loss_triggered = True
            self.stop_loss_trigger_date = sl_date
        else:
            self.stop_loss_triggered_label.config(text="No", fg="#2ecc71")
            self.stop_loss_trigger_date_label.config(text="")
            self.stop_loss_trigger_price_label.config(text="")
            self.stop_loss_triggered = False
            self.stop_loss_trigger_date = None

    def update_summary_labels_for_optimize(self, best_params, best_pnl):
        self.optimized_grid_levels_label.config(text=f"{best_params['grid_levels']}")
        self.optimized_leverage_label.config(text=f"{best_params['leverage']}x")
        self.optimized_lower_limit_label.config(text=f"{best_params['lower_limit_pct']}%")
        self.optimized_upper_limit_label.config(text=f"{best_params['upper_limit_pct']}%")
        self.optimized_stop_loss_label.config(text=f"{best_params['stop_loss_pct']}%")
        self.optimized_net_pnl_label.config(text=f"{best_pnl:.2f}")
        self.optimized_roi_label.config(text=f"{best_params['roi']:.2f}%")

        if best_params['stop_loss_triggered']:
            self.optimized_stop_loss_triggered_label.config(text="Yes", fg="#e74c3c")
            self.optimized_stop_loss_trigger_date_label.config(text=best_params['stop_loss_trigger_date'].strftime('%Y-%m-%d'))
            self.optimized_stop_loss_trigger_price_label.config(text=f"{best_params['stop_loss_trigger_price']:.2f}")
        else:
            self.optimized_stop_loss_triggered_label.config(text="No", fg="#2ecc71")
            self.optimized_stop_loss_trigger_date_label.config(text="")
            self.optimized_stop_loss_trigger_price_label.config(text="")

    def update_optimized_trade_logs(self, trade_log_df):
        self.trade_log_tree_optimized.delete(*self.trade_log_tree_optimized.get_children())
        for _, row in trade_log_df.iterrows():
            self.trade_log_tree_optimized.insert("", "end", values=list(row))

    def show_equity_curve(self):
        if not hasattr(self, 'trade_log_df_default'):
            messagebox.showerror("Error", "Please run the strategy first to generate trade data.")
            return

        # Prepare data for plotting
        equity_curve = self.trade_log_df_default[['Date', 'Net_PNL']].copy()
        equity_curve.set_index('Date', inplace=True)
        equity_curve.index = pd.to_datetime(equity_curve.index)

        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot Net_PNL directly
        ax.plot(equity_curve.index, equity_curve['Net_PNL'], label='Equity Curve', color='purple')

        ax.set_xlabel('Date')
        ax.set_ylabel('Net PNL')
        ax.set_title('Equity Curve')

        # Indicate stop-loss trigger if applicable
        if self.stop_loss_triggered_label.cget("text") == "Yes":
            sl_date_str = self.stop_loss_trigger_date_label.cget("text")
            if sl_date_str:
                sl_date = pd.to_datetime(sl_date_str)
                # Find the closest date in equity_curve index
                if sl_date in equity_curve.index:
                    sl_pnl = equity_curve.loc[sl_date, 'Net_PNL']
                    if isinstance(sl_pnl, pd.Series):
                        sl_pnl = sl_pnl.iloc[-1]
                else:
                    # If exact date not found, find the closest one
                    closest_index = equity_curve.index.get_indexer([sl_date], method='nearest')[0]
                    sl_date = equity_curve.index[closest_index]
                    sl_pnl = equity_curve.iloc[closest_index]['Net_PNL']
                sl_pnl = float(sl_pnl)  # Ensure sl_pnl is a scalar float
                ax.axvline(x=sl_date, color='red', linestyle='--', label='Stop-Loss Triggered')
                ax.text(sl_date, sl_pnl, 'Stop-Loss', color='red', fontsize=12)

        ax.legend()
        ax.grid(True)
        fig.autofmt_xdate()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # Add interactive tooltip
        cursor = mplcursors.cursor(ax, hover=True)
        @cursor.connect("add")
        def on_add(sel):
            x = mdates.num2date(sel.target[0]).strftime('%Y-%m-%d %H:%M:%S')
            y = sel.target[1]
            sel.annotation.set_text(f"Date: {x}\nNet PNL: {y:.2f}")

        # Create a new window for the plot
        plot_window = tk.Toplevel(self.root)
        plot_window.title("Equity Curve")

        canvas = FigureCanvasTkAgg(fig, master=plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # Add a toolbar for navigation
        toolbar = NavigationToolbar2Tk(canvas, plot_window)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def show_trade_plot(self):
        if not hasattr(self, 'trade_log_df_default'):
            messagebox.showerror("Error", "Please run the strategy first to generate trade data.")
            return

        # Prepare data for plotting
        df_plot = self.df.copy()
        df_plot.set_index('Open time', inplace=True)

        buy_trades = self.trade_log_df_default[self.trade_log_df_default['B/S'].str.contains('Buy')]
        sell_trades = self.trade_log_df_default[self.trade_log_df_default['B/S'].str.contains('Sell')]

        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(df_plot.index, df_plot['Close'], label='Close Price', color='blue')

        ax.scatter(buy_trades['Date'], buy_trades['Price'], marker='^', color='green', label='Buy Trades', s=100)
        ax.scatter(sell_trades['Date'], sell_trades['Price'], marker='v', color='red', label='Sell Trades', s=100)

        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.set_title('Trade Plot')
        ax.legend()
        ax.grid(True)
        fig.autofmt_xdate()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # Add interactive tooltip
        cursor = mplcursors.cursor(ax, hover=True)
        @cursor.connect("add")
        def on_add(sel):
            x = mdates.num2date(sel.target[0]).strftime('%Y-%m-%d %H:%M:%S')
            y = sel.target[1]
            sel.annotation.set_text(f"Date: {x}\nPrice: {y:.2f}")

        # Create a new window for the plot
        plot_window = tk.Toplevel(self.root)
        plot_window.title("Trade Plot")

        canvas = FigureCanvasTkAgg(fig, master=plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # Add a toolbar for navigation
        toolbar = NavigationToolbar2Tk(canvas, plot_window)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def update_status(self, message, color):
        self.root.after(0, lambda: self.status_label.config(text=message, fg=color))

    def update_progress(self, progress):
        self.root.after(0, lambda: self._update_progress(progress))

    def _update_progress(self, progress):
        self.progress_bar['value'] = progress
        self.progress_percentage.config(text=f"{progress:.1f}%")

    def optimize_strategy(self):
        self.update_status("Optimizing Strategy...", "#f39c12")
        self.update_progress(0)
        try:
            # Ensure that the default data is available
            if not hasattr(self, 'df'):
                self.df = self.fetch_data(progress_callback=self.update_progress)

            initial_price = float(self.initial_price_absolute.get())

            # Fixed parameters for optimization
            initial_capital = float(self.initial_capital.get())
            stop_loss_enabled = self.stop_loss_enabled.get()

            # Variables to store the best results
            best_params = {}
            best_pnl = -float('inf')
            best_trade_log_df = None

            # Define parameter ranges
            leverage_values = [5, 10, 15, 20]
            lower_limit_percentages = [5, 10, 15, 20]
            upper_limit_percentages = [5, 10, 15, 20]
            stop_loss_percentages = [10, 15, 20, 25]
            grid_levels_list = [20, 30, 40, 50, 60, 70, 80]

            total_iterations = (len(leverage_values) * len(lower_limit_percentages) *
                                len(upper_limit_percentages) * len(stop_loss_percentages) *
                                len(grid_levels_list))
            current_iteration = 0

            # Use full data within date range without price filtering
            df_filtered = self.df[(self.df['Open time'] >= pd.to_datetime(self.start_date.get())) & (self.df['Open time'] <= pd.to_datetime(self.end_date.get()))]

            if df_filtered.empty:
                raise ValueError("No data available for the given parameters after filtering. Adjust your limits or date range.")

            for leverage in leverage_values:
                for lower_limit_pct in lower_limit_percentages:
                    for upper_limit_pct in upper_limit_percentages:
                        for stop_loss_pct in stop_loss_percentages:
                            for grid_levels in grid_levels_list:
                                current_iteration += 1
                                progress = (current_iteration / total_iterations) * 100
                                self.update_progress(progress)

                                # Calculate absolute limits and stop-loss levels
                                lower_limit = initial_price * (1 - lower_limit_pct / 100)
                                upper_limit = initial_price * (1 + upper_limit_pct / 100)
                                lower_stop_loss = initial_price * (1 - stop_loss_pct / 100)
                                upper_stop_loss = initial_price * (1 + stop_loss_pct / 100)

                                # Run strategy
                                results = grid_bot_strategy(
                                    df_filtered,
                                    start_date=self.start_date.get(),
                                    end_date=self.end_date.get(),
                                    initial_price=initial_price,
                                    lower_limit=lower_limit,
                                    upper_limit=upper_limit,
                                    grid_levels=grid_levels,
                                    initial_capital=initial_capital,
                                    leverage=leverage,
                                    lower_stop_loss=lower_stop_loss,
                                    upper_stop_loss=upper_stop_loss,
                                    stop_loss_enabled=stop_loss_enabled
                                )

                                pnl = results[3]  # total_mtm

                                # Check if this is the best result
                                if pnl > best_pnl:
                                    best_pnl = pnl
                                    best_params = {
                                        'leverage': leverage,
                                        'lower_limit_pct': lower_limit_pct,
                                        'upper_limit_pct': upper_limit_pct,
                                        'stop_loss_pct': stop_loss_pct,
                                        'grid_levels': grid_levels,
                                        'roi': results[5],
                                        'stop_loss_triggered': results[7],
                                        'stop_loss_trigger_date': results[8],
                                        'stop_loss_trigger_price': results[9]
                                    }
                                    best_trade_log_df = results[0]

            # Update the optimized summary in a thread-safe manner
            self.root.after(0, lambda: self.update_summary_labels_for_optimize(best_params, best_pnl))

            # Update optimized trade logs
            self.root.after(0, lambda: self.update_optimized_trade_logs(best_trade_log_df))

            self.update_status(f"Optimization Completed. Best Grid Levels: {best_params['grid_levels']}", "#2ecc71")

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.update_status("Error during optimization", "#e74c3c")
        finally:
            self.update_progress(100)

    def update_summary_labels_for_optimize(self, best_params, best_pnl):
        self.optimized_grid_levels_label.config(text=f"{best_params['grid_levels']}")
        self.optimized_leverage_label.config(text=f"{best_params['leverage']}x")
        self.optimized_lower_limit_label.config(text=f"{best_params['lower_limit_pct']}%")
        self.optimized_upper_limit_label.config(text=f"{best_params['upper_limit_pct']}%")
        self.optimized_stop_loss_label.config(text=f"{best_params['stop_loss_pct']}%")
        self.optimized_net_pnl_label.config(text=f"{best_pnl:.2f}")
        self.optimized_roi_label.config(text=f"{best_params['roi']:.2f}%")

        if best_params['stop_loss_triggered']:
            self.optimized_stop_loss_triggered_label.config(text="Yes", fg="#e74c3c")
            self.optimized_stop_loss_trigger_date_label.config(text=best_params['stop_loss_trigger_date'].strftime('%Y-%m-%d'))
            self.optimized_stop_loss_trigger_price_label.config(text=f"{best_params['stop_loss_trigger_price']:.2f}")
        else:
            self.optimized_stop_loss_triggered_label.config(text="No", fg="#2ecc71")
            self.optimized_stop_loss_trigger_date_label.config(text="")
            self.optimized_stop_loss_trigger_price_label.config(text="")

    def update_optimized_trade_logs(self, trade_log_df):
        self.trade_log_tree_optimized.delete(*self.trade_log_tree_optimized.get_children())
        for _, row in trade_log_df.iterrows():
            self.trade_log_tree_optimized.insert("", "end", values=list(row))

    def show_equity_curve(self):
        if not hasattr(self, 'trade_log_df_default'):
            messagebox.showerror("Error", "Please run the strategy first to generate trade data.")
            return

        # Prepare data for plotting
        equity_curve = self.trade_log_df_default[['Date', 'Net_PNL']].copy()
        equity_curve.set_index('Date', inplace=True)
        equity_curve.index = pd.to_datetime(equity_curve.index)

        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot Net_PNL directly
        ax.plot(equity_curve.index, equity_curve['Net_PNL'], label='Equity Curve', color='purple')

        ax.set_xlabel('Date')
        ax.set_ylabel('Net PNL')
        ax.set_title('Equity Curve')

        # Indicate stop-loss trigger if applicable
        if self.stop_loss_triggered_label.cget("text") == "Yes":
            sl_date_str = self.stop_loss_trigger_date_label.cget("text")
            if sl_date_str:
                sl_date = pd.to_datetime(sl_date_str)
                # Find the closest date in equity_curve index
                if sl_date in equity_curve.index:
                    sl_pnl = equity_curve.loc[sl_date, 'Net_PNL']
                    if isinstance(sl_pnl, pd.Series):
                        sl_pnl = sl_pnl.iloc[-1]
                else:
                    # If exact date not found, find the closest one
                    closest_index = equity_curve.index.get_indexer([sl_date], method='nearest')[0]
                    sl_date = equity_curve.index[closest_index]
                    sl_pnl = equity_curve.iloc[closest_index]['Net_PNL']
                sl_pnl = float(sl_pnl)  # Ensure sl_pnl is a scalar float
                ax.axvline(x=sl_date, color='red', linestyle='--', label='Stop-Loss Triggered')
                ax.text(sl_date, sl_pnl, 'Stop-Loss', color='red', fontsize=12)

        ax.legend()
        ax.grid(True)
        fig.autofmt_xdate()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # Add interactive tooltip
        cursor = mplcursors.cursor(ax, hover=True)
        @cursor.connect("add")
        def on_add(sel):
            x = mdates.num2date(sel.target[0]).strftime('%Y-%m-%d %H:%M:%S')
            y = sel.target[1]
            sel.annotation.set_text(f"Date: {x}\nNet PNL: {y:.2f}")

        # Create a new window for the plot
        plot_window = tk.Toplevel(self.root)
        plot_window.title("Equity Curve")

        canvas = FigureCanvasTkAgg(fig, master=plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # Add a toolbar for navigation
        toolbar = NavigationToolbar2Tk(canvas, plot_window)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def show_trade_plot(self):
        if not hasattr(self, 'trade_log_df_default'):
            messagebox.showerror("Error", "Please run the strategy first to generate trade data.")
            return

        # Prepare data for plotting
        df_plot = self.df.copy()
        df_plot.set_index('Open time', inplace=True)

        buy_trades = self.trade_log_df_default[self.trade_log_df_default['B/S'].str.contains('Buy')]
        sell_trades = self.trade_log_df_default[self.trade_log_df_default['B/S'].str.contains('Sell')]

        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(df_plot.index, df_plot['Close'], label='Close Price', color='blue')

        ax.scatter(buy_trades['Date'], buy_trades['Price'], marker='^', color='green', label='Buy Trades', s=100)
        ax.scatter(sell_trades['Date'], sell_trades['Price'], marker='v', color='red', label='Sell Trades', s=100)

        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.set_title('Trade Plot')
        ax.legend()
        ax.grid(True)
        fig.autofmt_xdate()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # Add interactive tooltip
        cursor = mplcursors.cursor(ax, hover=True)
        @cursor.connect("add")
        def on_add(sel):
            x = mdates.num2date(sel.target[0]).strftime('%Y-%m-%d %H:%M:%S')
            y = sel.target[1]
            sel.annotation.set_text(f"Date: {x}\nPrice: {y:.2f}")

        # Create a new window for the plot
        plot_window = tk.Toplevel(self.root)
        plot_window.title("Trade Plot")

        canvas = FigureCanvasTkAgg(fig, master=plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # Add a toolbar for navigation
        toolbar = NavigationToolbar2Tk(canvas, plot_window)
        toolbar.update()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)


if __name__ == "__main__":
    root = tk.Tk()
    app = GridBotGUI(root)
    root.mainloop()
