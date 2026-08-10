import { useEffect, useRef } from 'react';

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
    // Read via a ref rather than putting `onClose` in the effect's own
    // dependency array: a caller passing an inline arrow (both call sites
    // here do, e.g. `onClose = () => {}`) gets a new function identity on
    // every render, which would re-run the effect below — including its
    // "focus the first control" step — on every re-render of an ALREADY-OPEN
    // dialog, yanking focus back to the top of the dialog on every keystroke
    // or state update elsewhere in the component.
    const onCloseRef = useRef(onClose);
    onCloseRef.current = onClose;

    useEffect(() => {
        if (!isOpen) return undefined;
        const container = containerRef.current;
        if (!container) return undefined;

        // Excludes `:disabled` controls, and is called fresh on every
        // keydown rather than captured once: a control that starts disabled
        // (the consent dialog's Enable button, gated on the checkbox) is
        // never actually reachable via the browser's own native Tab order,
        // so treating it as "last" made the wrap-around condition
        // (`activeElement === last`) unsatisfiable — Tab from the true last
        // reachable control left the dialog entirely instead of wrapping.
        // Recomputing also picks up a control that becomes enabled after
        // this effect first ran (e.g. checking that same box).
        const getFocusable = () =>
            Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR))
                .filter((element) => !element.matches(':disabled'));

        const previouslyFocused = document.activeElement;
        const initialFocusable = getFocusable();
        if (initialFocusable.length > 0) {
            initialFocusable[0].focus();
        } else {
            container.focus();
        }

        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                onCloseRef.current();
                return;
            }
            const focusable = getFocusable();
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
    }, [isOpen, containerRef]);
}

export default useModalFocusTrap;
