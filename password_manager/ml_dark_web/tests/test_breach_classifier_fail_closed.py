"""The breach classifier fails closed.

A missing trained checkpoint, or an error while classifying, must raise. The
alternatives (an untrained base model, or answering "not a breach") turn a
failure into a clean "No breach detected" result.
"""
from unittest import mock

import pytest

ml_services = pytest.importorskip('ml_dark_web.ml_services')


def test_missing_trained_checkpoint_raises_instead_of_using_the_base_model(tmp_path):
    with mock.patch.object(ml_services, 'AutoTokenizer') as tokenizer, \
            mock.patch.object(ml_services, 'AutoModelForSequenceClassification') as model:
        with pytest.raises(FileNotFoundError):
            ml_services.BreachClassifierService(model_path=tmp_path / 'breach_classifier')
    tokenizer.from_pretrained.assert_called_once()
    model.from_pretrained.assert_not_called()


def test_a_classification_error_raises_instead_of_reporting_no_breach():
    service = ml_services.BreachClassifierService.__new__(ml_services.BreachClassifierService)
    service.config = ml_services.MLDarkWebConfig
    service.device = 'cpu'
    service.tokenizer = mock.Mock(side_effect=RuntimeError('tokenizer failed'))
    with pytest.raises(RuntimeError):
        service.classify_breach('leaked database dump')
