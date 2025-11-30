import React, { useState, useEffect } from 'react';
import { Activity, X, TrendingUp, TrendingDown, Minus } from 'lucide-react';

/**
 * Connection Health Monitor Component
 * 
 * Floating widget that shows real-time connection health history
 * Tracks last 20 connection state changes with visual timeline
 */
const ConnectionHealthMonitor = ({ isConnected, connectionQuality, reconnectAttempts }) => {
  const [healthHistory, setHealthHistory] = useState([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [stats, setStats] = useState({ goodCount: 0, poorCount: 0, disconnectedCount: 0 });

  useEffect(() => {
    const newEntry = {
      timestamp: new Date(),
      status: isConnected ? connectionQuality : 'disconnected',
      reconnectAttempts
    };

    setHealthHistory(prev => {
      const updated = [...prev.slice(-19), newEntry]; // Keep last 20 entries
      
      // Calculate stats
      const goodCount = updated.filter(e => e.status === 'good').length;
      const poorCount = updated.filter(e => e.status === 'poor').length;
      const disconnectedCount = updated.filter(e => e.status === 'disconnected').length;
      
      setStats({ goodCount, poorCount, disconnectedCount });
      
      return updated;
    });
  }, [isConnected, connectionQuality, reconnectAttempts]);

  const getStatusColor = (status) => {
    switch(status) {
      case 'good': return 'bg-green-500';
      case 'poor': return 'bg-yellow-500';
      case 'disconnected': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'good': return TrendingUp;
      case 'poor': return Minus;
      case 'disconnected': return TrendingDown;
      default: return Activity;
    }
  };

  const getUptimePercentage = () => {
    if (healthHistory.length === 0) return 100;
    const connectedCount = healthHistory.filter(e => e.status === 'good' || e.status === 'poor').length;
    return ((connectedCount / healthHistory.length) * 100).toFixed(1);
  };

  // Compact floating button when collapsed
  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="fixed bottom-4 right-4 bg-white rounded-full shadow-lg p-3 hover:bg-gray-50 transition-colors z-40 border border-gray-200"
        title="Show connection health monitor"
        aria-label="Show connection health"
      >
        <Activity className={`w-5 h-5 ${
          isConnected ? 'text-green-600' : 'text-red-600'
        }`} />
        {reconnectAttempts > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
            {reconnectAttempts}
          </span>
        )}
      </button>
    );
  }

  const StatusIcon = getStatusIcon(isConnected ? connectionQuality : 'disconnected');

  // Expanded health monitor panel
  return (
    <div className="fixed bottom-4 right-4 bg-white rounded-lg shadow-2xl border border-gray-200 w-80 z-40 animate-slide-in">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-gradient-to-r from-blue-50 to-indigo-50">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Connection Health</h3>
        </div>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-gray-400 hover:text-gray-600 transition-colors"
          aria-label="Close health monitor"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Current Status */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-2">
            <StatusIcon className={`w-5 h-5 ${
              isConnected ? 'text-green-600' : 'text-red-600'
            }`} />
            <span className="text-sm text-gray-600">Current Status</span>
          </div>
          <span className={`text-sm font-semibold ${
            isConnected ? 'text-green-600' : 'text-red-600'
          }`}>
            {isConnected ? 'Online' : 'Offline'}
          </span>
        </div>
        
        {/* Uptime Percentage */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Uptime</span>
          <span className="text-sm font-medium text-blue-600">
            {getUptimePercentage()}%
          </span>
        </div>
        
        {/* Reconnect Attempts (if any) */}
        {reconnectAttempts > 0 && (
          <div className="flex items-center justify-between p-2 bg-orange-50 rounded">
            <span className="text-sm text-gray-600">Reconnect Attempts</span>
            <span className="text-sm font-medium text-orange-600">
              {reconnectAttempts} / 10
            </span>
          </div>
        )}
        
        {/* Connection History Timeline */}
        <div>
          <p className="text-sm text-gray-600 mb-2 font-medium">Last 20 Events</p>
          <div className="flex gap-0.5 h-8 rounded overflow-hidden">
            {healthHistory.map((entry, idx) => (
              <div
                key={idx}
                className={`flex-1 ${getStatusColor(entry.status)} transition-all hover:opacity-75`}
                title={`${entry.status} at ${entry.timestamp.toLocaleTimeString()}`}
              />
            ))}
            {/* Fill remaining slots if less than 20 */}
            {Array(Math.max(0, 20 - healthHistory.length)).fill(0).map((_, idx) => (
              <div
                key={`empty-${idx}`}
                className="flex-1 bg-gray-200"
              />
            ))}
          </div>
          
          {/* Legend */}
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-green-500 rounded" />
              <span>Good ({stats.goodCount})</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-yellow-500 rounded" />
              <span>Poor ({stats.poorCount})</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-red-500 rounded" />
              <span>Offline ({stats.disconnectedCount})</span>
            </div>
          </div>
        </div>
        
        {/* Info Text */}
        <div className="text-xs text-gray-500 pt-2 border-t border-gray-200 space-y-1">
          <p>✓ Auto-reconnects with exponential backoff</p>
          <p>✓ Ping/pong health monitoring every 30s</p>
          <p>✓ Up to 10 reconnection attempts (max 30s delay)</p>
        </div>
      </div>

      <style>{`
        @keyframes slide-in {
          from {
            transform: translateY(20px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        
        .animate-slide-in {
          animation: slide-in 0.3s ease-out;
        }
      `}</style>
    </div>
  );
};

export default ConnectionHealthMonitor;

