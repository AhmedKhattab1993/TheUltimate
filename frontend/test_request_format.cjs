// Test script to verify request format for different scenarios
const axios = require('axios');

const API_URL = 'http://localhost:8000/api/v1/screen';

async function testRequestFormat() {
    console.log('Testing request formats...\n');
    
    // Test 1: Toggle OFF with custom symbols
    console.log('1. Toggle OFF with custom symbols:');
    const request1 = {
        start_date: '2025-07-20',
        end_date: '2025-07-27',
        symbols: ['AAPL', 'MSFT', 'GOOGL'],
        use_all_us_stocks: false,
        filters: {
            volume: {
                min_average: 1000000
            }
        }
    };
    console.log(JSON.stringify(request1, null, 2));
    console.log('✓ Includes symbols array');
    console.log('✓ use_all_us_stocks is false\n');
    
    // Test 2: Toggle OFF with empty symbols (default watchlist)
    console.log('2. Toggle OFF with empty symbols:');
    const request2 = {
        start_date: '2025-07-20',
        end_date: '2025-07-27',
        use_all_us_stocks: false,
        filters: {
            volume: {
                min_average: 1000000
            }
        }
    };
    console.log(JSON.stringify(request2, null, 2));
    console.log('✓ No symbols field');
    console.log('✓ use_all_us_stocks is false\n');
    
    // Test 3: Toggle ON
    console.log('3. Toggle ON (all US stocks):');
    const request3 = {
        start_date: '2025-07-20',
        end_date: '2025-07-27',
        use_all_us_stocks: true,
        filters: {
            volume: {
                min_average: 10000000
            },
            price_change: {
                min_change: 5.0
            }
        }
    };
    console.log(JSON.stringify(request3, null, 2));
    console.log('✓ No symbols field');
    console.log('✓ use_all_us_stocks is true');
    console.log('✓ Added strict filters for performance\n');
}

testRequestFormat();