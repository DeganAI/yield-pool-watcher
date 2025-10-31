"""
Alert engine for monitoring thresholds and generating alerts
"""
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Alert:
    """Alert data structure"""

    def __init__(
        self,
        pool_address: str,
        protocol: str,
        alert_type: str,
        metric: str,
        threshold_percent: float,
        actual_change_percent: float,
        previous_value: float,
        current_value: float,
        triggered_at: str,
        severity: str,
    ):
        self.pool_address = pool_address
        self.protocol = protocol
        self.alert_type = alert_type
        self.metric = metric
        self.threshold_percent = threshold_percent
        self.actual_change_percent = actual_change_percent
        self.previous_value = previous_value
        self.current_value = current_value
        self.triggered_at = triggered_at
        self.severity = severity


class AlertEngine:
    """Monitor thresholds and generate alerts"""

    def __init__(self):
        pass

    def check_thresholds(
        self,
        pool_metrics: List[Any],
        deltas: List[Any],
        metric_type: str,
        threshold_percent: float,
        timeframe_minutes: int,
    ) -> List[Alert]:
        """
        Check if any deltas exceed thresholds and generate alerts

        Metric types:
        - tvl_drop: TVL decreased beyond threshold
        - tvl_spike: TVL increased beyond threshold
        - apy_spike: APY increased beyond threshold
        - apy_drop: APY decreased beyond threshold
        """
        alerts = []

        try:
            # Map metric types to base metrics and conditions
            metric_config = {
                "tvl_drop": {"base": "tvl", "condition": "drop", "severity_map": {20: "medium", 50: "high", 75: "critical"}},
                "tvl_spike": {"base": "tvl", "condition": "spike", "severity_map": {50: "medium", 100: "high", 200: "critical"}},
                "apy_spike": {"base": "apy", "condition": "spike", "severity_map": {50: "low", 100: "medium", 200: "high"}},
                "apy_drop": {"base": "apy", "condition": "drop", "severity_map": {30: "medium", 50: "high", 75: "critical"}},
            }

            config = metric_config.get(metric_type)
            if not config:
                logger.warning(f"Unknown metric type: {metric_type}")
                return alerts

            base_metric = config["base"]
            condition = config["condition"]
            severity_map = config["severity_map"]

            # Filter deltas for the specified metric and timeframe
            relevant_deltas = [
                d for d in deltas
                if d.metric == base_metric and d.timeframe_minutes == timeframe_minutes
            ]

            # Check each delta against threshold
            for delta in relevant_deltas:
                triggered = False
                change_percent = delta.change_percent

                if condition == "drop" and change_percent < -threshold_percent:
                    triggered = True
                elif condition == "spike" and change_percent > threshold_percent:
                    triggered = True

                if triggered:
                    # Find the pool this delta belongs to
                    pool_address = self._find_pool_for_delta(pool_metrics, delta)
                    if not pool_address:
                        continue

                    # Find protocol
                    protocol = self._find_protocol(pool_metrics, pool_address)

                    # Determine severity
                    severity = self._calculate_severity(abs(change_percent), severity_map)

                    alert = Alert(
                        pool_address=pool_address,
                        protocol=protocol,
                        alert_type=metric_type,
                        metric=base_metric,
                        threshold_percent=threshold_percent,
                        actual_change_percent=change_percent,
                        previous_value=delta.previous_value,
                        current_value=delta.current_value,
                        triggered_at=datetime.utcnow().isoformat() + "Z",
                        severity=severity,
                    )

                    alerts.append(alert)
                    logger.info(
                        f"Alert triggered: {metric_type} for pool {pool_address[:10]}... "
                        f"({change_percent:.2f}% vs {threshold_percent}% threshold)"
                    )

        except Exception as e:
            logger.error(f"Error checking thresholds: {e}", exc_info=True)

        return alerts

    def _find_pool_for_delta(self, pool_metrics: List[Any], delta: Any) -> str:
        """Find which pool a delta belongs to"""
        # In a real implementation, would track pool association with deltas
        # For now, return first pool if available
        if pool_metrics:
            return pool_metrics[0].pool_address
        return ""

    def _find_protocol(self, pool_metrics: List[Any], pool_address: str) -> str:
        """Find protocol for a pool"""
        for metric in pool_metrics:
            if metric.pool_address == pool_address:
                return metric.protocol
        return "unknown"

    def _calculate_severity(self, change_percent: float, severity_map: Dict[float, str]) -> str:
        """Calculate alert severity based on change magnitude"""
        severity = "low"

        for threshold, level in sorted(severity_map.items()):
            if change_percent >= threshold:
                severity = level

        return severity
