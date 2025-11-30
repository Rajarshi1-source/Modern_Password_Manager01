# Performance Monitoring Architecture

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────┐  ┌──────────────────────────┐  │
│  │  performanceMonitor.js     │  │   errorHandler.js        │  │
│  │  ────────────────────────  │  │  ──────────────────────  │  │
│  │  • Vault operations        │  │  • Global error handler  │  │
│  │  • API request tracking    │  │  • API error handler     │  │
│  │  • Component renders       │  │  • Validation errors     │  │
│  │  • Navigation timing       │  │  • Network errors        │  │
│  │  • Web Vitals (LCP, FID)   │  │  • Crypto errors        │  │
│  │  • Resource loading        │  │  • Error Boundary       │  │
│  │  • Auto-reporting          │  │  • Error reporting      │  │
│  └────────────────────────────┘  └──────────────────────────┘  │
│                    │                          │                  │
│                    └──────────┬───────────────┘                  │
│                               │                                  │
└───────────────────────────────┼──────────────────────────────────┘
                                │
                                │ HTTP/JSON
                                │
┌───────────────────────────────┼──────────────────────────────────┐
│                               │                                  │
│                               ▼                                  │
│                      API Endpoints                               │
│                  /api/performance/*                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     MIDDLEWARE LAYER                       │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  1. PerformanceMonitoringMiddleware                       │ │
│  │     ▸ Request/response timing                             │ │
│  │     ▸ Memory usage tracking                               │ │
│  │     ▸ Slow request detection                              │ │
│  │                                                            │ │
│  │  2. DatabaseQueryMonitoringMiddleware                     │ │
│  │     ▸ Query count tracking                                │ │
│  │     ▸ N+1 query detection                                 │ │
│  │     ▸ Query pattern analysis                              │ │
│  │                                                            │ │
│  │  3. APIPerformanceMiddleware                              │ │
│  │     ▸ Endpoint-specific metrics                           │ │
│  │     ▸ Status code tracking                                │ │
│  │     ▸ Error rate monitoring                               │ │
│  │                                                            │ │
│  │  4. CachePerformanceMiddleware                            │ │
│  │     ▸ Hit/miss rate tracking                              │ │
│  │     ▸ Cache efficiency                                    │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                               │                                  │
│                               ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     BACKEND (Django)                       │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  ┌──────────────────┐        ┌──────────────────────┐    │ │
│  │  │ Views Layer      │        │ ML Optimization      │    │ │
│  │  │ ──────────────── │        │ ──────────────────── │    │ │
│  │  │ • Summary        │        │ • Response Time      │    │ │
│  │  │ • System Health  │        │   Predictor (RF)     │    │ │
│  │  │ • Endpoints      │        │ • Anomaly Detector   │    │ │
│  │  │ • Database       │        │   (Isolation Forest) │    │ │
│  │  │ • Errors         │        │ • Optimization       │    │ │
│  │  │ • Alerts         │        │   Recommendations    │    │ │
│  │  │ • Dependencies   │        │ • Feature Analysis   │    │ │
│  │  │ • ML Predictions │        │                      │    │ │
│  │  │ • Optimization   │        └──────────────────────┘    │ │
│  │  └──────────────────┘                 │                   │ │
│  │           │                            │                   │ │
│  │           └──────────┬─────────────────┘                   │ │
│  │                      │                                     │ │
│  │                      ▼                                     │ │
│  │  ┌────────────────────────────────────────────────────┐  │ │
│  │  │              DATABASE LAYER                        │  │ │
│  │  ├────────────────────────────────────────────────────┤  │ │
│  │  │                                                    │  │ │
│  │  │  • PerformanceMetric         (Request metrics)    │  │ │
│  │  │  • APIPerformanceMetric      (API metrics)        │  │ │
│  │  │  • SystemMetric              (CPU, Memory, Disk)  │  │ │
│  │  │  • ErrorLog                  (Error tracking)     │  │ │
│  │  │  • PerformanceAlert          (Alert management)   │  │ │
│  │  │  • DependencyVersion         (Dependency status)  │  │ │
│  │  │  • PerformancePrediction     (ML predictions)     │  │ │
│  │  │                                                    │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              SYSTEM RESOURCE MONITOR                       │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  • CPU Usage Monitoring                                   │ │
│  │  • Memory Usage Monitoring                                │ │
│  │  • Disk Space Monitoring                                  │ │
│  │  • Automatic Alert Generation                             │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │          DEPENDENCY VULNERABILITY SCANNER                  │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │                                                            │ │
│  │  • pip-audit Integration                                  │ │
│  │  • safety Integration                                     │ │
│  │  • Outdated Package Detection                             │ │
│  │  • Auto-fix Capability                                    │ │
│  │  • Django Management Command                              │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow

### 1. Request Performance Tracking

```
HTTP Request
    │
    ▼
PerformanceMonitoringMiddleware
    │
    ├─► Start timer
    ├─► Track memory usage
    │
    ▼
Process Request (Your Views)
    │
    ▼
DatabaseQueryMonitoringMiddleware
    │
    ├─► Count queries
    ├─► Detect N+1 issues
    │
    ▼
APIPerformanceMiddleware
    │
    ├─► Record endpoint metrics
    ├─► Track status codes
    │
    ▼
Response
    │
    ├─► Calculate duration
    ├─► Store metrics in DB
    ├─► Generate alerts if needed
    │
    ▼
HTTP Response
```

### 2. ML Performance Prediction

```
Historical Data
    │
    ▼
PerformanceMetric Model (100+ records)
    │
    ▼
performance_optimizer.train_all_models()
    │
    ├─► Extract features
    ├─► Scale data
    ├─► Train Random Forest (response time)
    ├─► Train Isolation Forest (anomalies)
    │
    ▼
Save Models
    │
    ├─► response_time_predictor.pkl
    ├─► performance_anomaly_detector.pkl
    ├─► performance_scaler.pkl
    │
    ▼
prediction = predict_response_time(features)
anomaly = detect_anomaly(features)
recommendations = generate_optimization_recommendations()
```

### 3. Frontend Performance Tracking

```
User Interaction
    │
    ▼
Performance Events
    │
    ├─► Vault unlock
    ├─► Item decryption
    ├─► API request
    ├─► Component render
    │
    ▼
performanceMonitor.record*()
    │
    ├─► Store in memory (max 100 per type)
    ├─► Calculate averages
    │
    ▼
Auto-reporting (every 60s)
    │
    ▼
POST /api/performance/frontend/
    │
    ▼
Backend stores/logs data
```

### 4. Error Tracking

```
Error Occurs
    │
    ├─► API Error
    ├─► Validation Error
    ├─► Network Error
    ├─► Crypto Error
    ├─► React Error
    │
    ▼
errorHandler.handleError(error, context, info)
    │
    ├─► Log to console
    ├─► Add to error queue
    ├─► Record in performanceMonitor
    │
    ▼
Report to Backend
    │
    ▼
POST /api/errors/report/
    │
    ▼
ErrorLog Model
```

### 5. Dependency Scanning

```
python manage.py check_dependencies
    │
    ▼
Run pip-audit (or safety as fallback)
    │
    ├─► Parse vulnerabilities
    ├─► Determine severity
    │
    ▼
Run pip list --outdated
    │
    ├─► Parse outdated packages
    ├─► Determine update type (MAJOR/MINOR/PATCH)
    │
    ▼
Display Results
    │
    ├─► Vulnerability report
    ├─► Outdated package report
    │
    ▼
Save to Database (if --save flag)
    │
    ▼
DependencyVersion Model
```

---

## 🔄 Integration Points

### Frontend → Backend

```javascript
// API Request Tracking
performanceMonitor.recordAPIRequest(
  endpoint,
  method,
  duration,
  statusCode,
  success
);

// Error Reporting
errorHandler.reportError(errorRecord);

// Performance Reporting
performanceMonitor.reportToBackend('/api/performance/frontend/');
```

### Backend → Database

```python
# Automatic via middleware
PerformanceMetric.objects.create(
    path='/api/vault/items/',
    method='GET',
    duration=250,
    status_code=200,
    query_count=5,
    memory_usage=45.2,
    user=request.user
)
```

### ML → Optimization

```python
# Predict performance
prediction = performance_optimizer.predict_response_time({
    'hour_of_day': 14,
    'day_of_week': 2,
    'query_count': 10,
    'cpu_usage': 45
})

# Detect anomalies
is_anomaly, score = performance_optimizer.detect_anomaly(features)

# Get recommendations
recs = performance_optimizer.generate_optimization_recommendations()
```

---

## 🎯 Key Components

### Middleware Layer (4 components)

1. **PerformanceMonitoringMiddleware** - Request/response tracking
2. **DatabaseQueryMonitoringMiddleware** - Database optimization
3. **APIPerformanceMiddleware** - API-specific metrics
4. **CachePerformanceMiddleware** - Cache efficiency

### Data Models (7 models)

1. **PerformanceMetric** - Request performance
2. **APIPerformanceMetric** - API metrics
3. **SystemMetric** - System resources
4. **ErrorLog** - Error tracking
5. **PerformanceAlert** - Alert management
6. **DependencyVersion** - Dependency status
7. **PerformancePrediction** - ML predictions

### API Endpoints (11 endpoints)

1. `/api/performance/summary/` - Overall summary
2. `/api/performance/system-health/` - System health
3. `/api/performance/endpoints/` - Endpoint metrics
4. `/api/performance/database/` - Database performance
5. `/api/performance/errors/` - Error summary
6. `/api/performance/alerts/` - Performance alerts
7. `/api/performance/alerts/<id>/acknowledge/` - Acknowledge alert
8. `/api/performance/alerts/<id>/resolve/` - Resolve alert
9. `/api/performance/dependencies/` - Dependency status
10. `/api/performance/ml-predictions/` - ML predictions
11. `/api/performance/optimize/` - Trigger optimization

### ML Models (2 models)

1. **Random Forest Regressor** - Response time prediction
2. **Isolation Forest** - Anomaly detection

### Frontend Services (2 services)

1. **performanceMonitor.js** - Performance tracking
2. **errorHandler.js** - Error handling

---

## 📈 Metrics Hierarchy

```
Performance Monitoring
│
├── Request Metrics
│   ├── Duration
│   ├── Status Code
│   ├── HTTP Method
│   ├── Path
│   └── User
│
├── Database Metrics
│   ├── Query Count
│   ├── Query Time
│   ├── N+1 Detection
│   └── Query Patterns
│
├── System Metrics
│   ├── CPU Usage
│   ├── Memory Usage
│   ├── Disk Usage
│   └── Alerts
│
├── API Metrics
│   ├── Endpoint
│   ├── Request Count
│   ├── Avg Response Time
│   └── Error Rate
│
├── Frontend Metrics
│   ├── Vault Operations
│   ├── API Requests
│   ├── Component Renders
│   ├── Navigation Timing
│   └── Web Vitals
│
├── Error Metrics
│   ├── Error Type
│   ├── Stack Trace
│   ├── Context
│   ├── User Agent
│   └── Frequency
│
└── Dependency Metrics
    ├── Vulnerabilities
    ├── Severity
    ├── Outdated Packages
    └── Update Type
```

---

## 🔐 Security Architecture

```
Performance Data Access Control
│
├── Admin Users
│   ├── Full access to all endpoints
│   ├── View all user metrics
│   ├── Manage alerts
│   └── Trigger optimizations
│
├── Authenticated Users
│   ├── Submit frontend metrics
│   ├── View own metrics (limited)
│   └── No access to system data
│
└── Anonymous Users
    └── No access to performance data
```

---

## 🚀 Deployment Architecture

```
Production Environment
│
├── Web Server (Django)
│   ├── Performance Middleware
│   ├── API Endpoints
│   └── ML Models
│
├── Database (PostgreSQL/SQLite)
│   ├── Performance Tables
│   ├── Error Logs
│   └── ML Predictions
│
├── Background Jobs (Celery - Optional)
│   ├── System Resource Monitoring
│   ├── ML Model Training
│   └── Dependency Scanning
│
└── Frontend (React)
    ├── Performance Monitor
    ├── Error Handler
    └── Auto-Reporting
```

---

## 📊 Data Retention Policy

```
Data Type                  Retention Period
────────────────────────  ─────────────────
Performance Metrics        30 days
API Metrics               30 days
System Metrics            7 days
Error Logs                90 days
ML Predictions            14 days
Dependency Data           Until superseded
```

---

## 🎯 Performance Targets

```
Metric                    Target              Alert Threshold
────────────────────────  ──────────────────  ─────────────────
Request Response Time     < 500ms             > 1000ms
Database Queries          < 20 per request    > 50 per request
API Error Rate           < 1%                > 5%
CPU Usage                < 60%               > 80%
Memory Usage             < 70%               > 80%
Disk Usage               < 75%               > 80%
```

---

This architecture provides comprehensive performance monitoring, ML-based optimization, and proactive issue detection for the Password Manager application.

