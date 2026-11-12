"""Read Revolut transaction and multi-section PnL exports into a local snapshot."""

import argparse
from collections import defaultdict
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path


ZERO = Decimal('0')


def amount(text, currency):
    code, value = text.strip().split()
    if code != currency:
        raise ValueError(f'Unexpected currency {code}; expected {currency}')
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError('Non-finite money value')
    return number


def read_pnl(path):
    with open(path, newline='', encoding='utf-8-sig') as stream:
        return read_pnl_stream(stream)


def read_pnl_stream(stream):
    identities, sales = {}, []
    header = None
    for row in csv.reader(stream):
        if not row:
            header = None
            continue
        if row[0] in {'Date acquired', 'Date'} and 'ISIN' in row:
            header = row
            continue
        if header is None or len(row) != len(header):
            continue
        record = dict(zip(header, row))
        symbol, isin = record['Symbol'], record['ISIN']
        if symbol in identities and identities[symbol]['isin'] != isin:
            raise ValueError(f'Multiple ISINs for {symbol}; a dated identity map is required')
        if symbol not in identities or 'Date acquired' in record:
            identities[symbol] = {'isin': isin, 'name': html.unescape(record['Security name'])}
        if 'Date acquired' in record:
            sales.append(record)
    return identities, sales


def reconstruct(account_path, pnl_path):
    with open(account_path, newline='', encoding='utf-8-sig') as stream:
        transactions = list(csv.DictReader(stream))
    result = reconstruct_rows(transactions, *read_pnl(pnl_path))
    result['sources'] = [{'file': str(Path(p).resolve()), 'sha256': hashlib.sha256(Path(p).read_bytes()).hexdigest()}
                         for p in [account_path, pnl_path]]
    return result


def reconstruct_rows(transactions, identities, lots):
    if not transactions:
        raise ValueError('Empty account statement')
    transactions.sort(key=lambda row: datetime.fromisoformat(row['Date']))
    quantities, cash, totals = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
    last_trade, warnings, sales = {}, [], defaultdict(Decimal)
    for row in transactions:
        kind, ticker, currency = row['Type'], row['Ticker'], row['Currency']
        value = amount(row['Total Amount'], currency)
        totals[(kind, currency)] += value
        if kind in {'BUY - MARKET', 'SELL - MARKET'}:
            quantity = Decimal(row['Quantity'])
            price = amount(row['Price per share'], currency)
            if not quantity.is_finite() or quantity <= 0 or price <= 0 or value < 0:
                raise ValueError('Invalid trade')
            key = (ticker, currency)
            previous = last_trade.get(key)
            if previous and (price / previous['price'] > 3 or price / previous['price'] < Decimal('0.333')):
                warnings.append({'ticker': ticker, 'kind': 'large_trade_price_change',
                                 'date': row['Date'], 'quantity_held_before': str(quantities[key]),
                                 'previous_price': str(previous['price']), 'new_price': str(price)})
            direction = 1 if kind.startswith('BUY') else -1
            quantities[key] += direction * quantity
            cash[currency] -= direction * value
            if quantities[key] < 0:
                raise ValueError(f'Negative reconstructed holding for {ticker}; opening positions or corporate actions missing')
            last_trade[key] = {'price': price, 'date': row['Date']}
            if direction == -1:
                sales[(ticker, row['Date'][:10], currency)] += quantity
        elif kind in {'CASH TOP-UP', 'CASH WITHDRAWAL', 'ROBO MANAGEMENT FEE', 'DIVIDEND'}:
            cash[currency] += value
        else:
            raise ValueError(f'Unsupported transaction type: {kind}')
    pnl_sales = defaultdict(Decimal)
    pnl_total = defaultdict(Decimal)
    for lot in lots:
        pnl_sales[(lot['Symbol'], lot['Date sold'], lot['Currency'])] += Decimal(lot['Quantity'])
        pnl_total[lot['Currency']] += Decimal(lot['Gross PnL'])
    if set(pnl_sales) != set(sales) or any(abs(pnl_sales[k] - sales[k]) > Decimal('0.0000001') for k in sales):
        raise ValueError('Sales quantities do not reconcile between account and PnL statements')
    positions = []
    for (ticker, currency), quantity in sorted(quantities.items()):
        identity = identities.get(ticker, {})
        positions.append({'broker_ticker': ticker, 'quantity': str(quantity), 'currency': currency,
                          'open': quantity > 0, **identity,
                          'last_execution_price': str(last_trade[(ticker, currency)]['price']),
                          'last_execution_at': last_trade[(ticker, currency)]['date'],
                          'provider_mapping_status': 'unresolved'})
    return {'status': 'reconstructed_not_broker_balance_confirmed',
            'assumptions': ['Opening cash and holdings are zero', 'All trades and corporate actions affecting held positions are present'],
            'transaction_count': len(transactions), 'first_transaction': transactions[0]['Date'],
            'last_transaction': transactions[-1]['Date'], 'realized_pnl_lots': len(lots),
            'sale_quantities_reconciled': True, 'positions': positions,
            'cash': {k: str(v) for k, v in cash.items()},
            'realized_gross_pnl': {k: str(v) for k, v in pnl_total.items()},
            'totals': [{'type': k[0], 'currency': k[1], 'amount': str(v)} for k, v in totals.items()],
            'warnings': warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', required=True)
    parser.add_argument('--pnl', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = reconstruct(args.account, args.pnl)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(f"Imported {report['transaction_count']} transactions; {sum(p['open'] for p in report['positions'])} open positions; sales quantities reconcile")


if __name__ == '__main__':
    main()
