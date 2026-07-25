#!/usr/bin/env python3

import requests
from typing import List, Dict, Optional


class CoinMarketCapFetcher:
    """
    Fetch top gainers/losers from CoinMarketCap.

    Uses the public API (no key required for basic data).
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def get_trending_gainers_losers(self, limit: int = 20) -> Dict[str, List[Dict]]:
        """
        Get top gainers and losers from CoinMarketCap.

        Returns:
            Dict with 'gainers' and 'losers' lists containing:
            - symbol: Coin symbol
            - name: Coin name
            - price: Current price
            - change_24h: 24h % change
            - volume_24h: 24h volume
            - market_cap: Market cap
        """
        try:
            # CoinMarketCap API endpoint for trending coins
            url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/spotlight"

            print(f"   🌐 GET {url}")

            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            gainers = []
            losers = []

            # Extract gainers
            if 'data' in data and 'trendingList' in data['data']:
                for item in data['data']['trendingList'][:limit]:
                    if 'priceChange' in item and 'quotes' in item:
                        quote = item['quotes'][0] if item['quotes'] else {}

                        coin_data = {
                            'symbol': item.get('symbol', ''),
                            'name': item.get('name', ''),
                            'price': quote.get('price', 0),
                            'change_24h': quote.get('percentChange24h', 0),
                            'volume_24h': quote.get('volume24h', 0),
                            'market_cap': quote.get('marketCap', 0),
                            'source': 'coinmarketcap'
                        }

                        if coin_data['change_24h'] > 0:
                            gainers.append(coin_data)
                        else:
                            losers.append(coin_data)

            # Sort by absolute change
            gainers.sort(key=lambda x: x['change_24h'], reverse=True)
            losers.sort(key=lambda x: x['change_24h'])

            return {
                'gainers': gainers[:10],
                'losers': losers[:10],
                'timestamp': data.get('status', {}).get('timestamp', '')
            }

        except Exception as e:
            print(f"[ERROR] Failed to fetch CoinMarketCap data: {str(e)}")
            return {'gainers': [], 'losers': [], 'timestamp': ''}

    def get_top_movers(self) -> Dict[str, List[Dict]]:
        """
        Alternative method using CoinMarketCap's listings API.
        """
        try:
            url = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"
            params = {
                'start': 1,
                'limit': 100,
                'sortBy': 'percent_change_24h',
                'sortType': 'desc',
                'convert': 'USD'
            }

            full_url = f"{url}?start={params['start']}&limit={params['limit']}&sortBy={params['sortBy']}"
            print(f"   🌐 GET {full_url}")

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            gainers = []
            losers = []

            if 'data' in data and 'cryptoCurrencyList' in data['data']:
                for item in data['data']['cryptoCurrencyList']:
                    quote = item.get('quotes', [{}])[0]

                    coin_data = {
                        'symbol': item.get('symbol', ''),
                        'name': item.get('name', ''),
                        'price': quote.get('price', 0),
                        'change_24h': quote.get('percentChange24h', 0),
                        'volume_24h': quote.get('volume24h', 0),
                        'market_cap': quote.get('marketCap', 0),
                        'source': 'coinmarketcap'
                    }

                    if coin_data['change_24h'] > 5.0:  # Significant gainers
                        gainers.append(coin_data)
                    elif coin_data['change_24h'] < -5.0:  # Significant losers
                        losers.append(coin_data)

            return {
                'gainers': gainers[:15],
                'losers': losers[:15]
            }

        except Exception as e:
            print(f"[ERROR] Failed to fetch CoinMarketCap top movers: {str(e)}")
            return {'gainers': [], 'losers': []}
