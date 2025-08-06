#!/usr/bin/env python3
"""
Comprehensive test script for the stock screener application.
Tests CORS, API endpoints, request/response formats, and error handling.
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import traceback


class TestResult:
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.message = ""
        self.details = {}
        
    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        result = f"\n{status}: {self.test_name}"
        if self.message:
            result += f"\n   Message: {self.message}"
        if self.details:
            result += f"\n   Details: {json.dumps(self.details, indent=2)}"
        return result


class StockScreenerTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.results: List[TestResult] = []
        
    def add_result(self, result: TestResult):
        self.results.append(result)
        print(result)
        
    async def test_server_health(self) -> TestResult:
        """Test if the server is running and responsive."""
        result = TestResult("Server Health Check")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/") as response:
                    if response.status == 200:
                        data = await response.json()
                        result.passed = True
                        result.message = "Server is healthy"
                        result.details = data
                    else:
                        result.message = f"Server returned status {response.status}"
        except Exception as e:
            result.message = f"Failed to connect: {str(e)}"
        return result
        
    async def test_cors_headers(self) -> TestResult:
        """Test CORS headers for different origins."""
        result = TestResult("CORS Headers Test")
        test_origins = [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://34.125.88.131",
            "https://example.com"
        ]
        
        cors_results = {}
        
        try:
            for origin in test_origins:
                headers = {"Origin": origin}
                async with aiohttp.ClientSession() as session:
                    # Test OPTIONS request (preflight)
                    async with session.options(
                        f"{self.api_url}/screen",
                        headers=headers
                    ) as response:
                        cors_headers = {
                            "access-control-allow-origin": response.headers.get("access-control-allow-origin", "NOT SET"),
                            "access-control-allow-methods": response.headers.get("access-control-allow-methods", "NOT SET"),
                            "access-control-allow-headers": response.headers.get("access-control-allow-headers", "NOT SET"),
                            "access-control-allow-credentials": response.headers.get("access-control-allow-credentials", "NOT SET")
                        }
                        cors_results[origin] = {
                            "status": response.status,
                            "headers": cors_headers
                        }
                        
            # Check if all origins are allowed
            all_allowed = all(
                result["headers"]["access-control-allow-origin"] in ["*", origin]
                for origin, result in cors_results.items()
            )
            
            result.passed = all_allowed
            result.message = "CORS allows all origins" if all_allowed else "CORS restrictions found"
            result.details = cors_results
            
        except Exception as e:
            result.message = f"CORS test failed: {str(e)}"
            result.details = {"error": traceback.format_exc()}
            
        return result
        
    async def test_screen_endpoint_valid(self) -> TestResult:
        """Test the /screen endpoint with valid request."""
        result = TestResult("Screen Endpoint - Valid Request")
        
        # Valid request with new format
        request_data = {
            "filters": {
                "price_range": {"min": 50, "max": 200},
                "volume": {"min_average": 1000000},
                "price_change": {"min_percent": -5, "max_percent": 10},
                "market_cap": {"min_millions": 1000},
                "price_position": {"condition": "above_20_day_sma"}
            },
            "symbols": ["AAPL", "MSFT", "GOOGL"],
            "date_range": {
                "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end_date": datetime.now().strftime("%Y-%m-%d")
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/screen",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        
                        # Validate response structure
                        expected_fields = ["results", "total_results", "filters_applied", "date_range"]
                        has_all_fields = all(field in data for field in expected_fields)
                        
                        # Check if results have correct structure
                        if data.get("results"):
                            first_result = data["results"][0]
                            has_correct_structure = all(
                                field in first_result 
                                for field in ["symbol", "qualifying_dates", "metrics"]
                            )
                        else:
                            has_correct_structure = True  # No results is valid
                            
                        result.passed = has_all_fields and has_correct_structure
                        result.message = "Valid request processed successfully"
                        result.details = {
                            "status": response.status,
                            "total_results": data.get("total_results", 0),
                            "sample_result": data["results"][0] if data.get("results") else None
                        }
                    else:
                        result.message = f"Request failed with status {response.status}"
                        result.details = {
                            "status": response.status,
                            "response": response_text
                        }
                        
        except Exception as e:
            result.message = f"Request failed: {str(e)}"
            result.details = {"error": traceback.format_exc()}
            
        return result
        
    async def test_screen_endpoint_invalid(self) -> TestResult:
        """Test the /screen endpoint with invalid requests."""
        result = TestResult("Screen Endpoint - Invalid Request Handling")
        
        test_cases = [
            {
                "name": "Missing filters wrapper",
                "data": {
                    "price_range": {"min": 50, "max": 200}
                }
            },
            {
                "name": "Invalid filter structure",
                "data": {
                    "filters": {
                        "price_range": {"minimum": 50}  # Wrong field name
                    }
                }
            },
            {
                "name": "Invalid date format",
                "data": {
                    "filters": {},
                    "date_range": {
                        "start_date": "2024/01/01",  # Wrong format
                        "end_date": "2024/01/31"
                    }
                }
            }
        ]
        
        errors_handled_correctly = []
        
        try:
            for test_case in test_cases:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/screen",
                        json=test_case["data"],
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        # We expect 400 or 422 for validation errors
                        handled_correctly = response.status in [400, 422]
                        errors_handled_correctly.append({
                            "test": test_case["name"],
                            "status": response.status,
                            "handled_correctly": handled_correctly,
                            "response": await response.text()
                        })
                        
            result.passed = all(e["handled_correctly"] for e in errors_handled_correctly)
            result.message = "All invalid requests handled appropriately" if result.passed else "Some invalid requests not handled correctly"
            result.details = errors_handled_correctly
            
        except Exception as e:
            result.message = f"Error handling test failed: {str(e)}"
            result.details = {"error": traceback.format_exc()}
            
        return result
        
    async def test_public_ip_access(self) -> TestResult:
        """Test if the server would be accessible from public IP."""
        result = TestResult("Public IP Access Simulation")
        
        # Simulate request from public IP
        headers = {
            "Origin": "http://34.125.88.131",
            "X-Forwarded-For": "34.125.88.131",
            "Host": "34.125.88.131:8000"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/",
                    headers=headers
                ) as response:
                    cors_header = response.headers.get("access-control-allow-origin", "")
                    
                    # Check if CORS allows the public IP or all origins
                    allows_public = cors_header in ["*", "http://34.125.88.131"]
                    
                    result.passed = response.status == 200 and allows_public
                    result.message = "Public IP access allowed" if result.passed else "Public IP access restricted"
                    result.details = {
                        "status": response.status,
                        "cors_header": cors_header,
                        "allows_public_ip": allows_public
                    }
                    
        except Exception as e:
            result.message = f"Public IP test failed: {str(e)}"
            result.details = {"error": str(e)}
            
        return result
        
    async def test_response_format(self) -> TestResult:
        """Test the response format matches frontend expectations."""
        result = TestResult("Response Format Validation")
        
        # Minimal valid request
        request_data = {
            "filters": {}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/screen",
                    json=request_data
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check response format
                        checks = {
                            "has_results_array": isinstance(data.get("results"), list),
                            "has_total_results": isinstance(data.get("total_results"), int),
                            "has_filters_applied": isinstance(data.get("filters_applied"), dict),
                            "has_date_range": isinstance(data.get("date_range"), dict)
                        }
                        
                        # If there are results, check their structure
                        if data.get("results"):
                            first_result = data["results"][0]
                            checks.update({
                                "result_has_symbol": "symbol" in first_result,
                                "result_has_qualifying_dates": "qualifying_dates" in first_result,
                                "result_has_metrics": "metrics" in first_result
                            })
                            
                            # Check metrics structure
                            if "metrics" in first_result:
                                metrics = first_result["metrics"]
                                checks["metrics_has_average_price"] = "average_price" in metrics
                                checks["metrics_has_average_volume"] = "average_volume" in metrics
                                
                        result.passed = all(checks.values())
                        result.message = "Response format matches expectations" if result.passed else "Response format issues found"
                        result.details = checks
                        
                    else:
                        result.message = f"Request failed with status {response.status}"
                        result.details = {"response": await response.text()}
                        
        except Exception as e:
            result.message = f"Format validation failed: {str(e)}"
            result.details = {"error": traceback.format_exc()}
            
        return result
        
    async def run_all_tests(self):
        """Run all tests and generate summary."""
        print("\n" + "="*60)
        print("STOCK SCREENER COMPREHENSIVE TEST SUITE")
        print("="*60)
        print(f"Testing server at: {self.base_url}")
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run tests
        self.add_result(await self.test_server_health())
        
        # Only run other tests if server is healthy
        if self.results[0].passed:
            self.add_result(await self.test_cors_headers())
            self.add_result(await self.test_screen_endpoint_valid())
            self.add_result(await self.test_screen_endpoint_invalid())
            self.add_result(await self.test_public_ip_access())
            self.add_result(await self.test_response_format())
        
        # Generate summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFailed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  - {result.test_name}")
                    
        print("\n" + "="*60)
        
        return passed_tests == total_tests


async def main():
    """Main test execution."""
    tester = StockScreenerTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())