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
        self.cycles = set()  # Store unique cycles (as tuples of module.model strings)
        self.cycle_counts = Counter()  # Count occurrences of each cycle
        self.cycle_contexts = defaultdict(list)  # Store context of each cycle
        self.cycle_representations = {}  # Map cycle_key to the full cycle path with modules

    def record_cycle(self, cycle_path, module_map=None, context=None):
        """
        Record a detected cycle

        Args:
            cycle_path: List of models in the cycle (e.g., ['product.product', 'product.product'])
            module_map: Dictionary mapping model_name -> module_name, or a callable that takes model_name and returns module_name
            context: Additional context information (like file being processed)
        """
        # Build cycle with module information
        cycle_with_modules = []
        for model in cycle_path:
            if module_map:
                if callable(module_map):
                    module = module_map(model) or 'unknown'
                else:
                    module = module_map.get(model, 'unknown')
            else:
                module = 'unknown'
            
            # Format as module.model
            cycle_with_modules.append(f"{module}.{model}")
        
        # Create a unique representation of the cycle
        # Normalize by rotating to start from lexicographically smallest element
        # This allows us to detect the same cycle regardless of starting point
        if cycle_with_modules:
            min_index = min(range(len(cycle_with_modules)), key=lambda i: cycle_with_modules[i])
            normalized_cycle = cycle_with_modules[min_index:] + cycle_with_modules[:min_index]
            cycle_key = tuple(normalized_cycle)
        else:
            normalized_cycle = cycle_with_modules
            cycle_key = tuple(cycle_with_modules)
        
        # Record the cycle (preserve the full path with order)
        self.cycles.add(cycle_key)
        self.cycle_counts[cycle_key] += 1
        
        # Store the normalized cycle representation (for consistent CSV output)
        if cycle_key not in self.cycle_representations:
            # Store the normalized cycle path with modules
            self.cycle_representations[cycle_key] = normalized_cycle

        # Store context if provided
        if context:
            self.cycle_contexts[cycle_key].append(context)

        # Log based on verbosity
        cycle_str = " -> ".join(cycle_with_modules)
        if self.verbosity == 'high':
            # Detailed logging
            context_str = f" in {context}" if context else ""
            logger.warning(f"Inheritance cycle detected{context_str}: {cycle_str}")
        elif self.verbosity == 'medium' and self.cycle_counts[cycle_key] == 1:
            # Medium logging - only log first occurrence
            logger.warning(f"Inheritance cycle detected: {cycle_str}")
        elif self.verbosity == 'low' and self.cycle_counts[cycle_key] % 100 == 1:
            # Low verbosity - log only occasionally
            logger.warning(
                f"Inheritance cycle involving {', '.join(cycle_with_modules)} (occurred {self.cycle_counts[cycle_key]} times)")

    def get_summary(self):
        """
        Get a summary of detected cycles

        Returns:
            Dictionary with cycle statistics
        """
        # Extract unique models from cycles (remove module prefix)
        models_in_cycles = set()
        for cycle_key in self.cycles:
            cycle_repr = self.cycle_representations.get(cycle_key, [])
            for module_model in cycle_repr:
                # Extract model name from "module.model" format
                if '.' in module_model:
                    model = module_model.split('.', 1)[1]
                    models_in_cycles.add(model)
        
        return {
            'total_cycles': len(self.cycles),
            'total_occurrences': sum(self.cycle_counts.values()),
            'most_common_cycles': self.cycle_counts.most_common(10),
            'models_in_cycles': models_in_cycles
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
            for cycle_key, count in summary['most_common_cycles']:
                cycle_repr = self.cycle_representations.get(cycle_key, list(cycle_key))
                cycle_str = " -> ".join(cycle_repr)
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

            for cycle_key, count in self.cycle_counts.most_common():
                # Get the full cycle representation with modules
                cycle_repr = self.cycle_representations.get(cycle_key, list(cycle_key))
                cycle_str = " -> ".join(cycle_repr)
                
                # Extract just model names for "Models Involved" column
                models_only = [item.split('.', 1)[1] if '.' in item else item for item in cycle_repr]
                models_str = ", ".join(models_only)
                
                writer.writerow([
                    cycle_str,
                    count,
                    models_str
                ])

        # Export models involved in cycles
        models_in_cycles = defaultdict(int)
        for cycle_key, count in self.cycle_counts.items():
            cycle_repr = self.cycle_representations.get(cycle_key, list(cycle_key))
            for module_model in cycle_repr:
                # Extract model name from "module.model" format
                if '.' in module_model:
                    model = module_model.split('.', 1)[1]
                else:
                    model = module_model
                models_in_cycles[model] += count

        with open(os.path.join(output_dir, 'models_in_cycles.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Model', 'Cycle Occurrences'])

            for model, count in sorted(models_in_cycles.items(), key=lambda x: x[1], reverse=True):
                writer.writerow([model, count])