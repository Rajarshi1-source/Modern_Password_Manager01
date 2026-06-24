/**
 * Synesthetic Signature
 * =====================
 *
 * Renders a deterministic, multi-sensory "signature" for a password:
 *  - an identicon-style grid (at-a-glance recognition),
 *  - a row of coloured glyphs (one per character; shape + colour, so it is
 *    colour-blind safe), and
 *  - an optional on-demand melody (pentatonic, played via the Web Audio API).
 *
 * Privacy: the visualisation is reversible — it IS the password, encoded — so
 * this component is meant to live only where the plaintext is already visible
 * (e.g. the password generator). It never persists, logs, or transmits anything;
 * the password is held in memory only for the duration of a render. Per-glyph
 * accessible labels intentionally describe shape/position, never the character.
 *
 * Audio is OFF by default and only ever plays in response to an explicit click
 * (browsers also require a user gesture to start an AudioContext).
 */

import React, { useMemo, useRef, useEffect, useCallback } from 'react';
import styled from 'styled-components';
import { motion, useReducedMotion } from 'framer-motion';
import { FaVolumeUp } from 'react-icons/fa';
import { passwordToSensoryMap } from '../../utils/synesthesia';

// Cap how many notes we sonify so a 64-character password doesn't play a
// marathon tone sequence.
const MAX_MELODY_NOTES = 32;
const NOTE_DURATION_S = 0.18;

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
  margin: 12px 0;
  border-radius: 8px;
  background: ${(props) => props.theme.backgroundSecondary || 'rgba(127,127,127,0.06)'};
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
`;

const Title = styled.span`
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: ${(props) => props.theme.textSecondary || '#9ca3af'};
`;

const Body = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
`;

const GlyphRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: 1;
  min-width: 0;
`;

const PlayButton = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid ${(props) => props.theme.borderColor || 'rgba(127,127,127,0.3)'};
  background: transparent;
  color: ${(props) => props.theme.textSecondary || '#9ca3af'};
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s ease;

  &:hover {
    background: ${(props) => props.theme.backgroundHover || 'rgba(127,127,127,0.12)'};
  }
`;

const Hint = styled.span`
  font-size: 12px;
  color: ${(props) => props.theme.textSecondary || '#9ca3af'};
`;

// --- SVG helpers ------------------------------------------------------------

// Inner SVG geometry for each glyph name. Kept tiny and self-contained.
function GlyphShape({ name, color }) {
  switch (name) {
    case 'triangle':
      return <polygon points="11,3 19,19 3,19" fill={color} />;
    case 'square':
      return <rect x="4" y="4" width="14" height="14" rx="2" fill={color} />;
    case 'diamond':
      return <polygon points="11,2 20,11 11,20 2,11" fill={color} />;
    case 'wave':
      return (
        <path
          d="M2 11 Q6 4 11 11 T20 11"
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      );
    case 'hexagon':
      return <polygon points="11,2 19,6.5 19,15.5 11,20 3,15.5 3,6.5" fill={color} />;
    case 'star':
      return (
        <polygon
          points="11,2 13.5,8.5 20,8.5 14.7,12.5 16.8,19 11,15 5.2,19 7.3,12.5 2,8.5 8.5,8.5"
          fill={color}
        />
      );
    case 'cross':
      return <polygon points="8,2 14,2 14,8 20,8 20,14 14,14 14,20 8,20 8,14 2,14 2,8 8,8" fill={color} />;
    case 'circle':
    default:
      return <circle cx="11" cy="11" r="8" fill={color} />;
  }
}

function Identicon({ signature }) {
  const { cells, color, size } = signature;
  const unit = 8;
  const dim = size * unit;
  return (
    <svg
      width={dim}
      height={dim}
      viewBox={`0 0 ${dim} ${dim}`}
      aria-hidden="true"
      style={{ borderRadius: 6, flex: '0 0 auto', background: 'rgba(127,127,127,0.08)' }}
    >
      {cells.map((rowCells, r) =>
        rowCells.map((on, c) =>
          on ? (
            <rect
              // Grid coordinates are a stable identity for these static cells.
              key={`${r}-${c}`}
              x={c * unit}
              y={r * unit}
              width={unit}
              height={unit}
              fill={color}
            />
          ) : null,
        ),
      )}
    </svg>
  );
}

// --- Component --------------------------------------------------------------

const SynestheticSignature = ({ password = '', showAudio = true }) => {
  const prefersReducedMotion = useReducedMotion();
  const audioCtxRef = useRef(null);

  const sensory = useMemo(() => passwordToSensoryMap(password), [password]);

  // Tear down any AudioContext we created when the component unmounts so we
  // don't leak audio resources.
  useEffect(() => {
    return () => {
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    };
  }, []);

  const playMelody = useCallback(() => {
    const notes = sensory.chars.slice(0, MAX_MELODY_NOTES).map((c) => c.note.freq);
    if (notes.length === 0) return;

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return; // Web Audio unsupported — silently no-op.

    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioCtx();
    }
    const ctx = audioCtxRef.current;
    // A click may arrive while the context is suspended (autoplay policy).
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});

    const start = ctx.currentTime;
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const t = start + i * NOTE_DURATION_S;
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.18, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + NOTE_DURATION_S);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + NOTE_DURATION_S);
    });
  }, [sensory]);

  if (sensory.length === 0) {
    return null;
  }

  const motionProps = prefersReducedMotion
    ? {}
    : { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 } };

  return (
    <Container
      as={motion.div}
      {...motionProps}
      role="img"
      aria-label="Synesthetic signature: a colour-and-shape memory aid for the password shown above"
    >
      <Header>
        <Title>🎨 Synesthetic Signature</Title>
        {showAudio && (
          <PlayButton type="button" onClick={playMelody} aria-label="Play the password's melody">
            <FaVolumeUp aria-hidden="true" /> Play melody
          </PlayButton>
        )}
      </Header>

      <Body>
        <Identicon signature={sensory.signature} />
        <GlyphRow>
          {sensory.chars.map((c) => (
            <svg
              key={c.index}
              data-testid="syn-glyph"
              width="22"
              height="22"
              viewBox="0 0 22 22"
              aria-hidden="true"
              focusable="false"
            >
              <GlyphShape name={c.glyph.name} color={c.color.css} />
            </svg>
          ))}
        </GlyphRow>
      </Body>

      <Hint>Same password → same signature. A memory aid; do not treat it as less sensitive than the password itself.</Hint>
    </Container>
  );
};

export default SynestheticSignature;
