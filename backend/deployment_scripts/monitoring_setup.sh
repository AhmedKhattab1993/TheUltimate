#!/bin/bash

# Monitoring Setup Script for Enhanced Backtest System
# Sets up monitoring and alerting for production deployment

set -e

echo "=== MONITORING SETUP FOR ENHANCED BACKTEST SYSTEM ==="
echo "Timestamp: $(date)"

# Create monitoring directory
MONITOR_DIR="/home/ahmed/TheUltimate/backend/monitoring"
mkdir -p "$MONITOR_DIR"
mkdir -p "$MONITOR_DIR/logs"
mkdir -p "$MONITOR_DIR/alerts"

# 1. Database Performance Monitor
echo ""
echo "1. Setting up database performance monitoring..."
cat > "$MONITOR_DIR/db_performance_monitor.py" << 'EOF'
#!/usr/bin/env python3
"""
Database Performance Monitor for Enhanced Backtest System
Monitors query performance, index usage, and table statistics
"""

import asyncio
import asyncpg
import json
import os
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ahmed/TheUltimate/backend/monitoring/logs/db_performance.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseMonitor:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/stock_screener')
        
    async def check_performance(self):
        """Check database performance metrics"""
        try:
            conn = await asyncpg.connect(self.db_url)
            
            # Query performance stats
            query_stats = await conn.fetch('''
                SELECT query, mean_time, calls, total_time 
                FROM pg_stat_statements 
                WHERE query LIKE '%market_structure_results%' 
                ORDER BY mean_time DESC
                LIMIT 10
            ''')
            
            # Index usage stats
            index_stats = await conn.fetch('''
                SELECT indexname, idx_tup_read, idx_tup_fetch 
                FROM pg_stat_user_indexes 
                WHERE relname = 'market_structure_results'
            ''')
            
            # Table size and record count
            table_stats = await conn.fetchrow('''
                SELECT 
                    pg_size_pretty(pg_total_relation_size('market_structure_results')) as table_size,
                    COUNT(*) as record_count
                FROM market_structure_results
            ''')
            
            # Recent query performance
            recent_performance = await conn.fetchrow('''
                SELECT 
                    AVG(execution_time_ms) as avg_execution_time,
                    MAX(execution_time_ms) as max_execution_time,
                    COUNT(*) as recent_backtests
                FROM market_structure_results 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            ''')
            
            await conn.close()
            
            # Log results
            logger.info(f"Table Stats: {table_stats['record_count']} records, {table_stats['table_size']}")
            logger.info(f"Recent Performance: Avg {recent_performance['avg_execution_time']}ms, Max {recent_performance['max_execution_time']}ms")
            
            # Check for performance issues
            if recent_performance['avg_execution_time'] and recent_performance['avg_execution_time'] > 5000:
                logger.warning(f"High average execution time: {recent_performance['avg_execution_time']}ms")
                
            if recent_performance['max_execution_time'] and recent_performance['max_execution_time'] > 30000:
                logger.error(f"Very high max execution time: {recent_performance['max_execution_time']}ms")
            
            return {
                'table_stats': dict(table_stats),
                'recent_performance': dict(recent_performance),
                'index_count': len(index_stats),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database monitoring failed: {e}")
            return None
    
    async def check_cache_performance(self):
        """Check cache hit rates and effectiveness"""
        try:
            conn = await asyncpg.connect(self.db_url)
            
            # Cache hit rate
            cache_stats = await conn.fetchrow('''
                SELECT 
                    COUNT(*) as total_backtests,
                    COUNT(*) FILTER (WHERE cache_hit = true) as cache_hits,
                    ROUND(
                        (COUNT(*) FILTER (WHERE cache_hit = true)::decimal / COUNT(*)) * 100, 2
                    ) as cache_hit_rate
                FROM market_structure_results 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            ''')
            
            await conn.close()
            
            cache_hit_rate = cache_stats['cache_hit_rate'] or 0
            logger.info(f"Cache Performance: {cache_hit_rate}% hit rate ({cache_stats['cache_hits']}/{cache_stats['total_backtests']})")
            
            # Alert on low cache hit rate
            if cache_hit_rate < 40:
                logger.warning(f"Low cache hit rate: {cache_hit_rate}%")
            
            return dict(cache_stats)
            
        except Exception as e:
            logger.error(f"Cache monitoring failed: {e}")
            return None

async def main():
    monitor = DatabaseMonitor()
    
    # Run performance checks
    perf_stats = await monitor.check_performance()
    cache_stats = await monitor.check_cache_performance()
    
    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'performance': perf_stats,
        'cache': cache_stats
    }
    
    with open('/home/ahmed/TheUltimate/backend/monitoring/logs/performance_metrics.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("Performance monitoring completed")

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x "$MONITOR_DIR/db_performance_monitor.py"

# 2. API Health Monitor
echo ""
echo "2. Setting up API health monitoring..."
cat > "$MONITOR_DIR/api_health_monitor.py" << 'EOF'
#!/usr/bin/env python3
"""
API Health Monitor for Enhanced Backtest System
Monitors API endpoint response times and availability
"""

import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ahmed/TheUltimate/backend/monitoring/logs/api_health.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class APIMonitor:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.endpoints = [
            "/health",
            "/api/v1/backtest/results?limit=5",
            "/api/v1/backtest/strategies",
            "/api/v1/screener/results?limit=5"
        ]
    
    async def check_endpoint(self, session, endpoint):
        """Check single endpoint health and response time"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response_time = (time.time() - start_time) * 1000
                status = response.status
                
                if status == 200:
                    logger.info(f"✅ {endpoint}: {response_time:.0f}ms")
                    return {
                        'endpoint': endpoint,
                        'status': 'healthy',
                        'response_time_ms': response_time,
                        'http_status': status
                    }
                else:
                    logger.warning(f"⚠️  {endpoint}: HTTP {status}, {response_time:.0f}ms")
                    return {
                        'endpoint': endpoint,
                        'status': 'warning',
                        'response_time_ms': response_time,
                        'http_status': status
                    }
                    
        except asyncio.TimeoutError:
            logger.error(f"❌ {endpoint}: Timeout")
            return {
                'endpoint': endpoint,
                'status': 'timeout',
                'response_time_ms': 10000,
                'http_status': 0
            }
        except Exception as e:
            logger.error(f"❌ {endpoint}: {str(e)}")
            return {
                'endpoint': endpoint,
                'status': 'error',
                'response_time_ms': 0,
                'http_status': 0,
                'error': str(e)
            }
    
    async def check_all_endpoints(self):
        """Check all API endpoints"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.check_endpoint(session, endpoint) for endpoint in self.endpoints]
            results = await asyncio.gather(*tasks)
            
            # Calculate overall health
            healthy_count = sum(1 for r in results if r['status'] == 'healthy')
            total_count = len(results)
            health_percentage = (healthy_count / total_count) * 100
            
            avg_response_time = sum(r['response_time_ms'] for r in results if r['response_time_ms'] > 0) / len(results)
            
            overall_status = {
                'timestamp': datetime.now().isoformat(),
                'health_percentage': health_percentage,
                'avg_response_time_ms': avg_response_time,
                'healthy_endpoints': healthy_count,
                'total_endpoints': total_count,
                'endpoints': results
            }
            
            # Log overall status
            if health_percentage == 100:
                logger.info(f"🎉 All endpoints healthy (avg {avg_response_time:.0f}ms)")
            elif health_percentage >= 80:
                logger.warning(f"⚠️  {health_percentage}% endpoints healthy")
            else:
                logger.error(f"🚨 Only {health_percentage}% endpoints healthy")
            
            return overall_status

async def main():
    monitor = APIMonitor()
    results = await monitor.check_all_endpoints()
    
    # Save results
    with open('/home/ahmed/TheUltimate/backend/monitoring/logs/api_health.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("API health monitoring completed")

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x "$MONITOR_DIR/api_health_monitor.py"

# 3. System Resource Monitor
echo ""
echo "3. Setting up system resource monitoring..."
cat > "$MONITOR_DIR/system_monitor.py" << 'EOF'
#!/usr/bin/env python3
"""
System Resource Monitor for Enhanced Backtest System
Monitors CPU, memory, disk usage, and process health
"""

import psutil
import json
import logging
import subprocess
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ahmed/TheUltimate/backend/monitoring/logs/system_resources.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.alert_thresholds = {
            'cpu_percent': 80,
            'memory_percent': 85,
            'disk_percent': 90
        }
    
    def check_system_resources(self):
        """Check CPU, memory, and disk usage"""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # Process count
        process_count = len(psutil.pids())
        
        resources = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'memory_available_gb': memory.available / (1024**3),
            'disk_percent': disk_percent,
            'disk_free_gb': disk.free / (1024**3),
            'process_count': process_count,
            'timestamp': datetime.now().isoformat()
        }
        
        # Log alerts
        if cpu_percent > self.alert_thresholds['cpu_percent']:
            logger.warning(f"High CPU usage: {cpu_percent}%")
        
        if memory_percent > self.alert_thresholds['memory_percent']:
            logger.warning(f"High memory usage: {memory_percent}%")
        
        if disk_percent > self.alert_thresholds['disk_percent']:
            logger.error(f"High disk usage: {disk_percent}%")
        
        logger.info(f"Resources: CPU {cpu_percent}%, RAM {memory_percent}%, Disk {disk_percent}%")
        
        return resources
    
    def check_backend_process(self):
        """Check if backend process is running and healthy"""
        try:
            # Find backend process
            backend_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
                if 'python' in proc.info['name'].lower() and any('main.py' in cmd for cmd in proc.info['cmdline']):
                    backend_processes.append({
                        'pid': proc.info['pid'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_percent': proc.info['memory_percent'],
                        'cmdline': ' '.join(proc.info['cmdline'])
                    })
            
            if backend_processes:
                logger.info(f"Backend processes running: {len(backend_processes)}")
                return {
                    'status': 'running',
                    'process_count': len(backend_processes),
                    'processes': backend_processes
                }
            else:
                logger.error("Backend process not found")
                return {
                    'status': 'not_running',
                    'process_count': 0,
                    'processes': []
                }
                
        except Exception as e:
            logger.error(f"Process check failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

def main():
    monitor = SystemMonitor()
    
    # Check system resources
    resources = monitor.check_system_resources()
    
    # Check backend process
    process_status = monitor.check_backend_process()
    
    # Combine results
    results = {
        'timestamp': datetime.now().isoformat(),
        'system_resources': resources,
        'backend_process': process_status
    }
    
    # Save results
    with open('/home/ahmed/TheUltimate/backend/monitoring/logs/system_metrics.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("System monitoring completed")

if __name__ == "__main__":
    main()
EOF

chmod +x "$MONITOR_DIR/system_monitor.py"

# 4. Comprehensive monitoring script
echo ""
echo "4. Creating comprehensive monitoring script..."
cat > "$MONITOR_DIR/run_all_monitors.sh" << 'EOF'
#!/bin/bash

# Comprehensive Monitoring Script
# Runs all monitoring components and generates summary report

MONITOR_DIR="/home/ahmed/TheUltimate/backend/monitoring"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== COMPREHENSIVE SYSTEM MONITORING ==="
echo "Timestamp: $(date)"

# Run all monitors
echo ""
echo "Running database performance monitor..."
python3 "$MONITOR_DIR/db_performance_monitor.py"

echo ""
echo "Running API health monitor..."
python3 "$MONITOR_DIR/api_health_monitor.py"

echo ""
echo "Running system resource monitor..."
python3 "$MONITOR_DIR/system_monitor.py"

# Generate summary report
echo ""
echo "Generating monitoring summary..."
python3 << 'PYTHON_EOF'
import json
import os
from datetime import datetime

monitor_dir = "/home/ahmed/TheUltimate/backend/monitoring/logs"

# Load monitoring data
try:
    with open(f"{monitor_dir}/performance_metrics.json") as f:
        perf_data = json.load(f)
except:
    perf_data = {}

try:
    with open(f"{monitor_dir}/api_health.json") as f:
        api_data = json.load(f)
except:
    api_data = {}

try:
    with open(f"{monitor_dir}/system_metrics.json") as f:
        system_data = json.load(f)
except:
    system_data = {}

# Generate summary
summary = {
    'timestamp': datetime.now().isoformat(),
    'overall_status': 'healthy',
    'alerts': [],
    'performance_summary': {},
    'api_summary': {},
    'system_summary': {}
}

# Check for issues
alerts = []

# API health
if api_data.get('health_percentage', 0) < 100:
    alerts.append(f"API health: {api_data.get('health_percentage', 0)}%")
    summary['overall_status'] = 'warning'

# System resources
sys_resources = system_data.get('system_resources', {})
if sys_resources.get('cpu_percent', 0) > 80:
    alerts.append(f"High CPU: {sys_resources.get('cpu_percent', 0)}%")
    summary['overall_status'] = 'warning'

if sys_resources.get('memory_percent', 0) > 85:
    alerts.append(f"High memory: {sys_resources.get('memory_percent', 0)}%")
    summary['overall_status'] = 'warning'

if sys_resources.get('disk_percent', 0) > 90:
    alerts.append(f"High disk usage: {sys_resources.get('disk_percent', 0)}%")
    summary['overall_status'] = 'critical'

# Backend process
backend_status = system_data.get('backend_process', {}).get('status', 'unknown')
if backend_status != 'running':
    alerts.append(f"Backend process: {backend_status}")
    summary['overall_status'] = 'critical'

summary['alerts'] = alerts

# Performance summary
cache_data = perf_data.get('cache', {})
summary['performance_summary'] = {
    'cache_hit_rate': cache_data.get('cache_hit_rate', 0),
    'total_backtests': cache_data.get('total_backtests', 0)
}

# API summary
summary['api_summary'] = {
    'health_percentage': api_data.get('health_percentage', 0),
    'avg_response_time': api_data.get('avg_response_time_ms', 0)
}

# System summary
summary['system_summary'] = {
    'cpu_percent': sys_resources.get('cpu_percent', 0),
    'memory_percent': sys_resources.get('memory_percent', 0),
    'disk_percent': sys_resources.get('disk_percent', 0),
    'backend_status': backend_status
}

# Save summary
with open(f"{monitor_dir}/monitoring_summary.json", 'w') as f:
    json.dump(summary, f, indent=2)

# Print summary
print(f"Overall Status: {summary['overall_status'].upper()}")
if alerts:
    print("Alerts:")
    for alert in alerts:
        print(f"  ⚠️  {alert}")
else:
    print("✅ No alerts")

print(f"Cache hit rate: {summary['performance_summary']['cache_hit_rate']}%")
print(f"API health: {summary['api_summary']['health_percentage']}%")
print(f"System: CPU {summary['system_summary']['cpu_percent']}%, RAM {summary['system_summary']['memory_percent']}%")

PYTHON_EOF

echo ""
echo "=== MONITORING COMPLETED ==="
echo "Reports saved to: $MONITOR_DIR/logs/"
echo "Summary: $MONITOR_DIR/logs/monitoring_summary.json"
EOF

chmod +x "$MONITOR_DIR/run_all_monitors.sh"

# 5. Setup cron job for regular monitoring
echo ""
echo "5. Setting up automated monitoring..."
CRON_JOB="*/15 * * * * $MONITOR_DIR/run_all_monitors.sh >> $MONITOR_DIR/logs/monitoring_cron.log 2>&1"

# Add to crontab if not already present
(crontab -l 2>/dev/null | grep -v "run_all_monitors.sh"; echo "$CRON_JOB") | crontab -

echo "   ✅ Cron job added: Monitoring every 15 minutes"

# 6. Create alerting configuration
echo ""
echo "6. Creating alerting configuration..."
cat > "$MONITOR_DIR/alerts/alert_config.json" << 'EOF'
{
  "alert_thresholds": {
    "cpu_percent": 80,
    "memory_percent": 85,
    "disk_percent": 90,
    "api_health_percent": 95,
    "cache_hit_rate": 40,
    "avg_response_time_ms": 3000
  },
  "notification_methods": {
    "log_file": "/home/ahmed/TheUltimate/backend/monitoring/logs/alerts.log",
    "email": false,
    "webhook": false
  },
  "alert_intervals": {
    "critical": 300,
    "warning": 900,
    "info": 3600
  }
}
EOF

echo ""
echo "=== MONITORING SETUP COMPLETED ==="
echo "Monitoring directory: $MONITOR_DIR"
echo "Components installed:"
echo "  ✅ Database performance monitor"
echo "  ✅ API health monitor"
echo "  ✅ System resource monitor"
echo "  ✅ Comprehensive monitoring script"
echo "  ✅ Automated cron job (every 15 minutes)"
echo "  ✅ Alert configuration"
echo ""
echo "To run monitoring manually:"
echo "  $MONITOR_DIR/run_all_monitors.sh"
echo ""
echo "Monitor logs location:"
echo "  $MONITOR_DIR/logs/"
echo ""
echo "🎉 Monitoring system is ready!"