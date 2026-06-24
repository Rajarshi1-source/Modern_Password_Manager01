/**
 * Synesthetic Password Visualization — standalone surface (Phase 2)
 * =================================================================
 *
 * A reachable page for the feature: a short explainer, the preference toggles
 * (backed by preferencesService — persisted locally and synced through the
 * existing service, no new backend), and a live demo that reuses the password
 * generator so the signature is shown in its real context.
 *
 * The toggles here drive the same preferences the generator reads, so flipping
 * them updates the embedded demo (and the generator inside the vault) live.
 */

import React from 'react';
import styled from 'styled-components';
import { FaPalette } from 'react-icons/fa';
import {
  Section,
  SectionHeader,
  SectionHeaderContent,
  SectionIcon,
  SettingItem,
  SettingInfo,
  SettingControl,
  ToggleSwitch,
  InfoBox,
  InfoText,
} from '../settings/SettingsComponents';
import usePreference from '../../hooks/usePreference';
import PasswordGenerator from './PasswordGenerator';

const Page = styled.div`
  max-width: 760px;
  margin: 0 auto;
  padding: 24px 16px 48px;
`;

const PageHeader = styled.header`
  margin-bottom: 24px;

  h1 {
    font-size: 24px;
    margin: 0 0 8px;
    color: ${(props) => props.theme.textPrimary || 'inherit'};
  }

  p {
    margin: 0;
    color: ${(props) => props.theme.textSecondary || '#9ca3af'};
    line-height: 1.5;
  }
`;

const DemoSection = styled.div`
  margin-top: 28px;

  h2 {
    font-size: 16px;
    margin: 0 0 6px;
    color: ${(props) => props.theme.textPrimary || 'inherit'};
  }

  p {
    margin: 0 0 16px;
    color: ${(props) => props.theme.textSecondary || '#9ca3af'};
  }
`;

/**
 * Standalone page for the Synesthetic Password Visualization feature: a short
 * explainer, the preferencesService-backed display/audio toggles, and a live
 * demo (the password generator) that reflects those toggles.
 */
const SynestheticDashboard = () => {
  const [enabled, setEnabled] = usePreference('security.synestheticSignature', true);
  const [audio, setAudio] = usePreference('security.synestheticAudio', false);

  return (
    <Page>
      <PageHeader>
        <h1>🎨 Synesthetic Password Visualization</h1>
        <p>
          Every password maps to a stable colour-and-shape “signature” (and an optional pentatonic
          melody) so you can recognise it at a glance. The same password always looks and sounds the
          same — a memory aid, computed entirely in your browser.
        </p>
      </PageHeader>

      <Section>
        <SectionHeader>
          <SectionIcon $color="#A855F7">
            <FaPalette />
          </SectionIcon>
          <SectionHeaderContent>
            <h2>Display</h2>
            <p>Control where and how the signature appears</p>
          </SectionHeaderContent>
        </SectionHeader>

        <SettingItem>
          <SettingInfo>
            <h3>Show signature in the password generator</h3>
            <p>Renders the colour/shape signature beneath the strength meter wherever the generator appears.</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch checked={enabled} onChange={setEnabled} />
          </SettingControl>
        </SettingItem>

        <SettingItem $index={1}>
          <SettingInfo>
            <h3>Enable melody playback</h3>
            <p>Adds a “Play melody” button (Web Audio). Off by default — nothing ever plays without a click.</p>
          </SettingInfo>
          <SettingControl>
            <ToggleSwitch checked={audio} onChange={setAudio} disabled={!enabled} />
          </SettingControl>
        </SettingItem>

        <InfoBox>
          <InfoText>
            Privacy: the signature is derived from your password in the browser and is reversible — it
            is, in effect, the password re-encoded. Treat it as sensitively as the password itself. It
            is never stored, logged, or transmitted.
          </InfoText>
        </InfoBox>
      </Section>

      <DemoSection>
        <h2>Try it</h2>
        <p>
          {enabled
            ? `Generate a password to see its signature${audio ? ' and hear its melody' : ''}.`
            : 'Signature display is off, so the demo below won’t show a signature.'}{' '}
          Toggle the settings above to watch the demo update live.
        </p>
        <PasswordGenerator />
      </DemoSection>
    </Page>
  );
};

export default SynestheticDashboard;
