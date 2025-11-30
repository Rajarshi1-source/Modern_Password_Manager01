import axios from 'axios';
import { API_URL } from '../config';

class AuthService {
  constructor() {
    this.api = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    this.token = null;
  }
  
  async login(email, password) {
    try {
      const response = await this.api.post('/api/auth/login/', {
        username: email,
        password: password,
      });
      
      if (response.data && response.data.token) {
        this.token = response.data.token;
        this.saveToken(response.data.token);
        return { success: true, data: response.data };
      }
      
      return { success: false, error: 'Invalid credentials' };
    } catch (error) {
      console.error('Login error:', error);
      return { 
        success: false, 
        error: error.response?.data?.error || 'Authentication failed'
      };
    }
  }
  
  async checkMasterPassword(masterPassword) {
    try {
      const response = await this.api.post('/api/auth/verify-master/', {
        master_password: masterPassword,
      }, {
        headers: {
          'Authorization': `Token ${this.token}`
        }
      });
      
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.error || 'Verification failed'
      };
    }
  }
  
  saveToken(token) {
    // Save token to session storage
    // Note: In a real app, you might use AsyncStorage or similar
    this.token = token;
  }
  
  getToken() {
    return this.token;
  }
  
  logout() {
    this.token = null;
  }
}

export const authService = new AuthService();
