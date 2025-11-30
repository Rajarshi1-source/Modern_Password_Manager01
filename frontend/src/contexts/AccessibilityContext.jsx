import React, { createContext, useContext, useState, useCallback } from 'react';

const AccessibilityContext = createContext(null);

export const AccessibilityProvider = ({ children }) => {
  const [focusedElementId, setFocusedElementId] = useState(null);

  const handleKeyNavigation = useCallback((event, elementRefs) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const currentIndex = elementRefs.findIndex(ref => ref.current === document.activeElement);
      const nextIndex = event.key === 'ArrowDown' 
        ? (currentIndex + 1) % elementRefs.length 
        : (currentIndex - 1 + elementRefs.length) % elementRefs.length;
      
      elementRefs[nextIndex].current?.focus();
    }
  }, []);

  const trapFocus = useCallback((containerRef) => {
    const focusableElements = containerRef.current?.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    
    if (focusableElements?.length) {
      focusableElements[0].focus();
      
      return (e) => {
        if (e.key === 'Tab') {
          if (e.shiftKey && document.activeElement === focusableElements[0]) {
            e.preventDefault();
            focusableElements[focusableElements.length - 1].focus();
          } else if (!e.shiftKey && document.activeElement === focusableElements[focusableElements.length - 1]) {
            e.preventDefault();
            focusableElements[0].focus();
          }
        }
      };
    }
    
    return null;
  }, []);

  return (
    <AccessibilityContext.Provider value={{ 
      focusedElementId, 
      setFocusedElementId,
      handleKeyNavigation,
      trapFocus 
    }}>
      {children}
    </AccessibilityContext.Provider>
  );
};

export const useAccessibility = () => useContext(AccessibilityContext);
