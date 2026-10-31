"""The breach classifier fails closed.

A missing trained checkpoint, or an error while classifying, must raise. The
alternatives (an untrained base model, or answering "not a breach") turn a
failure into a clean "No breach detected" result.
"""
import importlib
import sys
import types
from unittest import mock

import pytest


@pytest.fixture
def ml_services(monkeypatch):
    # A stand-in transformers for this module only. The real one's model
    # classes import torch._dynamo and triton, which aborts the CI
    # interpreter at import (exit 134), and nothing here needs them.
    fake = types.ModuleType('transformers')
    fake.AutoTokenizer = mock.MagicMock()
    fake.AutoModelForSequenceClassification = mock.MagicMock()
    monkeypatch.setitem(sys.modules, 'transformers', fake)
    monkeypatch.delitem(sys.modules, 'ml_dark_web.ml_services', raising=False)
    module = importlib.import_module('ml_dark_web.ml_services')
    yield module
    sys.modules.pop('ml_dark_web.ml_services', None)


def test_missing_trained_checkpoint_raises_instead_of_using_the_base_model(ml_services, tmp_path):
    with pytest.raises(FileNotFoundError):
        ml_services.BreachClassifierService(model_path=tmp_path / 'breach_classifier')
    ml_services.AutoTokenizer.from_pretrained.assert_called_once()
    ml_services.AutoModelForSequenceClassification.from_pretrained.assert_not_called()


def test_a_classification_error_raises_instead_of_reporting_no_breach(ml_services):
    service = ml_services.BreachClassifierService.__new__(ml_services.BreachClassifierService)
    service.config = ml_services.MLDarkWebConfig
    service.device = 'cpu'
    service.tokenizer = mock.Mock(side_effect=RuntimeError('tokenizer failed'))
    with pytest.raises(RuntimeError):
        service.classify_breach('leaked database dump')
