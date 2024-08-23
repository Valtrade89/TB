import time
import requests
import matplotlib.pyplot as plt
import numpy as np
from binance.um_futures import UMFutures
from tradingview_ta import TA_Handler, Interval
from io import BytesIO
from datetime import datetime, timedelta

INTERVAL = Interval.INTERVAL_4_HOURS
TELEGRAM_TOKEN = '7545760045:AAErtZzBR2-ACWQUt2c0BzWBpJuoo38In3A'
TELEGRAM_CHANNEL = '@valtrade19'

client = UMFutures()

# Хранение данных лонгов и шортов
data_storage = {
    'longs': [],
    'shorts': [],
    'timestamps': []
}

# Хранение данных о волатильности
volatility_storage = {
    'volatilities': [],
    'timestamps': []
}

def get_supported_symbols():
    try:
        exchange_info = client.exchange_info()
        symbols = [s['symbol'] for s in exchange_info['symbols'] if s['contractType'] == 'PERPETUAL']
        return symbols
    except Exception as e:
        print(f"Ошибка получения поддерживаемых символов: {e}")
        return []

def get_data(symbol):
    try:
        output = TA_Handler(
            symbol=symbol,
            screener='Crypto',
            exchange='Binance',
            interval=INTERVAL
        )
        analysis = output.get_analysis().summary
        analysis['SYMBOL'] = symbol
        return analysis
    except:
        pass

def get_funding_rate(symbol):
    try:
        funding_rates = client.funding_rate(symbol=symbol)
        if funding_rates:
            return float(funding_rates[0]['fundingRate']) * 100  # Преобразуем в проценты
    except:
        pass

def get_long_short_ratio(symbol, period='1h'):
    try:
        data = client.long_short_account_ratio(symbol=symbol, period=period)
        if data:
            ratio = data[-1]['longShortRatio']  # Получаем последнюю запись
            return float(ratio)
    except Exception as e:
        print(f"Ошибка получения коэффициента лонгов/шортов: {e}")
        return None

def send_message(text, image=None):
    try:
        if image:
            files = {'photo': image}
            requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto', params={
                'chat_id': TELEGRAM_CHANNEL
            }, files=files)
        else:
            requests.get(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage', params={
                'chat_id': TELEGRAM_CHANNEL,
                'text': text
            })
    except:
        pass

def plot_funding_rates(funding_rates):
    symbols = list(funding_rates.keys())
    rates = list(funding_rates.values())

    plt.figure(figsize=(45, 35))
    plt.bar(symbols, rates, color='skyblue')
    plt.xlabel('Symbol')
    plt.ylabel('Funding Rate (%)')
    plt.title('Funding Rates of Perpetual Contracts')
    plt.xticks(rotation=90)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

def calculate_long_short_ratio(longs, shorts):
    total_positions = len(longs) + len(shorts)
    if total_positions == 0:
        return 0, 0  # Чтобы избежать деления на ноль

    long_percentage = (len(longs) / total_positions) * 100
    short_percentage = (len(shorts) / total_positions) * 100

    return long_percentage, short_percentage

def first_data(symbols):
    longs = []
    shorts = []
    funding_rates = {}

    print('Поиск первых данных')
    send_message('Поиск первых данных')

    for symbol in symbols:
        try:
            data = get_data(symbol)
            if data is None:
                continue
            funding_rate = get_funding_rate(symbol)
            long_short_ratio = get_long_short_ratio(symbol)

            if data['RECOMMENDATION'] == 'STRONG_BUY':
                longs.append(
                    {'symbol': data['SYMBOL'], 'funding_rate': funding_rate, 'long_short_ratio': long_short_ratio})

            if data['RECOMMENDATION'] == 'STRONG_SELL':
                shorts.append(
                    {'symbol': data['SYMBOL'], 'funding_rate': funding_rate, 'long_short_ratio': long_short_ratio})

            if funding_rate is not None:
                funding_rates[symbol] = funding_rate

            time.sleep(0.01)
        except:
            pass

    print('Лонги:')
    print(longs)
    print('Шорты:')
    print(shorts)

    image = plot_funding_rates(funding_rates)
    send_message('Гистограмма ставок финансирования', image)

    return longs, shorts

def get_historical_klines(symbol, interval, limit=1000):
    try:
        klines = client.klines(symbol=symbol, interval=interval, limit=limit)
        return [(float(k[1]), float(k[4])) for k in klines]  # Возвращаем цены открытия и закрытия
    except Exception as e:
        print(f"Ошибка получения исторических данных: {e}")
        return None

def calculate_volatility(prices):
    log_returns = np.log(np.array(prices[1:]) / np.array(prices[:-1]))
    volatility = np.std(log_returns) * np.sqrt(len(prices))  # Annualized volatility
    return volatility

def check_volatility(symbols, threshold=0.25, alert_interval=3600):
    for symbol in symbols:
        try:
            data = get_historical_klines(symbol, INTERVAL, limit=100)
            if data is None:
                continue

            close_prices = [price[1] for price in data]
            volatility = calculate_volatility(close_prices)

            # Сохраняем данные о волатильности
            now = datetime.now()
            volatility_storage['volatilities'].append(volatility)
            volatility_storage['timestamps'].append(now)

            # Удаляем старые данные (больше часа)
            one_hour_ago = now - timedelta(hours=1)
            while volatility_storage['timestamps'] and volatility_storage['timestamps'][0] < one_hour_ago:
                volatility_storage['volatilities'].pop(0)
                volatility_storage['timestamps'].pop(0)

            # Проверка времени последнего предупреждения
            current_time = time.time()
            last_alert_time = last_volatility_alerts.get(symbol, 0)

            if volatility > threshold and (current_time - last_alert_time) > alert_interval:
                print(f"{symbol} High Volatility Alert")
                send_message(f"{symbol} ⚠️ High Volatility Alert!")
                last_volatility_alerts[symbol] = current_time

            time.sleep(3)
        except Exception as e:
            print(f"Ошибка расчета волатильности для {symbol}: {e}")

def analyze_volatility():
    if not volatility_storage['timestamps']:
        return 0  # Возвращаем 0, если нет данных
    
    avg_volatility = np.mean(volatility_storage['volatilities'])
    return avg_volatility

def store_data(longs, shorts):
    now = datetime.now()
    data_storage['longs'].append(longs)
    data_storage['shorts'].append(shorts)
    data_storage['timestamps'].append(now)

    # Удаляем старые данные (больше суток)
    one_day_ago = now - timedelta(days=1)
    while data_storage['timestamps'] and data_storage['timestamps'][0] < one_day_ago:
        data_storage['longs'].pop(0)
        data_storage['shorts'].pop(0)
        data_storage['timestamps'].pop(0)

print('Запуск')
send_message('Запуск')

supported_symbols = get_supported_symbols()
print(f"Поддерживаемые символы: {supported_symbols}")

symbols = supported_symbols[:1000]
longs, shorts = first_data(symbols)

# Инициализация времени для отправки сообщения о соотношении лонгов/шортов
last_ratio_time = time.time()
ratio_interval = 3600  # Сообщение о соотношении лонгов/шортов отправляется раз в час

# Инициализация словаря для отслеживания времени последнего предупреждения о волатильности
last_volatility_alerts = {}
volatility_interval = 3600  # Интервал проверки волатильности

while True:
    print('______________НОВЫЙ РАУНД____________')
    check_volatility(symbols)
    
    # Обновляем данные и храним их
    current_longs = []
    current_shorts = []

    for symbol in symbols:
        try:
            data = get_data(symbol)
            if data is None:
                continue
            funding_rate = get_funding_rate(symbol)
            long_short_ratio = get_long_short_ratio(symbol)

            if data['RECOMMENDATION'] == 'STRONG_BUY' and not any(l['symbol'] == symbol for l in current_longs):
                print(f"{symbol} Buy")
                text = f"{symbol} BUY 🟢 - Ставка финансирования: {funding_rate if funding_rate else 'N/A'}, Коэффициент лонгов/шортов: {long_short_ratio if long_short_ratio else 'N/A'}"
                send_message(text)
                current_longs.append({'symbol': symbol, 'funding_rate': funding_rate, 'long_short_ratio': long_short_ratio})

            if data['RECOMMENDATION'] == 'STRONG_SELL' and not any(s['symbol'] == symbol for s in current_shorts):
                print(f"{symbol} Sell")
                text = f"{symbol} SELL 🔴 - Ставка финансирования: {funding_rate if funding_rate else 'N/A'}, Коэффициент лонгов/шортов: {long_short_ratio if long_short_ratio else 'N/A'}"
                send_message(text)
                current_shorts.append({'symbol': symbol, 'funding_rate': funding_rate, 'long_short_ratio': long_short_ratio})

            time.sleep(0.1)
        except:
            pass

    # Сохраняем данные
    store_data(current_longs, current_shorts)

    # Проверка времени с момента последней отправки сообщения о соотношении лонгов/шортов
    if time.time() - last_ratio_time >= ratio_interval:
        long_percentage, short_percentage = calculate_long_short_ratio([l for l in data_storage['longs']], [s for s in data_storage['shorts']])
        ratio_message = f"Соотношение лонгов к шортам за последние 24 часа:\nЛонги: {long_percentage:.2f}%\nШорты: {short_percentage:.2f}%"
        send_message(ratio_message)
        last_ratio_time = time.time()

    # Проверка времени с момента последнего предупреждения о волатильности
    if time.time() - last_volatility_alerts.get(symbol, 0) >= volatility_interval:
        avg_volatility = analyze_volatility()
        volatility_message = f"Средняя волатильность за последние 60 минут: {avg_volatility:.2f}"
        send_message(volatility_message)

    time.sleep(0.1)
