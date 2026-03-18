"""Evaluation harness package."""

from .metrics_schema import EvaluationConfig, EvaluationResult

__all__ = [
    "EvaluationConfig",
    "EvaluationResult",
    "evaluate_document_summary",
    "evaluate_summary",
    "run_batch_evaluation",
]


def evaluate_document_summary(*args, **kwargs):
    from .runner import evaluate_document_summary as _evaluate_document_summary

    return _evaluate_document_summary(*args, **kwargs)


def evaluate_summary(*args, **kwargs):
    from .runner import evaluate_summary as _evaluate_summary

    return _evaluate_summary(*args, **kwargs)


def run_batch_evaluation(*args, **kwargs):
    from .runner import run_batch_evaluation as _run_batch_evaluation

    return _run_batch_evaluation(*args, **kwargs)
