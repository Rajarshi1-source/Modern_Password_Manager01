// Improved login form detection and autofill
(function() {
  // Initialize variables
  let formDetected = false;
  let detectedForms = [];
  let currentUrl = window.location.origin;
  let domain = extractDomain(window.location.hostname);

  // Listen for DOM content loaded
  document.addEventListener('DOMContentLoaded', initFormDetection);

  // Also run immediately in case DOM is already loaded
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initFormDetection();
  }

  function initFormDetection() {
    // Initial scan for login forms
    scanForLoginForms();

    // Set up mutation observer to detect dynamically added forms
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length > 0) {
          scanForLoginForms();
        }
      });
    });

    // Start observing DOM changes
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    // Add event listeners for form submissions
    document.addEventListener('submit', handleFormSubmission);
  }

  function scanForLoginForms() {
    // Reset detected forms when rescanning
    detectedForms = [];
    
    // Find all password fields
    const passwordFields = document.querySelectorAll('input[type="password"]');
    
    if (passwordFields.length > 0 && !formDetected) {
      formDetected = true;

      // Process each password field
      passwordFields.forEach(passwordField => {
        const form = passwordField.closest('form');
        const usernameField = findUsernameField(passwordField, form);
        
        if (usernameField) {
          // Store form information
          detectedForms.push({
            form: form,
            passwordField: passwordField,
            usernameField: usernameField
          });
          
          // Notify background script about login form
          chrome.runtime.sendMessage({
            action: 'login_form_detected',
            url: window.location.href,
            domain: domain
          });
          
          // Add visual indicators next to fields
          addAutofillIndicator(usernameField);
        }
      });
    }
  }

  function findUsernameField(passwordField, form) {
    // Common username field selectors
    const usernameSelectors = [
      'input[type="email"]',
      'input[name="email"]',
      'input[name="username"]',
      'input[id="email"]',
      'input[id="username"]',
      'input[autocomplete="username"]',
      'input[autocomplete="email"]'
    ];
    
    // Try to find username field within the same form
    if (form) {
      for (const selector of usernameSelectors) {
        const field = form.querySelector(selector);
        if (field) return field;
      }
      
      // If not found by specific selectors, try to find any text input before password
      const inputs = Array.from(form.querySelectorAll('input[type="text"]'));
      const usernameInput = inputs.find(input => {
        return input.compareDocumentPosition(passwordField) & Node.DOCUMENT_POSITION_FOLLOWING;
      });
      
      if (usernameInput) return usernameInput;
    }
    
    // Fallback to looking in the entire document
    for (const selector of usernameSelectors) {
      const field = document.querySelector(selector);
      if (field) return field;
    }
    
    // Final fallback to any text input that precedes the password field
    const allInputs = Array.from(document.querySelectorAll('input[type="text"], input[type="email"]'));
    return allInputs.find(input => {
      return input.compareDocumentPosition(passwordField) & Node.DOCUMENT_POSITION_FOLLOWING;
    });
  }

  function addAutofillIndicator(field) {
    if (!field) return;
    
    // Add autofill icon/button
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    
    // Don't add duplicate indicators
    if (field.parentNode.classList.contains('pm-field-wrapper')) {
      return;
    }
    
    // Insert wrapper
    field.parentNode.insertBefore(wrapper, field);
    wrapper.appendChild(field);
    wrapper.classList.add('pm-field-wrapper');
    
    // Create indicator element
    const indicator = document.createElement('div');
    indicator.innerHTML = '🔑'; // Use an icon or emoji as indicator
    indicator.className = 'pm-autofill-indicator';
    indicator.style.cssText = `
      position: absolute;
      right: 10px;
      top: 50%;
      transform: translateY(-50%);
      cursor: pointer;
      z-index: 9999;
      font-size: 16px;
    `;
    
    // Attach event listener to the indicator
    indicator.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      // Request credentials for this domain
      chrome.runtime.sendMessage({
        action: 'get_credentials',
        url: window.location.href,
        domain: domain
      });
    });
    
    wrapper.appendChild(indicator);
  }

  function autofillCredentials(credentials) {
    // Handle case of multiple credentials
    if (Array.isArray(credentials) && credentials.length > 1) {
      showCredentialPicker(credentials);
      return;
    }
    
    // Single credential or first from array
    const credential = Array.isArray(credentials) ? credentials[0] : credentials;
    
    if (!credential || !credential.username) {
      console.error('Invalid credentials provided for autofill');
      return;
    }
    
    // Find form to fill
    if (detectedForms.length > 0) {
      const form = detectedForms[0];
      
      // Fill in the credentials
      if (form.usernameField && credential.username) {
        form.usernameField.value = credential.username;
        
        // Dispatch input event to trigger any listeners
        form.usernameField.dispatchEvent(new Event('input', { bubbles: true }));
      }
      
      if (form.passwordField && credential.password) {
        form.passwordField.value = credential.password;
        
        // Dispatch input event to trigger any listeners
        form.passwordField.dispatchEvent(new Event('input', { bubbles: true }));
      }
      
      return true;
    }
    
    return false;
  }

  function showCredentialPicker(credentials) {
    // Create credential picker UI
    const overlay = document.createElement('div');
    overlay.className = 'pm-credential-picker-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      z-index: 99999;
      display: flex;
      justify-content: center;
      align-items: center;
    `;
    
    const pickerContainer = document.createElement('div');
    pickerContainer.className = 'pm-credential-picker';
    pickerContainer.style.cssText = `
      background: white;
      border-radius: 8px;
      width: 350px;
      max-width: 90%;
      padding: 20px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    `;
    
    const title = document.createElement('h3');
    title.textContent = 'Choose account';
    title.style.cssText = `
      margin-top: 0;
      padding-bottom: 10px;
      border-bottom: 1px solid #eee;
      font-size: 16px;
    `;
    
    const list = document.createElement('div');
    
    // Add each credential as a selectable item
    credentials.forEach(cred => {
      const item = document.createElement('div');
      item.className = 'pm-credential-item';
      item.style.cssText = `
        padding: 10px;
        border-bottom: 1px solid #eee;
        cursor: pointer;
        display: flex;
        align-items: center;
      `;
      
      const icon = document.createElement('div');
      icon.textContent = '👤';
      icon.style.marginRight = '10px';
      
      const username = document.createElement('div');
      username.textContent = cred.username;
      username.style.flexGrow = '1';
      
      item.appendChild(icon);
      item.appendChild(username);
      
      // Handle credential selection
      item.addEventListener('click', () => {
        autofillCredentials(cred);
        document.body.removeChild(overlay);
      });
      
      list.appendChild(item);
    });
    
    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.textContent = 'Cancel';
    closeBtn.style.cssText = `
      margin-top: 15px;
      padding: 8px 12px;
      background: #f5f5f5;
      border: 1px solid #ddd;
      border-radius: 4px;
      cursor: pointer;
    `;
    closeBtn.addEventListener('click', () => {
      document.body.removeChild(overlay);
    });
    
    // Assemble picker
    pickerContainer.appendChild(title);
    pickerContainer.appendChild(list);
    pickerContainer.appendChild(closeBtn);
    overlay.appendChild(pickerContainer);
    
    // Add to DOM
    document.body.appendChild(overlay);
  }

  function handleFormSubmission(e) {
    if (!formDetected) return;
    
    // Find the form that's being submitted
    const form = e.target;
    const passwordField = form.querySelector('input[type="password"]');
    
    if (passwordField) {
      const usernameField = findUsernameField(passwordField, form);
      
      if (usernameField && passwordField.value) {
        // Capture credentials
        const credentials = {
          domain: domain,
          url: window.location.href,
          username: usernameField.value,
          password: passwordField.value
        };
        
        // Send to background script to save
        chrome.runtime.sendMessage({
          action: 'save_credentials',
          credentials: credentials
        });
      }
    }
  }

  // Extract domain from hostname
  function extractDomain(hostname) {
    const parts = hostname.split('.');
    if (parts.length <= 2) return hostname;
    
    // Handle special cases like co.uk, com.au
    if (parts.length > 2 && (parts[parts.length-2] === 'co' || parts[parts.length-2] === 'com')) {
      return parts.slice(-3).join('.');
    }
    
    return parts.slice(-2).join('.');
  }

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'autofill') {
      const success = autofillCredentials(message.credentials);
      sendResponse({ success });
    }
    return true;
  });
})();
