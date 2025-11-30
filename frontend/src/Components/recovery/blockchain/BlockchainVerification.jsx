/**
 * Blockchain Verification Component
 * 
 * Displays blockchain verification status for behavioral commitments.
 * Shows Merkle proof, transaction details, and links to Arbiscan explorer.
 * 
 * Phase 2B.1: Blockchain Anchoring
 */

import React, { useState, useEffect } from 'react';
import { Box, Typography, Card, CardContent, CircularProgress, Alert, Button, Chip, Link } from '@mui/material';
import { CheckCircle, Pending, Error as ErrorIcon, OpenInNew } from '@mui/icons-material';
import axios from 'axios';
import arbitrumService from '../../../services/blockchain/arbitrumService';

const BlockchainVerification = ({ commitmentId, showDetails = true }) => {
  const [verificationData, setVerificationData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [verifyingOnChain, setVerifyingOnChain] = useState(false);

  useEffect(() => {
    if (commitmentId) {
      fetchVerificationData();
    }
  }, [commitmentId]);

  const fetchVerificationData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.get(
        `/api/blockchain/verify-commitment/${commitmentId}/`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }
      );

      setVerificationData(response.data);
    } catch (err) {
      console.error('Error fetching verification data:', err);
      setError(err.response?.data?.error || 'Failed to fetch verification data');
    } finally {
      setLoading(false);
    }
  };

  const verifyOnChain = async () => {
    try {
      setVerifyingOnChain(true);

      // Call API with on-chain verification enabled
      const response = await axios.get(
        `/api/blockchain/verify-commitment/${commitmentId}/?verify_onchain=true`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }
      );

      setVerificationData(response.data);
    } catch (err) {
      console.error('On-chain verification failed:', err);
      setError('On-chain verification failed. Please try again.');
    } finally {
      setVerifyingOnChain(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" p={3}>
        <CircularProgress size={24} />
        <Typography variant="body2" ml={2}>
          Verifying blockchain anchor...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!verificationData) {
    return null;
  }

  // Handle different statuses
  if (verificationData.status === 'pending') {
    return (
      <Card sx={{ mt: 2, borderLeft: 4, borderColor: 'warning.main' }}>
        <CardContent>
          <Box display="flex" alignItems="center" mb={1}>
            <Pending color="warning" sx={{ mr: 1 }} />
            <Typography variant="h6">Pending Blockchain Anchoring</Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Your commitment is queued for blockchain anchoring. This typically happens within 24 hours.
          </Typography>
          <Typography variant="caption" display="block" mt={1}>
            Queued since: {new Date(verificationData.pending_since).toLocaleString()}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (verificationData.status === 'not_anchored') {
    return (
      <Card sx={{ mt: 2, borderLeft: 4, borderColor: 'grey.500' }}>
        <CardContent>
          <Typography variant="body2" color="text.secondary">
            This commitment has not been anchored to the blockchain yet.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  // Main verification display
  const { verified, verified_onchain, blockchain_anchor, arbiscan_url } = verificationData;

  return (
    <Card sx={{ mt: 2, borderLeft: 4, borderColor: verified ? 'success.main' : 'error.main' }}>
      <CardContent>
        {/* Verification Status Header */}
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Box display="flex" alignItems="center">
            {verified ? (
              <CheckCircle color="success" sx={{ mr: 1 }} />
            ) : (
              <ErrorIcon color="error" sx={{ mr: 1 }} />
            )}
            <Typography variant="h6">
              {verified ? 'Verified on Blockchain' : 'Verification Failed'}
            </Typography>
          </Box>
          
          <Chip 
            label={blockchain_anchor.network === 'testnet' ? 'Testnet' : 'Mainnet'}
            size="small"
            color={blockchain_anchor.network === 'testnet' ? 'warning' : 'success'}
          />
        </Box>

        {/* Verification Details */}
        {showDetails && (
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Your behavioral commitment has been anchored to the Arbitrum blockchain with cryptographic proof of existence.
            </Typography>

            <Box mt={2} sx={{ bgcolor: 'grey.50', p: 2, borderRadius: 1 }}>
              <Typography variant="caption" display="block" fontWeight="bold" mb={1}>
                Blockchain Details
              </Typography>
              
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Network:</Typography>
                <Typography variant="caption">Arbitrum {blockchain_anchor.network === 'testnet' ? 'Sepolia' : 'One'}</Typography>
              </Box>
              
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Block:</Typography>
                <Typography variant="caption">{blockchain_anchor.block_number.toLocaleString()}</Typography>
              </Box>
              
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Timestamp:</Typography>
                <Typography variant="caption">
                  {new Date(blockchain_anchor.timestamp).toLocaleString()}
                </Typography>
              </Box>
              
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Batch Size:</Typography>
                <Typography variant="caption">{blockchain_anchor.batch_size} commitments</Typography>
              </Box>
              
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Merkle Root:</Typography>
                <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.65rem' }}>
                  {verificationData.merkle_root.substring(0, 10)}...{verificationData.merkle_root.substring(58)}
                </Typography>
              </Box>
            </Box>

            {/* On-Chain Verification */}
            <Box mt={2}>
              {verified_onchain === null ? (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={verifyOnChain}
                  disabled={verifyingOnChain}
                  startIcon={verifyingOnChain ? <CircularProgress size={16} /> : null}
                >
                  {verifyingOnChain ? 'Verifying on-chain...' : 'Verify on Arbitrum'}
                </Button>
              ) : (
                <Alert 
                  severity={verified_onchain ? 'success' : 'error'} 
                  variant="outlined"
                  sx={{ py: 0.5 }}
                >
                  <Typography variant="caption">
                    {verified_onchain 
                      ? '✅ Verified on-chain via smart contract' 
                      : '❌ On-chain verification failed'}
                  </Typography>
                </Alert>
              )}
            </Box>

            {/* Arbiscan Link */}
            <Box mt={2}>
              <Link 
                href={arbiscan_url} 
                target="_blank" 
                rel="noopener noreferrer"
                sx={{ display: 'flex', alignItems: 'center', fontSize: '0.875rem' }}
              >
                View on Arbiscan <OpenInNew fontSize="small" sx={{ ml: 0.5 }} />
              </Link>
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default BlockchainVerification;

