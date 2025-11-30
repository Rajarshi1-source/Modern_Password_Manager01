document.addEventListener('DOMContentLoaded', async () => {
  // Get references to UI elements
  const unlockButton = document.getElementById('unlock-btn');
  const openAppButton = document.getElementById('open-app-btn');
  const statusIndicator = document.querySelector('.status-indicator');
  const statusText = document.querySelector('.status-text');
  const loginForm = document.getElementById('login-form');
  const passwordInput = document.getElementById('master-password');
  const loginError = document.getElementById('login-error');
  const logoutButton = document.getElementById('logout-btn');
  const vaultSection = document.getElementById('vault-section');
  const loginSection = document.getElementById('login-section');
  const settingsSection = document.getElementById('settings-section');
  
  // Check auth status
  const isAuthenticated = await checkAuthStatus();
  updateUI(isAuthenticated);
  
  // Setup event listeners
  unlockButton.addEventListener('click', showLoginForm);
  
  openAppButton.addEventListener('click', () => {
    chrome.tabs.create({ url: 'http://localhost:8000' });
  });
  
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    await handleLogin();
  });
  
  logoutButton.addEventListener('click', async () => {
    await handleLogout();
  });
  
  // Check current tab for login forms
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0] && isAuthenticated) {
      checkForLoginForms(tabs[0]);
    }
  });
  
  // Load auto-lock settings
  chrome.storage.local.get(['settings'], (result) => {
    const settings = result.settings || {};
    const autoLockSelect = document.getElementById('auto-lock-timeout');
    
    if (autoLockSelect) {
      autoLockSelect.value = settings.autoLockTimeout || 5;
      
      autoLockSelect.addEventListener('change', () => {
        const timeout = parseInt(autoLockSelect.value, 10);
        chrome.storage.local.set({
          settings: {
            ...settings,
            autoLockTimeout: timeout
          }
        });
      });
    }
  });
  
  async function checkAuthStatus() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: 'check_auth_status' }, (response) => {
        resolve(response.isAuthenticated);
      });
    });
  }
  
  function updateUI(isAuthenticated) {
    if (isAuthenticated) {
      statusIndicator.style.backgroundColor = '#4CAF50';
      statusText.textContent = 'Vault is unlocked';
      unlockButton.style.display = 'none';
      logoutButton.style.display = 'block';
      vaultSection.style.display = 'block';
      loginSection.style.display = 'none';
      settingsSection.style.display = 'block';
    } else {
      statusIndicator.style.backgroundColor = '#cc0000';
      statusText.textContent = 'Vault is locked';
      unlockButton.style.display = 'block';
      logoutButton.style.display = 'none';
      vaultSection.style.display = 'none';
      loginSection.style.display = 'none';
      settingsSection.style.display = 'none';
    }
  }
  
  function showLoginForm() {
    loginSection.style.display = 'block';
    unlockButton.style.display = 'none';
    loginError.style.display = 'none';
    passwordInput.focus();
  }
  
  async function handleLogin() {
    const masterPassword = passwordInput.value;
    
    if (!masterPassword) {
      loginError.textContent = 'Master password is required';
      loginError.style.display = 'block';
      return;
    }
    
    // Disable form during login
    passwordInput.disabled = true;
    loginForm.querySelector('button').disabled = true;
    
    // Send login request
    chrome.runtime.sendMessage(
      { action: 'authenticate', masterPassword },
      (response) => {
        passwordInput.disabled = false;
        loginForm.querySelector('button').disabled = false;
        
        if (response.success) {
          updateUI(true);
          passwordInput.value = '';
          
          // Check if there are login forms on the current tab
          chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
              checkForLoginForms(tabs[0]);
            }
          });
        } else {
          loginError.textContent = response.error || 'Authentication failed';
          loginError.style.display = 'block';
        }
      }
    );
  }
  
  async function handleLogout() {
    chrome.runtime.sendMessage({ action: 'logout' }, (response) => {
      if (response.success) {
        updateUI(false);
      }
    });
  }
  
  function checkForLoginForms(tab) {
    // Check if the current tab has login forms
    chrome.tabs.sendMessage(
      tab.id,
      { action: 'check_for_forms' },
      (response) => {
        if (response && response.hasLoginForm) {
          const formSection = document.getElementById('form-section');
          const fillButton = document.getElementById('fill-password-btn');
          
          formSection.style.display = 'block';
          
          fillButton.addEventListener('click', () => {
            chrome.tabs.sendMessage(
              tab.id,
              { action: 'show_credential_picker' }
            );
            window.close(); // Close popup after triggering picker
          });
        }
      }
    );
  }
});
