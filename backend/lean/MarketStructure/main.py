# region imports
from AlgorithmImports import *
import json
from datetime import time, timedelta
import os
# endregion

class MarketStructureAlgorithm(QCAlgorithm):
    """
    Market Structure Break of Structure (BOS) Trading Algorithm
    
    Always-in-market reversal system using only the lower timeframe:
    - Tracks pivot highs/lows on the specified timeframe (e.g., 5-minute)
    - Updates pivot detection on each new bar
    - Goes LONG when price breaks above pivot highs
    - Goes SHORT when price breaks below pivot lows
    - Flips positions immediately on opposite signals
    - No stop losses or take profits - only exits to reverse position
    """
    
    def _log_debug(self, message):
        """Helper method to log debug messages with timestamp."""
        # self.debug(f"[{self.time}] {message}")
        pass
    
    def initialize(self):
        """Initialize the algorithm with parameters and symbol setup."""
        # self._log_debug("[INIT] MarketStructure algorithm starting initialization...")
        
        # Load parameters
        self._load_parameters()
        
        # Initialize data structures
        self.symbol_data = {}
        self.trading_symbols = []
        
        # Set zero fees for all securities
        self.set_security_initializer(lambda x: x.set_fee_model(ConstantFeeModel(0)))
        
        # Setup symbols
        self._setup_symbols()
        
        # Calculate equal allocation
        self.target_allocation = 1.0 / len(self.trading_symbols) if self.trading_symbols else 0
        
        # Time management
        self.no_entry_time = time(15, 59)  # No new entries after 3:59 PM
        self.liquidation_time = time(15, 59)  # Liquidate all positions at 3:59 PM
        
        # Set warm-up period for indicators
        self.set_warm_up(timedelta(days=2))
        
        self.log(f"MarketStructure initialized with {len(self.trading_symbols)} symbols, allocation: {self.target_allocation:.2%} each")
    
    def _load_parameters(self):
        """Load algorithm parameters from configuration."""
        # Allow callers to override the mapping file and pivot options
        self.symbol_mapping_file = self.get_parameter("symbol_mapping_file", "")

        pivot_values_param = self.get_parameter("pivot_values", "")
        if pivot_values_param:
            separators = [";", ",", "|"]
            raw_values = [pivot_values_param]
            for sep in separators:
                if sep in pivot_values_param:
                    raw_values = pivot_values_param.split(sep)
                    break
            try:
                self.pivot_options = [int(value.strip()) for value in raw_values if value.strip()]
            except ValueError:
                self.error(f"Invalid pivot_values parameter: {pivot_values_param}")
                self.pivot_options = [1, 2, 3, 5, 10, 20]
        else:
            self.pivot_options = [1, 2, 3, 5, 10, 20]

        # Dates and cash
        start_date = self.get_parameter("startDate", "20240101")
        end_date = self.get_parameter("endDate", "20241231")
        cash = float(self.get_parameter("cash", "100000"))
        
        # Log all parameters for debugging
        # self._log_debug(f"[PARAMS] startDate: {start_date}")
        # self._log_debug(f"[PARAMS] endDate: {end_date}")
        # self._log_debug(f"[PARAMS] cash: {cash}")
        
        self.set_start_date(int(start_date[:4]), int(start_date[4:6]), int(start_date[6:8]))
        self.set_end_date(int(end_date[:4]), int(end_date[4:6]), int(end_date[6:8]))
        self.set_cash(cash)
        
        # Strategy parameters
        pivot_slot_param = self.get_parameter("pivot_slot", None)
        if pivot_slot_param is not None:
            try:
                slot_index = int(float(pivot_slot_param))
            except ValueError:
                slot_index = 0
            slot_index = max(0, min(slot_index, len(self.pivot_options) - 1))
            self.pivot_bars = self.pivot_options[slot_index]
        else:
            default_pivot = str(self.pivot_options[-1]) if self.pivot_options else "20"
            self.pivot_bars = int(self.get_parameter("pivot_bars", default_pivot))
        self.use_screener_results = self.get_parameter("use_screener_results", "false").lower() == "true"
        self.screener_results_file = self.get_parameter("screener_results_file", "")
        
        # Log strategy parameters
        # self._log_debug(f"[PARAMS] pivot_bars: {self.pivot_bars}")
        # self._log_debug(f"[PARAMS] use_screener_results: {self.use_screener_results}")
        # self._log_debug(f"[PARAMS] screener_results_file: {self.screener_results_file}")
        
        # Timeframe parameters - only use lower timeframe
        lower_timeframe_str = self.get_parameter("lower_timeframe", "5min")
        self.lower_timeframe = self._parse_resolution(lower_timeframe_str)
        self.consolidator_minutes = self._get_timeframe_minutes(lower_timeframe_str)
        
        # Log timeframe parameters
        # self._log_debug(f"[PARAMS] lower_timeframe: {lower_timeframe_str} -> {self.lower_timeframe}")
        # self._log_debug(f"[PARAMS] consolidator_minutes: {self.consolidator_minutes}")
    
    def _parse_resolution(self, resolution_str):
        """Convert string resolution to LEAN Resolution enum."""
        resolution_map = {
            "1min": Resolution.MINUTE,
            "5min": Resolution.MINUTE,  # Will use consolidator
            "15min": Resolution.MINUTE,  # Will use consolidator
            "30min": Resolution.MINUTE,  # Will use consolidator
            "1hour": Resolution.HOUR,
            "hour": Resolution.HOUR,
            "daily": Resolution.DAILY,
            "day": Resolution.DAILY
        }
        return resolution_map.get(resolution_str.lower(), Resolution.MINUTE)
    
    def _get_timeframe_minutes(self, timeframe_str):
        """Get the number of minutes for consolidator based on timeframe string."""
        timeframe_minutes = {
            "1min": 1,
            "5min": 5,
            "15min": 15,
            "30min": 30,
            "1hour": 60,
            "hour": 60
        }
        return timeframe_minutes.get(timeframe_str.lower(), 5)
    
    def _load_symbol_mapping(self):
        """Load the symbol mapping from the data directory."""
        try:
            candidate_paths = []
            if getattr(self, "symbol_mapping_file", None):
                candidate_paths.append(self.symbol_mapping_file)

            candidate_paths.extend([
                "/data/symbol_mapping.json",
                os.path.join(os.path.dirname(__file__), "symbol_mapping.json"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "symbol_mapping.json")
            ])

            data_path = next((path for path in candidate_paths if path and os.path.exists(path)), None)

            if not data_path:
                raise FileNotFoundError("symbol_mapping.json not found")

            with open(data_path, 'r') as f:
                mapping_data = json.load(f)
                return mapping_data.get("index_to_symbol", {})
        except Exception as e:
            self.error(f"Failed to load symbol mapping: {str(e)}")
            raise
    
    def _setup_symbols(self):
        """Setup trading symbols from parameters or screener results."""
        # self._log_debug("[SETUP] Starting symbol setup...")
        symbols = []
        
        # Load symbol mapping
        self.symbol_mapping = self._load_symbol_mapping()
        
        if self.use_screener_results and self.screener_results_file:
            # Load symbols from screener results
            # self._log_debug(f"[SETUP] Loading symbols from screener file: {self.screener_results_file}")
            symbols = self._load_screener_symbols()
        else:
            # Load symbol indices from parameter
            symbol_indices_param = self.get_parameter("symbol_indices", "0")  # Default to index 0 (SPY)
            
            # Parse indices (can be comma-separated)
            indices = []
            for idx_str in symbol_indices_param.split(","):
                try:
                    # Convert float to int (for LEAN optimize compatibility)
                    idx = str(int(float(idx_str.strip())))
                    indices.append(idx)
                except ValueError:
                    self.error(f"Invalid symbol index: {idx_str}")
            
            # Convert indices to symbols
            for idx in indices:
                if idx in self.symbol_mapping:
                    symbols.append(self.symbol_mapping[idx])
                    self.debug(f"Index {idx} mapped to symbol: {self.symbol_mapping[idx]}")
                else:
                    self.error(f"Symbol index {idx} not found in mapping")
            
            # self._log_debug(f"[SETUP] Using symbols from indices: {indices} -> {symbols}")
        
        # Add symbols with minute resolution (base resolution)
        for symbol in symbols[:20]:  # Limit to 20 symbols for performance
            try:
                equity = self.add_equity(symbol, Resolution.MINUTE)
                sym = equity.symbol
                self.trading_symbols.append(sym)
                
                # Create symbol data
                data = SymbolData(sym, self.pivot_bars)
                
                # Setup indicators and consolidators
                self._setup_indicators(data)
                
                self.symbol_data[sym] = data
                
                # self._log_debug(f"[SETUP] Successfully added symbol: {symbol} with pivot detection")
            except Exception as e:
                self.log(f"Failed to add symbol {symbol}: {str(e)}")
    
    def _setup_indicators(self, data):
        """Setup consolidator for the specified timeframe."""
        # Note: We're using manual pivot detection instead of PivotPointsHighLow indicator
        # for better control and debugging
        
        # Setup consolidator for the specified timeframe (e.g., 5-minute)
        if self.consolidator_minutes > 1:
            consolidator = TradeBarConsolidator(timedelta(minutes=self.consolidator_minutes))
            consolidator.data_consolidated += lambda sender, bar: self._on_consolidated_bar(data, bar)
            self.subscription_manager.add_consolidator(data.symbol, consolidator)
            # self._log_debug(f"[SETUP] Added {self.consolidator_minutes}-minute consolidator for {data.symbol}")
        else:
            # For 1-minute, we'll use the regular OnData updates
            # self._log_debug(f"[SETUP] Using 1-minute bars directly for {data.symbol}")
            pass
    
    def _on_consolidated_bar(self, data, bar):
        """Handle consolidated bar updates for the specified timeframe."""
        # Track bars processed
        data.bars_processed += 1
        
        # Log the bar data for debugging
        # self._log_debug(f"[UPDATE] {data.symbol}: Bar #{data.bars_processed} - High: {bar.high}, Low: {bar.low}, Close: {bar.close}")
        
        # Always update pivot levels, even during warm-up
        self._update_pivot_levels(data, bar)
        
        # Skip trading logic during warm-up
        if self.is_warming_up:
            # self._log_debug(f"[WARMUP] {data.symbol}: Accumulating data during warm-up, bar #{data.bars_processed}")
            return
        
        # Check if it's time to liquidate all positions
        if self.time.time() >= self.liquidation_time:
            self._liquidate_all_positions()
            return
        
        # Check for break of structure on each new bar
        self._check_break_of_structure(data, bar.close)
        
        # Manage existing positions
        self._manage_position(data, bar.close)
        
        # self._log_debug(f"[BAR] {data.symbol} - Close: {bar.close}, High: {bar.high}, Low: {bar.low}")
        # self._log_debug(f"[PIVOTS] {data.symbol} - Last High: {data.last_pivot_high}, Last Low: {data.last_pivot_low}")
        
        # Log BOS check status
        # if data.last_pivot_high > 0:
        #     self._log_debug(f"[BOS CHECK] {data.symbol} - Price {bar.close} vs High Pivot {data.last_pivot_high} = {'ABOVE' if bar.close > data.last_pivot_high else 'BELOW'}")
    
    def _update_pivot_levels(self, data, bar):
        """Update pivot high/low levels using manual detection."""
        # Add current bar to history
        data.high_history.append(bar.high)
        data.low_history.append(bar.low)
        data.close_history.append(bar.close)
        
        # Keep only required bars
        max_size = 2 * self.pivot_bars + 1
        if len(data.high_history) > max_size:
            data.high_history.pop(0)
            data.low_history.pop(0)
            data.close_history.pop(0)
        
        # Check if we have enough bars
        if len(data.high_history) < max_size:
            # self._log_debug(f"[PIVOT] {data.symbol}: Need {max_size - len(data.high_history)} more bars for pivot detection")
            return
        
        # Check for pivot at the middle position
        middle_idx = self.pivot_bars
        
        # Check for pivot high
        middle_high = data.high_history[middle_idx]
        is_pivot_high = all(data.high_history[i] <= middle_high for i in range(len(data.high_history)) if i != middle_idx)
        
        if is_pivot_high and middle_high != data.last_pivot_high:
            data.last_pivot_high = middle_high
            data.pivot_high_time = self.time
            # self._log_debug(f"[PIVOT] {data.symbol}: New Pivot High detected at {middle_high}")
        
        # Check for pivot low
        middle_low = data.low_history[middle_idx]
        is_pivot_low = all(data.low_history[i] >= middle_low for i in range(len(data.low_history)) if i != middle_idx)
        
        if is_pivot_low and middle_low != data.last_pivot_low:
            data.last_pivot_low = middle_low
            data.pivot_low_time = self.time
            # self._log_debug(f"[PIVOT] {data.symbol}: New Pivot Low detected at {middle_low}")
    
    def _load_screener_symbols(self):
        """Load symbols from screener results file."""
        symbols = []
        
        try:
            if self.screener_results_file and os.path.exists(self.screener_results_file):
                with open(self.screener_results_file, 'r') as f:
                    results = json.load(f)
                    
                # Extract symbols
                if "symbols" in results:
                    symbols = results["symbols"]
                    self.log(f"Loaded {len(symbols)} symbols from screener results")
        except Exception as e:
            self.log(f"Error loading screener results: {str(e)}")
        
        # Default to SPY if no symbols loaded
        if not symbols:
            symbols = ["SPY"]
        
        return symbols
    
    def on_data(self, data):
        """Process incoming data and check for trading signals."""
        # For 1-minute timeframe, process bars directly
        if self.consolidator_minutes == 1:
            for symbol, symbol_data in self.symbol_data.items():
                if not data.bars.contains_key(symbol):
                    continue
                
                bar = data.bars[symbol]
                
                # Track bars processed
                symbol_data.bars_processed += 1
                
                # Log the bar data for debugging
                # self._log_debug(f"[UPDATE] {symbol}: Bar #{symbol_data.bars_processed} - High: {bar.high}, Low: {bar.low}, Close: {bar.close}")
                
                # Always update pivot levels, even during warm-up
                self._update_pivot_levels(symbol_data, bar)
                
                # Skip trading logic during warm-up
                if self.is_warming_up:
                    # self._log_debug(f"[WARMUP] {symbol}: Accumulating data during warm-up, bar #{symbol_data.bars_processed}")
                    continue
                
                # Check if it's time to liquidate all positions
                if self.time.time() >= self.liquidation_time:
                    self._liquidate_all_positions()
                    return
                
                # Check for break of structure
                self._check_break_of_structure(symbol_data, bar.close)
                
                # Manage existing positions
                self._manage_position(symbol_data, bar.close)
                
                # self._log_debug(f"[1MIN BAR] {symbol} - Close: {bar.close}, High: {bar.high}, Low: {bar.low}")
                # self._log_debug(f"[PIVOTS] {symbol} - Last High: {symbol_data.last_pivot_high}, Last Low: {symbol_data.last_pivot_low}")
                
                # Log BOS check status
                # if symbol_data.last_pivot_high > 0:
                #     self._log_debug(f"[BOS CHECK] {symbol} - Price {bar.close} vs High Pivot {symbol_data.last_pivot_high} = {'ABOVE' if bar.close > symbol_data.last_pivot_high else 'BELOW'}")
    
    def _check_break_of_structure(self, data, price):
        """Check for Break of Structure (BOS) signals and flip positions."""
        # Don't enter new positions close to market close
        if self.time.time() >= self.no_entry_time:
            return
        
        # Bullish BOS: Price breaks above pivot high - go long
        if data.last_pivot_high > 0 and price > data.last_pivot_high:
            # Only act if we're not already long
            if not data.is_long or not data.has_position:
                # self._log_debug(f"[BOS] {data.symbol} - BULLISH BREAK! Price {price} > Pivot High {data.last_pivot_high}")
                data.current_trend = TrendDirection.BULLISH
                data.last_bos_time = self.time
                
                # Close short position if exists
                if data.has_position and not data.is_long:
                    self.liquidate(data.symbol)
                    data.reset_position()
                    self.log(f"Closed Short: {data.symbol} at ${price:.2f} - Flipping to Long")
                
                # Enter long
                self._on_bullish_bos(data, price)
        
        # Bearish BOS: Price breaks below pivot low - go short
        elif data.last_pivot_low > 0 and price < data.last_pivot_low:
            # Only act if we're not already short
            if data.is_long or not data.has_position:
                # self._log_debug(f"[BOS] {data.symbol} - BEARISH BREAK! Price {price} < Pivot Low {data.last_pivot_low}")
                data.current_trend = TrendDirection.BEARISH
                data.last_bos_time = self.time
                
                # Close long position if exists
                if data.has_position and data.is_long:
                    self.liquidate(data.symbol)
                    data.reset_position()
                    self.log(f"Closed Long: {data.symbol} at ${price:.2f} - Flipping to Short")
                
                # Enter short
                self._on_bearish_bos(data, price)
    
    def _on_bullish_bos(self, data, price):
        """Handle bullish break of structure signal."""
        if not self.portfolio[data.symbol].invested:
            quantity = self._calculate_position_size(data.symbol, price)
            if quantity > 0:
                self.market_order(data.symbol, quantity)
                
                data.has_position = True
                data.is_long = True
                data.entry_price = price
                data.entry_time = self.time
                
                self.log(f"BOS Long Entry: {data.symbol} at ${price:.2f}")
    
    def _on_bearish_bos(self, data, price):
        """Handle bearish break of structure signal."""
        if not self.portfolio[data.symbol].invested:
            quantity = -self._calculate_position_size(data.symbol, price)
            if quantity < 0:
                self.market_order(data.symbol, quantity)
                
                data.has_position = True
                data.is_long = False
                data.entry_price = price
                data.entry_time = self.time
                
                self.log(f"BOS Short Entry: {data.symbol} at ${price:.2f}")
    
    def _manage_position(self, data, price):
        """Manage existing positions - no stops, only position flipping."""
        # This method is now empty as we only exit on opposite signals
        # Position management is handled in _check_break_of_structure
        pass
    
    def _calculate_position_size(self, symbol, price):
        """Calculate position size based on equal allocation."""
        target_value = self.portfolio.total_portfolio_value * self.target_allocation
        quantity = int(target_value / price)
        
        # Ensure we don't exceed available buying power
        max_quantity = int(self.portfolio.margin_remaining / price) * 0.95
        
        return min(quantity, max_quantity)
    
    def _liquidate_all_positions(self):
        """Liquidate all positions and cancel all orders at market close."""
        # Cancel all open orders
        self.transactions.cancel_open_orders()
        
        # Liquidate all positions
        liquidated_symbols = []
        for symbol, symbol_data in self.symbol_data.items():
            if self.portfolio[symbol].invested:
                self.liquidate(symbol)
                symbol_data.reset_position()
                liquidated_symbols.append(symbol.value)
        
        if liquidated_symbols:
            self.log(f"Market close (15:59): Liquidated all positions for {', '.join(liquidated_symbols)}")
        
        # Log once per day that we've hit liquidation time
        if not hasattr(self, '_last_liquidation_date') or self._last_liquidation_date != self.time.date():
            self._last_liquidation_date = self.time.date()
            self.log("Market close (15:59): All positions liquidated, all orders cancelled")
    
    def on_end_of_algorithm(self):
        """Log final statistics when algorithm ends."""
        self.log(f"Algorithm completed. Final Portfolio Value: ${self.portfolio.total_portfolio_value:.2f}")
        
        # Count trades
        total_trades = sum(1 for order in self.transactions.get_orders() if order.status == OrderStatus.FILLED)
        self.log(f"Total Trades: {total_trades}")


class SymbolData:
    """Container for symbol-specific data and indicators."""
    
    def __init__(self, symbol, pivot_bars):
        self.symbol = symbol
        
        # Pivot indicator
        self.pivot_indicator = None
        
        # Pivot tracking
        self.last_pivot_high = 0
        self.last_pivot_low = 0
        self.bars_processed = 0
        
        # Bar history for manual pivot detection
        self.high_history = []
        self.low_history = []
        self.close_history = []
        self.pivot_high_time = None
        self.pivot_low_time = None
        
        # Market structure
        self.current_trend = TrendDirection.NEUTRAL
        self.last_bos_time = None
        
        # Position management
        self.has_position = False
        self.is_long = False
        self.entry_price = 0
        self.entry_time = None
    
    def reset_position(self):
        """Reset position-related fields."""
        self.has_position = False
        self.is_long = False
        self.entry_price = 0
        self.entry_time = None


class TrendDirection:
    """Enumeration for trend direction."""
    NEUTRAL = 0
    BULLISH = 1
    BEARISH = 2
