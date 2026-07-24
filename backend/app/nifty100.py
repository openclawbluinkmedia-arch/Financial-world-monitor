"""
Hardcoded NIFTY 100 issuer mapping — used as fallback when security_master table is empty.
Ticker -> (company_name, sector, industry)
"""

NIFTY_100: dict[str, tuple[str, str, str]] = {
    "RELIANCE": ("Reliance Industries Ltd", "Energy", "Oil & Gas"),
    "TCS": ("Tata Consultancy Services", "Information Technology", "IT Services"),
    "HDFCBANK": ("HDFC Bank Ltd", "Financials", "Banks"),
    "INFY": ("Infosys Ltd", "Information Technology", "IT Services"),
    "ICICIBANK": ("ICICI Bank Ltd", "Financials", "Banks"),
    "HINDUNILVR": ("Hindustan Unilever Ltd", "Consumer Staples", "FMCG"),
    "ITC": ("ITC Ltd", "Consumer Staples", "FMCG"),
    "SBIN": ("State Bank of India", "Financials", "Banks"),
    "BHARTIARTL": ("Bharti Airtel Ltd", "Communication Services", "Telecom"),
    "KOTAKBANK": ("Kotak Mahindra Bank Ltd", "Financials", "Banks"),
    "BAJFINANCE": ("Bajaj Finance Ltd", "Financials", "Capital Markets"),
    "LT": ("Larsen & Toubro Ltd", "Industrials", "Construction"),
    "WIPRO": ("Wipro Ltd", "Information Technology", "IT Services"),
    "AXISBANK": ("Axis Bank Ltd", "Financials", "Banks"),
    "TITAN": ("Titan Company Ltd", "Consumer Discretionary", "Consumer Discretionary"),
    "ASIANPAINT": ("Asian Paints Ltd", "Materials", "Chemicals"),
    "MARUTI": ("Maruti Suzuki India Ltd", "Consumer Discretionary", "Automobiles"),
    "SUNPHARMA": ("Sun Pharmaceutical Industries Ltd", "Healthcare", "Pharmaceuticals"),
    "ULTRACEMCO": ("UltraTech Cement Ltd", "Materials", "Cement"),
    "NTPC": ("NTPC Ltd", "Utilities", "Power"),
    "ONGC": ("Oil and Natural Gas Corporation Ltd", "Energy", "Oil & Gas"),
    "M&M": ("Mahindra & Mahindra Ltd", "Consumer Discretionary", "Automobiles"),
    "POWERGRID": ("Power Grid Corporation of India Ltd", "Utilities", "Power"),
    "HCLTECH": ("HCL Technologies Ltd", "Information Technology", "IT Services"),
    "NESTLEIND": ("Nestlé India Ltd", "Consumer Staples", "FMCG"),
    "JSWSTEEL": ("JSW Steel Ltd", "Materials", "Metals & Mining"),
    "TATASTEEL": ("Tata Steel Ltd", "Materials", "Metals & Mining"),
    "BAJAJFINSV": ("Bajaj Finserv Ltd", "Financials", "Capital Markets"),
    "TRENT": ("Trent Ltd", "Consumer Discretionary", "Consumer Discretionary"),
    "HDFC": ("Housing Development Finance Corporation Ltd", "Financials", "Banks"),
    "ADANIENT": ("Adani Enterprises Ltd", "Industrials", "Industrials"),
    "ADANIPORTS": ("Adani Ports and Special Economic Zone Ltd", "Industrials", "Construction"),
    "COALINDIA": ("Coal India Ltd", "Energy", "Metals & Mining"),
    "IOC": ("Indian Oil Corporation Ltd", "Energy", "Oil & Gas"),
    "SBILIFE": ("SBI Life Insurance Company Ltd", "Financials", "Insurance"),
    "HINDALCO": ("Hindalco Industries Ltd", "Materials", "Metals & Mining"),
    "BAJAJ-AUTO": ("Bajaj Auto Ltd", "Consumer Discretionary", "Automobiles"),
    "TATAMOTORS": ("Tata Motors Ltd", "Consumer Discretionary", "Automobiles"),
    "MARICO": ("Marico Ltd", "Consumer Staples", "FMCG"),
    "CIPLA": ("Cipla Ltd", "Healthcare", "Pharmaceuticals"),
    "DIVISLAB": ("Divi's Laboratories Ltd", "Healthcare", "Pharmaceuticals"),
    "DRREDDY": ("Dr. Reddy's Laboratories Ltd", "Healthcare", "Pharmaceuticals"),
    "EICHERMOT": ("Eicher Motors Ltd", "Consumer Discretionary", "Automobiles"),
    "GRASIM": ("Grasim Industries Ltd", "Materials", "Cement"),
    "TECHM": ("Tech Mahindra Ltd", "Information Technology", "IT Services"),
    "BRITANNIA": ("Britannia Industries Ltd", "Consumer Staples", "FMCG"),
    "INDUSINDBK": ("IndusInd Bank Ltd", "Financials", "Banks"),
    "TATACONSUM": ("Tata Consumer Products Ltd", "Consumer Staples", "FMCG"),
    "HDFCLIFE": ("HDFC Life Insurance Company Ltd", "Financials", "Insurance"),
    "BPCL": ("Bharat Petroleum Corporation Ltd", "Energy", "Oil & Gas"),
    "DABUR": ("Dabur India Ltd", "Consumer Staples", "FMCG"),
    "ICICIPRULI": ("ICICI Prudential Life Insurance Company Ltd", "Financials", "Insurance"),
    "PIDILITIND": ("Pidilite Industries Ltd", "Materials", "Chemicals"),
    "HEROMOTOCO": ("Hero MotoCorp Ltd", "Consumer Discretionary", "Automobiles"),
    "APOLLOHOSP": ("Apollo Hospitals Enterprise Ltd", "Healthcare", "Healthcare"),
    "SHREECEM": ("Shree Cement Ltd", "Materials", "Cement"),
    "BAJAJHLDNG": ("Bajaj Holdings & Investment Ltd", "Financials", "Capital Markets"),
    "DLF": ("DLF Ltd", "Real Estate", "Real Estate"),
    "ADANIGREEN": ("Adani Green Energy Ltd", "Utilities", "Power"),
    "ADANITRANS": ("Adani Transmission Ltd", "Utilities", "Power"),
    "GAIL": ("GAIL (India) Ltd", "Energy", "Oil & Gas"),
    "HAL": ("Hindustan Aeronautics Ltd", "Industrials", "Industrials"),
    "BEL": ("Bharat Electronics Ltd", "Industrials", "Industrials"),
    "COLPAL": ("Colgate-Palmolive (India) Ltd", "Consumer Staples", "FMCG"),
    "HAVELLS": ("Havells India Ltd", "Industrials", "Industrials"),
    "ICICIGI": ("ICICI Lombard General Insurance Company Ltd", "Financials", "Insurance"),
    "MUTHOOTFIN": ("Muthoot Finance Ltd", "Financials", "Capital Markets"),
    "NAUKRI": ("Info Edge (India) Ltd", "Information Technology", "IT Services"),
    "PAGEIND": ("Page Industries Ltd", "Consumer Discretionary", "Consumer Discretionary"),
    "SIEMENS": ("Siemens Ltd", "Industrials", "Industrials"),
    "SRTRANSFIN": ("Shriram Transport Finance Company Ltd", "Financials", "Capital Markets"),
    "TVSMOTOR": ("TVS Motor Company Ltd", "Consumer Discretionary", "Automobiles"),
    "VEDL": ("Vedanta Ltd", "Materials", "Metals & Mining"),
    "ZOMATO": ("Zomato Ltd", "Consumer Discretionary", "Consumer Discretionary"),
    "PFC": ("Power Finance Corporation Ltd", "Financials", "Capital Markets"),
    "RECLTD": ("REC Ltd", "Financials", "Capital Markets"),
    "BANDHANBNK": ("Bandhan Bank Ltd", "Financials", "Banks"),
    "GODREJCP": ("Godrej Consumer Products Ltd", "Consumer Staples", "FMCG"),
    "BERGEPAINT": ("Berger Paints India Ltd", "Materials", "Chemicals"),
    "AMBUJACEM": ("Ambuja Cements Ltd", "Materials", "Cement"),
    "DIXON": ("Dixon Technologies (India) Ltd", "Industrials", "Industrials"),
    "INDUSTOWER": ("Indus Towers Ltd", "Communication Services", "Telecom"),
    "TORNTPHARM": ("Torrent Pharmaceuticals Ltd", "Healthcare", "Pharmaceuticals"),
    "MCDOWELL-N": ("United Spirits Ltd", "Consumer Staples", "FMCG"),
    "BANKBARODA": ("Bank of Baroda", "Financials", "Banks"),
    "CANBK": ("Canara Bank", "Financials", "Banks"),
    "PNB": ("Punjab National Bank", "Financials", "Banks"),
    "UNIONBANK": ("Union Bank of India", "Financials", "Banks"),
    "IDFCFIRSTB": ("IDFC First Bank Ltd", "Financials", "Banks"),
    "LICI": ("Life Insurance Corporation of India", "Financials", "Insurance"),
    "IRCTC": ("Indian Railway Catering and Tourism Corporation Ltd", "Industrials", "Industrials"),
    "NHPC": ("NHPC Ltd", "Utilities", "Power"),
    "JSWENERGY": ("JSW Energy Ltd", "Utilities", "Power"),
    "GMRINFRA": ("GMR Airports Infrastructure Ltd", "Industrials", "Construction"),
    "VOLTAS": ("Voltas Ltd", "Industrials", "Industrials"),
    "ABB": ("ABB India Ltd", "Industrials", "Industrials"),
    "PEL": ("Piramal Enterprises Ltd", "Financials", "Capital Markets"),
    "MACPOWR": ("Macpower CNC Machines Ltd", "Industrials", "Industrials"),
}


def lookup_ticker(ticker: str) -> tuple[str, str, str] | None:
    ticker = ticker.upper().strip()
    return NIFTY_100.get(ticker)


def lookup_company(name: str) -> tuple[str, str, str, str] | None:
    """Fuzzy match company name to a ticker."""
    name_lower = name.lower().strip()
    best: tuple[str, str, str, str] | None = None
    best_score = 0.0
    for ticker, (cname, sector, industry) in NIFTY_100.items():
        cn_lower = cname.lower()
        if name_lower in cn_lower or cn_lower in name_lower:
            score = max(len(name_lower) / len(cn_lower), len(cn_lower) / len(name_lower))
            if score > best_score:
                best_score = score
                best = (ticker, cname, sector, industry)
    return best


def get_all_tickers() -> list[dict[str, str]]:
    return [
        {"ticker": t, "company_name": c, "sector": s, "industry": i}
        for t, (c, s, i) in NIFTY_100.items()
    ]
