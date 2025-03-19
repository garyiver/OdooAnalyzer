"""
Helper module for handling inheritance cycles
"""
import logging
import csv
import os
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class CycleManager:
    """
    Manages detection and reporting of inheritance cycles
    """

    def __init__(self, verbosity='medium'):
        # Options: 'low', 'medium', 'high'
        self.verbosity = verbosity
        self.cycles = set()  # Store unique cycles
        self.cycle_counts = Counter()  # Count occurrences of each cycle
        self.cycle_contexts = defaultdict(list)  # Store context of each cycle

    def record_cycle(self, cycle_path, context=None):
        """
        Record a detected cycle

        Args:
            cycle_path: List of models in the cycle
            context: Additional context information (like file being processed)
        """
        # Create a unique representation of the cycle (tuple of sorted models)
        cycle_key = tuple(sorted(cycle_path))

        # Record the cycle
        self.cycles.add(cycle_key)
        self.cycle_counts[cycle_key] += 1

        # Store context if provided
        if context:
            self.cycle_contexts[cycle_key].append(context)

        # Log based on verbosity
        if self.verbosity == 'high':
            # Detailed logging
            cycle_str = " -> ".join(cycle_path)
            context_str = f" in {context}" if context else ""
            logger.warning(f"Inheritance cycle detected{context_str}: {cycle_str}")
        elif self.verbosity == 'medium' and self.cycle_counts[cycle_key] == 1:
            # Medium logging - only log first occurrence
            cycle_str = " -> ".join(cycle_path)
            logger.warning(f"Inheritance cycle detected: {cycle_str}")
        elif self.verbosity == 'low' and self.cycle_counts[cycle_key] % 100 == 1:
            # Low verbosity - log only occasionally
            logger.warning(
                f"Inheritance cycle involving {', '.join(cycle_path)} (occurred {self.cycle_counts[cycle_key]} times)")

    def get_summary(self):
        """
        Get a summary of detected cycles

        Returns:
            Dictionary with cycle statistics
        """
        return {
            'total_cycles': len(self.cycles),
            'total_occurrences': sum(self.cycle_counts.values()),
            'most_common_cycles': self.cycle_counts.most_common(10),
            'models_in_cycles': set(model for cycle in self.cycles for model in cycle)
        }

    def log_summary(self):
        """Log a summary of detected cycles"""
        summary = self.get_summary()

        logger.info("=== Inheritance Cycle Summary ===")
        logger.info(f"Total unique cycles: {summary['total_cycles']}")
        logger.info(f"Total cycle occurrences: {summary['total_occurrences']}")
        logger.info(f"Total models involved in cycles: {len(summary['models_in_cycles'])}")

        if summary['most_common_cycles']:
            logger.info("Most common cycles:")
            for cycle, count in summary['most_common_cycles']:
                cycle_str = " -> ".join(cycle)
                logger.info(f"  {cycle_str}: {count} occurrences")

    def export_to_csv(self, output_dir):
        """
        Export cycle information to CSV files

        Args:
            output_dir: Directory to save CSV files
        """
        os.makedirs(output_dir, exist_ok=True)

        # Export cycle summary
        with open(os.path.join(output_dir, 'inheritance_cycles.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Cycle', 'Count', 'Models Involved'])

            for cycle, count in self.cycle_counts.most_common():
                writer.writerow([
                    " -> ".join(cycle),
                    count,
                    ", ".join(cycle)
                ])

        # Export models involved in cycles
        models_in_cycles = defaultdict(int)
        for cycle, count in self.cycle_counts.items():
            for model in cycle:
                models_in_cycles[model] += count

        with open(os.path.join(output_dir, 'models_in_cycles.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Model', 'Cycle Occurrences'])

            for model, count in sorted(models_in_cycles.items(), key=lambda x: x[1], reverse=True):
                writer.writerow([model, count])