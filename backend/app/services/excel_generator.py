import pandas as pd
import xlsxwriter
import os

class ExcelGenerator:
    def __init__(self, ticker: str, data: dict):
        self.ticker = ticker
        self.data = data
        
        # Save securely in a temp or outputs folder
        if not os.path.exists("outputs"):
            os.makedirs("outputs")
            
        self.filename = f"{self.ticker}_Financial_Model.xlsx"
        self.filepath = os.path.join(os.getcwd(), "outputs", self.filename)

    def generate(self):
        engine = self.data.get('engine') # Instance of FinanceEngine
        if not engine:
            raise ValueError("No finance engine data provided to ExcelGenerator.")
            
        projections = self.data.get('projections')

        # Create a Pandas Excel writer using XlsxWriter as the engine.
        with pd.ExcelWriter(self.filepath, engine='xlsxwriter') as writer:
            workbook = writer.book

            # Define standard formats
            header_format = workbook.add_format({
                'bold': True, 'bg_color': '#0f172a', 'font_color': 'white', 'border': 1
            })
            # Safe JSON/Excel format using the actual stock currency
            currency_format = workbook.add_format({'num_format': f'"{engine.currency_symbol.strip()}"* #,##0.00'})
            number_format = workbook.add_format({'num_format': '#,##0.00'})
            percent_format = workbook.add_format({'num_format': '0.00%'})

            def write_sheet(df, sheet_name):
                if df is None or df.empty:
                    df = pd.DataFrame(["No data available"])
                df.to_excel(writer, sheet_name=sheet_name)
                worksheet = writer.sheets[sheet_name]
                
                # Format headers and columns
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num + 1, str(value), header_format)
                
                # Aesthetic Upgrades: Widen columns and freeze top header row
                worksheet.set_column(0, 0, 35) # Index row names wider
                worksheet.set_column(1, len(df.columns), 18, number_format) # Data cells wider
                worksheet.freeze_panes(1, 1) # Freeze top row and first column

            # Sheet 1: Raw Income Statement
            write_sheet(engine.income_stmt.transpose() if not engine.income_stmt.empty else None, 'Raw Income Statement')

            # Sheet 2: Raw Balance Sheet
            write_sheet(engine.balance_sheet.transpose() if not engine.balance_sheet.empty else None, 'Raw Balance Sheet')

            # Sheet 3: Cash Flow Statement
            write_sheet(engine.cash_flow.transpose() if not engine.cash_flow.empty else None, 'Cash Flow Statement')

            # Sheet 4: Ratio Analysis
            ratios_df = self.data.get('ratios')
            
            # We need to explicitly check that ratios is not None and not empty before generating charts
            has_ratios = ratios_df is not None and not ratios_df.empty
            write_sheet(ratios_df.transpose() if has_ratios else None, 'Ratio Analysis')
            
            # --- Inject Native Excel Charts onto Ratio Analysis Sheet ---
            if has_ratios:
                ratio_ws = writer.sheets['Ratio Analysis']
                num_cols = len(ratios_df.index) # Years across columns (B, C, D...)
                
                # Helper to quickly find the row number by string name logic since index is transposed.
                # Ratios dataframe has margin strings as column headers. Transposed they become row 1, 2, 3 in Excel index 0.
                # Pandas to_excel shifts index to Col A and columns to Row 1.
                labels = list(ratios_df.columns)
                
                def get_row(label):
                    if label in labels:
                        return labels.index(label) + 1 # 1-indexed because Row 0 is the Year Headers
                    return None
                
                # 1. Profitability Margins Line Chart
                prof_chart = workbook.add_chart({'type': 'line'})
                prof_chart.set_title({'name': 'Profitability Margins'})
                for row_label in ['Gross Profit Margin (%)', 'EBITDA Margin (%)', 'EBIT Margin (%)', 'Net Profit Margin (%)']:
                    r_idx = get_row(row_label)
                    if r_idx is not None:
                        prof_chart.add_series({
                            'name':       ['Ratio Analysis', r_idx, 0],
                            'categories': ['Ratio Analysis', 0, 1, 0, num_cols],
                            'values':     ['Ratio Analysis', r_idx, 1, r_idx, num_cols],
                            'marker':     {'type': 'circle'}
                        })
                prof_chart.set_size({'width': 600, 'height': 350})
                ratio_ws.insert_chart('B' + str(len(labels) + 3), prof_chart) # Anchor chart below data
                
                # 2. Returns Bar Chart (ROA / ROE)
                ret_chart = workbook.add_chart({'type': 'column'})
                ret_chart.set_title({'name': 'Return on Assets & Equity'})
                for row_label in ['Return on Assets (ROA) (%)', 'Return on Equity (ROE) (%)']:
                    r_idx = get_row(row_label)
                    if r_idx is not None:
                        ret_chart.add_series({
                            'name':       ['Ratio Analysis', r_idx, 0],
                            'categories': ['Ratio Analysis', 0, 1, 0, num_cols],
                            'values':     ['Ratio Analysis', r_idx, 1, r_idx, num_cols],
                        })
                ret_chart.set_size({'width': 600, 'height': 350})
                ratio_ws.insert_chart('J' + str(len(labels) + 3), ret_chart) # Anchor next to prof chart
                
                # 3. Liquidity Line Chart
                liq_chart = workbook.add_chart({'type': 'line'})
                liq_chart.set_title({'name': 'Liquidity Ratios (Current / Quick)'})
                for row_label in ['Current Ratio', 'Quick Ratio']:
                    r_idx = get_row(row_label)
                    if r_idx is not None:
                        liq_chart.add_series({
                            'name':       ['Ratio Analysis', r_idx, 0],
                            'categories': ['Ratio Analysis', 0, 1, 0, num_cols],
                            'values':     ['Ratio Analysis', r_idx, 1, r_idx, num_cols],
                            'marker':     {'type': 'diamond'}
                        })
                liq_chart.set_size({'width': 600, 'height': 350})
                ratio_ws.insert_chart('B' + str(len(labels) + 23), liq_chart) 
                
                # 4. Revenue Growth / Efficiency Chart
                rev_chart = workbook.add_chart({'type': 'column'})
                rev_chart.set_title({'name': 'Revenue YoY Growth'})
                r_idx = get_row('Revenue Growth (%)')
                if r_idx is not None:
                    rev_chart.add_series({
                        'name':       ['Ratio Analysis', r_idx, 0],
                        'categories': ['Ratio Analysis', 0, 1, 0, num_cols],
                        'values':     ['Ratio Analysis', r_idx, 1, r_idx, num_cols],
                        'fill':       {'color': '#2563eb'}
                    })
                rev_chart.set_size({'width': 600, 'height': 350})
                ratio_ws.insert_chart('J' + str(len(labels) + 23), rev_chart)
            
            # Deep Tech R&D Projections (Sheets 5-9)
            if projections:
                for sheet_name, df_proj in projections.items():
                    # We will transpose so months go across columns
                    write_sheet(df_proj.transpose(), sheet_name)

            # Dashboard Sheet
            worksheet = workbook.add_worksheet('Summary Dashboard')
            worksheet.set_column(0, 0, 25)
            worksheet.set_column(1, 1, 40)
            
            title_format = workbook.add_format({'bold': True, 'font_size': 16})
            bold_format = workbook.add_format({'bold': True})
            
            worksheet.write('A1', f'{self.ticker} Financial Summary Dashboard', title_format)
            
            if ratios_df is not None and not ratios_df.empty:
                # Calculate aggregated summaries safely
                avg_roe = ratios_df['Return on Equity (ROE) (%)'].mean() if 'Return on Equity (ROE) (%)' in ratios_df else 0
                avg_ebitda_margin = ratios_df['EBITDA Margin (%)'].mean() if 'EBITDA Margin (%)' in ratios_df else 0
                latest_de = ratios_df['Debt to Equity'].iloc[-1] if 'Debt to Equity' in ratios_df else 0
                cagr = 0
                if 'Revenue Growth (%)' in ratios_df and len(ratios_df) > 1:
                    revs = engine.income_stmt['Total Revenue']
                    if len(revs) > 1 and revs.iloc[0] > 0:
                        cagr = ((revs.iloc[-1] / revs.iloc[0]) ** (1/(len(revs)-1)) - 1) * 100

                worksheet.write('A3', 'Key Metric', bold_format)
                worksheet.write('B3', 'Value', bold_format)
                
                worksheet.write('A4', '5-Year Revenue CAGR')
                worksheet.write('B4', f"{cagr:.2f}%")
                
                worksheet.write('A5', 'Average ROE')
                worksheet.write('B5', f"{avg_roe:.2f}%")
                
                worksheet.write('A6', 'Average EBITDA Margin')
                worksheet.write('B6', f"{avg_ebitda_margin:.2f}%")
                
                worksheet.write('A7', 'Latest Debt/Equity')
                worksheet.write('B7', f"{latest_de:.2f}x")

                # AI Summary text
                worksheet.write('A9', 'AI Intelligence Summary', bold_format)
                worksheet.write('A10', self.data.get('ai_summary', "Summary not available."))
            
        return self.filepath
