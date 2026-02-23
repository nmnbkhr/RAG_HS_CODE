# Phase 3: Performance & Caching - Requirements

## Overview
Implement caching, offline support, and performance monitoring to reduce API calls and improve response times.

## Requirements

### P3-REQ-001: Exchange Rate Cache (SQLite)
- Cache NBP exchange rates in SQLite database
- TTL: 4 hours (rates update infrequently)
- Serve from cache when available and fresh
- Background refresh before TTL expires
- Store both TT Buying and TT Selling rates
- Fallback to last known rate if fetch fails

### P3-REQ-002: WEBOC Duty Data Cache
- Cache WEBOC duty lookups by HS code
- TTL: 24 hours (duty rates change rarely)
- Store full duty response (CD, ST, IT, AD, RD, description, UOM)
- Invalidation on user request
- Max cache size: 10,000 entries

### P3-REQ-003: RAG Query Cache
- Cache RAG query results by normalized query string
- TTL: 12 hours
- Deduplication of similar queries
- Max cache size: 1,000 entries

### P3-REQ-004: Performance Monitor
- Track response times for all external API calls
- Log slow queries (>2 seconds)
- Provide statistics (avg, p50, p95, p99)
- Expose metrics for Streamlit sidebar display

### P3-REQ-005: Offline Mode
- Detect internet connectivity
- Serve from cache when offline
- Display offline banner in UI
- Graceful degradation (calculations work, live data shows cached)

## Acceptance Criteria
- API response time < 2 seconds (cached)
- Cached queries < 100ms
- App works offline with cached data
- Memory usage < 500MB
- All tests passing
