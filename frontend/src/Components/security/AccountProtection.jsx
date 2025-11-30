import React, { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import LoginHistory from './components/LoginHistory';
import NotificationSettings from './components/NotificationSettings';
// Standard HTML components - can be replaced with your preferred UI library later
import { 
    Shield, AlertTriangle, Lock, Unlock, Plus,
    Smartphone, Monitor, Globe, CheckCircle, ExternalLink
} from 'lucide-react';

// Simple UI component replacements
const Card = ({ children, className = '' }) => (
    <div className={`bg-white rounded-lg shadow border ${className}`}>{children}</div>
);

const CardHeader = ({ children, className = '' }) => (
    <div className={`px-6 py-4 border-b ${className}`}>{children}</div>
);

const CardTitle = ({ children, className = '' }) => (
    <h3 className={`text-lg font-medium ${className}`}>{children}</h3>
);

const CardContent = ({ children, className = '' }) => (
    <div className={`p-6 ${className}`}>{children}</div>
);

const Button = ({ children, onClick, variant = 'default', size = 'default', disabled = false, className = '', ...props }) => {
    const baseClasses = 'inline-flex items-center justify-center rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none';
    const variants = {
        default: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
        outline: 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus:ring-blue-500',
        destructive: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
        success: 'bg-green-600 text-white hover:bg-green-700 focus:ring-green-500'
    };
    const sizes = {
        default: 'px-4 py-2 text-sm',
        sm: 'px-3 py-1 text-xs',
        lg: 'px-6 py-3 text-base'
    };
    
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${className}`}
            {...props}
        >
            {children}
        </button>
    );
};

const Badge = ({ children, variant = 'default', className = '' }) => {
    const variants = {
        default: 'bg-gray-100 text-gray-800',
        success: 'bg-green-100 text-green-800',
        destructive: 'bg-red-100 text-red-800',
        secondary: 'bg-gray-100 text-gray-800'
    };
    
    return (
        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${variants[variant]} ${className}`}>
            {children}
        </span>
    );
};

const Input = ({ className = '', ...props }) => (
    <input
        className={`flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
        {...props}
    />
);

const Switch = ({ checked, onCheckedChange, className = '' }) => (
    <button
        type="button"
        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
            checked ? 'bg-blue-600' : 'bg-gray-200'
        } ${className}`}
        onClick={() => onCheckedChange(!checked)}
    >
        <span
            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                checked ? 'translate-x-5' : 'translate-x-0'
            }`}
        />
    </button>
);

const Select = ({ value, onValueChange, children, className = '' }) => (
    <select
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className={`flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${className}`}
    >
        {children}
    </select>
);

const SelectItem = ({ value, children }) => (
    <option value={value}>{children}</option>
);

// Removed unused SelectTrigger, SelectValue, SelectContent components

const Alert = ({ children, className = '' }) => (
    <div className={`rounded-lg border p-4 ${className}`}>{children}</div>
);

const Dialog = ({ open, onOpenChange, children }) => {
    if (!open) return null;
    
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white rounded-lg max-w-md w-full mx-4">
                {children}
            </div>
        </div>
    );
};

const DialogContent = ({ children, className = '' }) => (
    <div className={`p-6 ${className}`}>{children}</div>
);

const DialogHeader = ({ children, className = '' }) => (
    <div className={`mb-4 ${className}`}>{children}</div>
);

const DialogTitle = ({ children, className = '' }) => (
    <h2 className={`text-lg font-semibold ${className}`}>{children}</h2>
);

const DialogTrigger = ({ children, asChild }) => {
    if (asChild) return children;
    return children;
};

const FormField = ({ children }) => <div className="space-y-2">{children}</div>;
const FormLabel = ({ children, className = '' }) => (
    <label className={`text-sm font-medium text-gray-700 ${className}`}>{children}</label>
);

const Table = ({ children, className = '' }) => (
    <div className="overflow-x-auto">
        <table className={`min-w-full divide-y divide-gray-200 ${className}`}>{children}</table>
    </div>
);

const TableHeader = ({ children }) => <thead className="bg-gray-50">{children}</thead>;
const TableBody = ({ children }) => <tbody className="bg-white divide-y divide-gray-200">{children}</tbody>;
const TableRow = ({ children, className = '' }) => <tr className={`hover:bg-gray-50 ${className}`}>{children}</tr>;
const TableHead = ({ children, className = '' }) => (
    <th className={`px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider ${className}`}>
        {children}
    </th>
);
const TableCell = ({ children, className = '' }) => (
    <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-900 ${className}`}>{children}</td>
);

const Tabs = ({ value, onValueChange, children, className = '' }) => (
    <div className={className}>{children}</div>
);

const TabsList = ({ children, className = '' }) => (
    <div className={`flex border-b border-gray-200 ${className}`}>{children}</div>
);

const TabsTrigger = ({ value, children, activeTab, setActiveTab }) => (
    <button
        onClick={() => setActiveTab(value)}
        className={`px-4 py-2 text-sm font-medium border-b-2 ${
            activeTab === value 
                ? 'border-blue-600 text-blue-600' 
                : 'border-transparent text-gray-500 hover:text-gray-700'
        }`}
    >
        {children}
    </button>
);

const TabsContent = ({ value, children, activeTab, className = '' }) => {
    if (activeTab !== value) return null;
    return <div className={className}>{children}</div>;
};

const AccountProtection = () => {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [securityData, setSecurityData] = useState(null);
    const [socialAccounts, setSocialAccounts] = useState([]);
    const [loginAttempts, setLoginAttempts] = useState([]);
    const [securityAlerts, setSecurityAlerts] = useState([]);
    const [devices, setDevices] = useState([]);
    const [notificationSettings, setNotificationSettings] = useState({});
    const [loading, setLoading] = useState(true);
    const [isAddAccountDialogOpen, setIsAddAccountDialogOpen] = useState(false);

    useEffect(() => {
        loadSecurityDashboard();
    }, []);

    const loadSecurityDashboard = async () => {
        try {
            setLoading(true);
            const response = await fetch('/api/security/account-protection/security_dashboard/', {
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                setSecurityData(data.security_metrics);
                setSocialAccounts(data.social_accounts);
                setLoginAttempts(data.recent_attempts);
                setSecurityAlerts(data.active_alerts);
                setDevices(data.devices);
            } else {
                toast.error('Failed to load security dashboard');
            }
        } catch (error) {
            console.error('Error loading security dashboard:', error);
            toast.error('Error loading security data');
        } finally {
            setLoading(false);
        }
    };

    const loadNotificationSettings = async () => {
        try {
            const response = await fetch('/api/security/account-protection/notification_settings/', {
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                setNotificationSettings(data);
            }
        } catch (error) {
            console.error('Error loading notification settings:', error);
        }
    };

    const lockAccounts = async (platform) => {
        try {
            const response = await fetch('/api/security/account-protection/lock_accounts/', {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    platform: platform,
                    reason: 'Manual lock by user'
                })
            });

            if (response.ok) {
                const data = await response.json();
                toast.success(data.message);
                loadSecurityDashboard();
            } else {
                toast.error('Failed to lock accounts');
            }
        } catch (error) {
            console.error('Error locking accounts:', error);
            toast.error('Error locking accounts');
        }
    };

    const unlockAccounts = async (platform) => {
        try {
            const response = await fetch('/api/security/account-protection/unlock_accounts/', {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    platform: platform
                })
            });

            if (response.ok) {
                const data = await response.json();
                toast.success(data.message);
                loadSecurityDashboard();
            } else {
                toast.error('Failed to unlock accounts');
            }
        } catch (error) {
            console.error('Error unlocking accounts:', error);
            toast.error('Error unlocking accounts');
        }
    };

    const addSocialAccount = async (accountData) => {
        try {
            const response = await fetch('/api/security/social-accounts/', {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(accountData)
            });

            if (response.ok) {
                toast.success('Social media account added successfully');
                setIsAddAccountDialogOpen(false);
                loadSecurityDashboard();
            } else {
                const errorData = await response.json();
                toast.error(errorData.error || 'Failed to add social media account');
            }
        } catch (error) {
            console.error('Error adding social account:', error);
            toast.error('Error adding social media account');
        }
    };

    const trustDevice = async (deviceId) => {
        try {
            const response = await fetch('/api/security/account-protection/trust_device/', {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ device_id: deviceId })
            });

            if (response.ok) {
                toast.success('Device marked as trusted');
                loadSecurityDashboard();
            } else {
                toast.error('Failed to trust device');
            }
        } catch (error) {
            console.error('Error trusting device:', error);
            toast.error('Error trusting device');
        }
    };

    const resolveAlert = async (alertId) => {
        try {
            const response = await fetch('/api/security/account-protection/resolve_alert/', {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ alert_id: alertId })
            });

            if (response.ok) {
                toast.success('Alert resolved');
                loadSecurityDashboard();
            } else {
                toast.error('Failed to resolve alert');
            }
        } catch (error) {
            console.error('Error resolving alert:', error);
            toast.error('Error resolving alert');
        }
    };

    const updateNotificationSettings = async (settings) => {
        try {
            const response = await fetch('/api/security/account-protection/notification_settings/', {
                method: 'PUT',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            });

            if (response.ok) {
                toast.success('Notification settings updated');
                setNotificationSettings(settings);
            } else {
                toast.error('Failed to update settings');
            }
        } catch (error) {
            console.error('Error updating settings:', error);
            toast.error('Error updating settings');
        }
    };

    const getDeviceIcon = (deviceType) => {
        switch (deviceType) {
            case 'mobile':
                return <Smartphone className="h-4 w-4" />;
            case 'desktop':
                return <Monitor className="h-4 w-4" />;
            default:
                return <Globe className="h-4 w-4" />;
        }
    };

    const getStatusBadge = (status) => {
        const variant = status === 'active' ? 'success' : 
                      status === 'locked' ? 'destructive' : 'secondary';
        return <Badge variant={variant}>{status}</Badge>;
    };

    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'high':
                return 'text-red-600';
            case 'medium':
                return 'text-yellow-600';
            case 'low':
                return 'text-blue-600';
            default:
                return 'text-gray-600';
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold flex items-center gap-2">
                    <Shield className="h-8 w-8 text-blue-600" />
                    Account Protection
                </h1>
                <Button onClick={loadSecurityDashboard} variant="outline">
                    Refresh
                </Button>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full grid-cols-7 lg:grid-cols-7">
                    <TabsTrigger value="dashboard" activeTab={activeTab} setActiveTab={setActiveTab}>Dashboard</TabsTrigger>
                    <TabsTrigger value="accounts" activeTab={activeTab} setActiveTab={setActiveTab}>Social Accounts</TabsTrigger>
                    <TabsTrigger value="alerts" activeTab={activeTab} setActiveTab={setActiveTab}>Security Alerts</TabsTrigger>
                    <TabsTrigger value="devices" activeTab={activeTab} setActiveTab={setActiveTab}>Devices</TabsTrigger>
                    <TabsTrigger value="settings" activeTab={activeTab} setActiveTab={setActiveTab}>Settings</TabsTrigger>
                    <TabsTrigger value="history" activeTab={activeTab} setActiveTab={setActiveTab}>Login History</TabsTrigger>
                    <TabsTrigger value="notifications" activeTab={activeTab} setActiveTab={setActiveTab}>Notification Settings</TabsTrigger>
                </TabsList>

                <TabsContent value="dashboard" activeTab={activeTab} className="space-y-6">
                    {/* Security Metrics */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <Card>
                            <CardContent className="p-6">
                                <div className="flex items-center">
                                    <div className="p-2 bg-red-100 rounded-full">
                                        <AlertTriangle className="h-6 w-6 text-red-600" />
                                    </div>
                                    <div className="ml-4">
                                        <p className="text-sm font-medium text-gray-600">Failed Attempts Today</p>
                                        <p className="text-2xl font-bold">{securityData?.failed_attempts_today || 0}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardContent className="p-6">
                                <div className="flex items-center">
                                    <div className="p-2 bg-yellow-100 rounded-full">
                                        <Shield className="h-6 w-6 text-yellow-600" />
                                    </div>
                                    <div className="ml-4">
                                        <p className="text-sm font-medium text-gray-600">Suspicious This Week</p>
                                        <p className="text-2xl font-bold">{securityData?.suspicious_attempts_week || 0}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardContent className="p-6">
                                <div className="flex items-center">
                                    <div className="p-2 bg-orange-100 rounded-full">
                                        <Lock className="h-6 w-6 text-orange-600" />
                                    </div>
                                    <div className="ml-4">
                                        <p className="text-sm font-medium text-gray-600">Locked Accounts</p>
                                        <p className="text-2xl font-bold">{securityData?.locked_accounts || 0}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardContent className="p-6">
                                <div className="flex items-center">
                                    <div className="p-2 bg-green-100 rounded-full">
                                        <CheckCircle className="h-6 w-6 text-green-600" />
                                    </div>
                                    <div className="ml-4">
                                        <p className="text-sm font-medium text-gray-600">Trusted Devices</p>
                                        <p className="text-2xl font-bold">{securityData?.trusted_devices || 0}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Recent Login Attempts */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Recent Login Attempts</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Time</TableHead>
                                        <TableHead>IP Address</TableHead>
                                        <TableHead>Location</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Threat Score</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {loginAttempts.map((attempt) => (
                                        <TableRow key={attempt.id}>
                                            <TableCell>
                                                {new Date(attempt.timestamp).toLocaleString()}
                                            </TableCell>
                                            <TableCell>{attempt.ip_address}</TableCell>
                                            <TableCell>{attempt.location}</TableCell>
                                            <TableCell>
                                                <Badge variant={attempt.status === 'success' ? 'success' : 'destructive'}>
                                                    {attempt.status}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant={attempt.threat_score > 50 ? 'destructive' : 'secondary'}>
                                                    {attempt.threat_score}
                                                </Badge>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="accounts" activeTab={activeTab} className="space-y-6">
                    <div className="flex justify-between items-center">
                        <h2 className="text-2xl font-bold">Social Media Accounts</h2>
                        <Dialog open={isAddAccountDialogOpen} onOpenChange={setIsAddAccountDialogOpen}>
                            <DialogTrigger asChild>
                                <Button>
                                    <Plus className="mr-2 h-4 w-4" />
                                    Add Account
                                </Button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Add Social Media Account</DialogTitle>
                                </DialogHeader>
                                <AddSocialAccountForm onSubmit={addSocialAccount} />
                            </DialogContent>
                        </Dialog>
                    </div>

                    <div className="grid gap-4">
                        {socialAccounts.map((account) => (
                            <Card key={account.id}>
                                <CardContent className="p-6">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center space-x-4">
                                            <div className="h-12 w-12 bg-blue-100 rounded-full flex items-center justify-center">
                                                <ExternalLink className="h-6 w-6 text-blue-600" />
                                            </div>
                                            <div>
                                                <h3 className="font-semibold">{account.platform}</h3>
                                                <p className="text-sm text-gray-600">{account.username}</p>
                                                <p className="text-xs text-gray-500">{account.email}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            {getStatusBadge(account.status)}
                                            {account.status === 'active' ? (
                                                <Button 
                                                    variant="destructive" 
                                                    size="sm"
                                                    onClick={() => lockAccounts(account.platform)}
                                                >
                                                    <Lock className="mr-2 h-4 w-4" />
                                                    Lock
                                                </Button>
                                            ) : (
                                                <Button 
                                                    variant="outline" 
                                                    size="sm"
                                                    onClick={() => unlockAccounts(account.platform)}
                                                >
                                                    <Unlock className="mr-2 h-4 w-4" />
                                                    Unlock
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </TabsContent>

                <TabsContent value="alerts" activeTab={activeTab} className="space-y-6">
                    <h2 className="text-2xl font-bold">Security Alerts</h2>
                    
                    <div className="space-y-4">
                        {securityAlerts.map((alert) => (
                            <Alert key={alert.id} className="p-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-start space-x-3">
                                        <AlertTriangle className={`h-5 w-5 mt-0.5 ${getSeverityColor(alert.severity)}`} />
                                        <div>
                                            <h4 className="font-semibold">{alert.title}</h4>
                                            <p className="text-sm text-gray-600 mt-1">{alert.message}</p>
                                            <p className="text-xs text-gray-500 mt-2">
                                                {new Date(alert.created_at).toLocaleString()}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <Badge variant={alert.severity === 'high' ? 'destructive' : 'secondary'}>
                                            {alert.severity_display}
                                        </Badge>
                                        <Button 
                                            variant="outline" 
                                            size="sm"
                                            onClick={() => resolveAlert(alert.id)}
                                        >
                                            Resolve
                                        </Button>
                                    </div>
                                </div>
                            </Alert>
                        ))}
                    </div>
                </TabsContent>

                <TabsContent value="devices" activeTab={activeTab} className="space-y-6">
                    <h2 className="text-2xl font-bold">Trusted Devices</h2>
                    
                    <div className="grid gap-4">
                        {devices.map((device) => (
                            <Card key={device.id}>
                                <CardContent className="p-6">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center space-x-4">
                                            <div className="p-2 bg-gray-100 rounded-full">
                                                {getDeviceIcon(device.device_type)}
                                            </div>
                                            <div>
                                                <h3 className="font-semibold">{device.device_name}</h3>
                                                <p className="text-sm text-gray-600">{device.browser} on {device.os}</p>
                                                <p className="text-xs text-gray-500">
                                                    Last seen: {new Date(device.last_seen).toLocaleString()}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            {device.is_trusted ? (
                                                <Badge variant="success">Trusted</Badge>
                                            ) : (
                                                <Button 
                                                    variant="outline" 
                                                    size="sm"
                                                    onClick={() => trustDevice(device.device_id)}
                                                >
                                                    Trust Device
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </TabsContent>

                <TabsContent value="settings" activeTab={activeTab} className="space-y-6">
                    {/* Using inline settings component for account-specific settings */}
                    <InlineNotificationSettings 
                        settings={notificationSettings}
                        onUpdate={updateNotificationSettings}
                        onLoad={loadNotificationSettings}
                    />
                </TabsContent>

                <TabsContent value="history" activeTab={activeTab} className="space-y-6">
                    <LoginHistory />
                </TabsContent>

                <TabsContent value="notifications" activeTab={activeTab} className="space-y-6">
                    {/* Using the imported comprehensive notification settings component */}
                    <NotificationSettings />
                </TabsContent>
            </Tabs>
        </div>
    );
};

// Add Social Account Form Component
const AddSocialAccountForm = ({ onSubmit }) => {
    const [formData, setFormData] = useState({
        platform: '',
        username: '',
        email: '',
        auto_lock_enabled: true
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit(formData);
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <FormField>
                <FormLabel>Platform</FormLabel>
                <Select 
                    value={formData.platform} 
                    onValueChange={(value) => setFormData({...formData, platform: value})}
                >
                    <SelectItem value="">Select platform</SelectItem>
                    <SelectItem value="facebook">Facebook</SelectItem>
                    <SelectItem value="twitter">Twitter</SelectItem>
                    <SelectItem value="instagram">Instagram</SelectItem>
                    <SelectItem value="linkedin">LinkedIn</SelectItem>
                    <SelectItem value="google">Google</SelectItem>
                </Select>
            </FormField>

            <FormField>
                <FormLabel>Username</FormLabel>
                <Input
                    value={formData.username}
                    onChange={(e) => setFormData({...formData, username: e.target.value})}
                    placeholder="Enter username"
                    required
                />
            </FormField>

            <FormField>
                <FormLabel>Email</FormLabel>
                <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    placeholder="Enter email"
                    required
                />
            </FormField>

            <FormField>
                <div className="flex items-center space-x-2">
                    <Switch
                        checked={formData.auto_lock_enabled}
                        onCheckedChange={(checked) => setFormData({...formData, auto_lock_enabled: checked})}
                    />
                    <FormLabel>Enable auto-lock on suspicious activity</FormLabel>
                </div>
            </FormField>

            <Button type="submit" className="w-full">
                Add Account
            </Button>
        </form>
    );
};

// Notification Settings Component
// Renamed the inline component to avoid conflicts with the imported one
//This component is specifically designed for account protection settings
const InlineNotificationSettings = ({ settings, onUpdate, onLoad }) => {
    const [localSettings, setLocalSettings] = useState(settings);

    useEffect(() => {
        if (onLoad) {
            onLoad();
        }
    }, [onLoad]);

    useEffect(() => {
        setLocalSettings(settings);
    }, [settings]);

    const handleSave = () => {
        if (onUpdate) {
            onUpdate(localSettings);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>Account Protection Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h4 className="font-medium">Email Alerts</h4>
                        <p className="text-sm text-gray-600">Receive security alerts via email</p>
                    </div>
                    <Switch
                        checked={localSettings.email_alerts || false}
                        onCheckedChange={(checked) => 
                            setLocalSettings({...localSettings, email_alerts: checked})
                        }
                    />
                </div>

                <div className="flex items-center justify-between">
                    <div>
                        <h4 className="font-medium">Auto-lock Accounts</h4>
                        <p className="text-sm text-gray-600">Automatically lock social media accounts on suspicious activity</p>
                    </div>
                    <Switch
                        checked={localSettings.auto_lock_accounts || false}
                        onCheckedChange={(checked) => 
                            setLocalSettings({...localSettings, auto_lock_accounts: checked})
                        }
                    />
                </div>

                <div>
                    <FormLabel>Suspicious Activity Threshold</FormLabel>
                    <Input
                        type="number"
                        min="1"
                        max="10"
                        value={localSettings.suspicious_activity_threshold || 3}
                        onChange={(e) => 
                            setLocalSettings({
                                ...localSettings, 
                                suspicious_activity_threshold: parseInt(e.target.value)
                            })
                        }
                    />
                    <p className="text-sm text-gray-600 mt-1">
                        Number of suspicious attempts before triggering alerts
                    </p>
                </div>

                <Button onClick={handleSave} className="w-full">
                    Save Settings
                </Button>
            </CardContent>
        </Card>
    );
};

export default AccountProtection; 