import { describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { HybridModel } from './HybridModel';
import { BackendAPI } from './BackendAPI';

// The raw behavioral profile must never reach the server, even when the
// in-browser model fails.
vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe('behavioral embeddings stay in the browser', () => {
  it('fails instead of falling back to the server', async () => {
    const model = new HybridModel();
    model.transformerModel.loadModel = vi.fn().mockResolvedValue(undefined);
    model.transformerModel.generateEmbedding = vi.fn().mockRejectedValue(new Error('tfjs failed'));
    await expect(model.generateEmbedding({ keystrokes: [1, 2, 3] })).rejects.toThrow('tfjs failed');
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('refuses to start when the in-browser model cannot load', async () => {
    const model = new HybridModel();
    model.transformerModel.loadModel = vi.fn().mockRejectedValue(new Error('no tfjs'));
    await expect(model.generateEmbedding({ keystrokes: [1] })).rejects.toThrow();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('the retired BackendAPI methods send nothing', async () => {
    const api = new BackendAPI();
    await expect(api.generateEmbedding({ keystrokes: [1] })).rejects.toThrow();
    await expect(api.verifyProfile({ keystrokes: [1] }, [0.1])).rejects.toThrow();
    expect(axios.post).not.toHaveBeenCalled();
  });
});
