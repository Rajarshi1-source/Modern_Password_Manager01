/**
 * Regression test for the ExpressionChallenge progress/advance split.
 *
 * The advance-to-next-expression logic used to live inside the setCurrentProgress
 * updater. React 18 StrictMode double-invokes updaters in dev, which enqueued the
 * advance twice and skipped an expression (firing onComplete after the FIRST bar
 * instead of the last). This renders under StrictMode (so the double-invocation
 * is active) and asserts the sequence advances by exactly one per filled bar.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { StrictMode } from 'react';
import { render, screen, act } from '@testing-library/react';
import ExpressionChallenge from '../ExpressionChallenge';

describe('ExpressionChallenge advance is StrictMode-safe', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it('advances one expression per filled bar and completes only after the last', () => {
        const onComplete = vi.fn();
        render(
            <StrictMode>
                <ExpressionChallenge
                    challenge={{ data: { expressions: ['happy', 'surprise'] } }}
                    onComplete={onComplete}
                    holdMsPerExpression={1000}
                />
            </StrictMode>
        );

        // Two expressions requested, first one showing.
        expect(screen.getByText('1 / 2')).toBeInTheDocument();

        // Fill the first bar. Must advance to the SECOND expression, not skip it
        // and complete (the pre-fix bug advanced twice under StrictMode).
        act(() => { vi.advanceTimersByTime(1000); });
        expect(screen.getByText('2 / 2')).toBeInTheDocument();
        expect(onComplete).not.toHaveBeenCalled();

        // Fill the second bar -> completes exactly once.
        act(() => { vi.advanceTimersByTime(1000); });
        expect(onComplete).toHaveBeenCalledTimes(1);
    });
});
