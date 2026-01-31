
import unittest
import time
from collections import deque
from decimal import Decimal
from typing import Optional, Tuple, Deque

# COPY OF THE CLASS TO BE TESTED (To avoid import issues in this environment)
class RollingPriceChannel:
    """Maintains a rolling window of prices to calculate High/Low."""
    def __init__(self, window_seconds: float):
        self.window_seconds = window_seconds
        self.prices: Deque = deque() # Stores (timestamp, price)
        self.high: Optional[Decimal] = None
        self.low: Optional[Decimal] = None

    def add_price(self, price: Decimal, timestamp: float):
        """Add a new price observation."""
        self.prices.append((timestamp, price))
        self._prune(timestamp)
        self._recalculate()

    def _prune(self, current_time: float):
        """Remove old prices outside the window."""
        cutoff = current_time - self.window_seconds
        while self.prices and self.prices[0][0] < cutoff:
            self.prices.popleft()

    def _recalculate(self):
        """Recalculate High/Low from current window."""
        if not self.prices:
            self.high = None
            self.low = None
            return

        # Optimization: We could be smarter than O(N) here, but for simple bot usually fine
        # unless tick density is massive.
        prices = [p for _, p in self.prices]
        self.high = max(prices)
        self.low = min(prices)

    def is_ready(self) -> bool:
        """
        Check if we have enough data to form a 'valid' channel.
        For this implementation, we consider it valid as soon as we have data,
        but user should know it expands over time.
        """
        return bool(self.prices)

    @property
    def channel(self) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        return self.high, self.low

class TestRollingPriceChannel(unittest.TestCase):
    def test_rolling_logic(self):
        # Window of 10 seconds
        channel = RollingPriceChannel(window_seconds=10)
        
        now = 1000.0 # Mock time
        
        # 1. Add first price (10)
        channel.add_price(Decimal("10"), now)
        self.assertEqual(channel.channel, (Decimal("10"), Decimal("10")))
        
        # 2. Add higher price (20) 5 seconds later
        now += 5
        channel.add_price(Decimal("20"), now)
        self.assertEqual(channel.channel, (Decimal("20"), Decimal("10")))
        
        # 3. Add lower price (5) 2 seconds later (Time = 1007)
        now += 2
        channel.add_price(Decimal("5"), now)
        # Window is [997, 1007]. Contains: 10, 20, 5
        self.assertEqual(channel.channel, (Decimal("20"), Decimal("5")))
        
        # 4. Advance time to 1012 (First point '10' at 1000 expires)
        # Window is [1002, 1012].
        # 10 at 1000: EXPIRED
        # 20 at 1005: KEPT
        # 5 at 1007: KEPT
        # New: 15 at 1012
        now = 1012.0
        channel.add_price(Decimal("15"), now)
        
        # Expected: Max=20, Min=5
        self.assertEqual(channel.channel, (Decimal("20"), Decimal("5")))
        
        # 5. Advance to 1016. Cutoff 1006.
        # 20 at 1005: EXPIRED
        # 5 at 1007: KEPT
        # 15 at 1012: KEPT
        # New: 18 at 1016
        now = 1016.0
        channel.add_price(Decimal("18"), now)
        
        # Expected: Points are 5, 15, 18. Max=18, Min=5
        self.assertEqual(channel.channel, (Decimal("18"), Decimal("5")))
        
        # 6. Advance to 1030. All expired.
        # New: 25
        now = 1030.0
        channel.add_price(Decimal("25"), now)
        self.assertEqual(channel.channel, (Decimal("25"), Decimal("25")))

if __name__ == '__main__':
    unittest.main()
