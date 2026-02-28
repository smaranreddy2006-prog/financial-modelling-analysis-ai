import yfinance as yf
import pandas as pd
import numpy as np

class FinanceEngine:
    def __init__(self, ticker_symbol: str):
        self.ticker_symbol = ticker_symbol.upper()
        self.stock = yf.Ticker(self.ticker_symbol)
        
        # Raw Data Dataframes
        self.income_stmt = pd.DataFrame()
        self.balance_sheet = pd.DataFrame()
        self.cash_flow = pd.DataFrame()
        self.currency_symbol = '$'

    def fetch_data(self):
        try:
            # Currency mapping
            info = self.stock.info
            curr = info.get('currency')
            if not curr:
                curr = 'USD'
            sym_map = {'USD': '$', 'INR': '₹', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CAD': 'C$'}
            self.currency_symbol = str(sym_map.get(curr, str(curr) + ' '))
            
            # Fetch up to 5 years of annual data
            self.income_stmt = self.stock.financials.transpose().head(5)
            self.balance_sheet = self.stock.balance_sheet.transpose().head(5)
            self.cash_flow = self.stock.cashflow.transpose().head(5)
            
            if self.income_stmt.empty or self.balance_sheet.empty or self.cash_flow.empty:
                raise ValueError("Incomplete financial data fetched from Yahoo Finance.")
            
            # Sort chronologically (oldest to newest)
            self.income_stmt = self.income_stmt.sort_index()
            self.balance_sheet = self.balance_sheet.sort_index()
            self.cash_flow = self.cash_flow.sort_index()
            
            return True
        except Exception as e:
            print(f"Error fetching data for {self.ticker_symbol}: {e}")
            return False

    def _safe_get(self, df, column, default=0):
        if column in df.columns:
            return df[column].fillna(default)
        return pd.Series(default, index=df.index)

    def calculate_metrics(self):
        # We will create a new DataFrame for structured ratios (5 years)
        ratios = pd.DataFrame(index=self.income_stmt.index)
        
        # Pull key lines safely from IS
        rev = self._safe_get(self.income_stmt, 'Total Revenue')
        gross_profit = self._safe_get(self.income_stmt, 'Gross Profit')
        cogs = self._safe_get(self.income_stmt, 'Cost Of Revenue')
        ebit = self._safe_get(self.income_stmt, 'EBIT')
        ebitda = self._safe_get(self.income_stmt, 'EBITDA')
        net_income = self._safe_get(self.income_stmt, 'Net Income')
        interest_exp = self._safe_get(self.income_stmt, 'Interest Expense', default=0.0001).abs() # Avoid div by zero and make positive
        pretax_income = self._safe_get(self.income_stmt, 'Pretax Income').replace(0, 1)
        tax_prov = self._safe_get(self.income_stmt, 'Tax Provision')
        
        # BS
        assets = self._safe_get(self.balance_sheet, 'Total Assets')
        liabilities = self._safe_get(self.balance_sheet, 'Total Liabilities Net Minority Interest')
        equity = self._safe_get(self.balance_sheet, 'Stockholders Equity')
        total_debt = self._safe_get(self.balance_sheet, 'Total Debt')
        current_assets = self._safe_get(self.balance_sheet, 'Current Assets')
        current_liab = self._safe_get(self.balance_sheet, 'Current Liabilities')
        inventory = self._safe_get(self.balance_sheet, 'Inventory', default=0)
        cash_equiv = self._safe_get(self.balance_sheet, 'Cash And Cash Equivalents', default=0)
        receivables = self._safe_get(self.balance_sheet, 'Accounts Receivable', default=0)
        payables = self._safe_get(self.balance_sheet, 'Accounts Payable', default=0)
        
        # CF
        op_cf = self._safe_get(self.cash_flow, 'Operating Cash Flow')
        capex = self._safe_get(self.cash_flow, 'Capital Expenditure', default=0).abs() # Make positive
        depreciation = self._safe_get(self.cash_flow, 'Depreciation And Amortization', default=0)
        change_in_wc = self._safe_get(self.cash_flow, 'Change In Working Capital', default=0)

        # 1. Income Statement (Profitability & Returns)
        ratios['Gross Profit Margin (%)'] = (gross_profit / rev) * 100
        ratios['EBITDA Margin (%)'] = (ebitda / rev) * 100
        ratios['EBIT Margin (%)'] = (ebit / rev) * 100
        ratios['Net Profit Margin (%)'] = (net_income / rev) * 100
        ratios['Interest Coverage Ratio'] = ebit / interest_exp
        ratios['Cash Conversion Ratio'] = op_cf / net_income
        ratios['Asset Turnover'] = rev / assets
        ratios['Asset to Equity'] = assets / equity
        ratios['Return on Equity (ROE) (%)'] = (net_income / equity) * 100
        ratios['Debt to Equity'] = total_debt / equity
        ratios['Return on Assets (ROA) (%)'] = (net_income / assets) * 100

        # 2. Balance Sheet (Liquidity)
        ratios['Current Ratio'] = current_assets / current_liab
        ratios['Quick Ratio'] = (current_assets - inventory) / current_liab
        ratios['Working Capital'] = current_assets - current_liab
        ratios['Debt to Capital'] = total_debt / (total_debt + equity)
        ratios['Inventory Days'] = (inventory / cogs) * 365
        ratios['Receivable Days'] = (receivables / rev) * 365
        ratios['Payable Days'] = (payables / gross_profit) * 365
        ratios['Cash to Debt'] = cash_equiv / total_debt

        # 3. Revenue Sheet
        ratios['Revenue Growth (%)'] = rev.pct_change() * 100
        ratios['Debt to Assets'] = total_debt / assets
        ratios['% of Debt Change'] = total_debt.pct_change() * 100
        
        # FCFF
        tax_rate = (tax_prov / pretax_income).fillna(0.18)
        ratios['FCFF'] = (ebit * (1 - tax_rate)) + depreciation - capex - change_in_wc

        # 4. Cash Flow Statement
        ratios['Free Cash Flow'] = op_cf - capex
        # Using EBITDA as proxy for Operating Profit before WC Changes here as per Standard Model
        ratios['Operating CF Ratio'] = op_cf / ebitda 
        ratios['FCF to Net Profit'] = ratios['Free Cash Flow'] / net_income
        
        return ratios.replace([np.inf, -np.inf], np.nan).fillna(0)
        
    def generate_monte_carlo(self, days=252, simulations=1000):
        """
        Uses Geometric Brownian Motion (GBM) to forecast future price paths 
        based on the historical volatility of the asset.
        """
        try:
            ticker = yf.Ticker(self.ticker_symbol)
            # Fetch 1 year of historical data to find Mu and Sigma
            hist = ticker.history(period="1y")
            if hist.empty or 'Close' not in hist.columns:
                return None
                
            closes = hist['Close']
            last_price = closes.iloc[-1]
            
            # Calculate daily returns
            returns = closes.pct_change().dropna()
            mu = returns.mean()
            sigma = returns.std()
            
            # Setup simulation array [days, simulations]
            dt = 1 # 1 day step
            price_paths = np.zeros((days, simulations))
            price_paths[0] = last_price
            
            # Run Geometric Brownian Motion Random Walks
            for t in range(1, days):
                # Random shock Z ~ N(0,1)
                Z = np.random.standard_normal(simulations)
                # GBM Formula: S_t = S_{t-1} * exp((mu - 0.5 * sigma^2)dt + sigma * sqrt(dt) * Z)
                drift = mu - (0.5 * sigma**2)
                shock = sigma * Z
                price_paths[t] = price_paths[t-1] * np.exp(drift + shock)
                
            # Extract statistical percentiles for the UI
            mean_path = np.mean(price_paths, axis=1)
            p10_path = np.percentile(price_paths, 10, axis=1) # Bear Case
            p90_path = np.percentile(price_paths, 90, axis=1) # Bull Case
            
            return {
                "last_price": last_price,
                "mean_path": mean_path.tolist(),
                "p10_path": p10_path.tolist(),
                "p90_path": p90_path.tolist()
            }
        except Exception as e:
            print(f"Monte Carlo failed for {self.ticker_symbol}: {e}")
            return None

    def generate_projections(self):
        """
        Generates a 24-month high-risk deep-tech Hardware R&D projection model.
        Returns a dict of DataFrames for the Excel Control Panel.
        """
        months = [f"Month {i}" for i in range(1, 25)]
        
        # 1. Assumptions Tab
        assumptions = pd.DataFrame({
            "TAM (Total Addressable Market)": [50_000_000_000] * 24,
            "SAM (Serviceable Available Market)": [5_000_000_000] * 24,
            "SOM (Serviceable Obtainable Market)": [100_000_000] * 24,
            "Target Unit Price": [250_000] * 24,
            "New Customers/Month": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 3, 3, 5, 5, 8, 10, 12, 15, 20, 25],
        }, index=months)
        
        cum_customers = assumptions["New Customers/Month"].cumsum()
        active_revenue = cum_customers * assumptions["Target Unit Price"]

        # 2. CapEx & Depreciation
        capex = pd.DataFrame(index=months)
        capex["Infrastructure (Labs)"] = [2_000_000 if i == 0 else 0 for i in range(24)]
        capex["Machinery & Eqpt"] = [5_000_000 if i == 0 else (500_000 if i == 12 else 0) for i in range(24)]
        capex["Total CapEx"] = capex["Infrastructure (Labs)"] + capex["Machinery & Eqpt"]
        # Straight-line depreciation (60 months, 10% salvage)
        capex["Depreciation Expense"] = capex["Total CapEx"].cumsum() * 0.9 / 60

        # 3. OpEx & R&D Budget
        opex = pd.DataFrame(index=months)
        opex["Personnel (Sci/Eng)"] = [200_000 + (10_000 * i) for i in range(24)]
        opex["Prototyping & Materials"] = [150_000] * 12 + [50_000] * 12
        opex["Testing & Energy"] = [50_000] * 24
        
        unit_cogs = 100_000
        opex["COGS (BOM+Labor)"] = assumptions["New Customers/Month"] * unit_cogs
        opex["SG&A (Legal/Marketing)"] = [100_000] * 24
        opex["Total OpEx"] = opex["Personnel (Sci/Eng)"] + opex["Prototyping & Materials"] + opex["Testing & Energy"] + opex["COGS (BOM+Labor)"] + opex["SG&A (Legal/Marketing)"]

        # 4. Valuation & Returns
        val = pd.DataFrame(index=months)
        val["Revenue"] = active_revenue
        val["EBITDA"] = val["Revenue"] - opex["Total OpEx"]
        val["EBIT"] = val["EBITDA"] - capex["Depreciation Expense"]
        val["Net Income"] = val["EBIT"] # Ignore tax/interest
        val["Op Cash Flow"] = val["Net Income"] + capex["Depreciation Expense"]
        val["Free Cash Flow"] = val["Op Cash Flow"] - capex["Total CapEx"]
        
        initial_cash = 25_000_000
        cash_balance = []
        curr_cash = initial_cash
        for fcf in val["Free Cash Flow"]:
            curr_cash += fcf
            cash_balance.append(curr_cash)
            
        val["Ending Cash Balance"] = cash_balance
        val["Monthly Burn Rate"] = val["Free Cash Flow"].apply(lambda x: abs(x) if x < 0 else 0)
        
        runways = []
        for c, b in zip(val["Ending Cash Balance"], val["Monthly Burn Rate"]):
            runways.append(999 if b == 0 else c / b)
        val["Runway (Months)"] = runways
        
        # NPV @ 15% WACC
        wacc = 0.15 / 12
        dcfs = [fcf / ((1 + wacc) ** i) for i, fcf in enumerate(val["Free Cash Flow"])]
        val["Discounted FCF"] = dcfs

        # 5. Sensitivity Analysis
        base_fcf = val["Free Cash Flow"].sum()
        best_fcf = (val["Revenue"].sum() * 1.2) - (opex["Total OpEx"].sum() * 0.9) - capex["Total CapEx"].sum()
        worst_fcf = (val["Revenue"].sum() * 0.8) - (opex["Total OpEx"].sum() * 1.2) - capex["Total CapEx"].sum()
        npv_base = sum(dcfs)
        
        sens = pd.DataFrame(index=["Best Case", "Base Case", "Worst Case"])
        sens["Cumulative 24M FCF"] = [best_fcf, base_fcf, worst_fcf]
        sens["NPV (15% WACC)"] = [npv_base * 1.3, npv_base, npv_base * 0.7] # Rough theoretical impact
        sens["IRR (Estimate)"] = ["N/A", "N/A", "N/A"] # Simplified
        
        return {
            "Assumptions & Drivers": assumptions,
            "CapEx & Depreciation": capex,
            "OpEx & R&D Budget": opex,
            "Valuation & Returns": val,
            "Sensitivity Analysis": sens
        }

