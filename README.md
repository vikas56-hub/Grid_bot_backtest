# Grid Bot Strategy Backtesting and Optimization Tool

A Python-based backtesting tool for simulating and optimizing grid trading strategies on cryptocurrency markets. The tool features a user-friendly Tkinter GUI, allowing traders and developers to evaluate trading strategies using historical data. This project integrates real-time market data through CCXT and provides visual insights into trading performance with Matplotlib.

## Features

- **Backtesting Engine**: Simulates grid trading strategies on historical cryptocurrency market data.
- **User-Friendly GUI**: Built using Tkinter, allowing users to easily input parameters like grid levels, initial capital, leverage, and stop-loss.
- **Real-time Data**: Integrated with CCXT for fetching real-time cryptocurrency data.
- **Customizable Parameters**: Adjust grid levels, price range, leverage, and stop-loss to optimize your trading strategy.
- **Detailed Trade Logs**: Logs every buy/sell trade, including PNL calculations.
- **Data Visualization**: Visualizes trade execution and performance through interactive trade plots and equity curves using Matplotlib.
- **Performance Metrics**: Provides key insights such as total PNL, number of trades, and average profit per trade.

## Prerequisites

To run this project, you need to have the following installed on your system:

- Python 3.x
- `tkinter`
- `pandas`
- `matplotlib`
- `CCXT` (for real-time data fetching)
- `numpy`

You can install the required packages using pip:

```bash
pip install pandas matplotlib ccxt numpy
```

## How to Run the Project

1. **Clone the Repository**  
   First, clone the repository to your local machine:

   ```bash
   git clone https://github.com/vikas56-hub/quantz_grid.git
   cd quantz_grid
   ```

2. **Run the Script**  
   Start the backtesting tool by running the main script:

   ```bash
   python main.py
   ```

3. **Input Parameters in the GUI**  
   After launching the tool, you can input your desired parameters:
   - Grid upper and lower price levels
   - Initial capital
   - Number of grid levels
   - Leverage
   - Start and end dates for backtesting

4. **Load Data**  
   Load historical data by selecting a CSV file or fetch real-time data using CCXT.

5. **Start Backtest**  
   Click "Start Backtest" to run the strategy on the selected data. The tool will execute buy/sell trades according to the grid strategy.

6. **View Results**  
   After the backtest, you can view detailed trade logs and performance metrics. Visualizations of trade execution points and equity curves will be displayed using Matplotlib.

## How the Grid Trading Strategy Works

The grid trading strategy is a simple but effective method of capitalizing on market volatility. The strategy divides a price range into multiple grid levels. When the price moves to a certain grid level, the bot automatically buys or sells a portion of the asset. It profits by repeatedly buying low and selling high, making it ideal for volatile markets.

## Example Parameters

- **Grid Upper Limit**: $45,000
- **Grid Lower Limit**: $30,000
- **Number of Grids**: 10
- **Initial Capital**: $10,000
- **Leverage**: 2x
- **Stop-Loss**: $28,000

## Output

After the backtest is completed, the tool generates the following outputs:
- **Trade Log**: Details every buy and sell action with corresponding prices and times.
- **PNL Calculations**: Shows profit/loss for each closed trade.
- **Total PNL**: Summary of the overall profit/loss from the entire backtest period.
- **Visuals**: Plots showing price movements, trade points, and equity curves.

## Visualization Example

A typical plot showing the price movement and corresponding buy/sell points looks like this:

- **Price movement (X-axis: Time, Y-axis: Price)** with buy/sell points marked.
- **Equity curve** showing account balance after each trade.

## Future Enhancements

- Implement machine learning for strategy optimization.
- Integrate additional technical indicators.
- Improve execution speed for large datasets.

## Contribution

Feel free to fork this repository and contribute to the project by creating a pull request. For major changes, please open an issue first to discuss what you would like to change.

---
