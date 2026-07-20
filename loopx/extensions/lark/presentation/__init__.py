"""Lark/Feishu collaboration surface capability."""

from .periodic_report import (
    periodic_report_lark_sink_adapter,
    periodic_report_miaoda_html_sink_adapter,
)

__all__ = [
    "periodic_report_lark_sink_adapter",
    "periodic_report_miaoda_html_sink_adapter",
]
