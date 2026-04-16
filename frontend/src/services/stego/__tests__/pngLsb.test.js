/**
 * Tests for the browser PNG-LSB helpers.
 *
 * We avoid a full PNG round-trip (which would need an actual ``<canvas>``
 * implementation driven by jsdom) and instead verify:
 *
 *   * The non-PNG rejection path.
 *   * That ``PngLsbError`` / ``NotAPngError`` / ``CoverTooSmallError``
 *     form a sensible class hierarchy.
 */

import { describe, expect, test } from 'vitest';

import {
  PngLsbError,
  NotAPngError,
  CoverTooSmallError,
  extractBlobFromPng,
} from '../pngLsb';

describe('pngLsb error hierarchy', () => {
  test('NotAPngError and CoverTooSmallError subclass PngLsbError', () => {
    expect(new NotAPngError()).toBeInstanceOf(PngLsbError);
    expect(new CoverTooSmallError()).toBeInstanceOf(PngLsbError);
  });
});

describe('pngLsb signature guard', () => {
  test('rejects buffers shorter than the PNG signature', async () => {
    await expect(extractBlobFromPng(new Uint8Array(3))).rejects.toBeInstanceOf(
      NotAPngError,
    );
  });

  test('rejects bytes that do not start with the PNG signature', async () => {
    const jpegLike = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0, 0, 0]);
    await expect(extractBlobFromPng(jpegLike)).rejects.toBeInstanceOf(NotAPngError);
  });
});
