from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import math
from ..services.finance_engine import FinanceEngine
from ..services.excel_generator import ExcelGenerator

router = APIRouter()

def sanitize_list(lst):
    return [None if (isinstance(x, float) and math.isnan(x)) else x for x in lst]

def format_currency(val, symbol):
    if val is None or math.isnan(val):
        return "N/A"
    if symbol == '₹' and abs(val) >= 1_00_00_000: # 1 Crore
        return f"₹{val / 1_00_00_000:,.2f} Cr"
    return f"{symbol.strip()}{val:,.0f}"

@router.get("/analyze")
async def analyze_company(ticker: str):
    """
    Analyzes the company and returns structured financial JSON.
    """
    engine = FinanceEngine(ticker)
    if not engine.fetch_data():
        raise HTTPException(status_code=404, detail=f"Could not fetch data for ticker: {ticker}")
    
    ratios = engine.calculate_metrics()
    projections = engine.generate_projections()
    monte_carlo = engine.generate_monte_carlo()
    
    # Generate basic AI summary
    cagr = 0
    if not engine.income_stmt.empty and len(engine.income_stmt) > 1:
        revs = engine.income_stmt['Total Revenue'].dropna()
        if len(revs) > 1 and revs.iloc[0] > 0:
            # FinanceEngine pre-sorts chronologically. iloc[0] = oldest, iloc[-1] = newest
            cagr = ((revs.iloc[-1] / revs.iloc[0]) ** (1 / (len(revs)-1)) - 1) * 100
            
    avg_roe = ratios['Return on Equity (ROE) (%)'].mean() if 'Return on Equity (ROE) (%)' in ratios else 0
    latest_de = ratios['Debt to Equity'].iloc[-1] if 'Debt to Equity' in ratios else 0
    
    ai_summary = f"The company has a 5-year Revenue CAGR of {cagr:.1f}%. Average Return on Equity stands at {avg_roe:.1f}%. "
    if latest_de > 2.0:
        ai_summary += f"However, current debt levels are high with a Debt/Equity ratio of {latest_de:.2f}x, indicating elevated financial risk."
    else:
        ai_summary += f"The balance sheet appears stable with a Debt/Equity ratio of {latest_de:.2f}x."

    # Send a standardized JSON payload to the frontend
    # Since DataFrames contain NaNs/Infs, we must ensure JSON serialization is safe.
    # By mapping it to dicts, `fastapi` will handle it, but we need to drop NA rows or handle them.
    # We'll just extract the latest KPI values for the dashboard.
    
    return {
        "status": "success",
        "ticker": ticker.upper(),
        "currency": engine.currency_symbol,
        "kpis": {
            "ebitda": format_currency((ratios['EBITDA Margin (%)'].iloc[-1]/100 * engine.income_stmt['Total Revenue'].iloc[-1]) if not engine.income_stmt.empty else None, engine.currency_symbol),
            "roe": f"{ratios['Return on Equity (ROE) (%)'].iloc[-1]:.1f}%" if 'Return on Equity (ROE) (%)' in ratios else "N/A",
            "de": f"{ratios['Debt to Equity'].iloc[-1]:.2f}x" if 'Debt to Equity' in ratios else "N/A",
            "fcf": format_currency(ratios['Free Cash Flow'].iloc[-1] if 'Free Cash Flow' in ratios else None, engine.currency_symbol),
        },
        "valuation": {
            "runway": f"{projections['Valuation & Returns']['Runway (Months)'].iloc[-1]:.1f} Months",
            "burn_rate": format_currency(projections['Valuation & Returns']['Monthly Burn Rate'].iloc[-1], engine.currency_symbol) + "/mo",
            "npv": format_currency(projections['Sensitivity Analysis']['NPV (15% WACC)'].iloc[1], engine.currency_symbol)
        },
        "ai_summary": ai_summary,
        # Original Chart Arrays
        "years": [str(x)[:4] for x in ratios.index.tolist()],
        "revenue_trend": sanitize_list(engine.income_stmt['Total Revenue'].tolist() if not engine.income_stmt.empty else []),
        "ebitda_margins": sanitize_list(ratios['EBITDA Margin (%)'].tolist() if 'EBITDA Margin (%)' in ratios else []),
        # New Marginal Analysis Chart Arrays
        "gross_margins": sanitize_list(ratios['Gross Profit Margin (%)'].tolist() if 'Gross Profit Margin (%)' in ratios else []),
        "net_margins": sanitize_list(ratios['Net Profit Margin (%)'].tolist() if 'Net Profit Margin (%)' in ratios else []),
        "ebit_margins": sanitize_list(ratios['EBIT Margin (%)'].tolist() if 'EBIT Margin (%)' in ratios else []),
        "roa": sanitize_list(ratios['Return on Assets (ROA) (%)'].tolist() if 'Return on Assets (ROA) (%)' in ratios else []),
        "liquid_ratios": sanitize_list(ratios['Current Ratio'].tolist() if 'Current Ratio' in ratios else []),
        "quick_ratios": sanitize_list(ratios['Quick Ratio'].tolist() if 'Quick Ratio' in ratios else []),
        "asset_turnover": sanitize_list(ratios['Asset Turnover'].tolist() if 'Asset Turnover' in ratios else []),
        "cash_conversion": sanitize_list(ratios['Cash Conversion Ratio'].tolist() if 'Cash Conversion Ratio' in ratios else []),
        # New Monte Carlo Simulation Arrays (252-Day Forecast)
        "monte_carlo": monte_carlo
    }

@router.get("/download")
async def download_model(ticker: str):
    """
    Generates and returns the structured Excel model.
    """
    engine = FinanceEngine(ticker)
    if not engine.fetch_data():
        raise HTTPException(status_code=404, detail=f"Could not fetch data for ticker: {ticker}")
    
    ratios = engine.calculate_metrics()
    projections = engine.generate_projections()
    
    data_payload = {
        "engine": engine,
        "ratios": ratios,
        "projections": projections,
        "ai_summary": "Auto-generated financial model by FinModel AI."
    }
    
    generator = ExcelGenerator(ticker, data_payload)
    filepath = generator.generate()
    
    headers = {"Content-Disposition": f'attachment; filename="{os.path.basename(filepath)}"'}
    return FileResponse(
        path=filepath, 
        filename=os.path.basename(filepath), 
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers=headers
    )
