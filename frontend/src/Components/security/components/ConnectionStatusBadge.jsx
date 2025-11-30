import React from 'react';
import { Wifi, WifiOff, Activity } from 'lucide-react';

/**
 * Connection Status Badge Component
 * 
 * Displays the current WebSocket connection status with visual indicators
 * Shows connection quality (good, poor, disconnected) and reconnection attempts
 */
const ConnectionStatusBadge = ({ isConnected, connectionQuality, reconnectAttempts, onReconnect }) => {
  const statusConfig = {
    good: {
      icon: Wifi,
      color: 'bg-green-500',
      text: 'Connected',
      textColor: 'text-green-700',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200'
    },
    poor: {
      icon: Activity,
      color: 'bg-yellow-500',
      text: 'Unstable Connection',
      textColor: 'text-yellow-700',
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200'
    },
    disconnected: {
      icon: WifiOff,
      color: 'bg-red-500',
      text: reconnectAttempts > 0 ? `Reconnecting (${reconnectAttempts})...` : 'Disconnected',
      textColor: 'text-red-700',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200'
    }
  };

  const status = isConnected 
    ? (connectionQuality === 'poor' ? 'poor' : 'good')
    : 'disconnected';
  
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={`flex items-center gap-3 px-4 py-2 rounded-lg border ${config.bgColor} ${config.borderColor}`}>
      <div className="flex items-center gap-2">
        {/* Animated status indicator */}
        <div className={`w-2 h-2 rounded-full ${config.color} ${isConnected ? 'animate-pulse' : ''}`} />
        
        {/* Icon */}
        <Icon className={`w-4 h-4 ${config.textColor}`} />
        
        {/* Status text */}
        <span className={`text-sm font-medium ${config.textColor}`}>
          {config.text}
        </span>
      </div>
      
      {/* Manual retry button for disconnected state */}
      {!isConnected && (
        <button
          onClick={onReconnect}
          className="ml-2 text-xs px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors"
          aria-label="Retry connection"
        >
          Retry Now
        </button>
      )}
    </div>
  );
};

export default ConnectionStatusBadge;

