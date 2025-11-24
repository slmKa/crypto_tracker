#!/bin/bash

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "🔍 CRYPTO TRACKER - HEALTH CHECK"
echo "==========================================${NC}"
echo ""

# 1. Check Docker containers
echo -e "${BLUE}🐳 Docker Containers:${NC}"
docker-compose ps 2>&1 | grep -E "(crypto_|Up|Exited)" | while read line; do
    if echo "$line" | grep -q "Up"; then
        echo -e "${GREEN}  ✅ $line${NC}"
    else
        echo -e "${RED}  ❌ $line${NC}"
    fi
done
echo ""

# 2. Check TimescaleDB
echo -e "${BLUE}📊 TimescaleDB Status:${NC}"
TICKER_COUNT=$(docker exec crypto_timescaledb psql -U crypto_user -d crypto_db -t -c "SELECT COUNT(*) FROM tickers;" 2>&1 | xargs)
OHLCV_COUNT=$(docker exec crypto_timescaledb psql -U crypto_user -d crypto_db -t -c "SELECT COUNT(*) FROM ohlcv;" 2>&1 | xargs)
LATEST_TIME=$(docker exec crypto_timescaledb psql -U crypto_user -d crypto_db -t -c "SELECT MAX(time) FROM tickers;" 2>&1 | xargs)
SECONDS_AGO=$(docker exec crypto_timescaledb psql -U crypto_user -d crypto_db -t -c "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(time))) FROM tickers;" 2>&1 | xargs | cut -d. -f1)

if [ "$SECONDS_AGO" -lt 300 ]; then
    echo -e "${GREEN}  ✅ Tickers: $TICKER_COUNT rows${NC}"
    echo -e "${GREEN}  ✅ OHLCV: $OHLCV_COUNT rows${NC}"
    echo -e "${GREEN}  ✅ Latest update: $LATEST_TIME (${SECONDS_AGO}s ago)${NC}"
else
    echo -e "${RED}  ❌ Data is stale (${SECONDS_AGO}s ago)${NC}"
fi
echo ""

# 3. Check Redis
echo -e "${BLUE}🔴 Redis Status:${NC}"
REDIS_KEYS=$(docker exec crypto_redis redis-cli KEYS "*" 2>&1 | wc -l)
REDIS_MEMORY=$(docker exec crypto_redis redis-cli INFO memory 2>&1 | grep "used_memory_human" | cut -d: -f2 | xargs)
if [ "$REDIS_KEYS" -gt 0 ]; then
    echo -e "${GREEN}  ✅ Keys: $REDIS_KEYS${NC}"
    echo -e "${GREEN}  ✅ Memory: $REDIS_MEMORY${NC}"
else
    echo -e "${RED}  ❌ No keys in Redis${NC}"
fi
echo ""

# 4. Check Airflow DAG
echo -e "${BLUE}⚙️  Airflow DAG Status:${NC}"
DAG_RUNS=$(docker exec crypto_airflow airflow dags list-runs --dag-id crypto_etl_pipeline 2>&1)
LAST_RUN_STATE=$(echo "$DAG_RUNS" | grep "crypto_etl_pipeline" | head -1 | grep -oE "success|failed|running" | head -1)
LAST_RUN_TIME=$(echo "$DAG_RUNS" | grep "crypto_etl_pipeline" | head -1 | grep -oE "2025-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}" | head -1)

if [ "$LAST_RUN_STATE" = "success" ]; then
    echo -e "${GREEN}  ✅ Last run: SUCCESS ($LAST_RUN_TIME)${NC}"
elif [ -z "$LAST_RUN_STATE" ]; then
    echo -e "${YELLOW}  ⚠️  No runs found${NC}"
else
    echo -e "${RED}  ❌ Last run: $LAST_RUN_STATE${NC}"
fi

# Count successful runs
SUCCESS_COUNT=$(echo "$DAG_RUNS" | grep -c "success")
echo -e "${GREEN}  ✅ Total successful runs: $SUCCESS_COUNT${NC}"
echo ""

# 5. Check Streamlit
echo -e "${BLUE}🎨 Streamlit Status:${NC}"
STREAMLIT_STATUS=$(docker-compose ps streamlit 2>&1 | grep "crypto_streamlit" | grep -o "Up.*" | head -1)
if [ ! -z "$STREAMLIT_STATUS" ]; then
    echo -e "${GREEN}  ✅ Streamlit: $STREAMLIT_STATUS${NC}"
    echo -e "${GREEN}  📍 URL: http://localhost:8501${NC}"
else
    echo -e "${RED}  ❌ Streamlit is not running${NC}"
fi
echo ""

# 6. Check Kafka
echo -e "${BLUE}📨 Kafka Status:${NC}"
KAFKA_TOPICS=$(docker exec crypto_kafka kafka-topics.sh --list --bootstrap-server localhost:9092 2>&1 | wc -l)
echo -e "${GREEN}  ✅ Topics: $KAFKA_TOPICS${NC}"
echo ""

# 7. Summary
echo -e "${BLUE}=========================================="
echo "📋 SUMMARY"
echo "==========================================${NC}"

# Validate numeric values
if ! [[ "$SECONDS_AGO" =~ ^[0-9]+$ ]]; then
    SECONDS_AGO=0
fi

if [ "$LAST_RUN_STATE" = "success" ] && [ "$SECONDS_AGO" -lt 300 ] && [ "$REDIS_KEYS" -gt 0 ]; then
    echo -e "${GREEN}✅ ALL SYSTEMS OPERATIONAL!${NC}"
    echo -e "${GREEN}   Data is fresh and updating regularly${NC}"
else
    echo -e "${YELLOW}⚠️  SOME ISSUES DETECTED${NC}"
    if [ "$SECONDS_AGO" -ge 300 ] 2>/dev/null; then
        echo -e "${YELLOW}   - Data is stale (last update: ${SECONDS_AGO}s ago)${NC}"
    fi
    if [ "$REDIS_KEYS" -eq 0 ] 2>/dev/null; then
        echo -e "${YELLOW}   - Redis is empty${NC}"
    fi
    if [ "$LAST_RUN_STATE" != "success" ] && [ ! -z "$LAST_RUN_STATE" ]; then
        echo -e "${YELLOW}   - Last DAG run: $LAST_RUN_STATE${NC}"
    fi
fi
echo ""
