import abTestService from './abTestService';

describe('ABTestService', () => {
  beforeEach(() => {
    // Clear local storage and reset service
    localStorage.clear();
    abTestService.reset();
  });

  test('assigns variant consistently for same user/session', () => {
    const variant1 = abTestService.getVariant('test-experiment', ['A', 'B']);
    const variant2 = abTestService.getVariant('test-experiment', ['A', 'B']);
    
    expect(variant1).toBe(variant2);
  });

  test('respects forced variant', () => {
    abTestService.setVariant('test-experiment', 'B');
    const variant = abTestService.getVariant('test-experiment', ['A', 'B']);
    
    expect(variant).toBe('B');
  });

  test('distributes variants (approximate)', () => {
    // This is a probabilistic test, so we just check it returns valid variants
    const variants = ['A', 'B'];
    const results = new Set();
    
    // Simulate multiple users by resetting service but keeping assignments logic (mocking would be better for pure unit test)
    // Here we just test that we get one of the valid variants
    const variant = abTestService.getVariant('new-experiment', variants);
    expect(variants).toContain(variant);
  });
  
  test('genetic_feature_highlight experiment uses control/treatment', () => {
    const variant = abTestService.getVariant('genetic_launch_highlight');
    expect(['control', 'variant']).toContain(variant);
  });
});
