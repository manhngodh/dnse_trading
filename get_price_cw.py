from vnstock import Vnstock

try:
    stock = Vnstock().stock(symbol='CHPG2602', source='VCI')
    quote = stock.quote.now()
    print(quote)
except Exception as e:
    print(f"Error: {e}")
