"""
DNA Provider Integration Service
================================

Handles OAuth authentication and data fetching from DNA providers:
- Sequencing.com (Primary - recommended)
- 23andMe (Limited access since 2018)
- Manual file upload (23andMe, AncestryDNA, VCF formats)

Privacy Model:
- Raw DNA data is processed immediately and discarded
- Only cryptographic hashes are stored
- OAuth tokens are encrypted at rest

Author: Password Manager Team
Created: 2026-01-16
"""

import os
import csv
import io
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum

import httpx

from django.conf import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

class DNAProviderType(Enum):
    """Supported DNA data providers."""
    SEQUENCING = "sequencing"
    TWENTYTHREEME = "23andme"
    ANCESTRY = "ancestry"
    MANUAL = "manual"


# API Endpoints
SEQUENCING_BASE_URL = "https://api.sequencing.com"
TWENTYTHREEME_BASE_URL = "https://api.23andme.com"


# =============================================================================
# Abstract Base Provider
# =============================================================================

class DNAProvider(ABC):
    """
    Abstract base class for DNA data providers.
    
    All providers must implement:
    - OAuth URL generation
    - Token exchange
    - SNP data fetching
    """
    
    @abstractmethod
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate OAuth authorization URL."""
        pass
    
    @abstractmethod
    async def authenticate(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        pass
    
    @abstractmethod
    async def fetch_snp_data(self, access_token: str) -> Dict[str, str]:
        """Fetch SNP genotype data."""
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh expired access token."""
        pass
    
    def get_provider_name(self) -> str:
        """Return provider identifier."""
        return "unknown"
    
    def get_provider_display_name(self) -> str:
        """Return human-readable provider name."""
        return "Unknown Provider"


# =============================================================================
# Sequencing.com Provider (Primary)
# =============================================================================

class SequencingDNAProvider(DNAProvider):
    """
    Sequencing.com DNA API integration.
    
    Primary provider because:
    - Works with data from 23andMe, AncestryDNA, and others
    - Dedicated developer API with OAuth 2.0
    - Allows raw genetic data access with user consent
    - HIPAA compliant
    
    API Documentation: https://sequencing.com/developer-documentation
    """
    
    BASE_URL = SEQUENCING_BASE_URL
    
    def __init__(self):
        self.client_id = getattr(settings, 'SEQUENCING_CLIENT_ID', 
                                  os.environ.get('SEQUENCING_CLIENT_ID', ''))
        self.client_secret = getattr(settings, 'SEQUENCING_CLIENT_SECRET',
                                      os.environ.get('SEQUENCING_CLIENT_SECRET', ''))
    
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate Sequencing.com OAuth authorization URL.
        
        Scopes:
        - snps: Access to SNP data
        - files: Access to raw data files
        """
        if not self.client_id:
            raise ValueError("SEQUENCING_CLIENT_ID not configured")
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "snps files",
            "state": state,
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.BASE_URL}/oauth2/authorize?{query}"
    
    async def authenticate(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Returns:
            {
                "access_token": "...",
                "refresh_token": "...",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/oauth2/token",
                data={
                    "code": auth_code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Sequencing OAuth failed: {response.text}")
                raise Exception(f"OAuth failed: {response.status_code}")
            
            return response.json()
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh expired access token."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/oauth2/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                raise Exception("Token refresh failed")
            
            return response.json()
    
    async def fetch_snp_data(self, access_token: str) -> Dict[str, str]:
        """
        Fetch SNP genotype data from Sequencing.com.
        
        Returns:
            Dictionary of SNP ID -> genotype
            Example: {"rs1426654": "AG", "rs12913832": "GG"}
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # First, get available files
            files_response = await client.get(
                f"{self.BASE_URL}/v3/files",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if files_response.status_code != 200:
                logger.error(f"Failed to fetch files: {files_response.text}")
                raise Exception("Failed to fetch genetic files")
            
            files_data = files_response.json()
            
            # Find SNP/genotype file
            snp_file = None
            for f in files_data.get("files", []):
                if f.get("type") in ["snp", "genotype", "vcf"]:
                    snp_file = f
                    break
            
            if not snp_file:
                logger.warning("No SNP file found, trying direct SNP endpoint")
                return await self._fetch_direct_snps(client, access_token)
            
            # Fetch SNP data from file
            snp_response = await client.get(
                f"{self.BASE_URL}/v3/files/{snp_file['id']}/snps",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if snp_response.status_code != 200:
                raise Exception("Failed to fetch SNP data")
            
            return self._parse_snp_response(snp_response.json())
    
    async def _fetch_direct_snps(
        self, 
        client: httpx.AsyncClient, 
        access_token: str
    ) -> Dict[str, str]:
        """Fetch SNPs directly from user profile."""
        response = await client.get(
            f"{self.BASE_URL}/v3/user/snps",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            raise Exception("Failed to fetch direct SNPs")
        
        return self._parse_snp_response(response.json())
    
    def _parse_snp_response(self, data: Dict) -> Dict[str, str]:
        """
        Parse Sequencing.com SNP response to standard format.
        
        Input format varies, but typically:
        {"snps": [{"rsid": "rs123", "genotype": "AG"}, ...]}
        """
        snps = {}
        
        for snp in data.get("snps", []):
            rsid = snp.get("rsid", snp.get("id", ""))
            genotype = snp.get("genotype", snp.get("alleles", ""))
            
            if rsid.startswith("rs") and genotype:
                # Normalize genotype
                if isinstance(genotype, list):
                    genotype = "".join(genotype)
                snps[rsid] = genotype.upper()
        
        logger.info(f"Parsed {len(snps)} SNPs from Sequencing.com")
        return snps
    
    def get_provider_name(self) -> str:
        return "sequencing"
    
    def get_provider_display_name(self) -> str:
        return "Sequencing.com"


# =============================================================================
# 23andMe Provider (Limited)
# =============================================================================

class TwentyThreeMeProvider(DNAProvider):
    """
    23andMe API integration.
    
    IMPORTANT: Since 2018, 23andMe has restricted raw genotype access.
    This provider works with report-level data only unless you have
    special research partnership access.
    
    For raw genotype access, users should download their data and
    use the manual upload option instead.
    """
    
    BASE_URL = TWENTYTHREEME_BASE_URL
    
    def __init__(self):
        self.client_id = getattr(settings, 'TWENTYTHREEME_CLIENT_ID',
                                  os.environ.get('TWENTYTHREEME_CLIENT_ID', ''))
        self.client_secret = getattr(settings, 'TWENTYTHREEME_CLIENT_SECRET',
                                      os.environ.get('TWENTYTHREEME_CLIENT_SECRET', ''))
    
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate 23andMe OAuth URL."""
        if not self.client_id:
            raise ValueError("TWENTYTHREEME_CLIENT_ID not configured")
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "basic ancestry",  # Limited scope
            "state": state,
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.BASE_URL}/authorize?{query}"
    
    async def authenticate(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange code for token."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/token/",
                data={
                    "code": auth_code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"23andMe OAuth failed: {response.status_code}")
            
            return response.json()
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/token/",
                data={
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                }
            )
            
            if response.status_code != 200:
                raise Exception("Token refresh failed")
            
            return response.json()
    
    async def fetch_snp_data(self, access_token: str) -> Dict[str, str]:
        """
        Fetch genetic data from 23andMe.
        
        Note: Raw genotype access is limited. This fetches ancestry
        composition data and derives a seed from it.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Get user profile
            profile_response = await client.get(
                f"{self.BASE_URL}/3/account/",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if profile_response.status_code != 200:
                raise Exception("Failed to fetch 23andMe profile")
            
            profile = profile_response.json()
            profile_id = profile.get("profiles", [{}])[0].get("id")
            
            if not profile_id:
                raise Exception("No 23andMe profile found")
            
            # Fetch ancestry composition (available to all)
            ancestry_response = await client.get(
                f"{self.BASE_URL}/3/profile/{profile_id}/ancestry/",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if ancestry_response.status_code != 200:
                raise Exception("Failed to fetch ancestry data")
            
            # Convert ancestry to pseudo-SNP format
            return self._ancestry_to_snps(ancestry_response.json())
    
    def _ancestry_to_snps(self, ancestry_data: Dict) -> Dict[str, str]:
        """
        Convert ancestry composition to pseudo-SNP format.
        
        This is a workaround for limited API access. The ancestry
        composition is hashed to create consistent seed data.
        """
        snps = {}
        
        # Create deterministic entries from ancestry data
        composition = ancestry_data.get("composition", ancestry_data)
        
        for i, (region, percentage) in enumerate(composition.items()):
            # Create pseudo-SNP from ancestry data
            pseudo_rsid = f"rs23andme_{i:05d}"
            # Encode percentage as genotype-like value
            encoded = self._encode_percentage(percentage)
            snps[pseudo_rsid] = encoded
        
        logger.info(f"Created {len(snps)} pseudo-SNPs from 23andMe ancestry")
        return snps
    
    def _encode_percentage(self, percentage: float) -> str:
        """Encode a percentage as a pseudo-genotype."""
        # Map percentage to allele codes
        if percentage >= 50:
            return "AA"
        elif percentage >= 25:
            return "AG"
        elif percentage >= 10:
            return "GG"
        elif percentage >= 1:
            return "GT"
        else:
            return "TT"
    
    def get_provider_name(self) -> str:
        return "23andme"
    
    def get_provider_display_name(self) -> str:
        return "23andMe"


# =============================================================================
# Manual File Upload Provider
# =============================================================================

class ManualUploadProvider(DNAProvider):
    """
    Handles manual DNA file uploads.
    
    Supports:
    - 23andMe raw data (.txt)
    - AncestryDNA raw data (.csv)
    - VCF format (.vcf)
    
    This is the most comprehensive option as it works with
    actual raw genotype data.
    """
    
    SUPPORTED_FORMATS = {
        "23andme": {
            "extensions": [".txt"],
            "parser": "_parse_23andme",
            "description": "23andMe Raw Data",
        },
        "ancestry": {
            "extensions": [".csv"],
            "parser": "_parse_ancestry",
            "description": "AncestryDNA Raw Data",
        },
        "vcf": {
            "extensions": [".vcf", ".vcf.gz"],
            "parser": "_parse_vcf",
            "description": "VCF (Variant Call Format)",
        },
    }
    
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Not applicable for manual upload."""
        raise NotImplementedError("Manual upload does not use OAuth")
    
    async def authenticate(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        """Not applicable for manual upload."""
        raise NotImplementedError("Manual upload does not use OAuth")
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Not applicable for manual upload."""
        raise NotImplementedError("Manual upload does not use OAuth")
    
    async def fetch_snp_data(self, access_token: str) -> Dict[str, str]:
        """Not applicable for manual upload."""
        raise NotImplementedError("Use parse_uploaded_file instead")
    
    def detect_format(self, filename: str, content_preview: str = None) -> str:
        """
        Detect file format from filename or content.
        
        Returns format key or raises ValueError if unsupported.
        """
        filename_lower = filename.lower()
        
        # Check by extension
        for format_key, config in self.SUPPORTED_FORMATS.items():
            for ext in config["extensions"]:
                if filename_lower.endswith(ext):
                    return format_key
        
        # Try to detect by content
        if content_preview:
            if "rsid\tchromosome\tposition\tgenotype" in content_preview.lower():
                return "23andme"
            elif "rsid,chromosome,position" in content_preview.lower():
                return "ancestry"
            elif content_preview.startswith("##fileformat=VCF"):
                return "vcf"
        
        raise ValueError(f"Unsupported file format: {filename}")
    
    def parse_uploaded_file(
        self, 
        file_content: bytes, 
        filename: str
    ) -> Tuple[Dict[str, str], str]:
        """
        Parse uploaded DNA file to SNP dictionary.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            
        Returns:
            Tuple of (snp_dict, detected_format)
        """
        # Decode content
        try:
            content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            content = file_content.decode('latin-1')
        
        # Detect format
        format_key = self.detect_format(filename, content[:1000])
        
        # Parse based on format
        parser_name = self.SUPPORTED_FORMATS[format_key]["parser"]
        parser = getattr(self, parser_name)
        snps = parser(content)
        
        logger.info(f"Parsed {len(snps)} SNPs from {format_key} file")
        return snps, format_key
    
    def _parse_23andme(self, content: str) -> Dict[str, str]:
        """
        Parse 23andMe raw data format.
        
        Format:
        # rsid	chromosome	position	genotype
        rs548049170	1	69869	TT
        rs13328684	1	74792	--
        rs9283150	1	565508	AG
        """
        snps = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) >= 4:
                rsid = parts[0]
                genotype = parts[3]
                
                # Only include valid SNPs
                if rsid.startswith('rs') and genotype not in ['--', 'II', 'DD', 'DI', 'ID']:
                    # Normalize genotype
                    genotype = genotype.upper()
                    if len(genotype) == 2:
                        genotype = "".join(sorted(genotype))
                    snps[rsid] = genotype
        
        return snps
    
    def _parse_ancestry(self, content: str) -> Dict[str, str]:
        """
        Parse AncestryDNA raw data format.
        
        Format (CSV):
        rsid,chromosome,position,allele1,allele2
        rs3094315,1,752566,G,G
        """
        snps = {}
        
        # Handle potential BOM and different line endings
        content = content.lstrip('\ufeff')
        
        reader = csv.DictReader(io.StringIO(content))
        
        for row in reader:
            rsid = row.get('rsid', row.get('RSID', ''))
            allele1 = row.get('allele1', row.get('Allele1', ''))
            allele2 = row.get('allele2', row.get('Allele2', ''))
            
            if rsid.startswith('rs') and allele1 and allele2:
                # Skip invalid genotypes
                if allele1 in ['0', '-'] or allele2 in ['0', '-']:
                    continue
                
                genotype = (allele1 + allele2).upper()
                genotype = "".join(sorted(genotype))
                snps[rsid] = genotype
        
        return snps
    
    def _parse_vcf(self, content: str) -> Dict[str, str]:
        """
        Parse VCF (Variant Call Format) file.
        
        Format:
        ##fileformat=VCFv4.2
        #CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	SAMPLE
        1	752566	rs3094315	G	A	.	PASS	.	GT	0/1
        """
        snps = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip headers
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) >= 10:
                chrom = parts[0]
                pos = parts[1]
                rsid = parts[2]
                ref = parts[3]
                alt = parts[4]
                sample_data = parts[9]
                
                # Only process rs-numbered variants
                if not rsid.startswith('rs'):
                    continue
                
                # Parse genotype from sample column
                genotype_field = sample_data.split(':')[0]
                
                # Build allele list
                alleles = [ref] + alt.split(',')
                
                # Convert genotype notation (0/1, 1|0, etc.) to actual alleles
                try:
                    gt = genotype_field.replace('/', '').replace('|', '')
                    genotype = ""
                    for idx in gt:
                        if idx.isdigit():
                            allele_idx = int(idx)
                            if allele_idx < len(alleles):
                                genotype += alleles[allele_idx]
                    
                    if len(genotype) == 2:
                        genotype = "".join(sorted(genotype.upper()))
                        snps[rsid] = genotype
                except (ValueError, IndexError):
                    continue
        
        return snps
    
    def get_provider_name(self) -> str:
        return "manual"
    
    def get_provider_display_name(self) -> str:
        return "Manual Upload"


# =============================================================================
# Provider Factory
# =============================================================================

def get_dna_provider(provider_type: str) -> DNAProvider:
    """
    Factory function to get the appropriate DNA provider.
    
    Args:
        provider_type: One of 'sequencing', '23andme', 'ancestry', 'manual'
        
    Returns:
        DNAProvider instance
    """
    providers = {
        "sequencing": SequencingDNAProvider,
        "23andme": TwentyThreeMeProvider,
        "ancestry": ManualUploadProvider,  # Ancestry uses manual upload
        "manual": ManualUploadProvider,
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_type}")
    
    return provider_class()


def get_supported_providers() -> Dict[str, Dict[str, Any]]:
    """
    Get information about supported DNA providers.
    
    Returns:
        Dictionary with provider info for UI display
    """
    return {
        "sequencing": {
            "name": "Sequencing.com",
            "description": "Universal DNA API - works with 23andMe, AncestryDNA, and more",
            "icon": "🧬",
            "color": "#10B981",
            "oauth_supported": True,
            "recommended": True,
        },
        "23andme": {
            "name": "23andMe",
            "description": "Direct 23andMe connection (limited to ancestry data)",
            "icon": "🔬",
            "color": "#8B5CF6",
            "oauth_supported": True,
            "recommended": False,
            "note": "For full SNP access, download your raw data and use manual upload",
        },
        "manual": {
            "name": "Manual Upload",
            "description": "Upload raw DNA data file (23andMe, AncestryDNA, VCF)",
            "icon": "📁",
            "color": "#6B7280",
            "oauth_supported": False,
            "supported_formats": [".txt", ".csv", ".vcf"],
        },
    }
