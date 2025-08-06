# UI Functionality Test Checklist

## Test Environment Setup
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Test Cases

### 1. Toggle Switch Functionality
- [ ] Toggle is OFF by default
- [ ] When OFF, custom symbols input is visible
- [ ] When ON, custom symbols input is hidden
- [ ] When ON, warning message is displayed
- [ ] Toggle state changes correctly when clicked

### 2. Custom Symbol Input (Toggle OFF)
- [ ] Input field accepts text
- [ ] Placeholder text is correct: "e.g., AAPL, MSFT, GOOGL (comma or space separated)"
- [ ] Help text is visible: "Leave empty to use default watchlist, or enter specific symbols"
- [ ] Input accepts comma-separated symbols
- [ ] Input accepts space-separated symbols

### 3. Warning Message (Toggle ON)
- [ ] Warning box is amber/yellow colored
- [ ] Warning icon is displayed
- [ ] Title reads: "Performance Notice"
- [ ] Message explains screening may take 30-60 seconds
- [ ] Warning is only visible when toggle is ON

### 4. Request Format Testing

#### When Toggle is OFF with custom symbols:
- Request should include: `"symbols": ["AAPL", "MSFT", "GOOGL"]`
- Request should include: `"use_all_us_stocks": false`

#### When Toggle is OFF with empty symbols:
- Request should NOT include symbols field
- Request should include: `"use_all_us_stocks": false`

#### When Toggle is ON:
- Request should NOT include symbols field
- Request should include: `"use_all_us_stocks": true`

### 5. Loading State
- [ ] When toggle is OFF: Button shows "Screening..."
- [ ] When toggle is ON: Button shows "Screening all US stocks..."
- [ ] Loading spinner is displayed
- [ ] UI is disabled during loading

### 6. Results Display
- [ ] Results show total symbols screened
- [ ] Results show execution time
- [ ] Results can be viewed by date or by stock
- [ ] Results can be filtered by symbol
- [ ] CSV export works correctly

### 7. Error Handling
- [ ] Validation errors are displayed properly
- [ ] Network errors are handled gracefully
- [ ] Timeout errors show appropriate message

## Visual Regression Tests

### 1. Light Theme
- [ ] Toggle switch is clearly visible
- [ ] Warning message has proper contrast
- [ ] All text is readable

### 2. Dark Theme
- [ ] Toggle switch adapts to dark theme
- [ ] Warning message adapts to dark theme
- [ ] All elements have proper contrast

## Performance Tests

### 1. With Specific Symbols (5-10 symbols)
- [ ] Response time < 5 seconds
- [ ] UI remains responsive

### 2. With All US Stocks
- [ ] Loading indicator shows progress
- [ ] Response time < 60 seconds
- [ ] No UI freezing or crashes
- [ ] Results load properly even with large datasets

## Integration Tests

### 1. Full Workflow - Specific Symbols
1. Enter symbols: AAPL, MSFT, GOOGL
2. Set date range (last 30 days)
3. Add volume filter (min 1M)
4. Click "Run Screener"
5. Verify results display correctly
6. Export CSV and verify format

### 2. Full Workflow - All US Stocks
1. Toggle "Screen All US Common Stocks" ON
2. Set date range (last 7 days)
3. Add strict filters (volume > 10M, price change > 5%)
4. Click "Run Screener"
5. Wait for completion
6. Verify results show 1000+ symbols screened
7. Export CSV and verify it contains results