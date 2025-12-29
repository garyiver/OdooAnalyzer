"""
Restructuring recommendations based on field analysis and code structure
"""
import csv
import os
import logging
from collections import defaultdict
from pathlib import Path
import config

logger = logging.getLogger(__name__)


class RestructuringRecommender:
    """
    Analyzes CSV results and generates recommendations for restructuring code
    into csl_core module
    """
    
    def __init__(self, analysis_results_dir, eligible_modules=None):
        self.analysis_results_dir = analysis_results_dir
        self.fields_data = []
        self.field_dependencies = []
        self.module_dependencies = []
        self.shared_fields = []
        
        # Determine eligible modules
        # Use provided list, or fall back to config
        if eligible_modules is not None:
            self.eligible_modules = set(eligible_modules)
        else:
            self.eligible_modules = set(config.ELIGIBLE_MODULES_FOR_CORE)
        
        logger.info(f"Eligible modules for consolidation: {sorted(self.eligible_modules)}")
        
    def load_csv_data(self):
        """Load all relevant CSV files"""
        # Load fields analysis
        fields_csv = os.path.join(self.analysis_results_dir, 'fields_analysis.csv')
        if os.path.exists(fields_csv):
            with open(fields_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.fields_data = list(reader)
            logger.info(f"Loaded {len(self.fields_data)} field definitions")
        
        # Load field dependencies if available
        deps_csv = os.path.join(self.analysis_results_dir, 'field_dependencies.csv')
        if os.path.exists(deps_csv):
            with open(deps_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.field_dependencies = list(reader)
            logger.info(f"Loaded {len(self.field_dependencies)} field dependency records")
        
        # Load module dependencies
        module_deps_csv = os.path.join(self.analysis_results_dir, 'module_dependencies.csv')
        if os.path.exists(module_deps_csv):
            with open(module_deps_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.module_dependencies = list(reader)
            logger.info(f"Loaded {len(self.module_dependencies)} module dependency records")
        
        # Load shared fields
        shared_csv = os.path.join(self.analysis_results_dir, 'shared_fields.csv')
        if os.path.exists(shared_csv):
            with open(shared_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.shared_fields = list(reader)
            logger.info(f"Loaded {len(self.shared_fields)} shared field records")
    
    def analyze_for_csl_core(self):
        """
        Generate recommendations for moving fields to csl_core
        """
        recommendations = {
            'fields_to_move': [],
            'modules_to_update': defaultdict(set),
            'circular_dependencies': [],
            'field_groups_by_module': defaultdict(list),
            'extension_analysis': defaultdict(list),
            'priority_order': []
        }
        
        # Group fields by root_module
        fields_by_root = defaultdict(list)
        for field in self.fields_data:
            root_module = field.get('root_module', field.get('module', 'unknown'))
            fields_by_root[root_module].append(field)
        
        # Analyze each root module
        for root_module, fields in fields_by_root.items():
            # Only process eligible modules (custom modules, especially CSL modules)
            if root_module not in self.eligible_modules:
                continue
            
            # Count fields and extensions
            total_fields = len(fields)
            extensions = [f for f in fields if f.get('is_extension', 'FALSE').upper() == 'TRUE']
            extending_modules = set()
            
            for field in fields:
                extending = field.get('extending_modules', '')
                if extending:
                    extending_modules.update(extending.split(', '))
            
            # Determine if this module should move to csl_core
            should_move = False
            reasons = []
            
            # Criteria for moving to csl_core:
            # 1. Fields are extended by multiple modules
            if len(extending_modules) > 1:
                should_move = True
                reasons.append(f"Extended by {len(extending_modules)} modules: {', '.join(extending_modules)}")
            
            # 2. Many fields in this module
            if total_fields > 10:
                should_move = True
                reasons.append(f"Contains {total_fields} fields")
            
            # 3. Fields are shared across modules
            shared_count = sum(1 for f in fields if f.get('used_in_modules'))
            if shared_count > 5:
                should_move = True
                reasons.append(f"{shared_count} fields used across multiple modules")
            
            if should_move:
                recommendations['fields_to_move'].append({
                    'root_module': root_module,
                    'field_count': total_fields,
                    'extending_modules': list(extending_modules),
                    'reasons': reasons,
                    'fields': fields
                })
                
                # Track which modules will need to be updated
                for ext_module in extending_modules:
                    recommendations['modules_to_update'][ext_module].add(root_module)
        
        # Analyze circular dependencies
        recommendations['circular_dependencies'] = self._analyze_circular_dependencies()
        
        # Generate priority order (modules to move first)
        recommendations['priority_order'] = self._generate_priority_order(recommendations['fields_to_move'])
        
        return recommendations
    
    def _analyze_circular_dependencies(self):
        """Identify potential circular dependencies"""
        circular = []
        seen_cycles = set()
        
        # Build dependency graph
        deps_graph = defaultdict(set)
        for dep in self.module_dependencies:
            module = dep.get('module', '')
            depends_on = dep.get('depends_on', '')
            if module and depends_on:
                deps_graph[module].add(depends_on)
        
        # Find cycles
        for module in deps_graph:
            visited = set()
            path = []
            cycle = self._find_cycle(module, deps_graph, visited, path)
            if cycle:
                # Normalize cycle (start from smallest module name to avoid duplicates)
                cycle_tuple = tuple(sorted(set(cycle)))
                if cycle_tuple not in seen_cycles:
                    seen_cycles.add(cycle_tuple)
                    circular.append(cycle)
        
        return circular
    
    def _find_cycle(self, module, graph, visited, path):
        """Find cycles in dependency graph"""
        if module in path:
            # Cycle found
            cycle_start = path.index(module)
            return path[cycle_start:] + [module]
        
        if module in visited:
            return None
        
        visited.add(module)
        path.append(module)
        
        for dep in graph.get(module, set()):
            cycle = self._find_cycle(dep, graph, visited, path)
            if cycle:
                return cycle
        
        path.pop()
        return None
    
    def _generate_priority_order(self, fields_to_move):
        """Generate order for moving modules (least dependencies first)"""
        # Sort by number of extending modules (fewer = easier to move)
        sorted_modules = sorted(
            fields_to_move,
            key=lambda x: (len(x['extending_modules']), -x['field_count'])
        )
        return [m['root_module'] for m in sorted_modules]
    
    def generate_report(self, recommendations, output_file):
        """Generate a detailed restructuring report"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# CSL Core Restructuring Recommendations\n\n")
            f.write("## Executive Summary\n\n")
            f.write(f"- **Total modules to consolidate**: {len(recommendations['fields_to_move'])}\n")
            f.write(f"- **Total fields to move**: {sum(m['field_count'] for m in recommendations['fields_to_move'])}\n")
            f.write(f"- **Modules that will need updates**: {len(recommendations['modules_to_update'])}\n")
            f.write(f"- **Circular dependencies found**: {len(recommendations['circular_dependencies'])}\n\n")
            
            f.write("## Priority Order for Migration\n\n")
            for i, module in enumerate(recommendations['priority_order'], 1):
                f.write(f"{i}. **{module}**\n")
            
            f.write("\n## Detailed Module Analysis\n\n")
            for module_info in recommendations['fields_to_move']:
                f.write(f"### {module_info['root_module']}\n\n")
                f.write(f"- **Field Count**: {module_info['field_count']}\n")
                f.write(f"- **Extending Modules**: {', '.join(module_info['extending_modules'])}\n")
                f.write(f"- **Reasons to Move**:\n")
                for reason in module_info['reasons']:
                    f.write(f"  - {reason}\n")
                f.write("\n")
            
            f.write("## Modules Requiring Updates\n\n")
            for module, depends_on in sorted(recommendations['modules_to_update'].items()):
                f.write(f"- **{module}**: Will need to depend on `csl_core` (currently depends on: {', '.join(depends_on)})\n")
            
            if recommendations['circular_dependencies']:
                f.write("\n## Circular Dependencies to Resolve\n\n")
                for cycle in recommendations['circular_dependencies']:
                    f.write(f"- {' -> '.join(cycle)} -> {cycle[0]}\n")
        
        logger.info(f"Generated restructuring report: {output_file}")
    
    def export_recommendations_csv(self, recommendations, output_dir):
        """Export recommendations to CSV files"""
        # Export modules to move
        modules_csv = os.path.join(output_dir, 'modules_to_move_to_csl_core.csv')
        with open(modules_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['module', 'field_count', 'extending_modules', 'reasons'])
            writer.writeheader()
            for module_info in recommendations['fields_to_move']:
                writer.writerow({
                    'module': module_info['root_module'],
                    'field_count': module_info['field_count'],
                    'extending_modules': ', '.join(module_info['extending_modules']),
                    'reasons': '; '.join(module_info['reasons'])
                })
        
        # Export modules requiring updates
        updates_csv = os.path.join(output_dir, 'modules_requiring_updates.csv')
        with open(updates_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['module', 'will_depend_on_csl_core', 'currently_depends_on'])
            writer.writeheader()
            for module, depends_on in sorted(recommendations['modules_to_update'].items()):
                writer.writerow({
                    'module': module,
                    'will_depend_on_csl_core': 'Yes',
                    'currently_depends_on': ', '.join(depends_on)
                })
        
        logger.info(f"Exported recommendations to {output_dir}")


def generate_restructuring_recommendations(analysis_results_dir, output_dir, eligible_modules=None):
    """
    Main function to generate restructuring recommendations
    
    Args:
        analysis_results_dir: Directory containing CSV analysis results
        output_dir: Directory to write recommendation files
        eligible_modules: Optional list of module names eligible for consolidation.
                        If None, will auto-detect CSL modules from the data.
    """
    recommender = RestructuringRecommender(analysis_results_dir, eligible_modules)
    recommender.load_csv_data()  # This will auto-detect CSL modules if needed
    
    recommendations = recommender.analyze_for_csl_core()
    
    # Generate report
    report_file = os.path.join(output_dir, 'restructuring_recommendations.md')
    recommender.generate_report(recommendations, report_file)
    
    # Export CSV files
    recommender.export_recommendations_csv(recommendations, output_dir)
    
    return recommendations

