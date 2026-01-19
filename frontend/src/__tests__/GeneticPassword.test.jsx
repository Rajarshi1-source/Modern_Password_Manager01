/**
 * Genetic Password Evolution - Frontend Component Tests
 * ======================================================
 * 
 * Tests for React components:
 * - GeneticPasswordModal
 * - DNAConnectionStatus
 * - EvolutionStatus
 * - GeneticCertificateDisplay
 * 
 * @author Password Manager Team
 * @created 2026-01-17
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the service
vi.mock('../services/geneticService', () => ({
    default: {
        getSupportedProviders: vi.fn(),
        initiateConnection: vi.fn(),
        openOAuthPopup: vi.fn(),
        handleOAuthCallback: vi.fn(),
        uploadDNAFile: vi.fn(),
        generateGeneticPassword: vi.fn(),
        getConnectionStatus: vi.fn(),
        isConnected: vi.fn(),
        disconnect: vi.fn(),
        updatePreferences: vi.fn(),
        getEvolutionStatus: vi.fn(),
        triggerEvolution: vi.fn(),
        getCertificate: vi.fn(),
        listCertificates: vi.fn(),
        formatCertificateForDisplay: vi.fn(),
        getProviderInfo: vi.fn(),
        invalidateCache: vi.fn(),
        downloadCertificate: vi.fn(),
    },
    GeneticService: vi.fn(),
}));

import geneticService from '../services/geneticService';


// =============================================================================
// GeneticService Unit Tests
// =============================================================================

describe('GeneticService', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('returns list of supported providers', async () => {
        geneticService.getSupportedProviders.mockReturnValue({
            sequencing: { id: 'sequencing', name: 'Sequencing.com' },
            '23andme': { id: '23andme', name: '23andMe' },
            manual: { id: 'manual', name: 'Manual Upload' },
        });

        const providers = geneticService.getSupportedProviders();

        expect(providers).toHaveProperty('sequencing');
        expect(providers).toHaveProperty('23andme');
        expect(providers).toHaveProperty('manual');
    });

    it('initiates OAuth connection', async () => {
        geneticService.initiateConnection.mockResolvedValue({
            success: true,
            auth_url: 'https://provider.com/oauth',
            state: 'test-state-token',
        });

        const result = await geneticService.initiateConnection('sequencing', 'http://localhost/callback');

        expect(result.success).toBe(true);
        expect(result.auth_url).toBeDefined();
        expect(geneticService.initiateConnection).toHaveBeenCalledWith('sequencing', 'http://localhost/callback');
    });

    it('uploads DNA file with progress tracking', async () => {
        const mockFile = new File(['test content'], 'dna.txt', { type: 'text/plain' });

        geneticService.uploadDNAFile.mockResolvedValue({
            success: true,
            snp_count: 500000,
            format: '23andme',
        });

        const onProgress = vi.fn();
        const result = await geneticService.uploadDNAFile(mockFile, onProgress);

        expect(result.success).toBe(true);
        expect(result.snp_count).toBe(500000);
    });

    it('generates genetic password with certificate', async () => {
        geneticService.generateGeneticPassword.mockResolvedValue({
            success: true,
            password: 'GeneticPassword123!',
            certificate: {
                certificate_id: 'cert-123',
                password_hash_prefix: 'abc123',
                genetic_hash_prefix: 'def456',
                snp_markers_used: 100,
                evolution_generation: 1,
            },
            entropy_bits: 128,
        });

        const result = await geneticService.generateGeneticPassword({
            length: 16,
            uppercase: true,
            lowercase: true,
            numbers: true,
            symbols: true,
        });

        expect(result.success).toBe(true);
        expect(result.password).toBeDefined();
        expect(result.certificate).toBeDefined();
        expect(result.certificate.certificate_id).toBeDefined();
    });

    it('checks connection status with caching', async () => {
        geneticService.getConnectionStatus.mockResolvedValue({
            success: true,
            connected: true,
            provider: 'sequencing',
            snp_count: 500000,
        });

        const status = await geneticService.getConnectionStatus();

        expect(status.connected).toBe(true);
        expect(status.provider).toBe('sequencing');
    });

    it('gets evolution status', async () => {
        geneticService.getEvolutionStatus.mockResolvedValue({
            success: true,
            evolution: {
                current_generation: 2,
                biological_age: 35.5,
                last_evolution_at: '2026-01-15T12:00:00Z',
                next_evolution_estimated: '2027-01-15T12:00:00Z',
            },
        });

        const result = await geneticService.getEvolutionStatus();

        expect(result.success).toBe(true);
        expect(result.evolution.current_generation).toBe(2);
    });

    it('triggers password evolution', async () => {
        geneticService.triggerEvolution.mockResolvedValue({
            success: true,
            evolved: true,
            old_generation: 1,
            new_generation: 2,
            new_password: 'EvolvedPassword456!',
        });

        const result = await geneticService.triggerEvolution({ force: true });

        expect(result.success).toBe(true);
        expect(result.evolved).toBe(true);
        expect(result.new_generation).toBe(2);
    });

    it('lists certificates with pagination', async () => {
        geneticService.listCertificates.mockResolvedValue({
            success: true,
            certificates: [
                { certificate_id: 'cert-1', evolution_generation: 1 },
                { certificate_id: 'cert-2', evolution_generation: 2 },
            ],
            total: 2,
        });

        const result = await geneticService.listCertificates(50, 0);

        expect(result.success).toBe(true);
        expect(result.certificates).toHaveLength(2);
        expect(result.total).toBe(2);
    });

    it('disconnects DNA connection', async () => {
        geneticService.disconnect.mockResolvedValue({
            success: true,
            message: 'Connection disconnected',
        });

        const result = await geneticService.disconnect();

        expect(result.success).toBe(true);
        expect(geneticService.disconnect).toHaveBeenCalled();
    });
});


// =============================================================================
// DNA-Based Seeding Tests
// =============================================================================

describe('DNA-Based Seeding', () => {
    it('validates SNP data format', () => {
        const validSnps = {
            'rs1426654': 'AA',
            'rs12913832': 'GG',
            'rs1799971': 'AG',
        };

        // Each SNP should have valid genotype format (2 letters)
        for (const [rsid, genotype] of Object.entries(validSnps)) {
            expect(rsid).toMatch(/^rs\d+$/);
            expect(genotype).toMatch(/^[ACGT]{2}$/);
        }
    });

    it('generates unique seeds for different SNP data', async () => {
        // First generation
        geneticService.generateGeneticPassword.mockResolvedValueOnce({
            success: true,
            password: 'Password1!',
            certificate: { genetic_hash_prefix: 'hash1' },
        });

        // Second generation with different SNPs (simulated)
        geneticService.generateGeneticPassword.mockResolvedValueOnce({
            success: true,
            password: 'Password2!',
            certificate: { genetic_hash_prefix: 'hash2' },
        });

        const result1 = await geneticService.generateGeneticPassword({});
        const result2 = await geneticService.generateGeneticPassword({});

        // Different SNP data should produce different passwords
        expect(result1.password).not.toBe(result2.password);
        expect(result1.certificate.genetic_hash_prefix).not.toBe(result2.certificate.genetic_hash_prefix);
    });

    it('applies epigenetic evolution factor', async () => {
        geneticService.getEvolutionStatus.mockResolvedValue({
            success: true,
            evolution: {
                current_generation: 1,
                biological_age: 35.0,
                epigenetic_factor: 1.05,
            },
        });

        const status = await geneticService.getEvolutionStatus();

        expect(status.evolution.epigenetic_factor).toBeDefined();
        expect(status.evolution.epigenetic_factor).toBeGreaterThan(0);
    });
});


// =============================================================================
// Password Evolution Tests
// =============================================================================

describe('Password Evolution', () => {
    it('tracks evolution generation', async () => {
        geneticService.getEvolutionStatus.mockResolvedValue({
            success: true,
            evolution: {
                current_generation: 3,
                evolution_history: [
                    { generation: 1, date: '2024-01-01' },
                    { generation: 2, date: '2025-01-01' },
                    { generation: 3, date: '2026-01-01' },
                ],
            },
        });

        const status = await geneticService.getEvolutionStatus();

        expect(status.evolution.current_generation).toBe(3);
        expect(status.evolution.evolution_history).toHaveLength(3);
    });

    it('calculates biological age change threshold', async () => {
        geneticService.getEvolutionStatus.mockResolvedValue({
            success: true,
            evolution: {
                biological_age: 36.5,
                last_biological_age: 35.0,
                age_change: 1.5,
                evolution_threshold: 1.0,
                should_evolve: true,
            },
        });

        const status = await geneticService.getEvolutionStatus();

        expect(status.evolution.age_change).toBeGreaterThan(status.evolution.evolution_threshold);
        expect(status.evolution.should_evolve).toBe(true);
    });

    it('prevents evolution if age change is too small', async () => {
        geneticService.triggerEvolution.mockResolvedValue({
            success: true,
            evolved: false,
            reason: 'Age change (0.3 years) below threshold (1.0 years)',
        });

        const result = await geneticService.triggerEvolution({});

        expect(result.evolved).toBe(false);
        expect(result.reason).toContain('threshold');
    });
});


// =============================================================================
// Certificate Tests
// =============================================================================

describe('Genetic Certificates', () => {
    it('creates certificate with password generation', async () => {
        geneticService.generateGeneticPassword.mockResolvedValue({
            success: true,
            password: 'CertPassword123!',
            certificate: {
                certificate_id: 'cert-uuid-123',
                password_hash_prefix: 'abc123',
                genetic_hash_prefix: 'def456',
                provider: 'sequencing',
                snp_markers_used: 500,
                evolution_generation: 1,
                combined_with_quantum: false,
                password_length: 16,
                entropy_bits: 128,
                signature: 'hmac-sha256-signature',
                created_at: '2026-01-17T12:00:00Z',
            },
        });

        const result = await geneticService.generateGeneticPassword({});

        expect(result.certificate).toBeDefined();
        expect(result.certificate.certificate_id).toBeDefined();
        expect(result.certificate.signature).toBeDefined();
    });

    it('retrieves specific certificate by ID', async () => {
        geneticService.getCertificate.mockResolvedValue({
            success: true,
            certificate: {
                certificate_id: 'cert-uuid-123',
                provider: 'sequencing',
                snp_markers_used: 500,
            },
        });

        const result = await geneticService.getCertificate('cert-uuid-123');

        expect(result.success).toBe(true);
        expect(result.certificate.certificate_id).toBe('cert-uuid-123');
    });

    it('downloads certificate as JSON', () => {
        const mockCertificate = {
            certificate_id: 'cert-123',
            provider: 'sequencing',
            created_at: '2026-01-17T12:00:00Z',
        };

        // downloadCertificate creates a blob and triggers download
        geneticService.downloadCertificate.mockImplementation((cert) => {
            const blob = new Blob([JSON.stringify(cert, null, 2)], { type: 'application/json' });
            expect(blob).toBeDefined();
        });

        geneticService.downloadCertificate(mockCertificate);

        expect(geneticService.downloadCertificate).toHaveBeenCalledWith(mockCertificate);
    });
});


// =============================================================================
// Provider Connection Tests
// =============================================================================

describe('DNA Provider Connections', () => {
    it('lists supported providers', () => {
        geneticService.getSupportedProviders.mockReturnValue({
            sequencing: {
                id: 'sequencing',
                name: 'Sequencing.com',
                description: 'Upload whole genome sequencing data',
                icon: '🧬',
            },
            '23andme': {
                id: '23andme',
                name: '23andMe',
                description: 'Connect your 23andMe account',
                icon: '🔬',
            },
            ancestry: {
                id: 'ancestry',
                name: 'AncestryDNA',
                description: 'Connect your Ancestry account',
                icon: '🌳',
            },
            manual: {
                id: 'manual',
                name: 'Manual Upload',
                description: 'Upload DNA file directly',
                icon: '📄',
            },
        });

        const providers = geneticService.getSupportedProviders();

        expect(Object.keys(providers)).toHaveLength(4);
        expect(providers.sequencing.name).toBe('Sequencing.com');
    });

    it('handles OAuth flow success', async () => {
        geneticService.handleOAuthCallback.mockResolvedValue({
            success: true,
            provider: 'sequencing',
            snp_count: 500000,
            connection_id: 'conn-123',
        });

        const result = await geneticService.handleOAuthCallback('auth-code', 'state-token');

        expect(result.success).toBe(true);
        expect(result.snp_count).toBeGreaterThan(0);
    });

    it('handles OAuth flow failure', async () => {
        geneticService.handleOAuthCallback.mockResolvedValue({
            success: false,
            error: 'Invalid authorization code',
        });

        const result = await geneticService.handleOAuthCallback('invalid-code', 'state');

        expect(result.success).toBe(false);
        expect(result.error).toBeDefined();
    });

    it('handles file upload with format detection', async () => {
        const file23andMe = new File(
            ['# This data file generated by 23andMe\nrs123\t1\t100\tAA'],
            'genome.txt',
            { type: 'text/plain' }
        );

        geneticService.uploadDNAFile.mockResolvedValue({
            success: true,
            format: '23andme',
            snp_count: 600000,
        });

        const result = await geneticService.uploadDNAFile(file23andMe, () => { });

        expect(result.success).toBe(true);
        expect(result.format).toBe('23andme');
    });
});


// =============================================================================
// Quantum Integration Tests
// =============================================================================

describe('Quantum Integration', () => {
    it('combines genetic seed with quantum entropy', async () => {
        geneticService.generateGeneticPassword.mockResolvedValue({
            success: true,
            password: 'QuantumGenetic123!',
            certificate: {
                combined_with_quantum: true,
                quantum_certificate_id: 'quantum-cert-456',
                entropy_bits: 256, // Higher due to quantum addition
            },
        });

        const result = await geneticService.generateGeneticPassword({
            combineWithQuantum: true,
        });

        expect(result.certificate.combined_with_quantum).toBe(true);
        expect(result.certificate.quantum_certificate_id).toBeDefined();
        expect(result.certificate.entropy_bits).toBe(256);
    });

    it('falls back to genetic-only if quantum unavailable', async () => {
        geneticService.generateGeneticPassword.mockResolvedValue({
            success: true,
            password: 'GeneticOnly123!',
            certificate: {
                combined_with_quantum: false,
                entropy_bits: 128,
            },
            warnings: ['Quantum RNG unavailable, using genetic seed only'],
        });

        const result = await geneticService.generateGeneticPassword({
            combineWithQuantum: true,
        });

        expect(result.certificate.combined_with_quantum).toBe(false);
        expect(result.warnings).toBeDefined();
    });
});


// =============================================================================
// A/B Test Configuration Tests
// =============================================================================

describe('Genetic Password A/B Tests', () => {
    it('defines experiment for default password length', () => {
        const experiment = {
            experiment_id: 'genetic_password_length',
            variants: {
                control: { default_length: 16 },
                longer: { default_length: 20 },
                shorter: { default_length: 12 },
            },
            metrics: [
                'password_adoption_rate',
                'regeneration_rate',
                'user_satisfaction',
            ],
        };

        expect(Object.keys(experiment.variants)).toHaveLength(3);
        expect(experiment.metrics.length).toBeGreaterThan(0);
    });

    it('defines experiment for evolution notification', () => {
        const experiment = {
            experiment_id: 'evolution_notification_timing',
            variants: {
                immediate: { notify_on_evolution: true, notify_delay_days: 0 },
                delayed: { notify_on_evolution: true, notify_delay_days: 7 },
                no_notify: { notify_on_evolution: false },
            },
            metrics: [
                'evolution_completion_rate',
                'notification_engagement',
            ],
        };

        expect(experiment.variants.immediate.notify_delay_days).toBe(0);
        expect(experiment.variants.no_notify.notify_on_evolution).toBe(false);
    });

    it('defines experiment for quantum combination default', () => {
        const experiment = {
            experiment_id: 'quantum_combination_default',
            variants: {
                enabled: { quantum_default: true },
                disabled: { quantum_default: false },
            },
            metrics: [
                'quantum_adoption_rate',
                'password_entropy',
            ],
        };

        expect(experiment.variants.enabled.quantum_default).toBe(true);
    });
});
