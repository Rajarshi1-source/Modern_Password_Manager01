"""
Epigenetic Service
==================

Handles epigenetic marker fetching and biological age calculations
for the Premium password evolution feature.

Providers:
- Humanity.health API (primary)
- Manual biological age input (fallback)

Premium Feature: Requires active subscription for automatic evolution.

Author: Password Manager Team
Created: 2026-01-16
"""

import os
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple

import httpx

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class EpigeneticData:
    """Container for epigenetic measurement data."""
    
    def __init__(
        self,
        biological_age: float,
        chronological_age: int,
        measurement_date: datetime,
        provider: str,
        aging_rate: float = 1.0,
        methylation_score: float = None,
        confidence: float = 0.95,
    ):
        self.biological_age = biological_age
        self.chronological_age = chronological_age
        self.measurement_date = measurement_date
        self.provider = provider
        self.aging_rate = aging_rate
        self.methylation_score = methylation_score
        self.confidence = confidence
    
    @property
    def evolution_factor(self) -> float:
        """
        Calculate evolution factor from biological vs chronological age.
        
        Returns:
            Factor typically between 0.8 and 1.2
            > 1.0: aging faster
            < 1.0: aging slower
        """
        if self.chronological_age <= 0:
            return 1.0
        return self.biological_age / self.chronological_age
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'biological_age': self.biological_age,
            'chronological_age': self.chronological_age,
            'measurement_date': self.measurement_date.isoformat(),
            'provider': self.provider,
            'aging_rate': self.aging_rate,
            'evolution_factor': self.evolution_factor,
            'methylation_score': self.methylation_score,
            'confidence': self.confidence,
        }


# =============================================================================
# Abstract Base Provider
# =============================================================================

class EpigeneticProvider(ABC):
    """Abstract base class for epigenetic data providers."""
    
    @abstractmethod
    async def fetch_biological_age(self, access_token: str) -> EpigeneticData:
        """Fetch biological age data."""
        pass
    
    @abstractmethod
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Get OAuth authorization URL."""
        pass
    
    @abstractmethod
    async def authenticate(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        pass
    
    def get_provider_name(self) -> str:
        return "unknown"


# =============================================================================
# Humanity.health API Provider
# =============================================================================

class HumanityHealthProvider(EpigeneticProvider):
    """
    Humanity.health API integration.
    
    Provides:
    - Biological age measurements
    - Aging rate calculations
    - DNA methylation scores
    
    API: https://humanity.health/developer
    """
    
    BASE_URL = "https://api.humanity.health/v1"
    
    def __init__(self):
        self.api_key = getattr(settings, 'HUMANITY_HEALTH_API_KEY',
                                os.environ.get('HUMANITY_HEALTH_API_KEY', ''))
        self.client_id = getattr(settings, 'HUMANITY_HEALTH_CLIENT_ID',
                                  os.environ.get('HUMANITY_HEALTH_CLIENT_ID', ''))
        self.client_secret = getattr(settings, 'HUMANITY_HEALTH_CLIENT_SECRET',
                                      os.environ.get('HUMANITY_HEALTH_CLIENT_SECRET', ''))
    
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        """Generate Humanity.health OAuth URL."""
        if not self.client_id:
            raise ValueError("HUMANITY_HEALTH_CLIENT_ID not configured")
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "biological_age wearables",
            "state": state,
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.BASE_URL}/oauth/authorize?{query}"
    
    async def authenticate(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/oauth/token",
                data={
                    "code": auth_code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Humanity OAuth failed: {response.text}")
                raise Exception(f"OAuth failed: {response.status_code}")
            
            return response.json()
    
    async def fetch_biological_age(self, access_token: str) -> EpigeneticData:
        """
        Fetch biological age from Humanity.health.
        
        Returns comprehensive epigenetic data including:
        - Biological age
        - Aging rate
        - DNA methylation score
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch biological age
            age_response = await client.get(
                f"{self.BASE_URL}/age/biological",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if age_response.status_code != 200:
                raise Exception("Failed to fetch biological age")
            
            age_data = age_response.json()
            
            # Fetch additional metrics if available
            try:
                metrics_response = await client.get(
                    f"{self.BASE_URL}/metrics/epigenetic",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                metrics_data = metrics_response.json() if metrics_response.status_code == 200 else {}
            except Exception:
                metrics_data = {}
            
            return EpigeneticData(
                biological_age=float(age_data.get("biological_age", 0)),
                chronological_age=int(age_data.get("chronological_age", 0)),
                measurement_date=datetime.fromisoformat(
                    age_data.get("measurement_date", datetime.now().isoformat())
                ),
                provider="humanity_health",
                aging_rate=float(age_data.get("aging_rate", 1.0)),
                methylation_score=float(metrics_data.get("methylation_score")) if metrics_data.get("methylation_score") else None,
                confidence=float(age_data.get("confidence", 0.95)),
            )
    
    def get_provider_name(self) -> str:
        return "humanity_health"


# =============================================================================
# Manual Input Provider
# =============================================================================

class ManualEpigeneticProvider(EpigeneticProvider):
    """
    Manual biological age input for users without API access.
    
    Allows users to manually enter their biological age from:
    - At-home epigenetic tests (TruAge, myDNAge, etc.)
    - Clinical methylation tests
    - Estimated values
    """
    
    def get_oauth_url(self, redirect_uri: str, state: str) -> str:
        raise NotImplementedError("Manual provider does not use OAuth")
    
    async def authenticate(self, auth_code: str, redirect_uri: str) -> Dict[str, Any]:
        raise NotImplementedError("Manual provider does not use OAuth")
    
    async def fetch_biological_age(self, access_token: str) -> EpigeneticData:
        raise NotImplementedError("Use create_from_manual_input instead")
    
    def create_from_manual_input(
        self,
        biological_age: float,
        chronological_age: int,
        test_provider: str = "self_reported",
    ) -> EpigeneticData:
        """
        Create EpigeneticData from manual user input.
        
        Args:
            biological_age: User-reported biological age
            chronological_age: User's actual age
            test_provider: Name of test used (e.g., "TruAge", "myDNAge")
        """
        return EpigeneticData(
            biological_age=biological_age,
            chronological_age=chronological_age,
            measurement_date=datetime.now(),
            provider=f"manual_{test_provider}",
            aging_rate=biological_age / chronological_age if chronological_age > 0 else 1.0,
            confidence=0.7,  # Lower confidence for manual input
        )
    
    def get_provider_name(self) -> str:
        return "manual"


# =============================================================================
# Epigenetic Evolution Manager
# =============================================================================

class EpigeneticEvolutionManager:
    """
    Manages the password evolution process based on epigenetic changes.
    
    Premium Feature: Automatic evolution requires active subscription.
    
    Evolution Process:
    1. Periodically check biological age (weekly/monthly)
    2. Compare to last recorded biological age
    3. If change >= threshold, trigger password evolution
    4. Update evolution generation and log the event
    """
    
    # Evolution configuration
    EVOLUTION_THRESHOLD = 0.5  # Years of biological age change
    CHECK_INTERVAL_DAYS = 30   # How often to check for evolution
    MAX_EVOLUTIONS_PER_YEAR = 12
    
    def __init__(self, epigenetic_provider: EpigeneticProvider = None):
        self.provider = epigenetic_provider or HumanityHealthProvider()
    
    async def check_and_evolve(
        self,
        user,
        dna_connection,
        force: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if evolution is needed and trigger if so.
        
        Args:
            user: Django User instance
            dna_connection: DNAConnection model instance
            force: Force evolution regardless of thresholds
            
        Returns:
            Tuple of (evolved: bool, message: str)
        """
        # Check subscription status
        try:
            subscription = user.genetic_subscription
            if not subscription.can_use_epigenetic():
                return False, "Epigenetic evolution requires premium subscription"
        except Exception:
            return False, "No genetic subscription found"
        
        # Check if enough time has passed since last check
        if not force and dna_connection.last_epigenetic_update:
            days_since = (timezone.now() - dna_connection.last_epigenetic_update).days
            if days_since < self.CHECK_INTERVAL_DAYS:
                return False, f"Next check in {self.CHECK_INTERVAL_DAYS - days_since} days"
        
        # Get current biological age
        try:
            # This would normally fetch from the API
            # For now, we'll check if manual input is available
            current_bio_age = dna_connection.last_biological_age
            
            if current_bio_age is None:
                return False, "No biological age data available"
            
        except Exception as e:
            logger.error(f"Failed to fetch biological age: {e}")
            return False, f"Failed to fetch epigenetic data: {str(e)}"
        
        # Check if evolution threshold is met
        last_bio_age = dna_connection.last_biological_age or current_bio_age
        age_change = abs(current_bio_age - last_bio_age)
        
        if not force and age_change < self.EVOLUTION_THRESHOLD:
            return False, f"Age change ({age_change:.2f}y) below threshold ({self.EVOLUTION_THRESHOLD}y)"
        
        # Trigger evolution
        old_generation = dna_connection.evolution_generation
        new_generation = old_generation + 1
        
        # Update connection
        dna_connection.evolution_generation = new_generation
        dna_connection.last_biological_age = current_bio_age
        dna_connection.last_epigenetic_update = timezone.now()
        dna_connection.save()
        
        # Update subscription counter
        subscription.evolutions_triggered += 1
        subscription.save()
        
        # Log the evolution
        from ..models import GeneticEvolutionLog
        GeneticEvolutionLog.objects.create(
            user=user,
            trigger_type='automatic' if not force else 'manual',
            old_evolution_gen=old_generation,
            new_evolution_gen=new_generation,
            old_biological_age=last_bio_age,
            new_biological_age=current_bio_age,
            passwords_evolved=0,  # Passwords are regenerated on-demand
            success=True,
            completed_at=timezone.now(),
        )
        
        logger.info(
            f"Password evolution triggered for {user.username}: "
            f"gen {old_generation} → {new_generation}"
        )
        
        return True, f"Evolution triggered: generation {old_generation} → {new_generation}"
    
    def calculate_next_evolution_estimate(
        self,
        current_bio_age: float,
        aging_rate: float
    ) -> Optional[datetime]:
        """
        Estimate when the next evolution will occur.
        
        Based on current aging rate and evolution threshold.
        """
        if aging_rate <= 0:
            return None
        
        # Calculate days until threshold is reached
        days_to_threshold = (self.EVOLUTION_THRESHOLD * 365) / aging_rate
        
        return timezone.now() + timedelta(days=days_to_threshold)
    
    def get_evolution_status(self, dna_connection) -> Dict[str, Any]:
        """
        Get current evolution status for a user.
        
        Returns status information for UI display.
        """
        status = {
            'current_generation': dna_connection.evolution_generation,
            'last_biological_age': dna_connection.last_biological_age,
            'last_update': dna_connection.last_epigenetic_update.isoformat() if dna_connection.last_epigenetic_update else None,
            'evolution_enabled': True,
        }
        
        # Calculate next check date
        if dna_connection.last_epigenetic_update:
            next_check = dna_connection.last_epigenetic_update + timedelta(days=self.CHECK_INTERVAL_DAYS)
            status['next_check'] = next_check.isoformat()
            status['days_until_check'] = max(0, (next_check - timezone.now()).days)
        
        return status


# =============================================================================
# Factory Functions
# =============================================================================

def get_epigenetic_provider(provider_type: str = "humanity") -> EpigeneticProvider:
    """
    Get an epigenetic provider instance.
    
    Args:
        provider_type: "humanity" or "manual"
    """
    providers = {
        "humanity": HumanityHealthProvider,
        "humanity_health": HumanityHealthProvider,
        "manual": ManualEpigeneticProvider,
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown epigenetic provider: {provider_type}")
    
    return provider_class()


def get_evolution_manager() -> EpigeneticEvolutionManager:
    """Get the evolution manager instance."""
    return EpigeneticEvolutionManager()
