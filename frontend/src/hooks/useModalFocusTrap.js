import { useEffect } from 'react';

const FOCUSABLE_SELECTOR =
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Standard modal focus lifecycle: move focus into the dialog when it opens,
 * trap Tab/Shift+Tab within its focusable controls, dismiss on Escape, and
 * restore focus to whatever was focused before the dialog opened.
 *
 * Self-contained — no context dependency — so it can be dropped into a
 * dialog component that is also exercised by unit tests rendering it in
 * isolation, without requiring every such test to wrap the render in an
 * app-level provider.
 *
 * @param {React.RefObject<HTMLElement>} containerRef - Ref to the dialog's
 *   root element (the thing carrying `role="dialog"`).
 * @param {boolean} isOpen - Whether the dialog is currently shown.
 * @param {() => void} onClose - Called when Escape is pressed.
 */
export function useModalFocusTrap(containerRef, isOpen, onClose) {
    useEffect(() => {
        if (!isOpen) return undefined;
        const container = containerRef.current;
        if (!container) return undefined;

        const previouslyFocused = document.activeElement;
        const focusable = container.querySelectorAll(FOCUSABLE_SELECTOR);
        if (focusable.length > 0) {
            focusable[0].focus();
        } else {
            container.focus();
        }

        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                onClose();
                return;
            }
            if (event.key !== 'Tab' || focusable.length === 0) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            if (previouslyFocused instanceof HTMLElement) {
                previouslyFocused.focus();
            }
        };
    }, [isOpen, containerRef, onClose]);
}

export default useModalFocusTrap;
