import { apiCall } from './api';

class AccountProtectionService {
    constructor() {
        this.baseUrl = '/api/security/account-protection';
    }

    // Security Dashboard
    async getSecurityDashboard() {
        return await apiCall(`${this.baseUrl}/security_dashboard/`, {
            method: 'GET'
        });
    }

    // Social Media Accounts
    async getSocialAccounts() {
        return await apiCall(`${this.baseUrl}/social_accounts/`, {
            method: 'GET'
        });
    }

    async addSocialAccount(accountData) {
        return await apiCall(`${this.baseUrl}/social_accounts/`, {
            method: 'POST',
            data: accountData
        });
    }

    async lockAccounts(platform, accountIds, reason = 'Manual lock by user') {
        return await apiCall(`${this.baseUrl}/lock_accounts/`, {
            method: 'POST',
            data: { 
                platform, 
                account_ids: accountIds,
                reason 
            }
        });
    }

    async unlockAccounts(platform, accountIds) {
        return await apiCall(`${this.baseUrl}/unlock_accounts/`, {
            method: 'POST',
            data: { 
                platform, 
                account_ids: accountIds 
            }
        });
    }

    // Login Attempts
    async getLoginAttempts(days = 30, limit = 50) {
        return await apiCall(`${this.baseUrl}/login_attempts/?days=${days}&limit=${limit}`, {
            method: 'GET'
        });
    }

    // Security Alerts
    async getSecurityAlerts(includeResolved = false, limit = 20) {
        return await apiCall(`${this.baseUrl}/security_alerts/?include_resolved=${includeResolved}&limit=${limit}`, {
            method: 'GET'
        });
    }

    async resolveAlert(alertId) {
        return await apiCall(`${this.baseUrl}/resolve_alert/`, {
            method: 'POST',
            data: { alert_id: alertId }
        });
    }

    // Notification Settings
    async getNotificationSettings() {
        return await apiCall(`${this.baseUrl}/notification_settings/`, {
            method: 'GET'
        });
    }

    async updateNotificationSettings(settings) {
        return await apiCall(`${this.baseUrl}/notification_settings/`, {
            method: 'PUT',
            data: settings
        });
    }

    // Devices
    async getDevices() {
        return await apiCall(`${this.baseUrl}/devices/`, {
            method: 'GET'
        });
    }

    async trustDevice(deviceId) {
        return await apiCall(`${this.baseUrl}/trust_device/`, {
            method: 'POST',
            data: { device_id: deviceId }
        });
    }

    async untrustDevice(deviceId) {
        return await apiCall(`${this.baseUrl}/untrust_device/`, {
            method: 'POST',
            data: { device_id: deviceId }
        });
    }

    // Lock Events
    async getLockEvents(limit = 20) {
        return await apiCall(`${this.baseUrl}/lock_events/?limit=${limit}`, {
            method: 'GET'
        });
    }

    // Social Media Account Management (using separate endpoint)
    async createSocialAccount(accountData) {
        return await apiCall('/api/security/social-accounts/', {
            method: 'POST',
            data: accountData
        });
    }

    async updateSocialAccount(accountId, accountData) {
        return await apiCall(`/api/security/social-accounts/${accountId}/`, {
            method: 'PATCH',
            data: accountData
        });
    }

    async deleteSocialAccount(accountId) {
        return await apiCall(`/api/security/social-accounts/${accountId}/`, {
            method: 'DELETE'
        });
    }

    // Real-time monitoring helpers
    startSecurityMonitoring(callback) {
        // Poll for new alerts every 30 seconds
        return setInterval(async () => {
            try {
                const alerts = await this.getSecurityAlerts(false, 5);
                if (alerts.alerts && alerts.alerts.length > 0) {
                    callback(alerts.alerts);
                }
            } catch (error) {
                console.error('Error checking for security alerts:', error);
            }
        }, 30000);
    }

    stopSecurityMonitoring(intervalId) {
        if (intervalId) {
            clearInterval(intervalId);
        }
    }

    // Analytics helpers
    async getSecurityAnalytics(days = 30) {
        try {
            const [dashboard, loginAttempts, alerts] = await Promise.all([
                this.getSecurityDashboard(),
                this.getLoginAttempts(days),
                this.getSecurityAlerts(true, 100)
            ]);

            return {
                metrics: dashboard.security_metrics,
                loginTrends: this.analyzeLoginTrends(loginAttempts.attempts),
                alertTrends: this.analyzeAlertTrends(alerts.alerts)
            };
        } catch (error) {
            console.error('Error getting security analytics:', error);
            throw error;
        }
    }

    analyzeLoginTrends(attempts) {
        const dailyStats = {};
        
        attempts.forEach(attempt => {
            const date = new Date(attempt.timestamp).toDateString();
            if (!dailyStats[date]) {
                dailyStats[date] = { success: 0, failed: 0, suspicious: 0 };
            }
            
            if (attempt.status === 'success') {
                dailyStats[date].success++;
            } else {
                dailyStats[date].failed++;
            }
            
            if (attempt.is_suspicious) {
                dailyStats[date].suspicious++;
            }
        });

        return Object.keys(dailyStats).map(date => ({
            date,
            ...dailyStats[date]
        }));
    }

    analyzeAlertTrends(alerts) {
        const alertTypes = {};
        const severityCounts = { low: 0, medium: 0, high: 0 };
        
        alerts.forEach(alert => {
            if (!alertTypes[alert.alert_type]) {
                alertTypes[alert.alert_type] = 0;
            }
            alertTypes[alert.alert_type]++;
            
            if (severityCounts[alert.severity] !== undefined) {
                severityCounts[alert.severity]++;
            }
        });

        return {
            alertTypes,
            severityCounts
        };
    }

    // Threat assessment
    calculateThreatLevel(securityData) {
        let threatScore = 0;
        
        // Failed attempts contribute to threat
        threatScore += (securityData.failed_attempts_today || 0) * 5;
        
        // Suspicious attempts are higher weight
        threatScore += (securityData.suspicious_attempts_week || 0) * 10;
        
        // Locked accounts indicate active threats
        threatScore += (securityData.locked_accounts || 0) * 15;
        
        // Trusted devices reduce threat
        threatScore -= (securityData.trusted_devices || 0) * 2;
        
        // Normalize to 0-100 scale
        threatScore = Math.max(0, Math.min(100, threatScore));
        
        let level = 'low';
        if (threatScore >= 70) level = 'high';
        else if (threatScore >= 40) level = 'medium';
        
        return {
            score: threatScore,
            level,
            recommendations: this.getThreatRecommendations(threatScore, securityData)
        };
    }

    getThreatRecommendations(threatScore, securityData) {
        const recommendations = [];
        
        if (securityData.failed_attempts_today > 5) {
            recommendations.push('Consider enabling additional 2FA methods');
        }
        
        if (securityData.suspicious_attempts_week > 3) {
            recommendations.push('Review and lock suspicious social media accounts');
        }
        
        if (securityData.trusted_devices < 1) {
            recommendations.push('Mark your regular devices as trusted');
        }
        
        if (threatScore > 50) {
            recommendations.push('Enable auto-lock for all social media accounts');
            recommendations.push('Review recent login attempts for unauthorized access');
        }
        
        return recommendations;
    }

    // Export security report
    async generateSecurityReport(format = 'json') {
        try {
            const [
                dashboard,
                loginAttempts,
                alerts,
                devices,
                lockEvents
            ] = await Promise.all([
                this.getSecurityDashboard(),
                this.getLoginAttempts(30),
                this.getSecurityAlerts(true, 100),
                this.getDevices(),
                this.getLockEvents(50)
            ]);

            const report = {
                generatedAt: new Date().toISOString(),
                period: '30 days',
                summary: dashboard.security_metrics,
                threatAssessment: this.calculateThreatLevel(dashboard.security_metrics),
                loginActivity: loginAttempts.attempts,
                securityAlerts: alerts.alerts,
                devices: devices.devices,
                accountLockEvents: lockEvents.events
            };

            if (format === 'csv') {
                return this.convertToCSV(report);
            }
            
            return report;
        } catch (error) {
            console.error('Error generating security report:', error);
            throw error;
        }
    }

    convertToCSV(report) {
        // Simple CSV conversion for login attempts
        const headers = ['Timestamp', 'IP Address', 'Location', 'Status', 'Threat Score', 'Is Suspicious'];
        const rows = report.loginActivity.map(attempt => [
            attempt.timestamp,
            attempt.ip_address,
            attempt.location,
            attempt.status,
            attempt.threat_score,
            attempt.is_suspicious
        ]);

        const csvContent = [headers, ...rows]
            .map(row => row.map(field => `"${field}"`).join(','))
            .join('\n');

        return csvContent;
    }
}

// Create and export service instance
const accountProtectionService = new AccountProtectionService();
export default accountProtectionService;